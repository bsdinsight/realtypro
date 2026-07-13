/** @odoo-module **/

import { Component, onMounted, onWillUnmount, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { BSDSyncfusionGanttAdapter }
    from "@rp_progress/js/bsd_gantt/bsd_syncfusion_gantt_adapter";

// Gantt lịch thi công theo HĐ nhà thầu — dùng Syncfusion EJ2 (bản quyền
// BSD, license param `syncfusion.license_key`, đã triển khai ở
// rp_progress/frm_gantt). Tái dùng BSDSyncfusionGanttAdapter:
// EJ2 tự có TreeGrid trái + splitter + zoom + context menu + drag bar.
//
// Hierarchy suy từ WBS chấm ("1.2" là con "1"); ngày trống → EJ2 tự
// aggregate summary; milestone (start=end) → EJ2 vẽ hình thoi.
export class RpGanttAction extends Component {
    static template = "rp_schedule.RpGantt";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.action = useService("action");
        this.ganttRef = useRef("gantt");
        this.state = useState({
            viewMode: "Week",
            count: 0,
            title: "",
            empty: false,
            loading: true,
            error: null,
        });
        const ctx = (this.props.action && this.props.action.context) || {};
        this.contractId =
            ctx.default_rp_contract_id || ctx.active_id ||
            (this.props.action.params && this.props.action.params.contract_id) || false;
        this.adapter = null;
        this._licenseKey = null;

        onMounted(async () => {
            await this.loadAndRender();
        });
        onWillUnmount(() => {
            if (this.adapter) this.adapter.destroy();
        });
    }

    _iso(d) {
        if (!d) return false;
        const dd = d instanceof Date ? d : new Date(d);
        const mm = String(dd.getMonth() + 1).padStart(2, "0");
        const day = String(dd.getDate()).padStart(2, "0");
        return `${dd.getFullYear()}-${mm}-${day}`;
    }

    // WBS "1.10.2" → [1,10,2] để sort số tự nhiên
    _wbsKey(w) {
        return String(w || "").split(".").map((s) => {
            const n = parseInt(s, 10);
            return isNaN(n) ? s : n;
        });
    }

    _wbsCompare(a, b) {
        const ka = this._wbsKey(a.wbs_code), kb = this._wbsKey(b.wbs_code);
        const len = Math.max(ka.length, kb.length);
        for (let i = 0; i < len; i++) {
            if (ka[i] === undefined) return -1;
            if (kb[i] === undefined) return 1;
            if (ka[i] !== kb[i]) {
                if (typeof ka[i] === "number" && typeof kb[i] === "number") {
                    return ka[i] - kb[i];
                }
                return String(ka[i]) < String(kb[i]) ? -1 : 1;
            }
        }
        return a.id - b.id;
    }

    async loadAndRender() {
        this.state.loading = true;
        this.state.error = null;
        try {
            await this._loadData();
            if (!this.state.empty) {
                await this._render();
            }
        } catch (err) {
            this.state.error = err.message || String(err);
        }
        this.state.loading = false;
    }

    async _loadData() {
        if (this.contractId) {
            const c = await this.orm.read(
                "rp.contract", [this.contractId], ["name"]);
            this.state.title = (c[0] && c[0].name) || "";
        }
        const domain = this.contractId
            ? [["rp_contract_id", "=", this.contractId]] : [];
        const recs = await this.orm.searchRead(
            "project.task", domain,
            ["name", "wbs_code", "planned_start", "planned_end",
             "progress_percent", "is_milestone", "predecessor_ids",
             "project_id"],
            { order: "id asc" }
        );
        recs.sort((a, b) => this._wbsCompare(a, b));
        this._recs = recs;
        this.state.count = recs.length;
        this.state.empty = recs.length === 0;

        // map WBS → task id để suy cha ("2.3" → cha là task wbs "2")
        const byWbs = new Map();
        recs.forEach((r) => {
            if (r.wbs_code) byWbs.set(String(r.wbs_code), r.id);
        });
        const idSet = new Set(recs.map((r) => r.id));
        this.tasks = recs.map((r) => {
            const w = String(r.wbs_code || "");
            let parent = null;
            if (w.includes(".")) {
                const pw = w.slice(0, w.lastIndexOf("."));
                if (byWbs.has(pw)) parent = String(byWbs.get(pw));
            }
            const hasDates = !!r.planned_start;
            return {
                id: String(r.id),
                parent,
                name: (w ? w + " · " : "") + r.name,
                start: hasDates ? r.planned_start : null,
                end: hasDates
                    ? (r.planned_end || r.planned_start) : null,
                progress: Math.round(r.progress_percent || 0),
                // taskMode 'Manual': predecessor chỉ VẼ mũi tên, không
                // auto-reschedule → giữ đúng ngày import từ MS Project
                dependencies: (r.predecessor_ids || [])
                    .filter((pid) => idSet.has(pid))
                    .map((pid) => `${pid}FS`).join(","),
                custom_class: r.is_milestone ? "rp-ej2-milestone" : "",
            };
        });
    }

    async _render() {
        // License key — cùng nguồn rp_progress (param syncfusion.license_key)
        if (!this._licenseKey) {
            const resp = await rpc("/rp_progress/syncfusion/license_key", {});
            if (!resp.configured) {
                this.state.error = _t(
                    "Syncfusion license key chưa cấu hình — Settings → "
                    + "Technical → System Parameters → 'syncfusion.license_key'.");
                return;
            }
            this._licenseKey = resp.key;
        }
        if (this.adapter) this.adapter.destroy();
        this.adapter = new BSDSyncfusionGanttAdapter(this.env);
        await this.adapter.render(this.ganttRef.el, this.tasks, {
            viewMode: this.state.viewMode,
            licenseKey: this._licenseKey,
            rowHeight: 42,
            taskMode: "Manual",
            allowAdding: true,
            allowDeleting: true,
            enableContextMenu: true,
            onClick: (task) => this._openTaskForm(parseInt(task.id, 10)),
            onDateChange: (task, start, end) =>
                this._onDateChange(task, start, end),
            onAdd: (data) => this._onAdd(data),
            onDelete: (rows) => this._onDelete(rows),
        });
    }

    _openTaskForm(id) {
        if (!id || isNaN(id)) return;
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "project.task",
            res_id: id,
            views: [[false, "form"]],
            target: "new",
        }, { onClose: () => this.loadAndRender() });
    }

    async _onDateChange(task, start, end) {
        const id = parseInt(task.id, 10);
        if (!id || isNaN(id)) return;
        const s = this._iso(start);
        const e = this._iso(end) || s;
        if (!s) return;
        try {
            await this.orm.write("project.task", [id],
                { planned_start: s, planned_end: e });
            this.notification.add(
                _t("Đã lưu ngày kế hoạch."), { type: "success" });
        } catch {
            this.notification.add(
                _t("Không lưu được thay đổi ngày."), { type: "danger" });
            await this.loadAndRender();   // hoàn tác hiển thị
        }
    }

    // Context menu EJ2 "Add" → tạo record thật trong Odoo rồi reload
    async _onAdd(data) {
        const base = this._recs && this._recs[0];
        try {
            await this.orm.create("project.task", [{
                name: data.TaskName || _t("Công việc mới"),
                rp_contract_id: this.contractId || false,
                project_id: base && base.project_id
                    ? base.project_id[0] : false,
                planned_start: this._iso(data.StartDate) || false,
                planned_end: this._iso(data.EndDate) || false,
            }]);
            this.notification.add(
                _t("Đã thêm công việc."), { type: "success" });
        } catch {
            this.notification.add(
                _t("Không thêm được công việc."), { type: "danger" });
        }
        await this.loadAndRender();
    }

    async _onDelete(rows) {
        const ids = rows.map((r) => parseInt(r.TaskID, 10))
            .filter((i) => i && !isNaN(i));
        if (!ids.length) return;
        try {
            await this.orm.unlink("project.task", ids);
            this.notification.add(
                _t("Đã xoá %s công việc.", ids.length), { type: "success" });
        } catch {
            this.notification.add(
                _t("Không xoá được (kiểm tra quyền/ràng buộc)."),
                { type: "danger" });
        }
        await this.loadAndRender();
    }

    setViewMode(mode) {
        this.state.viewMode = mode;
        if (this.adapter) this.adapter.changeViewMode(mode);
    }
}

registry.category("actions").add("rp_schedule.gantt", RpGanttAction);
