# -*- coding: utf-8 -*-
"""Sinh .po CHỈ cho tên thực đơn, gộp vào en_GB.po sẵn có của module.

Vì sao làm riêng một đường cho menu: tên thực đơn là thứ hiện rõ nhất
và rẻ nhất — 244 chuỗi, đổi xong là cả hệ thống trông khác hẳn, trong
khi dịch trọn một module tốn gấp mười. Nhưng không xuất khung .po mới
được cho các module ngoài EAMOne, nên ở đây dựng thẳng dòng tham chiếu
`#: model:ir.ui.menu,name:<xmlid>` từ chính xmlid đọc ra khỏi CSDL —
đó đúng là dạng tham chiếu Odoo ghi cho `ir.ui.menu`.

GỘP chứ không ghi đè: module nào đã có en_GB.po thì giữ nguyên mục cũ,
chỉ thêm mục menu còn thiếu. Ghi đè là xoá mất phần đã dịch.
"""
import io
import os
import sys

import po_lib as P

ADDONS = ['/Users/bsd/projects/realtypro-cnbuild/addons/_common',
          '/Users/bsd/projects/realtypro-cnbuild/addons/_project']


def thu_muc(mod):
    for g in ADDONS:
        d = os.path.join(g, mod)
        if os.path.isfile(os.path.join(d, '__manifest__.py')):
            return d
    return None


def main(tep_vi, tep_en):
    vi = {}
    for d in io.open(tep_vi, encoding='utf-8'):
        if d.startswith('@@@') or not d.strip():
            continue
        p = d.rstrip('\n').split('\t')
        if len(p) == 3:
            vi[p[1]] = p[2]
    en = {}
    for d in io.open(tep_en, encoding='utf-8'):
        if not d.strip():
            continue
        x, _, e = d.rstrip('\n').partition('\t')
        en[x] = e
    thieu = [x for x in vi if x not in en]
    if thieu:
        print('CHƯA dịch %d menu:' % len(thieu), thieu[:5])

    theo_mod = {}
    for xmlid, v in vi.items():
        if xmlid not in en:
            continue
        mod = xmlid.split('.')[0]
        theo_mod.setdefault(mod, []).append({
            'tham_chieu': ['#. module: %s' % mod,
                           '#: model:ir.ui.menu,name:%s' % xmlid],
            'msgid': v,
            'msgstr': en[xmlid],
        })

    bo_qua, xong, tong = [], 0, 0
    for mod, muc in sorted(theo_mod.items()):
        d = thu_muc(mod)
        if not d:
            bo_qua.append((mod, len(muc)))
            continue
        i18n = os.path.join(d, 'i18n')
        if not os.path.isdir(i18n):
            os.makedirs(i18n)
        po = os.path.join(i18n, 'en_GB.po')

        # Gộp với mục đã có, bỏ trùng theo (msgid, dòng tham chiếu)
        cu = P.doc_muc(po) if os.path.exists(po) else []
        da_co = {('\n'.join(m['tham_chieu']), m['msgid']) for m in cu}
        them = [m for m in muc
                if ('\n'.join(m['tham_chieu']), m['msgid']) not in da_co]
        P.ghi_po(po, mod, cu + them)
        xong += 1
        tong += len(them)
        print('   %-24s +%2d menu  (tổng %d mục)'
              % (mod, len(them), len(cu) + len(them)))

    print('\nghi %d mục menu vào %d module' % (tong, xong))
    if bo_qua:
        print('BỎ QUA (module không nằm trong repo realtypro-cnbuild):')
        for m, n in bo_qua:
            print('   %-24s %d menu' % (m, n))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
