/** @odoo-module **/

import { Component, onWillStart, onMounted, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

// Client action: Gantt lịch thi công của một HĐ nhà thầu (dùng frappe-gantt).
export class RpGanttAction extends Component {
    static template = "rp_schedule.RpGantt";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.ganttRef = useRef("gantt");
        this.state = useState({
            viewMode: "Week",
            loading: true,
            count: 0,
            title: "",
            empty: false,
        });
        const ctx = (this.props.action && this.props.action.context) || {};
        this.contractId =
            ctx.default_rp_contract_id || ctx.active_id ||
            (this.props.action.params && this.props.action.params.contract_id) || false;

        onWillStart(async () => { await this.loadData(); });
        onMounted(() => this.renderGantt());
    }

    async loadData() {
        if (this.contractId) {
            const c = await this.orm.read("rp.contract", [this.contractId], ["name"]);
            this.state.title = (c[0] && c[0].name) || "";
        }
        const domain = this.contractId ? [["rp_contract_id", "=", this.contractId]] : [];
        const recs = await this.orm.searchRead(
            "project.task", domain,
            ["name", "wbs_code", "planned_start", "planned_end",
             "progress_percent", "is_milestone", "predecessor_ids"],
            { order: "planned_start asc, wbs_code asc, id asc" }
        );
        // frappe-gantt cần start+end; bỏ task chưa có ngày bắt đầu
        this.tasks = recs
            .filter((r) => r.planned_start)
            .map((r) => ({
                id: String(r.id),
                name: (r.wbs_code ? r.wbs_code + " · " : "") + r.name,
                start: r.planned_start,
                end: r.planned_end || r.planned_start,
                progress: Math.round(r.progress_percent || 0),
                dependencies: (r.predecessor_ids || []).map(String).join(","),
                custom_class: r.is_milestone ? "rp-bar-milestone" : "rp-bar-task",
            }));
        this.state.count = this.tasks.length;
        this.state.empty = this.tasks.length === 0;
        this.state.loading = false;
    }

    renderGantt() {
        const el = this.ganttRef.el;
        if (!el || this.state.empty) return;
        if (typeof window.Gantt === "undefined") {
            el.innerHTML =
                "<div class='alert alert-warning m-3'>Không tải được thư viện Gantt.</div>";
            return;
        }
        el.innerHTML = "";
        this.gantt = new window.Gantt(el, this.tasks, {
            view_mode: this.state.viewMode,
            date_format: "YYYY-MM-DD",
            bar_height: 18,
            bar_corner_radius: 3,
            padding: 16,
            column_width: 32,
            custom_popup_html: (task) => {
                const s = task._start ? task._start.toLocaleDateString("vi-VN") : "";
                const e = task._end ? task._end.toLocaleDateString("vi-VN") : "";
                return (
                    "<div class='rp-gantt-popup'>" +
                    "<div class='rp-gantt-popup-title'>" + task.name + "</div>" +
                    "<div>" + s + " → " + e + "</div>" +
                    "<div>Tiến độ: " + task.progress + "%</div>" +
                    "</div>"
                );
            },
        });
    }

    setViewMode(mode) {
        this.state.viewMode = mode;
        if (this.gantt) {
            this.gantt.change_view_mode(mode);
        }
    }
}

registry.category("actions").add("rp_schedule.gantt", RpGanttAction);
