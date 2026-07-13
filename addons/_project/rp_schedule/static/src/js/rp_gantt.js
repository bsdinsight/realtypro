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
// lưới task trái (sticky, thu/mở cây) + timeline frappe-gantt bên phải.
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
            collapsed: {},          // {wbs: true} — hàng cha đang thu gọn
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

    // WBS "1.10.2" → [1,10,2] để sort số tự nhiên (không sort chữ 1,10,2,20…)
    _wbsKey(w) {
        return String(w || "")
            .split(".")
            .map((s) => {
                const n = parseInt(s, 10);
                return isNaN(n) ? s : n;
            });
    }

    _wbsCompare(a, b) {
        const ka = this._wbsKey(a.wbs_code), kb = this._wbsKey(b.wbs_code);
        const len = Math.max(ka.length, kb.length);
        for (let i = 0; i < len; i++) {
            if (ka[i] === undefined) return -1;   // cha trước con
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
            { order: "id asc" }
        );
        // Sort WBS theo SỐ tự nhiên; cha/con suy từ WBS chấm ("1.2" con của "1")
        recs.sort((a, b) => this._wbsCompare(a, b));
        recs.forEach((r) => {
            const w = String(r.wbs_code || "");
            r._wbs = w;
            r._level = w ? w.split(".").length - 1 : 0;
            r._parent = !!w && recs.some(
                (o) => o !== r && String(o.wbs_code || "").startsWith(w + "."));
        });
        this._recs = recs;
        this.state.count = recs.length;
        this.state.empty = recs.length === 0;
        this._rebuild();
    }

    // Dựng rows (lưới trái) + tasks (gantt phải) theo trạng thái thu/mở
    _rebuild() {
        const collapsed = this.state.collapsed;
        const hiddenBy = (w) => {
            for (const c of Object.keys(collapsed)) {
                if (collapsed[c] && w !== c && w.startsWith(c + ".")) return true;
            }
            return false;
        };
        const visible = this._recs.filter((r) => !hiddenBy(r._wbs));
        const anchor =
            (visible.find((r) => r.planned_start) || {}).planned_start ||
            new Date().toISOString().slice(0, 10);
        const datedIds = new Set(
            visible.filter((r) => r.planned_start).map((r) => r.id));
        this.state.rows = visible.map((r) => ({
            id: r.id,
            wbs: r._wbs,
            name: r.name,
            start: r.planned_start ? this._fmt(r.planned_start) : "—",
            end: (r.planned_end || r.planned_start)
                ? this._fmt(r.planned_end || r.planned_start) : "—",
            progress: Math.round(r.progress_percent || 0),
            milestone: r.is_milestone,
            nodate: !r.planned_start,
            level: r._level,
            parent: r._parent,
            open: !collapsed[r._wbs],
        }));
        this.tasks = visible.map((r) => ({
            id: String(r.id),
            name: r.name,
            start: r.planned_start || anchor,
            end: r.planned_end || r.planned_start || anchor,
            progress: Math.round(r.progress_percent || 0),
            dependencies: (r.predecessor_ids || [])
                .filter((pid) => datedIds.has(pid)).map(String).join(","),
            custom_class: !r.planned_start ? "rp-bar-nodate"
                : r._parent ? "rp-bar-parent"
                : r.is_milestone ? "rp-bar-milestone" : "rp-bar-task",
        }));
    }

    toggleRow(row) {
        if (!row.parent) return;
        this.state.collapsed = {
            ...this.state.collapsed,
            [row.wbs]: !this.state.collapsed[row.wbs],
        };
        this._rebuild();
        this.renderGantt();
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
            bar_corner_radius: 2,
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
