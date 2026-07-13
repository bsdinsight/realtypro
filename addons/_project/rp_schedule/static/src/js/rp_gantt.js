/** @odoo-module **/

import { Component, onWillStart, onMounted, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

// Hằng số layout — PHẢI khớp options truyền vào frappe-gantt bên dưới:
// row height = bar_height + padding; header = header_height + 10.
const BAR_HEIGHT = 24;
const PADDING = 18;
const HEADER_HEIGHT = 50;
export const ROW_H = BAR_HEIGHT + PADDING;        // 42px
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
            leftW: 520,             // bề rộng lưới trái (kéo splitter đổi)
            tl: { width: 0, cells: [], col: 30 },  // header timeline HTML sticky
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

    // Splitter: kéo đổi bề rộng lưới trái (kiểu Syncfusion)
    onSplitterDown(ev) {
        ev.preventDefault();
        const startX = ev.clientX;
        const startW = this.state.leftW;
        const move = (e) => {
            this.state.leftW = Math.min(
                900, Math.max(260, startW + (e.clientX - startX)));
        };
        const up = () => {
            window.removeEventListener("pointermove", move);
            window.removeEventListener("pointerup", up);
        };
        window.addEventListener("pointermove", move);
        window.addEventListener("pointerup", up);
    }

    // Bôi xám Thứ 7/CN (chế độ Ngày) — frappe-gantt không có.
    _augment() {
        const svg = this.ganttRef.el;
        const g = this.gantt;
        if (!svg || !g) return;
        const NS = "http://www.w3.org/2000/svg";
        const height = parseFloat(svg.getAttribute("height")) || 0;
        const gridLayer = svg.querySelector("g.grid");
        if (this.state.viewMode === "Day" && gridLayer && g.dates) {
            const col = g.options.column_width;
            g.dates.forEach((d, i) => {
                const day = d.getDay();
                if (day === 0 || day === 6) {
                    const rect = document.createElementNS(NS, "rect");
                    rect.setAttribute("x", i * col);
                    rect.setAttribute("y", HEAD_H);
                    rect.setAttribute("width", col);
                    rect.setAttribute("height", Math.max(0, height - HEAD_H));
                    rect.setAttribute("class", "rp-weekend");
                    gridLayer.appendChild(rect);
                }
            });
        }
    }

    // Header timeline HTML STICKY (thay header SVG — SVG không sticky được):
    // 2 tầng tháng/ngày luôn ghim trên đỉnh khi cuộn dọc, như Syncfusion.
    _buildTimelineHead() {
        const g = this.gantt;
        if (!g || !g.dates) return;
        const col = g.options.column_width;
        const mode = this.state.viewMode;
        const MONTHS = ["01", "02", "03", "04", "05", "06",
                        "07", "08", "09", "10", "11", "12"];
        const cells = [];
        let prevM = -1, prevY = -1;
        g.dates.forEach((d, i) => {
            const m = d.getMonth(), y = d.getFullYear();
            let lower = "", upper = "";
            if (mode === "Month") {
                lower = "Th" + MONTHS[m];
                if (y !== prevY) upper = String(y);
            } else {
                lower = String(d.getDate());
                if (m !== prevM || y !== prevY) {
                    upper = "Tháng " + MONTHS[m] + "/" + y;
                }
            }
            prevM = m; prevY = y;
            cells.push({ x: i * col, lower, upper });
        });
        this.state.tl = { width: g.dates.length * col, cells, col };
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
        this._augment();
        this._buildTimelineHead();
    }

    setViewMode(mode) {
        this.state.viewMode = mode;
        if (this.gantt) {
            this.gantt.change_view_mode(mode);
            this._augment();
            this._buildTimelineHead();
        }
    }
}

registry.category("actions").add("rp_schedule.gantt", RpGanttAction);
