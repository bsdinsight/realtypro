/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

// Bảng điều khiển "Ca trực sáng nay".
//
// Màn này trả lời ĐÚNG MỘT câu: sáng nay tôi phải làm gì trước. Mọi
// phong cách lấy từ khuôn dùng chung `eam_dashboard` — không khai lại
// SCSS, không gõ mã màu. Xem eam_dashboard/KHUON.md.
//
// Luật ① của khuôn áp ở ĐÂY, chỗ rẻ nhất để giữ: hàm `so()` dưới đây
// là nơi duy nhất quyết định một giá trị hiện ra thế nào, và nó trả
// dấu gạch cho `null`. Nhờ vậy không có đường nào để một ô "chưa đo
// được" lọt ra màn hình thành số 0 — kể cả khi người sau thêm ô mới
// mà quên luật.

const KHOA_NM = "eam_dash_shift.plant";

export class EamDashShift extends Component {
    static template = "eam_dash_shift.Board";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            loading: true,
            error: null,
            data: null,
            plantCode: null,
            ngay: null,
        });

        onWillStart(async () => {
            try {
                this.state.plantCode =
                    window.localStorage.getItem(KHOA_NM) || null;
            } catch {
                // Trình duyệt chặn localStorage (cửa sổ riêng tư) —
                // không sao, chỉ mất việc nhớ nhà máy lần trước.
            }
            await this.nap();
        });
    }

    async nap() {
        this.state.loading = true;
        this.state.error = null;
        try {
            this.state.data = await this.orm.call(
                "eam.dash.shift", "get_data",
                [], { plant_code: this.state.plantCode || null,
                       ngay: this.state.ngay || null });
            this.state.ngay = this.state.data.ngay;
        } catch (e) {
            this.state.error = (e && e.message) || String(e);
        } finally {
            this.state.loading = false;
        }
    }

    async doiNhaMay(ev) {
        this.state.plantCode = ev.target.value || null;
        try {
            if (this.state.plantCode) {
                window.localStorage.setItem(KHOA_NM, this.state.plantCode);
            } else {
                window.localStorage.removeItem(KHOA_NM);
            }
        } catch { }
        await this.nap();
    }

    async doiNgay(ev) {
        this.state.ngay = ev.target.value || null;
        await this.nap();
    }

    // ---- hiển thị ----

    /** Giá trị hoặc DẤU GẠCH. Không bao giờ trả 0 cho `null`. */
    so(v, le = 1) {
        if (v === null || v === undefined) {
            return "—";
        }
        return Number(v).toLocaleString("vi-VN", {
            minimumFractionDigits: le, maximumFractionDigits: le });
    }

    /** Lớp CSS của thẻ: ưu tiên "chưa đo được" trước mọi mức tốt/xấu. */
    lopThe(doDuoc, muc) {
        if (!doDuoc) {
            return "eam-card is-unknown";
        }
        return "eam-card" + (muc ? " is-" + muc : "");
    }

    /** Mẫu số dạng "trên 12/16 tổ máy" — luật ② của khuôn. */
    mauSo(cap, danh_tu = "tổ máy") {
        if (!cap) {
            return "";
        }
        return "trên " + cap[0] + "/" + cap[1] + " " + danh_tu + " có số";
    }

    mucKhaDung(v) {
        if (v === null || v === undefined) {
            return "";
        }
        return v < 90 ? "bad" : (v < 95 ? "warn" : "good");
    }

    // ---- mở màn chi tiết ----

    async moDanhSach(ma) {
        const BANG = {
            alarm_new: ["eam.alarm", "Cảnh báo chưa xác nhận",
                        [["state", "=", "new"]]],
            alarm_crit: ["eam.alarm", "Cảnh báo nghiêm trọng đang mở",
                         [["state", "in", ["new", "ack", "wo"]],
                          ["severity", "in", ["high", "critical"]]]],
            wo_late: ["eam.work.order", "Lệnh công việc quá hạn",
                      [["tre_han", "=", true],
                       ["state", "in", ["draft", "approved", "planned",
                                        "in_progress"]]]],
            wo_hold: ["eam.work.order", "Lệnh đang chờ",
                      [["is_on_hold", "=", true],
                       ["state", "in", ["draft", "approved", "planned",
                                        "in_progress"]]]],
            pm_over: ["eam.pm.schedule", "Bảo trì quá hạn",
                      [["state", "=", "overdue"]]],
            pm_soon: ["eam.pm.schedule", "Bảo trì sắp tới hạn",
                      [["state", "=", "due_soon"]]],
            rpt_draft: ["eam.daily.report", "Báo cáo ngày chưa chốt",
                        [["state", "=", "nhap"]]],
            outage_open: ["eam.outage", "Khoảng dừng đang mở",
                          [["is_open", "=", true],
                           ["counts_as_downtime", "=", true]]],
            outage_liab: ["eam.outage", "Khoảng dừng chưa quy trách nhiệm",
                          [["state", "=", "confirmed"],
                           ["liability", "=", false]]],
        };
        const c = BANG[ma];
        if (!c) {
            return;
        }
        const [model, ten, domain] = c;
        const d = domain.slice();
        // Lọc theo nhà máy đang chọn để danh sách mở ra khớp con số vừa
        // bấm. Không lọc thì người dùng bấm "3" rồi thấy 11 dòng.
        if (this.state.plantCode && this.state.data && this.state.data.plant) {
            d.push(["plant_id.code", "=", this.state.plantCode]);
        }
        await this.action.doAction({
            type: "ir.actions.act_window",
            name: ten,
            res_model: model,
            domain: d,
            views: [[false, "list"], [false, "form"]],
            target: "current",
        });
    }
}

registry.category("actions").add("eam_dash_shift.board", EamDashShift);
