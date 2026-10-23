# -*- coding: utf-8 -*-
"""Đo khả dụng từ sổ dừng máy — gom vào MỘT chỗ.

Vì sao tách riêng
-----------------
Khả dụng là con số đi thẳng vào tiền trả cho nhà thầu. Nếu phép đo nằm
rải trong model hợp đồng, model kỳ và màn hình báo cáo thì sớm muộn có
ba cách tính hơi khác nhau, và không ai biết biên bản tháng trước dùng
cách nào.

Ở đây đúng một hàm. Module "Khả dụng & kỳ hợp đồng" làm sau sẽ **mở rộng
hàm này**, không viết hàm thứ hai.

Ba luật đếm, cả ba đều từng làm người ta ra số sai
---------------------------------------------------

**① Mẫu số là giờ-máy.** Ba mươi tua-bin chạy một ngày là 720 giờ-máy.
Lấy tổng giờ dừng của cả ba mươi máy chia cho 24 thì ra số âm; mà chia
cho 24 lại là phản xạ tự nhiên vì "một ngày có 24 giờ".

**② Cắt khoảng về trong kỳ.** Một lần dừng bắt đầu từ tháng trước và kéo
sang tháng này thì chỉ phần nằm TRONG kỳ mới được tính vào kỳ này. Lấy
nguyên ``duration_hours`` là tính cả phần của tháng trước, và tháng
trước đã tính rồi.

**③ Bỏ khoảng dừng CHA.** Sự cố một chỗ kéo theo nhiều máy được ghi
thành một khoảng cha cộng nhiều khoảng con. Cộng cả hai là đếm đúp.
"""
from datetime import datetime

#: Quy trách nhiệm được tính vào phần nhà thầu O&M phải chịu.
TRACH_NHIEM_NHA_THAU = ('om_contract',)
#: Quy trách nhiệm "chưa quy" — chưa thuộc về ai, nhưng phải đếm RIÊNG
#: để người ký biết con số đẹp là do nhà thầu tốt hay do chưa ai phân loại.
CHUA_QUY = 'undetermined'


def _giao_gio(a1, a2, b1, b2):
    """Số giờ giao nhau giữa hai khoảng thời gian."""
    if not (a1 and b1):
        return 0.0
    dau = max(a1, b1)
    cuoi = min(a2, b2)
    if cuoi <= dau:
        return 0.0
    return (cuoi - dau).total_seconds() / 3600.0


def do_kha_dung_thoi_gian(env, plant, tu, den, so_don_vi=0,
                          tinh_ca_chua_quy=False):
    """Khả dụng theo thời gian của một nhà máy trong một khoảng.

    ``so_don_vi``  số đơn vị trong mẫu số. 0 nghĩa là coi cả nhà máy là
                   MỘT đơn vị — đúng khi cam kết đặt ở cấp nhà máy, sai
                   khi cam kết đặt ở cấp tổ máy.
    ``tinh_ca_chua_quy``  có tính luôn giờ dừng chưa quy trách nhiệm vào
                   phần nhà thầu hay không.

    Trả về dict, luôn có ``gio_chua_quy`` kể cả khi không tính vào — đó
    là con số nói cho người đọc biết kết quả đáng tin tới đâu.
    """
    gio_ky = _giao_gio(tu, den, tu, den)
    mau_so = gio_ky * (so_don_vi or 1)

    tinh = set(TRACH_NHIEM_NHA_THAU)
    if tinh_ca_chua_quy:
        tinh.add(CHUA_QUY)

    dom = [
        ('location_id', 'child_of', plant.id),
        ('state', '=', 'confirmed'),
        ('counts_as_downtime', '=', True),
        # Khoảng CHA chỉ là nguyên nhân; giờ-máy thật nằm ở khoảng con.
        ('is_root_cause', '=', False),
        ('date_start', '<', den),
        '|', ('date_end', '=', False), ('date_end', '>', tu),
    ]
    gio_nha_thau = gio_chua_quy = gio_tat_ca = 0.0
    bay_gio = datetime.now()
    khoang = env['eam.outage'].search(dom)
    for o in khoang:
        # Khoảng đang mở tính tới BÂY GIỜ, không tới vô cực.
        ket = o.date_end or min(bay_gio, den)
        g = _giao_gio(o.date_start, ket, tu, den)
        if not g:
            continue
        gio_tat_ca += g
        if o.liability == CHUA_QUY:
            gio_chua_quy += g
        if o.liability in tinh:
            gio_nha_thau += g

    kd = 100.0 * (mau_so - gio_nha_thau) / mau_so if mau_so else 0.0
    return {
        'do_duoc': True,
        'gia_tri': max(kd, 0.0),
        'gio_ky': gio_ky,
        'mau_so': mau_so,
        'so_don_vi': so_don_vi or 1,
        'gio_dung_tinh': gio_nha_thau,
        'gio_chua_quy': gio_chua_quy,
        'gio_dung_tat_ca': gio_tat_ca,
        'so_khoang': len(khoang),
    }


def chua_do_duoc(ly_do):
    """Kết quả cho cam kết mà hệ chưa đo được.

    Trả về một hình dạng GIỐNG HỆT bản đo thật, chỉ khác cờ ``do_duoc``.
    Nếu trả về ``None`` thì chỗ gọi sẽ phải viết nhánh riêng, và nhánh
    riêng là chỗ con số 0 len vào rồi biến thành "không đạt".
    """
    return {
        'do_duoc': False,
        'ly_do': ly_do,
        'gia_tri': 0.0,
        'gio_ky': 0.0,
        'mau_so': 0.0,
        'so_don_vi': 0,
        'gio_dung_tinh': 0.0,
        'gio_chua_quy': 0.0,
        'gio_dung_tat_ca': 0.0,
        'so_khoang': 0,
    }
