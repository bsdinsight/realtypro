# -*- coding: utf-8 -*-
"""Công suất khả dĩ — suy sản lượng đáng lẽ phát từ điều kiện tự nhiên.

Cách thứ hai, bên cạnh máy đối chứng
-------------------------------------
Sổ giờ dừng máy đã có cách **máy đối chứng**: lấy trung bình các máy anh
em đang chạy. Cách đó tốt khi còn đủ máy chạy, nhưng chịu thua đúng lúc
cần nhất — bão làm cả nhà máy dừng, hoặc nhà máy chỉ có vài tổ máy.

Cách ở đây không cần máy nào chạy: lấy **điều kiện tự nhiên đo được**
trong chính khoảng đó rồi tra ra công suất lẽ ra phát.

    điện gió     : tốc độ gió  → đường cong công suất đã nghiệm thu
    điện mặt trời: bức xạ      → diện tích × hiệu suất mô-đun

Vì sao vẫn giữ cả hai cách
---------------------------
Đường cong công suất là **cam kết của hãng trong điều kiện chuẩn**. Máy
thật sau vài năm không còn chạy đúng đường cong đó — cánh bẩn, hiệu
chỉnh góc lệch, suy giảm. Dùng đường cong để tính phần mất thì phần mất
luôn hơi cao, có lợi cho bên đi đòi; dùng máy đối chứng thì bám thực tế
hiện trường hơn.

Nên hợp đồng quy định dùng cách nào, và ở đây **khai được**, không viết
cứng. Con số khai ra cách nào thì ghi lại cách đó, vì hai cách ra hai
số và sáu tháng sau không ai nhớ.

Đường cong thuộc về TỔ MÁY nào
-------------------------------
Phải khai tường minh. Trên bản demo, đường cong có sẵn để trống ô loại
cấu phần, nên phép dò "đường cong nào khớp tổ máy này" khớp nhầm vì
rỗng-khớp-rỗng — một phép so trả về True mà không có gì đúng cả.
"""
from datetime import datetime


def _khong(ly_do):
    return {'tinh_duoc': False, 'ly_do': ly_do, 'kwh': 0.0,
            'so_mau': 0, 'cach': ''}


def san_luong_dang_le_gio(env, vitri, tu, den):
    """kWh lẽ ra phát của một tổ máy gió, suy từ tốc độ gió đo được."""
    duong_cong = vitri.power_curve_id
    if not duong_cong:
        return _khong(
            'vị trí "%s" chưa khai đường cong công suất. Không khai thì '
            'không có gì để tra — đừng đoán theo công suất định mức.'
            % vitri.complete_code)

    tag_gio = env['eam.tag'].search([
        ('location_id', '=', vitri.id),
        ('tag_type', '=', 'wind_speed'),
        ('is_virtual', '=', False)], limit=1)
    if not tag_gio:
        return _khong('vị trí này chưa khai điểm đo tốc độ gió')

    # Lấy theo bước mười phút: đủ mịn để bám đường cong (quan hệ giữa
    # gió và công suất là bậc ba, nên trung bình cả khoảng rồi mới tra
    # sẽ ra số thấp hơn hẳn tổng của từng bước).
    BUOC = 600
    doc = env['eam.historian'].doc_gop([tag_gio.id], tu, den, BUOC)
    diem = doc.get(tag_gio.id) or []
    co = [d for d in diem if d.get('gt') is not None]
    if not co:
        return _khong(
            'kho chuỗi thời gian chưa có số đo tốc độ gió trong khoảng này')

    kwh = 0.0
    for d in co:
        kw = duong_cong.tra_cong_suat(float(d['gt']))
        kwh += kw * (BUOC / 3600.0)
    return {'tinh_duoc': True, 'ly_do': '', 'kwh': kwh,
            'so_mau': len(co), 'cach': 'đường cong "%s"' % duong_cong.name}


def san_luong_dang_le_mat_troi(env, vitri, tu, den):
    """kWh lẽ ra phát của một nhà máy mặt trời, suy từ bức xạ đo được."""
    nm = vitri.plant_id
    if not (nm.pv_module_area and nm.pv_module_eff):
        return _khong(
            'nhà máy chưa khai diện tích mô-đun và hiệu suất mô-đun — '
            'thiếu một trong hai thì không dựng được mẫu số')
    tag_bx = env['eam.tag'].search([
        ('location_id', 'child_of', nm.id),
        ('tag_type', '=', 'irradiance'),
        ('is_virtual', '=', False)], limit=1)
    if not tag_bx:
        return _khong('nhà máy chưa khai điểm đo bức xạ')

    BUOC = 600
    doc = env['eam.historian'].doc_gop([tag_bx.id], tu, den, BUOC)
    co = [d for d in (doc.get(tag_bx.id) or []) if d.get('gt') is not None]
    if not co:
        return _khong(
            'kho chuỗi thời gian chưa có số đo bức xạ trong khoảng này')

    # Phần của riêng tổ máy này trong cả nhà máy. Bức xạ đo ở trạm khí
    # tượng là của CẢ nhà máy, nên phải chia theo số tổ máy — không chia
    # là mỗi tổ máy đòi sản lượng của cả nhà máy.
    anh_em = env['eam.location'].search_count([
        ('id', 'child_of', nm.id), ('location_type', '=', 'position'),
        ('category_id', '=', vitri.category_id.id)]) or 1

    kwh = 0.0
    for d in co:
        # bức xạ W/m² × diện tích m² × hiệu suất → W, rồi ra kWh.
        w = float(d['gt']) * nm.pv_module_area * (nm.pv_module_eff / 100.0)
        kwh += w / 1000.0 * (BUOC / 3600.0)
    return {'tinh_duoc': True, 'ly_do': '', 'kwh': kwh / anh_em,
            'so_mau': len(co),
            'cach': 'bức xạ × %g m² × %g%%, chia cho %d tổ máy'
                    % (nm.pv_module_area, nm.pv_module_eff, anh_em)}


def san_luong_dang_le(env, vitri, tu, den):
    """Chọn cách theo công nghệ của nhà máy."""
    if vitri.plant_id.is_solar:
        return san_luong_dang_le_mat_troi(env, vitri, tu, den)
    return san_luong_dang_le_gio(env, vitri, tu, den)
