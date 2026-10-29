# -*- coding: utf-8 -*-
"""Thay các MẢNH tiếng Việt còn nhúng bên trong câu đã dịch.

Tầng mẫu ở `dich_du_lieu_mau.py` dịch được KHUNG của câu sinh tự động
("Handover BG/… · contract …"), nhưng phần ruột là tên một bản ghi khác
— tên hợp đồng, tên mùa, tên nhà máy — nên nó đi nguyên qua. Ở đây
quét lại toàn bộ và thay từng mảnh, bất kể mảnh nằm ở đâu trong câu.

Chạy SAU `dich_du_lieu_mau.py`. Thay theo mảnh DÀI TRƯỚC: thay
'Mùa gió mạnh' trước 'Mùa gió mạnh Đắk Lắk' thì mảnh dài không còn
khớp được nữa.
"""
import re

print('@@@BATDAU')

VIET = re.compile('[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợ'
                  'ùúủũụưừứửữựỳýỷỹỵđÀÁẢÃẠĂÂÊÔƠƯĐ]')
BO_MODEL = {'eam.unit.day', 'eam.loss.day.line', 'eam.loss.day',
            'eam.energy.period', 'eam.availability.day', 'eam.alarm'}
BO_KHOA = {('eam.asset.category', 'alias_names'),
           ('product.template', 'eam_spec_key')}
BO_COT = {'complete_name'}

MANH = {
    'TSA — Cung cấp & lắp đặt tua-bin (TSI)':
        'TSA — Turbine supply & installation (TSI)',
    'Cung cấp & lắp đặt tua-bin': 'Turbine supply & installation',
    'Mùa gió mạnh Savannakhet': 'Savannakhet high-wind season',
    'Mùa gió mạnh Đắk Lắk': 'Đắk Lắk high-wind season',
    'Mùa mưa Đắk Lắk': 'Đắk Lắk rainy season',
    'Mùa phát cao — dừng máy ở đây mất sản lượng nhiều nhất':
        'high-output season — stopping a machine here loses the most energy',
    'Mùa phát cao': 'high-output season',
    'Kiểm định trong mùa mưa': 'statutory inspection during the rainy season',
    'kho chuỗi thời gian hiện chỉ phủ một phần thời gian của sổ dừng máy':
        'the historian currently covers only part of the outage log period',
    'Thay bộ điều khiển là đồng hồ giờ máy về 0':
        'Replacing the controller resets the run-hour meter to zero',
    'nhớ đánh dấu "đã thay đồng hồ"':
        'remember to flag "meter replaced"',
    'liệt kê đích danh máy': 'machine listed by name',
    'chưa rõ hợp đồng': 'contract not identified',
    'Thuộc diện kiểm định định kỳ': 'Subject to periodic statutory inspection',
    'gắn lịch kiểm định vào đây': 'attach the inspection schedule here',
    'Chỗ tiền đi qua': 'This is where the money passes',
    'Hộp số, máy phát, cánh, bộ biến tần':
        'Gearbox, generator, blades, converter',
    'Báo cáo mô phỏng gió': 'Wind simulation report',
    'phụ lục': 'appendix',
    'HĐ vay': 'loan agreement',
    'HĐ-OM-': 'OM-CONTRACT-',
    'Cánh quạt thay thế': 'Replacement blade',
    'Bộ biến tần toàn phần (FSC)': 'Full-scale converter (FSC)',
    'Hộp số thay thế': 'Replacement gearbox',
    'Máy phát thay thế': 'Replacement generator',
    'Máy biến áp tua-bin': 'Turbine transformer',
    'Ổ trục chính (main bearing)': 'Main bearing',
    'Ổ trục chính': 'Main bearing',
    'trạm khí tượng': 'weather station',
    'cột khí tượng': 'met mast',
    'tổ máy': 'unit', 'nhà máy': 'plant', 'vị trí': 'location',
    # Khung câu lịch theo mùa. Phải khai RIÊNG từng mảnh vì lượt thay
    # trước đã đổi tên mùa, nên mẫu regex nguyên câu không còn khớp —
    # thay mảnh và khớp mẫu đạp chân nhau nếu chạy sai thứ tự.
    'Đề xuất kéo lên sớm': 'Suggested: bring forward by',
    'ngày, làm ngày': 'days, to be done on',
    'Hạn kiểm định rơi vào': 'Statutory inspection due date falls in',
    'Hạn rơi vào': 'Due date falls in',
    'Hạn ': 'Due date ',
    'rơi vào': 'falls in',
    'Nên tránh:': 'best avoided:',
    'và KHÔNG tránh được trong giới hạn 30 ngày':
        'and it cannot be avoided within the 30-day limit',
    'Phải bố trí làm trong mùa — xem lý do ở luật mùa':
        'It has to be scheduled inside the season — see the seasonal rule '
        'for the reason',
    'machine listed by name này)': 'machine listed by name)',
    ' này)': ')',
}
# dài trước, để mảnh dài không bị mảnh ngắn ăn mất
THAY = sorted(MANH.items(), key=lambda x: -len(x[0]))

dat = 0
con = {}
for l in open('/var/lib/odoo/con_viet.tsv', encoding='utf-8'):
    p = l.rstrip('\n').split('\t')
    if len(p) < 6 or p[0] != 'T':
        continue
    mn, rid, col, tr = p[1], int(p[2]), p[3], p[4]
    if mn in BO_MODEL or col in BO_COT or (mn, col) in BO_KHOA:
        continue
    r = env[mn].with_context(active_test=False).browse(rid)
    if not r.exists():
        continue
    # Đọc GIÁ TRỊ HIỆN TẠI (đã qua lượt dịch trước), không đọc bản dump.
    cur = r.with_context(lang='en_GB')[col] if tr == 'T' else r[col]
    if not cur or not VIET.search(cur):
        continue
    moi = cur
    for a, b in THAY:
        moi = moi.replace(a, b)
    if moi == cur:
        con.setdefault(cur, 0)
        con[cur] += 1
        continue
    if tr == 'T':
        r.with_context(lang='en_GB').write({col: moi})
    else:
        r.write({col: moi})
    dat += 1
    if VIET.search(moi):
        con.setdefault(moi, 0)
        con[moi] += 1

env.cr.commit()
print('đã thay mảnh ở %d ô · còn %d chuỗi chưa sạch (%d ô)'
      % (dat, len(con), sum(con.values())))
for s, n in sorted(con.items(), key=lambda x: -x[1])[:25]:
    print('   %4d  %s' % (n, s[:92]))
