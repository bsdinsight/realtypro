# -*- coding: utf-8 -*-
"""Quy giờ dừng ra kWh mất — MỘT engine, dùng chung.

Vì sao gom vào một chỗ ngay từ đầu
-----------------------------------
"Sản lượng đáng lẽ phát được" bị hỏi ở hai nơi khác nhau: sổ giờ dừng
máy hỏi *"lần dừng này mất bao nhiêu kWh"*, còn khả dụng theo sản lượng
hỏi *"cả kỳ đáng lẽ phát bao nhiêu"*. Cùng một phép tính, hai câu hỏi.

Viết hai lần là lặp lại đúng bài học đã trả giá ở EVM: hai engine cùng
tên cho ra hai con số, và không ai biết báo cáo nào dùng cái nào. Nên
module khả dụng làm sau sẽ **gọi vào đây**, không viết hàm thứ hai.

Cách KHÔNG được dùng
---------------------
``công suất định mức × số giờ dừng``. Đây là cách nói sai phổ biến nhất
trong báo cáo năng lượng: nó giả định suốt thời gian dừng máy lẽ ra chạy
hết công suất, trong khi gió có thể lặng và trời có thể mưa. Con số ra
luôn lớn hơn thực tế, và lớn một cách có lợi cho người đi đòi bồi
thường — nên nó không đứng được trước nhà thầu.

Máy đối chứng
--------------
Cách dùng ở đây, và là cách các tiêu chuẩn vận hành công nhận: trong
đúng khoảng máy X dừng, xem **các máy anh em cùng nhà máy, cùng loại,
đang chạy** phát được bao nhiêu, lấy trung bình, rồi coi đó là thứ X lẽ
ra phát. Điều kiện gió và nắng được chính các máy kia đo hộ, không phải
giả định.

Ba chỗ phải nói thật thay vì trả về một con số
-----------------------------------------------
* Kho chuỗi thời gian **chưa có số đo** trong khoảng đó.
* Máy anh em **cũng đang dừng** hết, không còn ai làm đối chứng.
* Khoảng dừng ghi ở **cấp nhà máy hoặc cấp cấu phần**, không phải cấp tổ
  máy — không có "anh em" để so.

Cả ba trả về ``tinh_duoc=False`` kèm lý do. Trả 0 thì 0 kWh trông như
"lần dừng này không mất gì", mà đó là kết luận ngược hẳn.
"""
from datetime import datetime

PHUONG_PHAP = [
    ('doi_chung', 'Máy đối chứng'),
    ('duong_cong', 'Đường cong công suất'),
    ('tay', 'Nhập tay'),
]

#: Phương pháp CHƯA làm được, kèm lý do nói thẳng.
CHUA_LAM = {
    'duong_cong': 'cần đường cong công suất đã nghiệm thu cộng chuỗi '
                  'tốc độ gió hoặc bức xạ tại chính vị trí đó — thuộc '
                  'module Khả dụng, chưa làm',
}

#: Số máy đối chứng tối thiểu để con số có nghĩa. Một máy thì trung bình
#: chính là máy đó, và nếu nó gặp sự cố cục bộ thì cả phép tính lệch
#: theo mà không có gì báo.
TOI_THIEU = 3


def _khong(ly_do, **them):
    kq = {'tinh_duoc': False, 'ly_do': ly_do, 'kwh': 0.0,
          'so_doi_chung': 0, 'kwh_that': 0.0, 'kwh_mong_doi': 0.0}
    kq.update(them)
    return kq


def _gop_theo_tag(doc):
    """Một con số cho MỖI TAG, không phải mỗi điểm dữ liệu.

    ``doc_gop`` chia theo lưới thời gian TUYỆT ĐỐI, nên một khoảng dài
    vẫn rơi vào hai ô dù bước gộp bằng cả khoảng. Đếm điểm thay vì đếm
    tag thì mười hai tua-bin ra "hai mươi hai máy đối chứng", và lấy
    trung bình trên các mảnh thì tổng hụt đi một nửa — cả hai cái sai
    đều ra số dương trông hợp lý.
    """
    theo_tag = {}
    for tid, diem in doc.items():
        co = [float(d['gt']) for d in diem if d.get('gt') is not None]
        if co:
            # Điện năng luỹ kế gộp bằng hiệu đầu–cuối, nên hai mảnh thì
            # CỘNG lại mới ra hiệu của cả khoảng.
            theo_tag[tid] = sum(co)
    return list(theo_tag.values())


def _tag_san_luong(env, vitri):
    """Điểm đo điện năng luỹ kế của một vị trí, nếu có."""
    return env['eam.tag'].search([
        ('location_id', '=', vitri.id),
        ('tag_type', '=', 'energy'),
        ('is_virtual', '=', False)], limit=1)


def san_luong_mat(env, outage, toi_thieu=TOI_THIEU):
    """kWh lẽ ra phát được trong khoảng một lần dừng máy.

    Trả về dict luôn cùng hình dạng, ``tinh_duoc`` nói có dùng được hay
    không. Không bao giờ ném lỗi: sổ dừng máy có hàng trăm dòng và một
    dòng không tính được không được phép chặn cả lượt.
    """
    vt = outage.location_id
    if vt.location_type != 'position':
        return _khong(
            'khoảng dừng ghi ở cấp "%s", không phải cấp tổ máy — không có '
            'máy anh em để đối chứng' % dict(
                vt._fields['location_type'].selection).get(vt.location_type))

    tu = outage.date_start
    den = outage.date_end or datetime.now()
    if not tu or den <= tu:
        return _khong('khoảng dừng chưa có thời điểm kết thúc hợp lệ')
    giay = (den - tu).total_seconds()

    nha_may = vt.plant_id
    L = env['eam.location']
    anh_em = L.search([
        ('id', 'child_of', nha_may.id),
        ('location_type', '=', 'position'),
        ('id', '!=', vt.id),
        ('category_id', '=', vt.category_id.id)])
    if not anh_em:
        return _khong('nhà máy không có tổ máy nào cùng loại để đối chứng')

    # Máy anh em NÀO CŨNG đang dừng thì nó không còn là đối chứng.
    O = env['eam.outage']
    dang_dung = O.search([
        ('location_id', 'in', anh_em.ids),
        ('counts_as_downtime', '=', True),
        ('date_start', '<', den),
        '|', ('date_end', '=', False), ('date_end', '>', tu),
    ]).mapped('location_id')
    chay = anh_em - dang_dung
    if not chay:
        return _khong('mọi tổ máy cùng loại đều đang dừng trong khoảng này')

    tags = env['eam.tag'].browse()
    theo_vt = {}
    for m in chay:
        t = _tag_san_luong(env, m)
        if t:
            tags |= t
            theo_vt[t.id] = m
    if not tags:
        return _khong('các tổ máy đối chứng chưa khai điểm đo điện năng')

    # Gộp CẢ khoảng thành một bước, để mỗi tag ra đúng một con số theo
    # cách gộp của chính nó (điện năng luỹ kế lấy hiệu đầu–cuối).
    doc = env['eam.historian'].doc_gop(tags.ids, tu, den, int(giay) or 1)
    gt = _gop_theo_tag(doc)
    if len(gt) < toi_thieu:
        return _khong(
            'chỉ có %d tổ máy đối chứng có số đo trong khoảng này, cần ít '
            'nhất %d — kho chuỗi thời gian hiện chỉ phủ một phần thời '
            'gian của sổ dừng máy' % (len(gt), toi_thieu),
            so_doi_chung=len(gt))

    mong_doi = sum(gt) / len(gt)

    # Máy đang xét có thể vẫn phát một phần (giảm tải, chứ không dừng
    # hẳn). Trừ phần nó thật sự phát ra, nếu không thì phần đó bị tính
    # là mất trong khi nó đã vào công-tơ.
    that = 0.0
    tv = _tag_san_luong(env, vt)
    if tv:
        dv = env['eam.historian'].doc_gop([tv.id], tu, den, int(giay) or 1)
        rieng = _gop_theo_tag(dv)
        that = rieng[0] if rieng else 0.0

    # Máy được ghi là DỪNG mà số đo nói nó phát nhiều hơn trung bình máy
    # đang chạy: hai nguồn đang mâu thuẫn. Kẹp về 0 rồi im lặng là giấu
    # mất mâu thuẫn đó, và người đọc tưởng lần dừng này không mất gì.
    if that > mong_doi:
        return _khong(
            'số đo nói tổ máy này phát %.0f kWh trong chính khoảng sổ ghi '
            'là dừng, nhiều hơn trung bình %.0f kWh của %d máy đối chứng '
            '— sổ dừng máy và kho chuỗi thời gian đang mâu thuẫn, phải '
            'xem lại một trong hai trước khi tin con số nào'
            % (that, mong_doi, len(gt)),
            so_doi_chung=len(gt), kwh_mong_doi=mong_doi, kwh_that=that)

    return {
        'tinh_duoc': True, 'ly_do': '',
        'kwh': mong_doi - that,
        'kwh_mong_doi': mong_doi,
        'kwh_that': that,
        'so_doi_chung': len(gt),
    }
