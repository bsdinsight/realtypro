# -*- coding: utf-8 -*-
"""Tách khung .po gộp thành từng module, và liệt kê chuỗi CẦN DỊCH.

Vì sao tự tách thay vì để Odoo xuất từng module: thư mục addons gắn
vào container ở chế độ CHỈ ĐỌC, `odoo i18n export` không ghi được vào
`<module>/i18n/`. Gọi Odoo 30 lượt với `-o` thì mỗi lượt dựng lại
registry mất ~20 giây. Trong khi chính dòng tham chiếu đã nói mục
thuộc module nào, nên tách được bằng tay mà vẫn ra đúng kết quả Odoo
sẽ ra.

Lọc ra chuỗi CẦN dịch: nhiều msgid trong khung VỐN ĐÃ là tiếng Anh —
chúng đến từ trường kế thừa của mail.thread ("Action Needed",
"Active", "Followers"). Dịch lại là thừa, mà tệ hơn là ghi đè bản dịch
sẵn có của Odoo lõi.
"""
import io
import json
import re
import sys

import po_lib as P

VIET = re.compile(
    '[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợ'
    'ùúủũụưừứửữựỳýỷỹỵđÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊ'
    'ÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴĐ]')

# Dòng tham chiếu: lấy tên module đứng trước dấu chấm của xmlid, hoặc
# đoạn sau `addons/` với tham chiếu mã nguồn.
RE_XMLID = re.compile(r'#:\s*\S+:([a-z0-9_]+)\.')
RE_CODE = re.compile(r'#:\s*code:addons/([a-z0-9_]+)/')


def module_cua_ref(dong):
    g = RE_CODE.match(dong) or RE_XMLID.match(dong)
    return g.group(1) if g else None


def main(duong_po, ra_json, ra_txt):
    muc = P.doc_muc(duong_po)
    theo_mod = {}
    for m in muc:
        nhom = {}
        for d in m['tham_chieu']:
            if not d.startswith('#:'):
                continue
            mod = module_cua_ref(d)
            if mod:
                nhom.setdefault(mod, []).append(d)
        for mod, refs in nhom.items():
            theo_mod.setdefault(mod, []).append({
                'msgid': m['msgid'],
                'refs': refs,
            })

    can_dich = {}
    da_anh = 0
    for mod, ms in theo_mod.items():
        for e in ms:
            if VIET.search(e['msgid']):
                can_dich.setdefault(e['msgid'], set()).add(mod)
            else:
                da_anh += 1

    print('module có chuỗi: %d' % len(theo_mod))
    print('mục (tính cả trùng giữa module): %d' % sum(
        len(v) for v in theo_mod.values()))
    print('msgid VỐN ĐÃ tiếng Anh (bỏ qua): %d' % da_anh)
    print('msgid CẦN DỊCH: %d — %d ký tự'
          % (len(can_dich), sum(len(k) for k in can_dich)))

    json.dump({k: sorted(v) for k, v in can_dich.items()},
              io.open(ra_json, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=0)

    # Danh sách để dịch: gom theo module chính, ngắn trước dài sau, để
    # dịch nhãn cùng một màn hình liền mạch — thuật ngữ mới nhất quán.
    nhom_mod = {}
    for s, mods in can_dich.items():
        nhom_mod.setdefault(sorted(mods)[0], []).append(s)
    with io.open(ra_txt, 'w', encoding='utf-8') as f:
        for mod in sorted(nhom_mod):
            ds = sorted(nhom_mod[mod], key=lambda x: (len(x), x))
            f.write('\n### %s (%d)\n' % (mod, len(ds)))
            for s in ds:
                f.write('%s\n' % s.replace('\n', '\\n'))
    print('\nđã ghi %s và %s' % (ra_json, ra_txt))
    for mod in sorted(nhom_mod, key=lambda m: -len(nhom_mod[m]))[:12]:
        print('   %-24s %4d' % (mod, len(nhom_mod[mod])))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], sys.argv[3])
