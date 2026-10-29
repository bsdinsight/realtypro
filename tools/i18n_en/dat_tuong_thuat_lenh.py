# -*- coding: utf-8 -*-
"""Đặt bản tiếng Anh cho bốn trường TƯỜNG THUẬT của lệnh công việc.

`description`, `root_cause`, `corrective_action`, `cost_service_note`.
Cùng lý do với tên vị trí và tiêu đề: dữ liệu do seed tạo, không có
xmlid nên không có đường .po — phải ghi thẳng giá trị `en_GB`.

Bảng dịch ở `dich_du_lieu_tuong_thuat.tsv`: ba cột
`<trường><TAB><tiếng Việt><TAB><tiếng Anh>`, xuống dòng viết là `\\n`.
"""
import io

print('@@@BATDAU')

TSV = '/tmp/dich_du_lieu_tuong_thuat.tsv'


def go(s):
    return s.replace('\\n', '\n')


bang = {}
for dong in io.open(TSV, encoding='utf-8'):
    dong = dong.rstrip('\n')
    if not dong.strip():
        continue
    p = dong.split('\t')
    if len(p) != 3:
        print('!! dòng sai định dạng:', dong[:60])
        continue
    bang.setdefault(p[0], {})[go(p[1])] = go(p[2])
print('bảng dịch:', {k: len(v) for k, v in bang.items()})

W = env['eam.work.order']
for f, cap in bang.items():
    dat = thieu = 0
    chua = set()
    for r in W.search([]):
        vi = r.with_context(lang='vi_VN')[f] or ''
        if vi in cap:
            r.with_context(lang='en_GB').write({f: cap[vi]})
            dat += 1
        elif any(ord(c) > 127 for c in vi):
            thieu += 1
            chua.add(vi[:60])
    print('%-20s đặt %3d · thiếu %d' % (f, dat, thieu))
    for t in sorted(chua)[:5]:
        print('   !! %s' % t)

env.cr.commit()
print('đã commit')
