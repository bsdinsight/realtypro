/** @odoo-module **/

import { Component, onMounted, onWillUnmount, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { BSDFrappeGanttAdapter } from "./bsd_frappe_gantt_adapter";

const COMMUNITY_TASK_CAP = 500;

/**
 * BSDGanttView — client action OWL component
 *
 * Render Gantt cho tất cả rp.structure của 1 dự án.
 * Source: context.default_project_id (set bởi action_open_gantt
 * trên re.project model).
 *
 * Adapter selection:
 *   - Default: BSDFrappeGanttAdapter (Community)
 *   - Enterprise có thể override bằng registry "bsd_gantt_adapter"
 *
 * Cap 500 tasks Community. Nếu vượt → cảnh báo upgrade Enterprise.
 */
export class BSDGanttView extends Component {
    static template = "rp_progress.BSDGanttView";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.ganttRef = useRef("gantt");
        this.state = useState({
            loading: true,
            error: null,
            taskCount: 0,
            viewMode: "Month",
            projectName: "",
        });
        this.adapter = null;

        onMounted(async () => {
            await this._load();
        });
        onWillUnmount(() => {
            if (this.adapter) this.adapter.destroy();
        });
    }

    get projectId() {
        const ctx = this.props.action?.context || {};
        return ctx.default_project_id || ctx.active_id;
    }

    async _load() {
        const projectId = this.projectId;
        if (!projectId) {
            this.state.error = _t("Không có ID dự án trong context.");
            this.state.loading = false;
            return;
        }

        const [project] = await this.orm.read("re.project", [projectId], [
            "name",
        ]);
        this.state.projectName = project?.name || "";

        const structures = await this.orm.searchRead(
            "rp.structure",
            [["project_id", "=", projectId]],
            [
                "id",
                "name",
                "code",
                "date_planned_start",
                "date_planned_end",
                "progress_percent",
                "status",
                "is_delayed",
            ],
            { order: "date_planned_start asc, id asc" },
        );

        this.state.taskCount = structures.length;
        if (structures.length > COMMUNITY_TASK_CAP) {
            this.state.error = _t(
                "Dự án có %s hạng mục — vượt giới hạn Community Edition " +
                    "(%s tasks). Liên hệ sales@bsdinsight.com nâng cấp " +
                    "Realty Pro Enterprise để xem Gantt không giới hạn + " +
                    "tính năng nâng cao (critical path, baseline, " +
                    "resource leveling).",
                structures.length,
                COMMUNITY_TASK_CAP,
            );
            this.state.loading = false;
            return;
        }

        // Filter structures có dates
        const valid = structures.filter(
            (s) => s.date_planned_start && s.date_planned_end,
        );
        if (valid.length === 0) {
            this.state.error = _t(
                "Chưa có hạng mục nào có ngày kế hoạch (Ngày BĐ KH + " +
                    "Ngày KT KH). Vào Hạng mục → set 'date_planned_start' " +
                    "+ 'date_planned_end' để hiện trên Gantt.",
            );
            this.state.loading = false;
            return;
        }

        const tasks = valid.map((s) => ({
            id: String(s.id),
            name: s.code ? `[${s.code}] ${s.name}` : s.name,
            start: s.date_planned_start,
            end: s.date_planned_end,
            progress: Math.min(100, Math.max(0, s.progress_percent || 0)),
            dependencies: "",
            custom_class: this._statusClass(s.status, s.is_delayed),
        }));

        // Load adapter
        this.adapter = new BSDFrappeGanttAdapter(this.env);
        try {
            await this.adapter.render(this.ganttRef.el, tasks, {
                viewMode: this.state.viewMode,
                locale: "vi",
                onClick: (task) => this._openStructure(task.id),
                onDateChange: (task, start, end) =>
                    this._onDateChange(task, start, end),
                onProgressChange: (task, progress) =>
                    this._onProgressChange(task, progress),
            });
        } catch (err) {
            this.state.error = err.message || String(err);
        }
        this.state.loading = false;
    }

    _statusClass(status, isDelayed) {
        if (isDelayed) return "bsd_gantt_bar_delayed";
        switch (status) {
            case "completed":
                return "bsd_gantt_bar_completed";
            case "in_progress":
                return "bsd_gantt_bar_in_progress";
            case "paused":
                return "bsd_gantt_bar_paused";
            default:
                return "bsd_gantt_bar_not_started";
        }
    }

    _openStructure(taskId) {
        const id = parseInt(taskId, 10);
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "rp.structure",
            res_id: id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    async _onDateChange(task, start, end) {
        try {
            await this.orm.write("rp.structure", [parseInt(task.id, 10)], {
                date_planned_start: start.toISOString().slice(0, 10),
                date_planned_end: end.toISOString().slice(0, 10),
            });
            this.notification.add(
                _t("Đã cập nhật ngày kế hoạch."),
                { type: "success" },
            );
        } catch (err) {
            this.notification.add(_t("Lỗi cập nhật: ") + err.message, {
                type: "danger",
            });
            // Reload to revert
            await this._load();
        }
    }

    async _onProgressChange(task, progress) {
        // rp.structure.progress_percent là computed → không write trực tiếp.
        this.notification.add(
            _t(
                "% tiến độ được tính từ BBNT — không sửa tay trên Gantt. " +
                    "Sửa qua BBNT của hạng mục.",
            ),
            { type: "warning" },
        );
        // Reload để revert lại từ DB
        await this._load();
    }

    async setViewMode(mode) {
        this.state.viewMode = mode;
        if (this.adapter) {
            this.adapter.changeViewMode(mode);
        }
    }
}

registry.category("actions").add("bsd_gantt_view", BSDGanttView);
