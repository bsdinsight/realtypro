/** @odoo-module **/

import { Component, onMounted, onWillStart, onWillUnmount, useRef, useState }
    from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

// Bản đồ hiện trường — Leaflet nhúng sẵn trong module (không gọi CDN),
// ảnh vệ tinh lấy từ dịch vụ nền của trình duyệt người dùng.
//
// Toàn bộ dữ liệu về trong MỘT lần gọi `map_data`. Gọi từng điểm thì
// 30 tua-bin thành 30 vòng truy vấn và bản đồ giật mỗi lần kéo.

const MAU = {
    running:     { c: "#1a9850", t: "Đang phát" },
    down:        { c: "#d73027", t: "Dừng sự cố" },
    maintenance: { c: "#fd8d3c", t: "Bảo trì theo kế hoạch" },
    curtailed:   { c: "#4575b4", t: "Lưới bắt giảm" },
    standby:       { c: "#999999", t: "Sẵn sàng chờ" },
    no_data:       { c: "#6a3d9a", t: "Mất dữ liệu giám sát" },
    // Chưa lắp máy thì không nói chuyện phát điện. Thiếu trạng thái này
    // thì bản đồ của một dự án đang xây vẫn xanh rờn.
    not_installed: { c: "#ffffff", t: "Chưa lắp máy" },
    // Dựng xong nhưng chưa tới ngày vận hành thương mại — chạy thử và
    // nghiệm thu. Đây là bậc cả một dự án đang xây sống trong đó.
    commissioning: { c: "#e3a008", t: "Đã dựng, chưa vận hành" },
};

const NEN = {
    sat: {
        url: "https://server.arcgisonline.com/ArcGIS/rest/services/" +
             "World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr: "Ảnh vệ tinh: Esri",
        max: 19,
    },
    dia_hinh: {
        url: "https://server.arcgisonline.com/ArcGIS/rest/services/" +
             "World_Topo_Map/MapServer/tile/{z}/{y}/{x}",
        attr: "Bản đồ nền: Esri",
        max: 19,
    },
};

export class EamPlantMap extends Component {
    static template = "eam_map.PlantMap";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.mapRef = useRef("map");

        this.state = useState({
            loading: true,
            data: null,
            selected: null,
            months: 12,
            asOf: "",
            lop: { wake: true, pairs: true, nhan: true },
            nen: "sat",
            loc: Object.fromEntries(Object.keys(MAU).map((k) => [k, true])),
        });

        this._map = null;
        this._lopDiem = null;
        this._lopWake = null;
        this._lopCap = null;
        this._markers = {};

        onWillStart(async () => {
            await this._napLeaflet();
            await this._napDuLieu();
        });
        onMounted(() => this._dungBanDo());
        onWillUnmount(() => {
            if (this._map) {
                this._map.remove();
                this._map = null;
            }
        });
    }

    get plantCode() {
        return (this.props.action && this.props.action.params &&
                this.props.action.params.plant_code) || null;
    }

    // ------------------------------------------------------------------
    async _napLeaflet() {
        // Leaflet là thư viện UMD, nó tự gắn vào window.L. Nạp qua thẻ
        // script thay vì import: gói trong assets_backend của Odoo chạy
        // dưới module ES, nhúng thẳng sẽ không ra biến toàn cục.
        if (window.L) { return; }
        await new Promise((ok, loi) => {
            const s = document.createElement("script");
            s.src = "/eam_map/static/lib/leaflet/leaflet.js";
            s.onload = ok;
            s.onerror = () => loi(new Error("Không nạp được Leaflet"));
            document.head.appendChild(s);
        });
    }

    async _napDuLieu() {
        this.state.loading = true;
        try {
            this.state.data = await this.orm.call(
                "eam.location", "map_data",
                [], { plant_code: this.plantCode, months: this.state.months,
                      as_of: this.state.asOf || null });
            if (!this.state.asOf && this.state.data.as_of) {
                this.state.asOf = this.state.data.as_of.slice(0, 10);
            }
        } finally {
            this.state.loading = false;
        }
    }

    // ------------------------------------------------------------------
    _dungBanDo() {
        const d = this.state.data;
        if (!d || !window.L || !this.mapRef.el) { return; }
        const L = window.L;

        this._map = L.map(this.mapRef.el, { zoomControl: true })
            .setView(d.center, 13);
        this._nenLop = L.tileLayer(NEN.sat.url, {
            attribution: NEN.sat.attr, maxZoom: NEN.sat.max,
        }).addTo(this._map);

        this._lopWake = L.layerGroup().addTo(this._map);
        this._lopCap = L.layerGroup().addTo(this._map);
        this._lopDiem = L.layerGroup().addTo(this._map);

        this._ve();
        const b = d.points.filter((p) => p.lat && p.lon)
            .map((p) => [p.lat, p.lon]);
        if (b.length) {
            this._map.fitBounds(L.latLngBounds(b).pad(0.15));
        }
    }

    _ve() {
        const L = window.L;
        const d = this.state.data;
        if (!this._map || !d) { return; }
        this._lopDiem.clearLayers();
        this._lopWake.clearLayers();
        this._lopCap.clearLayers();
        this._markers = {};

        const hien = d.points.filter((p) => this.state.loc[p.state]);

        // Vòng ảnh hưởng dòng khí: bán kính nửa khoảng giãn yêu cầu, nên
        // HAI VÒNG CHẠM NHAU đúng bằng ngưỡng. Chồng nhau = quá gần.
        if (this.state.lop.wake) {
            for (const p of hien) {
                if (!p.rotor_d) { continue; }
                L.circle([p.lat, p.lon], {
                    radius: (d.spacing_d * p.rotor_d) / 2,
                    color: p.too_close ? "#d73027" : "#ffffff",
                    weight: 1,
                    opacity: p.too_close ? 0.9 : 0.45,
                    fillColor: p.too_close ? "#d73027" : "#ffffff",
                    fillOpacity: p.too_close ? 0.12 : 0.05,
                    interactive: false,
                }).addTo(this._lopWake);
            }
        }

        if (this.state.lop.pairs) {
            const vt = Object.fromEntries(d.points.map((p) => [p.code, p]));
            for (const c of d.pairs) {
                const a = vt[c.a], b = vt[c.b];
                if (!a || !b) { continue; }
                L.polyline([[a.lat, a.lon], [b.lat, b.lon]], {
                    color: "#d73027", weight: 2, dashArray: "6 4",
                }).bindTooltip(
                    `${c.a} ↔ ${c.b}: ${c.m} m (${c.d}D) — cần ≥ ${c.need} m`,
                    { sticky: true }
                ).addTo(this._lopCap);
            }
        }

        for (const p of hien) {
            const m = MAU[p.state] || MAU.standby;
            const mk = L.circleMarker([p.lat, p.lon], {
                radius: 9, color: "#ffffff", weight: 2,
                fillColor: m.c, fillOpacity: 0.95,
            }).addTo(this._lopDiem);
            mk.bindPopup(this._popup(p), { maxWidth: 380, minWidth: 320 });
            mk.on("click", () => { this.state.selected = p; });
            if (this.state.lop.nhan) {
                mk.bindTooltip(p.code, {
                    permanent: true, direction: "right", offset: [10, 0],
                    className: "eam-map-nhan",
                });
            }
            this._markers[p.code] = mk;
        }
    }

    _popup(p) {
        const d = this.state.data;
        const m = MAU[p.state] || MAU.standby;
        const tien = (v) => (v || 0).toLocaleString("vi-VN");
        const L = [];
        L.push(`<div class="eam-pop">
            <div class="eam-pop-h" style="border-color:${m.c}">
                <b>${p.code}</b> · ${this._esc(p.name || "")}</div>`);
        L.push(`<div class="eam-pop-b">`);
        L.push(`<div><span class="eam-chip" style="background:${m.c}">${m.t}</span>`);
        if (p.state_cat) {
            L.push(` <span class="text-muted">${this._esc(p.state_cat)}`
                + (p.state_cat_code ? ` (${p.state_cat_code})` : "") + `</span>`);
        }
        L.push(`</div>`);
        if (p.state_hours) {
            L.push(`<div>⏱ Đã ${p.state_hours} giờ`
                + (p.liability ? ` · quy cho <b>${p.liability}</b>` : "")
                + `</div>`);
        }
        L.push(`<hr/>`);
        L.push(`<div>🌀 ${p.mw || "—"} MW · rô-to ${p.rotor_d || "—"} m `
            + `· trục ${p.hub_h || "—"} m`
            + (p.elev ? ` · cao độ ${p.elev} m` : "") + `</div>`);
        L.push(`<div>📍 ${(p.lat || 0).toFixed(5)}, ${(p.lon || 0).toFixed(5)}</div>`);
        if (p.too_close) {
            L.push(`<div class="eam-canh">⚠ Nằm gần máy khác dưới `
                + `${d.spacing_d}D — xem đường nối đỏ</div>`);
        }
        L.push(`<hr/>`);
        L.push(`<div class="eam-pop-t">${d.months} tháng gần nhất</div>`);
        if (p.avail === null) {
            L.push(`<div>📈 ${p.state === "commissioning"
                ? "Chưa tới ngày vận hành — chưa có cam kết khả dụng"
                : "Chưa lắp máy — chưa có khả dụng để tính"}</div>`);
        } else {
            L.push(`<div>📈 Khả dụng <b>${p.avail}%</b> `
                + `· dừng ${p.down_hours} giờ · ${p.outage_count} lần</div>`);
        }
        if (p.lost_mwh) {
            L.push(`<div>⚡ Mất <b>${tien(p.lost_mwh)}</b> MWh`
                + (p.lost_money ? ` ≈ <b>${tien(p.lost_money)}</b> ${d.currency}`
                    : "") + `</div>`);
        }
        if (p.wo_open) {
            L.push(`<div>🔧 <b>${p.wo_open}</b> lệnh công việc đang mở`
                + (p.wo_hold
                    ? ` · <span class="eam-canh">${p.wo_hold} đang chờ: `
                      + this._esc(p.wo_hold_why.join(", ")) + `</span>`
                    : "") + `</div>`);
        }
        if (p.assets && p.assets.length) {
            L.push(`<hr/><div class="eam-pop-t">Thiết bị đang lắp `
                + `(${p.asset_count})</div>`);
            for (const a of p.assets) {
                const bh = a.wdays === null || a.wdays === undefined ? ""
                    : a.wdays < 0
                        ? ` <span class="eam-canh">hết bảo hành ${-a.wdays} ngày</span>`
                        : a.wdays <= 90
                            ? ` <span class="eam-canh">bảo hành còn ${a.wdays} ngày</span>`
                            : ` <span class="text-muted">bảo hành còn ${a.wdays} ngày</span>`;
                L.push(`<div>· ${this._esc(a.cat)}: ${this._esc(a.code)}`
                    + (a.serial ? ` · SN ${this._esc(a.serial)}` : "")
                    + bh + `</div>`);
            }
        }
        L.push(`</div></div>`);
        return L.join("");
    }

    _esc(s) {
        const e = document.createElement("div");
        e.textContent = s == null ? "" : String(s);
        return e.innerHTML;
    }

    // ------------------------------------------------------------------
    doiNen(k) {
        this.state.nen = k;
        if (!this._map) { return; }
        this._map.removeLayer(this._nenLop);
        this._nenLop = window.L.tileLayer(NEN[k].url, {
            attribution: NEN[k].attr, maxZoom: NEN[k].max,
        }).addTo(this._map);
    }

    batLop(k) {
        this.state.lop[k] = !this.state.lop[k];
        this._ve();
    }

    batLoc(k) {
        this.state.loc[k] = !this.state.loc[k];
        this._ve();
    }

    async doiKy(ev) {
        this.state.months = parseInt(ev.target.value, 10) || 12;
        await this._napDuLieu();
        this._ve();
    }

    async doiMoc(ev) {
        // Giữ giờ cuối ngày: chọn ngày 20 mà tính tới 00:00 thì cả ngày
        // hôm đó biến mất khỏi cửa sổ thống kê.
        const v = ev.target.value;
        this.state.asOf = v ? `${v} 23:59:59` : "";
        await this._napDuLieu();
        this._ve();
    }

    async nhayToiDuLieu() {
        const sp = this.state.data && this.state.data.data_span;
        if (!sp) { return; }
        this.state.asOf = sp.to;
        await this._napDuLieu();
        this._ve();
    }

    get mocNgay() {
        return (this.state.asOf || "").slice(0, 10);
    }

    get trong() {
        const d = this.state.data;
        if (!d || !d.points.length) { return false; }
        // Không có gì NGOÀI "chưa lắp" nghĩa là mốc đang xem nằm trước
        // lúc nhà máy chạy — nói thẳng ra thay vì bày bản đồ trắng.
        return (d.summary.by_state.not_installed || 0) === d.points.length;
    }

    bay(p) {
        this.state.selected = p;
        if (!this._map) { return; }
        this._map.setView([p.lat, p.lon], 16, { animate: true });
        const mk = this._markers[p.code];
        if (mk) { mk.openPopup(); }
    }

    moViTri(p) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "eam.location",
            res_id: p.id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    moLenh(p) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Lệnh công việc — %s", p.code),
            res_model: "eam.work.order",
            domain: [["location_id", "child_of", p.id]],
            views: [[false, "list"], [false, "form"]],
            target: "current",
        });
    }

    moDung(p) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Khoảng dừng — %s", p.code),
            res_model: "eam.outage",
            domain: [["location_id", "child_of", p.id]],
            views: [[false, "list"], [false, "form"]],
            target: "current",
        });
    }

    get mauList() {
        return Object.entries(MAU).map(([k, v]) => ({ k, ...v }));
    }

    get diemLoc() {
        const d = this.state.data;
        if (!d) { return []; }
        return d.points.filter((p) => this.state.loc[p.state]);
    }

    mauCua(k) {
        return (MAU[k] || MAU.standby).c;
    }

    tenCua(k) {
        return (MAU[k] || MAU.standby).t;
    }

    so(v) {
        return (v || 0).toLocaleString("vi-VN");
    }
}

registry.category("actions").add("eam_map.plant_map", EamPlantMap);
