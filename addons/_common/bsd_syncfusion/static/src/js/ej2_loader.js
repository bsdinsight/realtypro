/** @odoo-module **/

import { loadBundle } from "@web/core/assets";
import { rpc } from "@web/core/network/rpc";

/**
 * Nạp thư viện Syncfusion EJ2 THEO YÊU CẦU.
 *
 * Thư viện nặng 8,1 MB ngay cả sau khi đã rút gọn còn Gantt + Charts
 * (xem scripts/build_syncfusion_slim.py). Để trong `web.assets_backend`
 * thì MỌI trang Odoo — form khách hàng, danh sách hoá đơn, vừa đăng
 * nhập xong — đều phải tải và phân tích chừng đó mã, dù cả phiên làm
 * việc không ai mở Gantt; mỗi lần nâng cấp module lại đổi hash nên tải
 * lại từ đầu, và màn hình quay hàng chục giây.
 *
 * Vì vậy lib nằm ở bundle RIÊNG `bsd_syncfusion.assets_syncfusion`, và nơi
 * nào cần `window.ej` thì await hàm này trước. Odoo tự chèn thẻ script/
 * link và nhớ bundle đã nạp; ở đây giữ thêm promise để nhiều component
 * mở cùng lúc không kích hoạt hai lần.
 */
let _loading = null;
let _licensed = false;

export function loadEj2() {
    if (window.ej && window.ej.base) {
        return Promise.resolve();
    }
    if (!_loading) {
        _loading = loadBundle("bsd_syncfusion.assets_syncfusion");
    }
    return _loading;
}

/**
 * Nạp lib RỒI đăng ký giấy phép trong một lần gọi.
 *
 * Trước đây bốn nơi tự gọi `rpc` lấy khoá rồi tự `registerLicense` —
 * bốn bản sao của cùng một đoạn, và chỉ cần một bản quên xử lý trường
 * hợp chưa khai khoá là chỗ đó hiện watermark "trial" giữa màn hình
 * khách hàng. Gom về đây một chỗ.
 */
export async function loadEj2WithLicense() {
    await loadEj2();
    if (_licensed || !window.ej || !window.ej.base) {
        return;
    }
    try {
        const resp = await rpc("/bsd_syncfusion/license_key", {});
        if (resp && resp.key) {
            window.ej.base.registerLicense(resp.key);
            _licensed = true;
        }
    } catch {
        // Không lấy được khoá thì vẫn để component chạy — Syncfusion sẽ
        // hiện watermark, xấu nhưng còn hơn màn hình trắng.
    }
}
