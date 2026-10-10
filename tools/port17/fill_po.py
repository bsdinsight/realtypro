# -*- coding: utf-8 -*-
"""Điền bản dịch tiếng Việt vào khung .po do CHÍNH Odoo xuất ra.

Vì sao không tự sinh .po:
  Bộ nhập .po của Odoo đòi mỗi mục phải có chú thích `#. module: x` và
  dòng tham chiếu `#: model:…` / `model_terms:…` / `code:…` — chính
  các tham chiếu đó nói cho Odoo biết bản dịch thuộc trường nào, view
  nào. Tệp tự viết tay thiếu chúng thì hoặc Odoo nổ khi nạp, hoặc tệ
  hơn: nạp êm mà không dịch được gì.

  Nên khung .po phải do Odoo xuất ra (`--i18n-export`) trên bản ĐÃ
  dịch sang tiếng Anh; script này chỉ điền msgstr bằng tiếng Việt gốc,
  tra theo chính chuỗi tiếng Anh (msgid).

Dùng:
  python3 fill_po.py <thư mục khung .po> <thư mục bản 17>

Mỗi <mod>.po trong thư mục khung sẽ thành <bản 17>/<mod>/i18n/vi_VN.po.
"""
import csv
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DICT = os.path.join(HERE, 'i18n_data', 'vi_en.csv')

ESCAPES = {'n': '\n', 't': '\t', '"': '"', '\\': '\\'}


def po_decode(parts):
    """Gộp các dòng "…" của một khoá .po thành chuỗi thật."""
    out = []
    for raw in parts:
        body = raw.strip()
        if not (body.startswith('"') and body.endswith('"')):
            continue
        body = body[1:-1]
        i = 0
        while i < len(body):
            c = body[i]
            if c == '\\' and i + 1 < len(body):
                out.append(ESCAPES.get(body[i + 1], body[i + 1]))
                i += 2
            else:
                out.append(c)
                i += 1
    return ''.join(out)


def po_encode(key, value):
    """Viết `msgstr` một dòng, escape đúng kiểu .po."""
    body = (value.replace('\\', '\\\\').replace('"', '\\"')
            .replace('\n', '\\n').replace('\t', '\\t'))
    return '%s "%s"\n' % (key, body)


def fill(skel_text, en_to_vi, stats):
    out = []
    lines = skel_text.splitlines(True)
    i = 0
    first_entry_done = False
    while i < len(lines):
        line = lines[i]
        if not line.startswith('msgid '):
            out.append(line)
            i += 1
            continue
        # Khoá msgid + các dòng nối
        msgid_lines = [line[len('msgid '):]]
        j = i + 1
        while j < len(lines) and lines[j].startswith('"'):
            msgid_lines.append(lines[j])
            j += 1
        msgid = po_decode(msgid_lines)
        # msgstr + các dòng nối
        k = j
        if k < len(lines) and lines[k].startswith('msgstr '):
            k += 1
            while k < len(lines) and lines[k].startswith('"'):
                k += 1
        if not msgid:
            # Mục đầu tiên là phần đầu tệp — giữ nguyên.
            out.extend(lines[i:k])
            first_entry_done = True
            i = k
            continue
        vi = en_to_vi.get(msgid)
        out.extend(lines[i:j])
        if vi:
            out.append(po_encode('msgstr', vi))
            stats['filled'] += 1
        else:
            out.append('msgstr ""\n')
            stats['empty'].append(msgid)
        i = k
    assert first_entry_done, 'khung .po không có phần đầu tệp'
    return ''.join(out)


def main():
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    skel_dir, dst = sys.argv[1], sys.argv[2]
    en_to_vi = {}
    with io.open(DICT, encoding='utf-8') as f:
        for row in csv.DictReader(f):
            if row.get('en'):
                # Trùng tiếng Anh thì giữ bản dịch đầu — các chuỗi gốc
                # khác nhau mà ra cùng một câu tiếng Anh thì về tiếng
                # Việt chọn bản nào cũng đúng nghĩa.
                en_to_vi.setdefault(row['en'], row['vi'])
    total_filled = total_empty = 0
    for fn in sorted(os.listdir(skel_dir)):
        if not fn.endswith('.po'):
            continue
        mod = fn[:-3]
        mod_dir = os.path.join(dst, mod)
        if not os.path.isdir(mod_dir):
            continue
        stats = {'filled': 0, 'empty': []}
        text = io.open(os.path.join(skel_dir, fn), encoding='utf-8').read()
        filled = fill(text, en_to_vi, stats)
        if not stats['filled']:
            print('  %-24s bỏ qua (không có chuỗi nào dịch được)' % mod)
            continue
        d = os.path.join(mod_dir, 'i18n')
        if not os.path.isdir(d):
            os.makedirs(d)
        io.open(os.path.join(d, 'vi_VN.po'), 'w',
                encoding='utf-8').write(filled)
        total_filled += stats['filled']
        total_empty += len(stats['empty'])
        print('  %-24s %4d dịch / %4d để trống'
              % (mod, stats['filled'], len(stats['empty'])))
    print('TỔNG: %s mục có tiếng Việt, %s mục để trống (chuỗi vốn đã '
          'là tiếng Anh ở nguồn).' % (total_filled, total_empty))


if __name__ == '__main__':
    main()
