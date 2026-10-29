# -*- coding: utf-8 -*-
"""Vá dấu `#. odoo-javascript` / `#. odoo-python` còn thiếu trong .po.

LỖI ĐÃ XẢY RA: bộ sinh .po của đợt dịch hàng loạt ghi đủ dòng tham
chiếu `#: code:addons/<mod>/...` nhưng KHÔNG ghi dòng dấu
`#. odoo-javascript` / `#. odoo-python` đứng trước nó.

Vì sao điều đó làm hỏng im lặng: Odoo nạp bản dịch mã nguồn qua
`CodeTranslations._read_code_translations_file`, và bộ lọc ở đó là

    JAVASCRIPT_TRANSLATION_COMMENT in row['comments']

tức nó chỉ nhận mục CÓ dòng dấu. Thiếu dấu thì tệp vẫn nạp "thành
công", `i18n import` vẫn báo *translations are loaded successfully*,
mà `get_web_translations()` trả về RỖNG. Không một thông báo lỗi nào.

Đây là kiểu hỏng đắt nhất: công dịch đã bỏ ra đủ, tệp nằm đúng chỗ,
lệnh nạp báo xanh — chỉ có màn hình là vẫn tiếng Việt.

Cách vá: với mỗi mục có tham chiếu `#: code:`, chèn dấu tương ứng ngay
sau dòng `#. module:`. Tệp nằm dưới `static/src` là javascript, còn
lại là python; mục có cả hai thì ghi cả hai dấu, đúng như Odoo tự xuất.
"""
import os
import sys

import po_lib as P

REPOS = [
    '/Users/bsd/projects/realtypro-cnbuild/addons',
    '/Users/bsd/projects/realtypro-enterprise/addons',
]


def va_mot_tep(po):
    muc = P.doc_muc(po)
    if not muc:
        return 0, 0
    mod = os.path.basename(os.path.dirname(os.path.dirname(po)))
    sua = 0
    for m in muc:
        tc = m['tham_chieu']
        if any(d.startswith('#. odoo-') for d in tc):
            continue
        code = [d for d in tc if d.startswith('#: code:')]
        if not code:
            continue
        dau = []
        if any('/static/src/' in d for d in code):
            dau.append('#. odoo-javascript')
        if any('/static/src/' not in d for d in code):
            dau.append('#. odoo-python')
        # Chèn ngay sau dòng `#. module:` để trùng thứ tự Odoo tự xuất.
        i = next((k for k, d in enumerate(tc)
                  if d.startswith('#. module:')), -1)
        m['tham_chieu'] = tc[:i + 1] + dau + tc[i + 1:]
        sua += 1
    if sua:
        P.ghi_po(po, mod, muc)
    return sua, len(muc)


def main(chi_xem=False):
    tong_tep = tong_muc = 0
    for goc in REPOS:
        for nhom in sorted(os.listdir(goc)):
            d1 = os.path.join(goc, nhom)
            if not os.path.isdir(d1):
                continue
            for mod in sorted(os.listdir(d1)):
                po = os.path.join(d1, mod, 'i18n', 'en_GB.po')
                if not os.path.isfile(po):
                    continue
                if chi_xem:
                    muc = P.doc_muc(po)
                    n = sum(1 for m in muc
                            if any(d.startswith('#: code:') for d in m['tham_chieu'])
                            and not any(d.startswith('#. odoo-') for d in m['tham_chieu']))
                else:
                    n, _ = va_mot_tep(po)
                if n:
                    print('   %-28s %4d mục' % (mod, n))
                    tong_tep += 1
                    tong_muc += n
    print('\n%s %d mục trong %d tệp'
          % ('CẦN vá' if chi_xem else 'ĐÃ vá', tong_muc, tong_tep))


if __name__ == '__main__':
    main(chi_xem='--xem' in sys.argv)
