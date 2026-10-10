# -*- coding: utf-8 -*-
"""Rút và thay chuỗi giao diện tiếng Việt → tiếng Anh cho bản bàn giao.

Vì sao làm ở công cụ chuyển bản, không sửa nguồn:
  Nguồn Odoo 19 của BSD phục vụ khách Việt, chuỗi viết thẳng tiếng Việt
  là đúng cho họ. Đối tác lại theo chuẩn Odoo — chuỗi trong mã bằng
  tiếng Anh, tiếng Việt nằm ở tệp dịch. Hai yêu cầu đó không chọi nhau
  nếu việc đổi ngôn ngữ nằm ở BƯỚC SINH BẢN: nguồn giữ tiếng Việt, bản
  giao ra tiếng Anh + i18n/vi_VN.po dựng ngược từ chính chuỗi gốc.

  Nhờ vậy không ai phải bảo trì hai bản chuỗi bằng tay, và mỗi lần phát
  hành lại sinh lại từ đầu nên không trôi.

Nguyên tắc:
  - CHỈ rút thứ người dùng đọc: nhãn trường, trợ giúp, nhãn lựa chọn,
    câu báo lỗi, chữ trong khung cảnh báo của biểu mẫu, tên thực đơn /
    hành động / bộ lọc.
  - KHÔNG đụng chú thích trong mã, docstring, tên kỹ thuật (xmlid, tên
    trường, mã lựa chọn), hay chuỗi kỹ thuật (domain, context, eval).
  - Module nào đã khai là ĐÃ DỊCH thì phải phủ 100%: thiếu một chuỗi
    là công cụ dừng. Bản giao nửa Anh nửa Việt còn tệ hơn giữ nguyên.
"""
import ast
import io
import os
import re

from lxml import etree
from xml.sax.saxutils import escape as xml_escape

VIET = re.compile(
    '[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợ'
    'ùúủũụưừứửữựỳýỷỹỵđÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊ'
    'ÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴĐ]')

PLACEHOLDER = re.compile(r'%(?:\([a-zA-Z_0-9]+\))?[sdfr]|%%|\{[a-zA-Z_0-9]*\}')

# Thẻ trình bày: chữ nằm trong đây là chữ người dùng đọc.
TEXT_TAGS = {
    'div', 'p', 'span', 'b', 'i', 'em', 'strong', 'small', 'li', 'ul',
    'ol', 'td', 'th', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'label',
    'separator', 'a', 'u', 'br', 'blockquote', 'code',
}
# Trường của bản ghi dữ liệu mà NỘI DUNG là chữ người đọc.
TEXT_FIELDS = {
    'name', 'string', 'help', 'subject', 'description', 'summary',
    'note', 'body_html', 'legend', 'message',
}
ATTRS = ('string', 'confirm', 'placeholder', 'title', 'help', 'sum',
         'avg', 'data-tooltip', 'label')

SKIP_DIRS = {'__pycache__', 'i18n', 'static', 'migrations', 'tests'}


def is_user_text(s):
    s = (s or '').strip()
    return bool(s) and len(s) >= 2 and bool(VIET.search(s))


def placeholders(s):
    return sorted(PLACEHOLDER.findall(s or ''))


# ----------------------------------------------------------------------
# Python
# ----------------------------------------------------------------------
_LIT = r"(?:[ruRU]?'(?:[^'\\]|\\.)*'|[ruRU]?\"(?:[^\"\\]|\\.)*\")"
_CHAIN = r"(%s(?:\s*\+?\s*%s)*)" % (_LIT, _LIT)

PY_KW = re.compile(
    r"\b(?:string|help|placeholder|title|confirm)\s*=\s*" + _CHAIN, re.S)
PY_GETTEXT = re.compile(r"_\(\s*" + _CHAIN, re.S)
PY_DESC = re.compile(r"\b_description\s*=\s*" + _CHAIN, re.S)
PY_SELECTION = re.compile(
    r"\(\s*'[a-z0-9_]+'\s*,\s*" + _CHAIN + r"\s*\)", re.S)
STR_PIECE = re.compile(r"[ruRU]?('(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\")",
                       re.S)


def _join(raw):
    """Gộp chuỗi nối nhiều mảnh thành GIÁ TRỊ THẬT của python.

    Phải giải mã escape (\\n, \\', \\\\) chứ không cắt dấu nháy suông:
    chuỗi trong mã viết '...\\n' thì giá trị thật là một dòng mới, và
    từ điển dịch khớp theo giá trị thật. Cắt suông là hai chỗ lệch
    nhau một ký tự, tra từ điển trượt mà không ai biết vì sao.
    """
    out = []
    for m in STR_PIECE.finditer(raw):
        piece = m.group(1)
        try:
            out.append(ast.literal_eval(piece))
        except (ValueError, SyntaxError):
            out.append(piece[1:-1])
    return ''.join(out)


def py_items(text):
    """[(raw_literal_chain, giá_trị)] — raw dùng để thay đúng chỗ."""
    seen = []
    for rx in (PY_KW, PY_GETTEXT, PY_DESC, PY_SELECTION):
        for m in rx.finditer(text):
            raw = m.group(1)
            val = _join(raw)
            if is_user_text(val):
                seen.append((raw, val))
    return seen


def py_apply(text, mapping, missing):
    """Thay chuỗi trong .py. Trả về (text_mới, số_chỗ_đã_thay)."""
    n = [0]

    def repl_chain(raw):
        val = _join(raw)
        if not is_user_text(val):
            return raw
        en = mapping.get(val)
        if en is None:
            missing.add(val)
            return raw
        n[0] += 1
        return _py_literal(en)

    def sub_rx(rx, s, group=1):
        out = []
        last = 0
        for m in rx.finditer(s):
            out.append(s[last:m.start(group)])
            out.append(repl_chain(m.group(group)))
            last = m.end(group)
        out.append(s[last:])
        return ''.join(out)

    for rx in (PY_KW, PY_GETTEXT, PY_DESC, PY_SELECTION):
        text = sub_rx(rx, text)
    return text, n[0]


def _py_literal(s):
    """Chuỗi python một dòng, giữ nguyên \\n và dấu nháy."""
    body = s.replace('\\', '\\\\').replace("'", "\\'")
    body = body.replace('\n', '\\n')
    return "'%s'" % body


# ----------------------------------------------------------------------
# XML
# ----------------------------------------------------------------------
def _walk_text(el, out):
    tag = el.tag if isinstance(el.tag, str) else ''
    if tag == 'field':
        fname = el.get('name')
        if (fname in TEXT_FIELDS and el.get('type') is None
                and len(el) == 0 and is_user_text(el.text)):
            out.append(('text', ' '.join(el.text.split())))
    elif tag in TEXT_TAGS:
        if is_user_text(el.text):
            out.append(('text', ' '.join(el.text.split())))
    if tag in TEXT_TAGS or (el.getparent() is not None
                            and el.getparent().tag in TEXT_TAGS):
        if is_user_text(el.tail):
            out.append(('text', ' '.join(el.tail.split())))
    for child in el:
        _walk_text(child, out)


def xml_items(text):
    """[(kiểu, giá_trị)] — kiểu ∈ {attr, text}."""
    items = []
    for m in re.finditer(
            r'\b(%s)="([^"]*)"' % '|'.join(ATTRS), text):
        if is_user_text(m.group(2)):
            items.append(('attr', m.group(2)))
    try:
        root = etree.fromstring(text.encode('utf-8'))
    except etree.XMLSyntaxError:
        return items
    _walk_text(root, items)
    return items


def xml_apply(text, mapping, missing):
    n = [0]

    def attr_repl(m):
        val = m.group(2)
        if not is_user_text(val):
            return m.group(0)
        en = mapping.get(val)
        if en is None:
            missing.add(val)
            return m.group(0)
        n[0] += 1
        return '%s="%s"' % (m.group(1), en.replace('"', '&quot;'))

    text = re.sub(r'\b(%s)="([^"]*)"' % '|'.join(ATTRS), attr_repl, text)

    # Chữ trần giữa hai thẻ. PHẢI neo vào dấu > và < của chính nút đó:
    # nhãn ngắn ("mục đích") mà thay tự do giữa tệp thì nó ăn luôn vào
    # giữa các câu dài, câu dài hỏng khoá nên tra từ điển trượt — và
    # tệ hơn là trượt im lặng, vì chuỗi gốc đã bị sửa mất.
    # Thay chuỗi DÀI trước, ngắn sau, cho cùng một lý do.
    vals = sorted({v for k, v in xml_items(text) if k == 'text'},
                  key=len, reverse=True)
    for val in vals:
        en = mapping.get(val)
        if en is None:
            missing.add(val)
            continue
        # Nguyên văn trong tệp còn ở dạng thực thể (&amp;), còn giá trị
        # lxml trả về đã giải mã (&). Tìm theo bản ĐÃ MÃ HOÁ LẠI, không
        # thì chuỗi nào có dấu & sẽ không bao giờ khớp — và im lặng.
        raw = xml_escape(val)
        body = r'\s+'.join(re.escape(w) for w in raw.split())
        pat = re.compile(r'(>\s*)%s(\s*<)' % body)
        en_raw = xml_escape(en)
        text, k = pat.subn(lambda m: m.group(1) + en_raw + m.group(2), text)
        n[0] += k
    return text, n[0]


# ----------------------------------------------------------------------
# Quét / áp dụng cả module
# ----------------------------------------------------------------------
def scan(root, modules):
    hits = {}
    for mod in modules:
        for dp, dn, fn in os.walk(os.path.join(root, mod)):
            dn[:] = [d for d in dn if d not in SKIP_DIRS]
            for f in sorted(fn):
                p = os.path.join(dp, f)
                rel = os.path.relpath(p, root)
                if f.endswith('.py'):
                    items = [v for _, v in
                             py_items(io.open(p, encoding='utf-8').read())]
                elif f.endswith('.xml'):
                    items = [v for _, v in
                             xml_items(io.open(p, encoding='utf-8').read())]
                else:
                    continue
                for v in items:
                    hits.setdefault(v, []).append(rel)
    return hits


def apply_module(root, mod, mapping):
    """Dịch một module tại chỗ. Trả về (số_chỗ_thay, thiếu, dùng)."""
    missing = set()
    used = {}
    total = 0
    for dp, dn, fn in os.walk(os.path.join(root, mod)):
        dn[:] = [d for d in dn if d not in SKIP_DIRS]
        for f in sorted(fn):
            p = os.path.join(dp, f)
            if f.endswith('.py'):
                s = io.open(p, encoding='utf-8').read()
                before = [v for _, v in py_items(s)]
                s2, k = py_apply(s, mapping, missing)
            elif f.endswith('.xml'):
                s = io.open(p, encoding='utf-8').read()
                before = [v for _, v in xml_items(s)]
                s2, k = xml_apply(s, mapping, missing)
            else:
                continue
            for v in before:
                if v in mapping:
                    used[mapping[v]] = v
            if s2 != s:
                io.open(p, 'w', encoding='utf-8').write(s2)
                total += k
    return total, missing, used


PO_HEADER = '''# Translation of Odoo Server.
# This file contains the translation of the following modules:
# \t* %(mod)s
#
msgid ""
msgstr ""
"Project-Id-Version: Odoo Server 17.0\\n"
"Report-Msgid-Bugs-To: \\n"
"PO-Revision-Date: 2026-01-01 00:00+0000\\n"
"Last-Translator: \\n"
"Language-Team: \\n"
"Language: vi\\n"
"MIME-Version: 1.0\\n"
"Content-Type: text/plain; charset=UTF-8\\n"
"Content-Transfer-Encoding: 8bit\\n"
"Plural-Forms: nplurals=1; plural=0;\\n"

'''


def _po_quote(s):
    s = (s.replace('\\', '\\\\').replace('"', '\\"')
          .replace('\n', '\\n'))
    return '"%s"' % s


def write_po(root, mod, pairs):
    """pairs: {english: vietnamese}."""
    d = os.path.join(root, mod, 'i18n')
    if not os.path.isdir(d):
        os.makedirs(d)
    out = [PO_HEADER % {'mod': mod}]
    for en in sorted(pairs):
        out.append('msgid %s\nmsgstr %s\n\n'
                   % (_po_quote(en), _po_quote(pairs[en])))
    io.open(os.path.join(d, 'vi_VN.po'), 'w',
            encoding='utf-8').write(''.join(out))
    return len(pairs)
