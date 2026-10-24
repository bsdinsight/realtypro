# -*- coding: utf-8 -*-
"""Khả dụng theo SẢN LƯỢNG — và vì sao nó khác khả dụng theo thời gian.

Hai con số, hai câu hỏi
------------------------
Khả dụng theo **thời gian** hỏi *"bao nhiêu phần trăm thời gian nhà máy
sẵn sàng"*. Khả dụng theo **sản lượng** hỏi *"bao nhiêu phần trăm điện
lẽ ra phát được đã thật sự phát"*. Chúng khác nhau, và khác nhiều.

Một tua-bin dừng một ngày giữa mùa lặng gió mất gần như không gì; dừng
một ngày giữa mùa gió mạnh mất cả chục nghìn kWh. Khả dụng theo thời
gian trừ cùng một lượng cho cả hai. Đó là lý do hợp đồng dịch vụ dài hạn
của hãng thường cam kết theo **sản lượng**: nó là thứ ra tiền.

Công thức
---------
::

    sản lượng đáng lẽ = sản lượng thực + sản lượng mất
    khả dụng          = sản lượng thực ÷ sản lượng đáng lẽ

Mẫu số **không phải** một con số lý thuyết mà là thực tế cộng phần mất
đã hạch toán. Nhờ vậy nó truy ngược được tới từng lần dừng máy, và nhà
thầu cãi được từng dòng thay vì cãi một con số từ trên trời.

Sản lượng mất lấy từ đâu
-------------------------
Từ **đúng engine của sổ giờ dừng máy**, không tính lại. Hai nơi cùng
tính "sản lượng đáng lẽ phát được" là hai nơi sớm muộn ra hai số.

Sản lượng thực lấy từ đâu — và thứ tự ưu tiên
----------------------------------------------
1. **Bậc bán điện của chuỗi điểm đo** — số có hoá đơn làm chứng, nên
   luôn ưu tiên.
2. **Cộng điện năng từ các tổ máy** — khi nhà máy chưa khai chuỗi. Số
   này là số SCADA, có thể lệch công-tơ vài phần nghìn.
3. Không có cả hai → **nói chưa đo được**. Lấy 0 thì khả dụng ra 0%,
   đọc ra là "nhà máy chết cả kỳ" — ngược hẳn sự thật.
"""
import pytz

from datetime import datetime, timedelta


def _khong(ly_do):
    return {'do_duoc': False, 'ly_do': ly_do, 'gia_tri': 0.0,
            'sl_that': 0.0, 'sl_mat': 0.0, 'sl_dang_le': 0.0,
            'nguon_sl': '', 'so_khoang': 0, 'so_khoang_chua_tinh': 0}


def san_luong_that(env, plant, tu, den):
    """kWh nhà máy thật sự phát trong khoảng, kèm chỗ lấy số."""
    # 1. Bậc bán điện — số có hoá đơn làm chứng.
    chuoi = env['eam.chain'].search([('plant_id', '=', plant.id)], limit=1)
    bac = chuoi.node_ids.filtered('is_billing') if chuoi else None
    if bac:
        # HAI LOẠI "NGÀY" trong cùng một hàm, và chúng không đổi lẫn
        # nhau được:
        #
        #   * tu/den là mốc thời gian UTC — thứ kho chuỗi thời gian hiểu;
        #   * eam.chain.day khoá theo NGÀY LỊCH ĐỊA PHƯƠNG — thứ con
        #     người và hoá đơn hiểu.
        #
        # Lấy ``tu.date()`` thẳng từ mốc UTC là trộn hai loại ấy. Ngày
        # 20/10 của một nhà máy ở Việt Nam bắt đầu lúc 17:00 UTC ngày
        # 19, nên ``tu.date()`` ra 19/10 và cửa sổ nuốt TRỌN thêm một
        # ngày: đo trên dữ liệu thật, 261.630 kWh thành 374.301 — tức
        # 112.671 của ngày 19 cộng vào. Con số vẫn dương, vẫn hợp lý,
        # và chỉ lộ khi đem đối chiếu công-tơ.
        #
        # Nên đổi NGƯỢC về giờ địa phương rồi mới lấy ngày.
        mui = pytz.timezone(plant.mui_gio())
        d_tu = pytz.UTC.localize(tu).astimezone(mui).date()
        cuoi = (pytz.UTC.localize(den).astimezone(mui)
                - timedelta(microseconds=1)).date()
        ngay = env['eam.chain.day'].search([
            ('node_id', '=', bac.id),
            ('date', '>=', d_tu), ('date', '<=', cuoi)])
        if ngay:
            return (sum(ngay.mapped('energy')),
                    'bậc bán điện "%s", %d ngày' % (bac.name, len(ngay)))

    # 2. Cộng điện năng từng tổ máy — số SCADA.
    tags = env['eam.tag'].search([
        ('location_id', 'child_of', plant.id),
        ('tag_type', '=', 'energy'), ('is_virtual', '=', False)])
    if tags:
        # KHÔNG dùng doc_gop ở đây, dù đặt bước bằng đúng cả cửa sổ.
        #
        # doc_gop chia bục theo lưới thời gian TUYỆT ĐỐI
        # (floor(epoch/bước)*bước), nên một ngày địa phương bắt đầu lúc
        # 17:00 UTC rơi vào HAI bục. Với đồng hồ luỹ kế, mỗi lần cắt làm
        # mất đúng một nhịp lấy mẫu: tổng thành (cuối_A − đầu_A) +
        # (cuối_B − đầu_B) thay vì (cuối_B − đầu_A).
        #
        # Đo trên dữ liệu thật ngày 15/10: 154.361,030 thay vì
        # 154.432,390 — thiếu 71,36 kWh, tức 0,046%. Nhỏ, nhưng là cái
        # sai CÓ HỆ THỐNG và luôn thiếu về một phía, nên cộng cả năm thì
        # không còn nhỏ. Và nó không báo gì: con số vẫn dương, vẫn hợp
        # lý, chỉ lệch với công-tơ.
        #
        # tom_tat_ngay gộp thẳng trên cửa sổ, không chia bục.
        kq = env['eam.historian'].tom_tat_ngay(tags.ids, tu, den,
                                               gop_nhieu='tong')
        if kq and kq.get('gop') is not None:
            return kq['gop'], 'cộng điện năng %d tổ máy (số SCADA)' % (
                kq.get('so_diem_do') or len(tags))
    return None, ''


def san_luong_mat_ky(env, plant, tu, den, chi_om=True):
    """kWh mất trong khoảng, cộng từ sổ dừng máy.

    Khoảng dừng vắt qua ranh giới kỳ thì **chia theo tỷ lệ giờ** nằm
    trong kỳ. Lấy trọn là tính cả phần của kỳ trước, mà kỳ trước đã tính
    rồi — cộng hai kỳ lại sẽ lớn hơn tổng thật.
    """
    O = env['eam.outage']
    dom = [('location_id', 'child_of', plant.id),
           ('state', '=', 'confirmed'),
           ('is_root_cause', '=', False),
           ('date_start', '<', den),
           '|', ('date_end', '=', False), ('date_end', '>', tu)]
    if chi_om:
        dom.append(('liability', '=', 'om_contract'))
    bay_gio = datetime.now()
    tong = 0.0
    dem = chua = 0
    for o in O.search(dom):
        ket = o.date_end or min(bay_gio, den)
        dau, cuoi = max(o.date_start, tu), min(ket, den)
        if cuoi <= dau:
            continue
        dem += 1
        if not o.lost_mwh:
            chua += 1
            continue
        ca = (ket - o.date_start).total_seconds()
        trong = (cuoi - dau).total_seconds()
        ty = (trong / ca) if ca else 1.0
        tong += o.lost_mwh * 1000.0 * ty
    return tong, dem, chua


def kha_dung_san_luong(env, plant, tu, den, chi_om=True):
    """Khả dụng theo sản lượng của một nhà máy trong một khoảng."""
    that, nguon = san_luong_that(env, plant, tu, den)
    if that is None:
        return _khong(
            'nhà máy chưa khai chuỗi điểm đo có bậc bán điện, và cũng '
            'chưa có điểm đo điện năng nào có số trong khoảng này — '
            'không có sản lượng thực thì không có tử số')
    mat, dem, chua = san_luong_mat_ky(env, plant, tu, den, chi_om)
    dang_le = that + mat
    if dang_le <= 0:
        return _khong(
            'sản lượng thực và sản lượng mất đều bằng 0 trong khoảng này '
            '— chia cho 0 thì ra số vô nghĩa, nên để trống')
    return {
        'do_duoc': True, 'ly_do': '',
        'gia_tri': 100.0 * that / dang_le,
        'sl_that': that, 'sl_mat': mat, 'sl_dang_le': dang_le,
        'nguon_sl': nguon,
        'so_khoang': dem, 'so_khoang_chua_tinh': chua,
    }
