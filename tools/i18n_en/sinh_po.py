# -*- coding: utf-8 -*-
"""Đổ bản dịch vào khung .po, tách thành <module>/i18n/en_GB.po.

Hai thứ script này KHÔNG chịu bỏ qua, vì cả hai đều hỏng âm thầm:

① **Chỗ thay số phải khớp y hệt.** `%s`, `%(ten)s`, `%(n)d` trong bản
   dịch mà lệch với bản gốc thì Odoo nổ TypeError ngay lúc người dùng
   bấm — không phải lúc nạp. Đây là lỗi chỉ lộ trên máy khách.
② **Dòng tham chiếu phải giữ nguyên.** Bộ nhập của Odoo dựa vào
   `#: model:…` / `model_terms:…` / `code:…` để biết bản dịch thuộc
   trường nào. Mất chúng thì hoặc nổ, hoặc tệ hơn: nạp êm mà không
   dịch được gì.
"""
import io
import json
import os
import re
import sys

import po_lib as P

ADDONS = '/Users/bsd/projects/realtypro-cnbuild/addons'


def thu_muc_module(mod):
    """Module nằm ở _common hay _project — KHÔNG đoán.

    Ghi cứng `_common` là lần đầu tôi tạo nhầm hai thư mục module rỗng
    cho eam_energy và eam_procurement, vốn nằm ở _project. Thư mục rỗng
    có `i18n/` mà không có `__manifest__.py` thì Odoo lặng lẽ bỏ qua —
    bản dịch không bao giờ được nạp mà chẳng có gì báo.
    """
    for kho in ('_common', '_project'):
        d = os.path.join(ADDONS, kho, mod)
        if os.path.isfile(os.path.join(d, '__manifest__.py')):
            return d
    return None
# Bắt CẢ dạng có định dạng: %.2f, %(n).1f, %(t)02d. Bản đầu tôi mượn
# biểu thức của tools/port17 vốn chỉ bắt %s / %(ten)s — nó bỏ sót đúng
# những chỗ hay sai nhất, vì số có định dạng toàn nằm trong câu báo lỗi
# dài, chỗ người dịch dễ gõ lệch.
CHO_THAY = re.compile(r'%\(?[a-zA-Z_0-9]*\)?[0-9.]*[sdfr]|%%|\{[a-zA-Z_0-9]*\}')

RE_XMLID = re.compile(r'#:\s*\S+:([a-z0-9_]+)\.')
RE_CODE = re.compile(r'#:\s*code:addons/([a-z0-9_]+)/')


def module_cua_ref(d):
    g = RE_CODE.match(d) or RE_XMLID.match(d)
    return g.group(1) if g else None


def go_thoat(s):
    return (s.replace('\\n', '\n').replace('\\t', '\t')
            .replace('\\\\', '\\'))


def main(po_goc, thu_muc_dich, chi_ghi=None):
    idx = json.load(io.open('idx.json', encoding='utf-8'))

    dich = {}
    for f in sorted(os.listdir(thu_muc_dich)):
        if not f.endswith('.tsv'):
            continue
        for dong in io.open(os.path.join(thu_muc_dich, f), encoding='utf-8'):
            dong = dong.rstrip('\n')
            if not dong.strip():
                continue
            so, _, en = dong.partition('\t')
            if so not in idx:
                print('!! số %r không có trong idx (%s)' % (so, f))
                continue
            dich[idx[so]] = go_thoat(en)

    # ① kiểm chỗ thay số
    loi = 0
    for vi, en in dich.items():
        a = sorted(CHO_THAY.findall(vi))
        b = sorted(CHO_THAY.findall(en))
        if a != b:
            loi += 1
            print('!! LỆCH CHỖ THAY SỐ\n   gốc : %s\n   dịch: %s\n   %r vs %r'
                  % (vi[:90], en[:90], a, b))
    if loi:
        print('\nDừng: %d chuỗi lệch chỗ thay số.' % loi)
        return 1
    print('có %d bản dịch, chỗ thay số khớp hết' % len(dich))

    # ② tách theo module, giữ nguyên dòng tham chiếu
    muc = P.doc_muc(po_goc)
    theo_mod = {}
    for m in muc:
        if m['msgid'] not in dich:
            continue
        nhom = {}
        for d in m['tham_chieu']:
            if d.startswith('#:'):
                mod = module_cua_ref(d)
                if mod:
                    nhom.setdefault(mod, []).append(d)
        for mod, refs in nhom.items():
            theo_mod.setdefault(mod, []).append({
                'tham_chieu': ['#. module: %s' % mod] + refs,
                'msgid': m['msgid'],
                'msgstr': dich[m['msgid']],
            })

    tong = 0
    for mod in sorted(theo_mod):
        if chi_ghi and mod not in chi_ghi:
            continue
        goc_mod = thu_muc_module(mod)
        if not goc_mod:
            print('   !! %s: không tìm thấy module, BỎ QUA' % mod)
            continue
        d = os.path.join(goc_mod, 'i18n')
        if not os.path.isdir(d):
            os.makedirs(d)
        n = P.ghi_po(os.path.join(d, 'en_GB.po'), mod, theo_mod[mod])
        tong += n
        print('   %-24s %4d mục → %s/i18n/en_GB.po' % (mod, n, mod))
    print('\nghi %d mục vào %d tệp' % (tong, len(
        [m for m in theo_mod if not chi_ghi or m in chi_ghi])))
    return 0


if __name__ == '__main__':
    chi = set(sys.argv[3:]) or None
    sys.exit(main(sys.argv[1], sys.argv[2], chi))
