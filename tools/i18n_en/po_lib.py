# -*- coding: utf-8 -*-
"""Đọc/ghi .po cho việc dịch EAMOne sang tiếng Anh.

Khung .po PHẢI do chính Odoo xuất ra (`odoo i18n export`), không tự
viết: bộ nhập của Odoo dựa vào dòng tham chiếu `#: model:…` /
`model_terms:…` / `code:…` để biết bản dịch thuộc trường nào, view nào.
Tệp viết tay thiếu chúng thì hoặc nổ khi nạp, hoặc tệ hơn — nạp êm mà
không dịch được gì. Bài học này đã ghi sẵn trong tools/port17/fill_po.py.

Ở đây ta chỉ ĐIỀN msgstr, giữ nguyên từng dòng khác của khung.
"""
import io
import re

ESC = {'n': '\n', 't': '\t', 'r': '\r', '"': '"', '\\': '\\'}


def giai_ma(dong_list):
    """Gộp các dòng "…" của một khoá .po thành chuỗi thật."""
    ra = []
    for raw in dong_list:
        t = raw.strip()
        if not (t.startswith('"') and t.endswith('"')):
            continue
        b = t[1:-1]
        i = 0
        while i < len(b):
            c = b[i]
            if c == '\\' and i + 1 < len(b):
                ra.append(ESC.get(b[i + 1], b[i + 1]))
                i += 2
            else:
                ra.append(c)
                i += 1
    return ''.join(ra)


def ma_hoa(s):
    """Một chuỗi → các dòng msgstr của .po, ngắt theo \\n cho dễ đọc."""
    def q(x):
        return '"%s"' % (x.replace('\\', '\\\\').replace('"', '\\"')
                         .replace('\t', '\\t').replace('\n', '\\n'))
    if '\n' not in s:
        return [q(s)]
    phan = s.split('\n')
    ra = ['""']
    for i, p in enumerate(phan):
        ra.append(q(p + ('\n' if i < len(phan) - 1 else '')))
    return ra


def doc_muc(duong):
    """Trả về danh sách mục: {'msgid': str, 'msgstr': str, 'tham_chieu': [..]}

    Giữ nguyên thứ tự xuất hiện; mục đầu (header, msgid rỗng) bỏ qua.
    """
    muc = []
    hien = None
    che_do = None
    for dong in io.open(duong, encoding='utf-8'):
        t = dong.rstrip('\n')
        if t.startswith('#'):
            if hien is None:
                hien = {'tham_chieu': [], 'msgid': [], 'msgstr': []}
            hien['tham_chieu'].append(t)
            che_do = None
        elif t.startswith('msgid '):
            if hien is None:
                hien = {'tham_chieu': [], 'msgid': [], 'msgstr': []}
            hien['msgid'].append(t[6:])
            che_do = 'msgid'
        elif t.startswith('msgstr '):
            hien['msgstr'].append(t[7:])
            che_do = 'msgstr'
        elif t.startswith('"') and hien is not None and che_do:
            hien[che_do].append(t)
        elif not t.strip():
            if hien and hien['msgid']:
                muc.append({
                    'tham_chieu': hien['tham_chieu'],
                    'msgid': giai_ma(hien['msgid']),
                    'msgstr': giai_ma(hien['msgstr']),
                })
            hien = None
            che_do = None
    if hien and hien['msgid']:
        muc.append({'tham_chieu': hien['tham_chieu'],
                    'msgid': giai_ma(hien['msgid']),
                    'msgstr': giai_ma(hien['msgstr'])})
    return [m for m in muc if m['msgid']]


def module_cua(muc):
    """Module sở hữu mục, đọc từ dòng `#. module: xxx`."""
    for d in muc['tham_chieu']:
        g = re.match(r'#\.\s*module:\s*(\S+)', d)
        if g:
            return g.group(1)
    return None


PO_HEADER = '''# Translation of Odoo Server.
# This file contains the translation of the following modules:
# \t* %(mod)s
#
msgid ""
msgstr ""
"Project-Id-Version: Odoo Server 19.0\\n"
"Report-Msgid-Bugs-To: \\n"
"POT-Creation-Date: 2026-10-26 00:00+0000\\n"
"PO-Revision-Date: 2026-10-26 00:00+0000\\n"
"Last-Translator: \\n"
"Language-Team: \\n"
"Language: en_GB\\n"
"MIME-Version: 1.0\\n"
"Content-Type: text/plain; charset=UTF-8\\n"
"Content-Transfer-Encoding: 8bit\\n"
"Plural-Forms: nplurals=2; plural=(n != 1);\\n"

'''


def ghi_po(duong, mod, muc_list):
    """Ghi một tệp .po cho MỘT module, chỉ gồm mục đã có bản dịch."""
    ra = [PO_HEADER % {'mod': mod}]
    for m in muc_list:
        if not m['msgstr']:
            continue
        ra.append('\n'.join(m['tham_chieu']) + '\n')
        ra.append('msgid ' + '\n'.join(ma_hoa(m['msgid'])) + '\n')
        ra.append('msgstr ' + '\n'.join(ma_hoa(m['msgstr'])) + '\n\n')
    io.open(duong, 'w', encoding='utf-8').write(''.join(ra))
    return sum(1 for m in muc_list if m['msgstr'])
