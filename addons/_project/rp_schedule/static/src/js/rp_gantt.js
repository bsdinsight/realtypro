/** @odoo-module **/

import { Component, onWillStart, onMounted, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

// Hằng số layout — PHẢI khớp options truyền vào frappe-gantt bên dưới:
// row height = bar_height + padding; header = header_height + 10.
const BAR_HEIGHT = 18;
const PADDING = 16;
const HEADER_HEIGHT = 50;
export const ROW_H = BAR_HEIGHT + PADDING;        // 34px
export const HEAD_H = HEADER_HEIGHT + 10;         // 60px

// Client action: Gantt lịch thi công kiểu Syncfusion —
// lưới task bên trái (sticky) + timeline frappe-gantt bên phải.
export class RpGanttAction extends Component {
    static template = "rp_schedule.RpGantt";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.ganttRef = useRef("gantt");
        this.state = useState({
            viewMode: "Week",
            count: 0,
            title: "",
            empty: false,
            rows: [],
            rowH: ROW_H,
            headH: HEAD_H,
        });
        const ctx = (this.props.action && this.props.action.context) || {};
        this.contractId =
            ctx.default_rp_contract_id || ctx.active_id ||
            (this.props.action.params && this.props.action.params.contract_id) || false;

        onWillStart(async () => { await this.loadData(); });
        onMounted(() => this.renderGantt());
    }

    _fmt(d) {
        if (!d) return "";
        const [y, m, dd] = String(d).split("-");
        return `${dd}/${m}/${y}`;
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
        // TẤT CẢ task đều lên (kể cả chưa có ngày). frappe-gantt bắt buộc
        // start/end → task thiếu ngày gán ngày neo ảo + ẩn bar bằng CSS;
        // hàng lưới trái/phải vẫn khớp 1-1.
        const anchor =
            (recs.find((r) => r.planned_start) || {}).planned_start ||
            new Date().toISOString().slice(0, 10);
        // Lưới trái (cùng thứ tự với thanh gantt)
        this.state.rows = recs.map((r) => ({
            id: r.id,
            wbs: r.wbs_code || "",
            name: r.name,
            start: r.planned_start ? this._fmt(r.planned_start) : "—",
            end: (r.planned_end || r.planned_start)
                ? this._fmt(r.planned_end || r.planned_start) : "—",
            progress: Math.round(r.progress_percent || 0),
            milestone: r.is_milestone,
            nodate: !r.planned_start,
        }));
        // Thanh gantt phải
        this.tasks = recs.map((r) => ({
            id: String(r.id),
            name: r.name,
            start: r.planned_start || anchor,
            end: r.planned_end || r.planned_start || anchor,
            progress: Math.round(r.progress_percent || 0),
            dependencies: (r.predecessor_ids || []).map(String).join(","),
            custom_class: !r.planned_start ? "rp-bar-nodate"
                : r.is_milestone ? "rp-bar-milestone" : "rp-bar-task",
        }));
        this.state.count = this.tasks.length;
        this.state.empty = this.tasks.length === 0;
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
            bar_height: BAR_HEIGHT,
            padding: PADDING,
            header_height: HEADER_HEIGHT,
            bar_corner_radius: 3,
            column_width: 30,
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
