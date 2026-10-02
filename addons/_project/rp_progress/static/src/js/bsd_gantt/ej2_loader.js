/** @odoo-module **/

import { loadBundle } from "@web/core/assets";

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
 * Vì vậy lib nằm ở bundle RIÊNG `rp_progress.assets_syncfusion`, và nơi
 * nào cần `window.ej` thì await hàm này trước. Odoo tự chèn thẻ script/
 * link và nhớ bundle đã nạp; ở đây giữ thêm promise để nhiều component
 * mở cùng lúc không kích hoạt hai lần.
 */
let _loading = null;

export function loadEj2() {
    if (window.ej && window.ej.base) {
        return Promise.resolve();
    }
    if (!_loading) {
        _loading = loadBundle("rp_progress.assets_syncfusion");
    }
    return _loading;
}
