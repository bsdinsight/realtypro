# -*- coding: utf-8 -*-
"""Sinh .po cho TÊN ACTION, gộp vào en_GB.po sẵn có của từng module.

Vì sao cần đường riêng cho action, dù menu đã dịch xong: **dịch menu
KHÔNG kéo theo tên action**. Người dùng bấm menu "Projects" rồi mở ra
màn có tiêu đề "Dự án" — tên trên thanh điều hướng và tiêu đề màn là
hai bản ghi khác nhau, hai dòng dịch khác nhau. Đã dính đúng lỗi này
với `rp_handover.action_eam_project`.

Khác `sinh_po_menu.py` ở hai điểm:

* Quét **cả hai repo** (cnbuild và enterprise). Bộ sinh menu chỉ nhìn
  cnbuild, nên `rp_ai` nằm ở enterprise không bao giờ được chạm tới.
* **Gộp msgid trùng** trong cùng một module thành MỘT mục với nhiều
  dòng `#:`. Hai action cùng tên "Mốc chính" trong `rp_schedule` mà
  ghi thành hai mục cùng msgid là tệp .po sai chuẩn gettext.

Bảng dịch ở `dich_action_epcone.tsv`: hai cột
`<module>.<xmlid><TAB><tiếng Anh>`. Danh sách nguồn (msgid) đọc từ
CSDL chứ không chép tay — chép tay sai một dấu là msgid không khớp và
bản dịch im lặng không áp.
"""
import io
import os
import sys

import po_lib as P

REPOS = [
    '/Users/bsd/projects/realtypro-cnbuild/addons/_common',
    '/Users/bsd/projects/realtypro-cnbuild/addons/_project',
    '/Users/bsd/projects/realtypro-enterprise/addons/_common',
    '/Users/bsd/projects/realtypro-enterprise/addons/_project',
    '/Users/bsd/projects/realtypro-enterprise/addons/_sales',
    '/Users/bsd/projects/realtypro-enterprise/addons/_living',
]


def thu_muc(mod):
    for g in REPOS:
        d = os.path.join(g, mod)
        if os.path.isfile(os.path.join(d, '__manifest__.py')):
            return d
    return None


def main(tep_nguon, tep_dich):
    """tep_nguon: dòng `A<TAB>model<TAB>xmlid<TAB>tên tiếng Việt`."""
    nguon = {}
    for d in io.open(tep_nguon, encoding='utf-8'):
        p = d.rstrip('\n').split('\t')
        if len(p) == 4 and p[0] == 'A':
            nguon[p[2]] = (p[1], p[3])

    en = {}
    for d in io.open(tep_dich, encoding='utf-8'):
        if not d.strip():
            continue
        x, _, v = d.rstrip('\n').partition('\t')
        en[x] = v

    thieu = [x for x in nguon if x not in en]
    thua = [x for x in en if x not in nguon]
    if thieu:
        print('CHƯA dịch %d: %s' % (len(thieu), thieu[:5]))
    if thua:
        print('THỪA (không có trong CSDL) %d: %s' % (len(thua), thua[:5]))

    # gộp theo (module, msgid)
    theo_mod = {}
    for xmlid, (model, vi) in nguon.items():
        if xmlid not in en:
            continue
        mod = xmlid.split('.')[0]
        theo_mod.setdefault(mod, {}).setdefault((vi, en[xmlid]), []).append(
            '#: model:%s,name:%s' % (model, xmlid))

    xong = tong = 0
    bo_qua = []
    for mod, nhom in sorted(theo_mod.items()):
        d = thu_muc(mod)
        if not d:
            bo_qua.append((mod, len(nhom)))
            continue
        i18n = os.path.join(d, 'i18n')
        if not os.path.isdir(i18n):
            os.makedirs(i18n)
        po = os.path.join(i18n, 'en_GB.po')
        cu = P.doc_muc(po) if os.path.exists(po) else []
        da_co = {('\n'.join(m['tham_chieu']), m['msgid']) for m in cu}
        them = []
        for (vi, anh), refs in sorted(nhom.items()):
            tc = ['#. module: %s' % mod] + sorted(refs)
            if ('\n'.join(tc), vi) in da_co:
                continue
            them.append({'tham_chieu': tc, 'msgid': vi, 'msgstr': anh})
        if not them:
            continue
        P.ghi_po(po, mod, cu + them)
        xong += 1
        tong += len(them)
        print('   %-26s +%2d  (tổng %d mục)' % (mod, len(them), len(cu) + len(them)))

    print('\nghi %d mục vào %d module' % (tong, xong))
    if bo_qua:
        print('KHÔNG tìm thấy thư mục module:')
        for m, n in bo_qua:
            print('   %-26s %d' % (m, n))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
