/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

// Toàn danh mục nhà máy — màn người quản lý O&M mở mỗi sáng để biết
// NHÀ MÁY NÀO ĐANG KÉO CẢ ĐỘI XUỐNG.
//
// Khác màn "Ca trực sáng nay" (hỏi: hôm nay tôi làm gì trước) và khác
// mọi màn hiện có của EAMOne (đều trả lời cho MỘT nhà máy).
//
// Toàn bộ số về trong MỘT lần gọi `du_lieu`. Xem ghi chú đầu
// models/eam_fleet.py để biết vì sao đọc từ bảng kỳ chứ không tự cộng.

const DAU_GACH = "—";

/** In số, nhưng CHƯA ĐO ĐƯỢC thì ra dấu gạch — không bao giờ ra 0. */
function so(v, le = 0) {
    if (v === null || v === undefined) {
        return DAU_GACH;
    }
    return v.toLocaleString(undefined, {
        minimumFractionDigits: le, maximumFractionDigits: le,
    });
}

/** kWh → MWh. Giữ nguyên dấu gạch khi chưa đo được. */
function mwh(v, le = 1) {
    return v === null || v === undefined ? DAU_GACH : so(v / 1000, le);
}

function pct(v, le = 1) {
    return v === null || v === undefined ? DAU_GACH : so(v, le) + "%";
}

/** Bậc màu cho khả dụng. Đây là mốc ĐỂ QUÉT MẮT, không phải ngưỡng hợp
 *  đồng — mỗi hợp đồng O&M cam kết một mức riêng, việc chấm theo cam
 *  kết nằm ở Hợp đồng ▸ Đánh giá & thanh toán. */
function bacKd(v) {
    if (v === null || v === undefined) return "is-unknown";
    if (v >= 97) return "is-good";
    if (v >= 93) return "is-warn";
    return "is-bad";
}

function bacPr(v, camKet) {
    if (v === null || v === undefined) return "is-unknown";
    if (!camKet) return "";
    return v >= camKet ? "is-good" : "is-bad";
}

export class EamFleetDashboard extends Component {
    static template = "eam_fleet.Dashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ dang_tai: true, d: null, ngay: null });
        onWillStart(async () => {
            await this.nap();
        });
    }

    async nap(ngay) {
        this.state.dang_tai = true;
        const d = await this.orm.call(
            "eam.fleet.dashboard", "du_lieu", [], { ngay: ngay || false });
        this.state.d = d;
        this.state.ngay = d.ngay;
        this.state.dang_tai = false;
    }

    async doiNgay(ev) {
        await this.nap(ev.target.value);
    }

    // --- định dạng, gọi từ template ---
    so(v, le) { return so(v, le); }
    mwh(v, le) { return mwh(v, le); }
    pct(v, le) { return pct(v, le); }
    bacKd(v) { return bacKd(v); }
    bacPr(v, c) { return bacPr(v, c); }

    tien(v) {
        if (v === null || v === undefined) return DAU_GACH;
        return so(Math.round(v)) + " " + (this.state.d.tien_te || "");
    }

    /** Mũi tên xu hướng. Không tô màu theo dấu: sản lượng giảm vì trời
     *  ít gió không phải lỗi của ai, nên tô đỏ là đổ oan. */
    xuHuong(v) {
        if (v === null || v === undefined) return "";
        const s = v >= 0 ? "▲" : "▼";
        return `${s} ${so(Math.abs(v), 1)}%`;
    }

    /** Dòng phụ của mỗi thẻ: tỷ lệ phải kèm MẪU SỐ. Khả dụng 97% trên
     *  hai ngày có số không giống 97% trên cả tháng. */
    mauSo(p) {
        if (p.ngay_co_so === null || p.so_ngay === null) return "";
        const thieu = p.ngay_thieu
            ? _t(" · thiếu %s ngày", p.ngay_thieu) : "";
        return _t("%s/%s ngày có số", p.ngay_co_so, p.so_ngay) + thieu;
    }

    /** Câu ghép phải nằm TRỌN trong một chuỗi dịch.
     *
     * Viết "X <b>nhà máy</b> · Y tổ máy" thẳng trong template thì bộ rút
     * chuỗi của Odoo cắt ra thành ba mẩu rời ("nhà máy ·", "tổ máy"), và
     * người dịch nhận được ba mẩu không có ngữ cảnh. Tiếng Anh lại đảo
     * trật tự số–danh từ khác tiếng Việt, nên ghép mẩu là ra câu gãy.
     */
    heroSub() {
        const t = this.state.d.tong;
        return _t("%s plants · %s units", t.so_nha_may, t.so_to_may);
    }
    kdSub() {
        const t = this.state.d.tong;
        return _t("weighted by energy · %s of %s plants have data",
                  t.kd_mau_so, t.so_nha_may);
    }
    thangSub() {
        return _t("since %s", this.state.d.dau_thang);
    }
    tienSub() {
        return _t("loss valued at: %s", this.tien(this.state.d.tong.tien_mat_thang));
    }
    tinCaySub() {
        return _t(
            "All three numbers below make the figures above look better than " +
            "reality. Out of %s unit-day rows this month.",
            so(this.state.d.tin_cay.tong_dong));
    }

    moCanhBao(ma) {
        const T = {
            alarm_critical: ["eam_alarm.action_eam_alarm",
                { search_default_f_dang_mo: 1 }],
            alarm_high: ["eam_alarm.action_eam_alarm",
                { search_default_f_dang_mo: 1 }],
            wo_overdue: ["eam_wo_progress.action_eam_wo_tre_han", {}],
            pm_overdue: ["eam_pm.action_eam_pm_schedule", {}],
            pm_due_soon: ["eam_pm.action_eam_pm_schedule", {}],
            pm_no_data: ["eam_pm.action_eam_pm_schedule", {}],
        }[ma];
        if (!T) return;
        this.action.doAction(T[0], { additionalContext: T[1] });
    }
}

registry.category("actions").add("eam_fleet.dashboard", EamFleetDashboard);
