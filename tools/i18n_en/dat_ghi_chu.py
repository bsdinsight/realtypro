# -*- coding: utf-8 -*-
"""Đặt bản tiếng Anh cho các trường DIỄN GIẢI DÀI của dữ liệu mẫu.

Bảng dịch ở `dich_ghi_chu.tsv`, bốn cột:
`<model><TAB><cột><TAB><tiếng Việt><TAB><tiếng Anh>`, xuống dòng viết `\\n`.

Khác các script trước ở một chỗ: khoá tra là giá trị HIỆN TẠI trong
CSDL, không phải bản gốc tiếng Việt thuần. Lý do: lượt thay mảnh trước
đó có hai từ quá chung ('nhà máy' → 'plant', 'vị trí' → 'location'),
nên chúng bị thay cả bên trong câu tiếng Việt và để lại thứ nửa Anh
nửa Việt — "Cần mô hình bóng đổ theo location mặt trời". Khoá theo
nguyên văn hiện tại thì một lượt ghi đè dọn luôn chỗ hỏng ấy.

Bài học: bảng thay MẢNH chỉ được chứa cụm đủ đặc trưng. Từ thường
dùng như 'nhà máy' hay 'vị trí' xuất hiện trong mọi câu, nên thay
chúng là sửa cả những câu mình không định đụng tới.
"""
import io
import re

print('@@@BATDAU')

VIET = re.compile('[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợ'
                  'ùúủũụưừứửữựỳýỷỹỵđÀÁẢÃẠĂÂÊÔƠƯĐ]')

bang = {}
for dong in io.open('/var/lib/odoo/dich_ghi_chu.tsv', encoding='utf-8'):
    dong = dong.rstrip('\n')
    if not dong.strip():
        continue
    p = dong.split('\t')
    if len(p) != 4:
        print('!! dòng sai định dạng: %s' % dong[:70])
        continue
    mn, col, vi, en = p
    bang.setdefault((mn, col), {})[vi.replace('\\n', '\n')] = en
print('bảng dịch: %s'
      % {('%s.%s' % k): len(v) for k, v in sorted(bang.items())})

dat = 0
chua = {}
for (mn, col), cap in sorted(bang.items()):
    if mn not in env or col not in env[mn]._fields:
        print('!! không có %s.%s' % (mn, col))
        continue
    M = env[mn].with_context(active_test=False)
    co_dich = M._fields[col].translate
    for r in M.search([]):
        cur = r.with_context(lang='en_GB')[col] if co_dich else r[col]
        if not cur or not isinstance(cur, str):
            continue
        en = cap.get(cur)
        if en is None:
            if VIET.search(cur):
                chua.setdefault('%s.%s|%s' % (mn, col, cur), 0)
                chua['%s.%s|%s' % (mn, col, cur)] += 1
            continue
        if co_dich:
            r.with_context(lang='en_GB').write({col: en})
        else:
            r.write({col: en})
        dat += 1
    env.cr.commit()

print('ĐÃ ĐẶT %d ô · còn %d chuỗi chưa có bản dịch (%d ô)'
      % (dat, len(chua), sum(chua.values())))
for k, n in sorted(chua.items(), key=lambda x: -x[1])[:20]:
    mn, _, v = k.partition('|')
    print('   %4d  %-30s %s' % (n, mn, v.replace('\n', ' | ')[:70]))
