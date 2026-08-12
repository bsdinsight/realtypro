/** @odoo-module **/
/**
 * Bảng điều khiển dự án (EVM) — client action `rp_evm.dashboard`.
 *
 * OWL component + Syncfusion EJ2 Charts (lib do rp_progress ship —
 * window.ej.charts). Số liệu lấy từ rp.evm.dashboard.get_evm_dashboard():
 * S-curve PV/EV/AC time-phased · KPI CPI/SPI/EAC/VAC · tiến độ gói thầu ·
 * dòng tiền thu-chi. Toàn bộ là số thật của dự án (không rollup).
 */
import {
    Component, onMounted, onWillUnmount, onPatched, useRef, useState,
} from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";

const TY = 1e9; // 1 tỷ

function ymToDate(ym) {
    return new Date(parseInt(ym.slice(0, 4), 10), parseInt(ym.slice(5, 7), 10) - 1, 1);
}

/** Định dạng tiền VN gọn: 1.284 tỷ / 320 tr / 45.000 */
function fmtMoney(v) {
    const n = Math.round(v || 0);
    const a = Math.abs(n);
    if (a >= TY) return (n / TY).toLocaleString("vi-VN", { maximumFractionDigits: 1 }) + " tỷ";
    if (a >= 1e6) return (n / 1e6).toLocaleString("vi-VN", { maximumFractionDigits: 0 }) + " tr";
    return n.toLocaleString("vi-VN");
}

export class RpEvmDashboard extends Component {
    static template = "rp_evm.Dashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ loading: true, error: null, data: null, projectId: false });
        this.scurveRef = useRef("scurve");
        this.donutRef = useRef("donut");
        this.cashRef = useRef("cash");
        this.manpowerRef = useRef("manpower");
        this.qaRef = useRef("qa");
        this._charts = [];
        this._needRender = false;

        onMounted(() => this.load());
        onPatched(() => {
            if (this._needRender && this.state.data && this.state.data.ok) {
                this._needRender = false;
                this.renderCharts();
            }
        });
        onWillUnmount(() => this.destroyCharts());
    }

    // ---- helpers exposed to template ----
    fmt(v) { return fmtMoney(v); }
    fmtTy(v) { return (Math.round((v || 0) / TY * 10) / 10).toLocaleString("vi-VN"); }
    pct(v) { return (Math.round((v || 0) * 10) / 10).toLocaleString("vi-VN") + "%"; }

    get k() { return (this.state.data && this.state.data.kpi) || {}; }

    cpiClass(v) { return v >= 1 ? "is-good" : v >= 0.9 ? "is-warn" : "is-bad"; }
    healthClass(v) { return v >= 75 ? "is-good" : v >= 50 ? "is-warn" : "is-bad"; }

    heatClass(score) {
        return score >= 15 ? "lv-critical"
            : score >= 10 ? "lv-high"
                : score >= 5 ? "lv-medium" : "lv-low";
    }
    levelLabel(lv) {
        return { critical: "Nghiêm trọng", high: "Cao", medium: "Trung bình", low: "Thấp" }[lv] || lv;
    }
    msLabel(st) {
        return { done: "Hoàn thành", overdue: "Trễ hạn", ontrack: "Đúng kế hoạch" }[st] || st;
    }

    // ---- data ----
    async _ensureLicense() {
        if (this._licenseDone) return;
        try {
            const resp = await rpc("/rp_progress/syncfusion/license_key", {});
            if (resp && resp.key && window.ej && window.ej.base
                && window.ej.base.registerLicense) {
                window.ej.base.registerLicense(resp.key);
            }
        } catch (e) { /* không có key → trial, không chặn */ }
        this._licenseDone = true;
    }

    async load(projectId) {
        this.state.loading = true;
        this.state.error = null;
        this.destroyCharts();
        try {
            await this._ensureLicense();
            const data = await this.orm.call(
                "rp.evm.dashboard", "get_evm_dashboard", [projectId || false]);
            this.state.data = data;
            if (data && data.ok) {
                this.state.projectId = data.project.id;
                this._needRender = true;
            } else {
                this.state.error = "Chưa có dữ liệu dự án để hiển thị.";
            }
        } catch (e) {
            this.state.error = (e && e.message) || String(e);
        } finally {
            this.state.loading = false;
        }
    }

    onSelectProject(ev) {
        const pid = parseInt(ev.target.value, 10);
        if (pid) this.load(pid);
    }
    onRefresh() { this.load(this.state.projectId); }

    // ---- charts ----
    destroyCharts() {
        for (const c of this._charts) { try { c.destroy(); } catch (e) { /* noop */ } }
        this._charts = [];
    }

    renderCharts() {
        const ej = window.ej;
        if (!ej || !ej.charts) {
            this.state.error = "Thư viện biểu đồ Syncfusion chưa nạp.";
            return;
        }
        this.destroyCharts();
        try {
            this._renderScurve(ej);
            this._renderDonut(ej);
            this._renderCashflow(ej);
            this._renderManpower(ej);
            this._renderQa(ej);
        } catch (e) {
            // eslint-disable-next-line no-console
            console.error("EVM charts render error", e);
        }
    }

    _renderScurve(ej) {
        const C = ej.charts;
        C.Chart.Inject(C.LineSeries, C.DateTime, C.Legend, C.Tooltip, C.Category);
        const src = this.state.data.scurve.map((p) => ({
            x: ymToDate(p.ym),
            pv: p.pv != null ? p.pv / TY : null,
            ev: p.ev != null ? p.ev / TY : null,
            ac: p.ac != null ? p.ac / TY : null,
        }));
        const chart = new C.Chart({
            primaryXAxis: {
                valueType: "DateTime", intervalType: "Months", interval: 3,
                labelFormat: "MM/yy", edgeLabelPlacement: "Shift",
                majorGridLines: { width: 0 },
            },
            primaryYAxis: {
                labelFormat: "{value} tỷ", title: "Giá trị lũy kế",
                majorGridLines: { width: 1, color: "#eee" },
                lineStyle: { width: 0 }, majorTickLines: { width: 0 },
            },
            chartArea: { border: { width: 0 } },
            series: [
                {
                    type: "Line", dataSource: src, xName: "x", yName: "pv",
                    name: "Kế hoạch (PV)", width: 2.5, fill: "#34617a",
                    dashArray: "6,4",
                },
                {
                    type: "Line", dataSource: src, xName: "x", yName: "ev",
                    name: "Giá trị làm ra (EV)", width: 3, fill: "#2e7d5b",
                    marker: { visible: true, width: 8, height: 8 },
                },
                {
                    type: "Line", dataSource: src, xName: "x", yName: "ac",
                    name: "Chi phí thực (AC)", width: 3, fill: "#c0453b",
                    marker: { visible: true, width: 8, height: 8 },
                },
            ],
            legendSettings: { visible: true, position: "Top" },
            tooltip: { enable: true, shared: true, format: "${series.name}: ${point.y} tỷ" },
            width: "100%", height: "300px",
        });
        chart.appendTo(this.scurveRef.el);
        this._charts.push(chart);
    }

    _renderDonut(ej) {
        const C = ej.charts;
        C.AccumulationChart.Inject(
            C.PieSeries, C.AccumulationLegend, C.AccumulationTooltip,
            C.AccumulationDataLabel);
        const palette = ["#34617a", "#c9873d", "#2e7d5b", "#8a6fb0", "#c0453b", "#5a7d8c"];
        const src = this.state.data.cost_breakdown.map((d, i) => ({
            name: d.name, value: Math.round(d.value / TY * 10) / 10,
            label: fmtMoney(d.value), fill: palette[i % palette.length],
        }));
        const donut = new C.AccumulationChart({
            series: [{
                dataSource: src, xName: "name", yName: "value",
                pointColorMapping: "fill", innerRadius: "60%", radius: "88%",
                dataLabel: {
                    visible: true, position: "Outside", name: "label",
                    connectorStyle: { length: "8px" },
                    font: { size: "11px" },
                },
            }],
            legendSettings: { visible: true, position: "Bottom", textWrap: "Wrap", maximumLabelWidth: 140 },
            tooltip: { enable: true, format: "${point.x}: ${point.y} tỷ" },
            enableSmartLabels: true,
            width: "100%", height: "300px",
        });
        donut.appendTo(this.donutRef.el);
        this._charts.push(donut);
    }

    _renderCashflow(ej) {
        const C = ej.charts;
        C.Chart.Inject(C.ColumnSeries, C.LineSeries, C.DateTime, C.Legend, C.Tooltip);
        const src = this.state.data.cashflow.map((p) => ({
            x: ymToDate(p.ym),
            inflow: p.inflow / TY,
            outflow: -p.outflow / TY,
            net: p.net_cum / TY,
        }));
        const chart = new C.Chart({
            primaryXAxis: {
                valueType: "DateTime", intervalType: "Months", interval: 2,
                labelFormat: "MM/yy", edgeLabelPlacement: "Shift",
                majorGridLines: { width: 0 },
            },
            primaryYAxis: {
                labelFormat: "{value} tỷ",
                majorGridLines: { width: 1, color: "#eee" },
                lineStyle: { width: 0 }, majorTickLines: { width: 0 },
            },
            chartArea: { border: { width: 0 } },
            series: [
                {
                    type: "Column", dataSource: src, xName: "x", yName: "inflow",
                    name: "Thu từ CĐT", fill: "#2e7d5b", columnWidth: 0.6,
                    cornerRadius: { topLeft: 3, topRight: 3 },
                },
                {
                    type: "Column", dataSource: src, xName: "x", yName: "outflow",
                    name: "Chi nhà thầu", fill: "#d98b8b", columnWidth: 0.6,
                    cornerRadius: { bottomLeft: 3, bottomRight: 3 },
                },
                {
                    type: "Line", dataSource: src, xName: "x", yName: "net",
                    name: "Dòng tiền ròng (lũy kế)", width: 2.5, fill: "#c9873d",
                    marker: { visible: true, width: 6, height: 6 },
                },
            ],
            legendSettings: { visible: true, position: "Top" },
            tooltip: { enable: true, shared: true },
            width: "100%", height: "300px",
        });
        chart.appendTo(this.cashRef.el);
        this._charts.push(chart);
    }

    _renderManpower(ej) {
        if (!this.manpowerRef.el) return;
        const C = ej.charts;
        C.Chart.Inject(C.ColumnSeries, C.SplineSeries, C.DateTime, C.Tooltip, C.Legend);
        const src = this.state.data.manpower.series.map((p) => ({
            x: new Date(p.date), y: p.count,
        }));
        const chart = new C.Chart({
            primaryXAxis: {
                valueType: "DateTime", labelFormat: "dd/MM",
                intervalType: "Days", edgeLabelPlacement: "Shift",
                majorGridLines: { width: 0 },
            },
            primaryYAxis: {
                title: "Người/ngày",
                majorGridLines: { width: 1, color: "#eee" },
                lineStyle: { width: 0 }, majorTickLines: { width: 0 },
            },
            chartArea: { border: { width: 0 } },
            series: [{
                type: "Column", dataSource: src, xName: "x", yName: "y",
                name: "Nhân lực", fill: "#34617a", columnWidth: 0.55,
                cornerRadius: { topLeft: 3, topRight: 3 },
            }],
            legendSettings: { visible: false },
            tooltip: { enable: true, format: "${point.x}: ${point.y} người" },
            width: "100%", height: "300px",
        });
        chart.appendTo(this.manpowerRef.el);
        this._charts.push(chart);
    }

    _renderQa(ej) {
        if (!this.qaRef.el) return;
        const C = ej.charts;
        C.AccumulationChart.Inject(
            C.PieSeries, C.AccumulationLegend, C.AccumulationTooltip,
            C.AccumulationDataLabel);
        const colors = { "Nghiêm trọng": "#c0453b", "Nặng": "#d98b3d", "Nhẹ": "#e0b93d" };
        const src = this.state.data.qaqc.breakdown
            .filter((d) => d.value > 0)
            .map((d) => ({ name: d.name, value: d.value, fill: colors[d.name] || "#8a6fb0" }));
        const donut = new C.AccumulationChart({
            series: [{
                dataSource: src.length ? src : [{ name: "Không có lỗi mở", value: 1, fill: "#8bbf9c" }],
                xName: "name", yName: "value", pointColorMapping: "fill",
                innerRadius: "58%", radius: "86%",
                dataLabel: { visible: true, position: "Outside", name: "name", font: { size: "11px" } },
            }],
            legendSettings: { visible: true, position: "Bottom" },
            tooltip: { enable: true, format: "${point.x}: ${point.y} lỗi" },
            width: "100%", height: "300px",
        });
        donut.appendTo(this.qaRef.el);
        this._charts.push(donut);
    }
}

registry.category("actions").add("rp_evm.dashboard", RpEvmDashboard);
