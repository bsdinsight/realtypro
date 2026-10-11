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
import { loadEj2 } from "@bsd_syncfusion/js/ej2_loader";

function ymToDate(ym) {
    return new Date(parseInt(ym.slice(0, 4), 10), parseInt(ym.slice(5, 7), 10) - 1, 1);
}

// Đơn vị rút gọn do SERVER chọn theo độ lớn của số (currency.div/unit).
// Trước đây chỗ này chia cứng cho 1e9 và dán chữ "tỷ": đúng với dự án
// ghi bằng đồng, nhưng dự án ghi bằng USD 189 triệu thì trục biểu đồ
// hiện "0,2 tỷ". Mặc định dưới đây chỉ dùng khi chưa có dữ liệu.
const MAC_DINH = { div: 1e9, unit: "tỷ" };

export class RpEvmDashboard extends Component {
    static template = "rp_evm.Dashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            loading: true, error: null, data: null, projectId: false,
            tab: "tong-quan",
        });
        this.scurveRef = useRef("scurve");
        this.donutRef = useRef("donut");
        this.cashRef = useRef("cash");
        this.manpowerRef = useRef("manpower");
        this.qaRef = useRef("qa");
        this.disbRef = useRef("disb");
        this.payableRef = useRef("payable");
        this.wlRef = useRef("workload");
        this.statusRef = useRef("status");
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
    get cur() {
        return (this.state.data && this.state.data.currency) || MAC_DINH;
    }
    get div() { return this.cur.div || 1; }
    get unit() { return this.cur.unit || ""; }
    /** Trục biểu đồ: "{value} tr" — đơn vị theo tiền tệ dự án. */
    get axisFmt() { return this.unit ? "{value} " + this.unit : "{value}"; }

    fmt(v) {
        const n = Math.round(v || 0);
        const d = this.div;
        if (d <= 1) return n.toLocaleString("vi-VN");
        const so = (n / d).toLocaleString("vi-VN", {
            maximumFractionDigits: Math.abs(n / d) >= 100 ? 0 : 1,
        });
        return this.unit ? so + " " + this.unit : so;
    }
    /** Có kèm ký hiệu tiền — dùng cho các số đứng một mình. */
    fmtCur(v) {
        const s = this.cur.symbol || "";
        return this.cur.position === "before" ? s + " " + this.fmt(v)
            : this.fmt(v) + " " + s;
    }
    pct(v) { return (Math.round((v || 0) * 10) / 10).toLocaleString("vi-VN") + "%"; }

    get k() { return (this.state.data && this.state.data.kpi) || {}; }
    get m() { return (this.state.data && this.state.data.money) || {}; }
    get mk() { return this.m.kpi || {}; }
    get s() { return (this.state.data && this.state.data.schedule) || {}; }
    get sk() { return this.s.kpi || {}; }

    execLabel(st) {
        return {
            not_started: "Chưa bắt đầu", in_progress: "Đang làm",
            late: "Trễ", done: "Xong",
        }[st] || st;
    }
    sevLabel(sv) {
        return { critical: "Nghiêm trọng", warning: "Cảnh báo",
            info: "Thông tin" }[sv] || sv;
    }

    onTab(t) {
        if (this.state.tab === t) return;
        this.state.tab = t;
        // Mỗi tab dựng DOM riêng bằng t-if, nên biểu đồ của tab vừa hiện
        // chưa tồn tại — phải vẽ lại sau khi OWL gắn DOM. Giữ t-if thay
        // vì ẩn bằng CSS là có lý do: Syncfusion vẽ vào thẻ đang
        // display:none sẽ ra biểu đồ rộng 0px.
        this._needRender = true;
    }
    tabClass(t) { return this.state.tab === t ? "is-active" : ""; }

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
        // Lib Syncfusion nằm ở bundle riêng của rp_progress — phải nạp
        // xong mới có window.ej.base để đăng ký bản quyền và vẽ biểu đồ.
        await loadEj2();
        if (this._licenseDone) return;
        try {
            const resp = await rpc("/bsd_syncfusion/license_key", {});
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
            // Mỗi hàm tự bỏ qua khi thẻ chứa không có trên DOM — tab
            // không hiện thì ref của nó là null.
            this._renderScurve(ej);
            this._renderDonut(ej);
            this._renderCashflow(ej);
            this._renderManpower(ej);
            this._renderQa(ej);
            this._renderDisbursement(ej);
            this._renderPayable(ej);
            this._renderWorkload(ej);
            this._renderStatus(ej);
        } catch (e) {
            // eslint-disable-next-line no-console
            console.error("EVM charts render error", e);
        }
    }

    _renderScurve(ej) {
        if (!this.scurveRef.el) return;
        const C = ej.charts;
        C.Chart.Inject(C.LineSeries, C.DateTime, C.Legend, C.Tooltip, C.Category);
        const D = this.div;
        const src = this.state.data.scurve.map((p) => ({
            x: ymToDate(p.ym),
            pv: p.pv != null ? p.pv / D : null,
            ev: p.ev != null ? p.ev / D : null,
            ac: p.ac != null ? p.ac / D : null,
        }));
        const chart = new C.Chart({
            primaryXAxis: {
                valueType: "DateTime", intervalType: "Months", interval: 3,
                labelFormat: "MM/yy", edgeLabelPlacement: "Shift",
                majorGridLines: { width: 0 },
            },
            primaryYAxis: {
                labelFormat: this.axisFmt, title: "Giá trị lũy kế",
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
            tooltip: {
                enable: true, shared: true,
                format: "${series.name}: ${point.y} " + this.unit,
            },
            width: "100%", height: "300px",
        });
        chart.appendTo(this.scurveRef.el);
        this._charts.push(chart);
    }

    _renderDonut(ej) {
        if (!this.donutRef.el) return;
        const C = ej.charts;
        C.AccumulationChart.Inject(
            C.PieSeries, C.AccumulationLegend, C.AccumulationTooltip,
            C.AccumulationDataLabel);
        const palette = ["#34617a", "#c9873d", "#2e7d5b", "#8a6fb0", "#c0453b", "#5a7d8c"];
        const D = this.div;
        const src = this.state.data.cost_breakdown.map((d, i) => ({
            name: d.name, value: Math.round(d.value / D * 10) / 10,
            label: this.fmt(d.value), fill: palette[i % palette.length],
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
            tooltip: { enable: true, format: "${point.x}: ${point.y} " + this.unit },
            enableSmartLabels: true,
            width: "100%", height: "300px",
        });
        donut.appendTo(this.donutRef.el);
        this._charts.push(donut);
    }

    _renderCashflow(ej) {
        if (!this.cashRef.el) return;
        const C = ej.charts;
        C.Chart.Inject(C.ColumnSeries, C.LineSeries, C.DateTime, C.Legend, C.Tooltip);
        const D = this.div;
        const src = this.state.data.cashflow.map((p) => ({
            x: ymToDate(p.ym),
            inflow: p.inflow / D,
            outflow: -p.outflow / D,
            net: p.net_cum / D,
        }));
        const chart = new C.Chart({
            primaryXAxis: {
                valueType: "DateTime", intervalType: "Months", interval: 2,
                labelFormat: "MM/yy", edgeLabelPlacement: "Shift",
                majorGridLines: { width: 0 },
            },
            primaryYAxis: {
                labelFormat: this.axisFmt,
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

    /** Đường cong giải ngân: kế hoạch vs thực chi, luỹ kế. */
    _renderDisbursement(ej) {
        if (!this.disbRef.el) return;
        const C = ej.charts;
        C.Chart.Inject(C.LineSeries, C.ColumnSeries, C.DateTime, C.Legend, C.Tooltip);
        const D = this.div;
        const src = (this.m.disbursement || []).map((p) => ({
            x: ymToDate(p.ym),
            plan: p.plan / D,
            actual: p.actual / D,
            plan_cum: p.plan_cum / D,
            // null để đường thực chi DỪNG ở tháng hiện tại — vẽ tiếp là
            // vẽ một đường phẳng trông như dự án đã ngừng chi tiền.
            actual_cum: p.actual_cum != null ? p.actual_cum / D : null,
        }));
        const chart = new C.Chart({
            primaryXAxis: {
                valueType: "DateTime", intervalType: "Months", interval: 3,
                labelFormat: "MM/yy", edgeLabelPlacement: "Shift",
                majorGridLines: { width: 0 },
            },
            primaryYAxis: {
                labelFormat: this.axisFmt, title: "Luỹ kế",
                majorGridLines: { width: 1, color: "#eee" },
                lineStyle: { width: 0 }, majorTickLines: { width: 0 },
            },
            // Trục phụ cho cột THEO THÁNG. Dùng chung một trục với đường
            // luỹ kế thì cột bị dẹp xuống gần mặt đất — luỹ kế lên tới
            // 215 trong khi tháng cao nhất chỉ 27, tức cột chiếm chưa
            // tới 1/8 chiều cao và không đọc được tháng nào hơn tháng nào.
            axes: [{
                name: "thang", opposedPosition: true,
                labelFormat: this.axisFmt, title: "Theo tháng",
                majorGridLines: { width: 0 },
                lineStyle: { width: 0 }, majorTickLines: { width: 0 },
            }],
            chartArea: { border: { width: 0 } },
            series: [
                {
                    type: "Column", dataSource: src, xName: "x", yName: "plan",
                    name: "Kế hoạch chi (tháng)", fill: "#cfd8dd",
                    columnWidth: 0.6, yAxisName: "thang",
                    cornerRadius: { topLeft: 3, topRight: 3 },
                },
                {
                    type: "Column", dataSource: src, xName: "x", yName: "actual",
                    name: "Thực chi (tháng)", fill: "#2e7d5b", columnWidth: 0.6,
                    yAxisName: "thang",
                    cornerRadius: { topLeft: 3, topRight: 3 },
                },
                {
                    type: "Line", dataSource: src, xName: "x", yName: "plan_cum",
                    name: "Kế hoạch luỹ kế", width: 2.5, fill: "#34617a",
                    dashArray: "6,4",
                },
                {
                    type: "Line", dataSource: src, xName: "x",
                    yName: "actual_cum", name: "Thực chi luỹ kế",
                    width: 3, fill: "#c9873d",
                    marker: { visible: true, width: 6, height: 6 },
                },
            ],
            legendSettings: { visible: true, position: "Top" },
            tooltip: { enable: true, shared: true },
            width: "100%", height: "320px",
        });
        chart.appendTo(this.disbRef.el);
        this._charts.push(chart);
    }

    /** Lịch phải trả 12 kỳ tới — đợt đến hạn chưa trả, theo tháng. */
    _renderPayable(ej) {
        if (!this.payableRef.el) return;
        const C = ej.charts;
        C.Chart.Inject(C.ColumnSeries, C.Category, C.Tooltip, C.DataLabel);
        const D = this.div;
        const src = (this.m.payable || []).map((p) => ({
            x: p.ym.slice(5) + "/" + p.ym.slice(2, 4),
            y: p.amount / D,
            lbl: this.fmt(p.amount),
        }));
        const chart = new C.Chart({
            primaryXAxis: {
                valueType: "Category", majorGridLines: { width: 0 },
                labelIntersectAction: "Rotate45",
            },
            primaryYAxis: {
                labelFormat: this.axisFmt,
                majorGridLines: { width: 1, color: "#eee" },
                lineStyle: { width: 0 }, majorTickLines: { width: 0 },
            },
            chartArea: { border: { width: 0 } },
            series: [{
                type: "Column", dataSource: src, xName: "x", yName: "y",
                name: "Phải trả", fill: "#34617a", columnWidth: 0.55,
                cornerRadius: { topLeft: 3, topRight: 3 },
                marker: {
                    dataLabel: {
                        visible: true, position: "Top", name: "lbl",
                        font: { size: "10px" },
                    },
                },
            }],
            legendSettings: { visible: false },
            tooltip: { enable: true },
            width: "100%", height: "320px",
        });
        chart.appendTo(this.payableRef.el);
        this._charts.push(chart);
    }

    /** Khối lượng việc đến hạn 12 tháng tới — thấy chỗ dồn việc. */
    _renderWorkload(ej) {
        if (!this.wlRef.el) return;
        const C = ej.charts;
        C.Chart.Inject(C.ColumnSeries, C.StackingColumnSeries, C.Category,
            C.Legend, C.Tooltip);
        const src = (this.s.workload || []).map((p) => ({
            x: p.ym.slice(5) + "/" + p.ym.slice(2, 4),
            done: p.done,
            // Phần CÒN LẠI, không phải tổng — xếp chồng mà lấy tổng là
            // vẽ cột cao gấp đôi sự thật.
            rest: Math.max(p.total - p.done, 0),
        }));
        const chart = new C.Chart({
            primaryXAxis: {
                valueType: "Category", majorGridLines: { width: 0 },
                labelIntersectAction: "Rotate45",
            },
            primaryYAxis: {
                title: "Số việc đến hạn",
                majorGridLines: { width: 1, color: "#eee" },
                lineStyle: { width: 0 }, majorTickLines: { width: 0 },
            },
            chartArea: { border: { width: 0 } },
            series: [
                {
                    type: "StackingColumn", dataSource: src, xName: "x",
                    yName: "done", name: "Đã xong", fill: "#2e7d5b",
                    columnWidth: 0.55,
                },
                {
                    type: "StackingColumn", dataSource: src, xName: "x",
                    yName: "rest", name: "Chưa xong", fill: "#cfd8dd",
                    columnWidth: 0.55,
                    cornerRadius: { topLeft: 3, topRight: 3 },
                },
            ],
            legendSettings: { visible: true, position: "Top" },
            tooltip: { enable: true, shared: true },
            width: "100%", height: "300px",
        });
        chart.appendTo(this.wlRef.el);
        this._charts.push(chart);
    }

    /** Trạng thái thực hiện toàn dự án. */
    _renderStatus(ej) {
        if (!this.statusRef.el) return;
        const C = ej.charts;
        C.AccumulationChart.Inject(
            C.PieSeries, C.AccumulationLegend, C.AccumulationTooltip,
            C.AccumulationDataLabel);
        const st = this.sk.status || {};
        const mau = {
            done: "#2e7d5b", in_progress: "#34617a",
            late: "#c0453b", not_started: "#cfd8dd",
        };
        const src = Object.keys(mau)
            .filter((k) => st[k])
            .map((k) => ({ name: this.execLabel(k), value: st[k], fill: mau[k] }));
        const donut = new C.AccumulationChart({
            series: [{
                dataSource: src.length ? src
                    : [{ name: "Chưa có việc", value: 1, fill: "#cfd8dd" }],
                xName: "name", yName: "value", pointColorMapping: "fill",
                innerRadius: "58%", radius: "86%",
                dataLabel: {
                    visible: true, position: "Outside", name: "name",
                    font: { size: "11px" },
                },
            }],
            legendSettings: { visible: true, position: "Bottom" },
            tooltip: { enable: true, format: "${point.x}: ${point.y} việc" },
            width: "100%", height: "300px",
        });
        donut.appendTo(this.statusRef.el);
        this._charts.push(donut);
    }
}

registry.category("actions").add("rp_evm.dashboard", RpEvmDashboard);
