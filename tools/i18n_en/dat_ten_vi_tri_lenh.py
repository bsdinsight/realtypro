# -*- coding: utf-8 -*-
"""Đặt bản tiếng Anh cho TÊN VỊ TRÍ và TIÊU ĐỀ LỆNH CÔNG VIỆC.

Hai cột này là DỮ LIỆU do script seed tạo, không có xmlid, nên
`odoo i18n export` không xuất được — không có đường .po nào cả. Cách
duy nhất là ghi thẳng giá trị `en_GB`.

Ngữ cảnh `lang='en_GB'` CHỈ đặt bản dịch, giữ nguyên `en_US` (bản gốc
tiếng Việt). Viết không có ngữ cảnh đó là đè mất bản tiếng Việt.

Tên vị trí lặp lại rất nhiều (1.365 bản ghi dùng 115 tên), nên tra theo
TÊN chứ không theo id: khai một lần, áp cho mọi bản ghi trùng tên.

Chạy:
  docker exec -i <ct> odoo shell -d <db> ... < dat_ten_vi_tri_lenh.py
Bảng dịch đọc từ dich_du_lieu_vi_tri_lenh.tsv đặt cạnh tệp này; nếu
chạy qua stdin thì truyền sẵn nội dung vào biến BANG bên dưới.
"""
import io
import os

print('@@@BATDAU')

TSV = os.path.join(os.path.dirname(os.path.abspath(__file__ or '.')),
                   'dich_du_lieu_vi_tri_lenh.tsv') \
    if '__file__' in dir() else '/tmp/dich_du_lieu_vi_tri_lenh.tsv'

bang = {'T': {}, 'L': {}}
for dong in io.open(TSV, encoding='utf-8'):
    dong = dong.rstrip('\n')
    if not dong.strip():
        continue
    p = dong.split('\t')
    if len(p) != 3:
        print('!! dòng sai định dạng:', dong[:60])
        continue
    bang[p[0]][p[1]] = p[2]
print('bảng dịch: %d tiêu đề lệnh, %d tên vị trí'
      % (len(bang['T']), len(bang['L'])))

# ---- tiêu đề lệnh công việc ----
dat = thieu = 0
for r in env['eam.work.order'].search([]):
    vi = r.with_context(lang='vi_VN').title or ''
    if vi in bang['T']:
        r.with_context(lang='en_GB').write({'title': bang['T'][vi]})
        dat += 1
    elif any(ord(c) > 127 for c in vi):
        thieu += 1
        print('!! chưa có bản dịch cho tiêu đề %r' % vi[:60])
print('tiêu đề lệnh: đặt %d, thiếu %d' % (dat, thieu))

# ---- tên vị trí ----
dat = thieu = 0
con_thieu = set()
for r in env['eam.location'].with_context(active_test=False).search([]):
    vi = r.with_context(lang='vi_VN').name or ''
    if vi in bang['L']:
        r.with_context(lang='en_GB').write({'name': bang['L'][vi]})
        dat += 1
    elif any(ord(c) > 127 for c in vi):
        thieu += 1
        con_thieu.add(vi)
print('tên vị trí: đặt %d bản ghi, thiếu %d bản ghi (%d tên)'
      % (dat, thieu, len(con_thieu)))
for t in sorted(con_thieu)[:10]:
    print('   !! %s' % t)

env.cr.commit()
print('đã commit')
