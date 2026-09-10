#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Chuyển bộ Vay/Bảo lãnh/Thuê từ Odoo 19 sang Odoo 17.

DÙNG ĐỂ LÀM GÌ
--------------
Nhánh 19 là sản phẩm BSD phát triển tiếp; nhánh 17 là bản bàn giao cho
đối tác. Dòng chảy đã chốt là MỘT CHIỀU 19 → 17: sửa trên 19 trước, rồi
port xuống. Nếu port bằng tay thì sau vài tháng hai nhánh thành hai sản
phẩm khác nhau. Script này giữ cho việc port là một THAO TÁC LẶP LẠI
ĐƯỢC: chạy lại trên mã 19 mới nhất là ra nhánh 17 mới.

    python3 tools/port17/port_to_17.py <thư mục _common nguồn> <thư mục đích>

Script CHỈ ĐỌC thư mục nguồn; thư mục đích bị xoá và dựng lại.

NHỮNG GÌ ODOO 17 KHÁC 19 (theo thứ tự gặp phải khi cài thật)
-----------------------------------------------------------
 1. manifest phải bắt đầu bằng '17.0.' — và TÊN THƯ MỤC migration phải
    đổi theo, không thì migration không chạy.
 2. <list> → <tree>
 3. <chatter/> → khối oe_chatter. Chỉ chèn activity_ids cho model có
    mail.activity.mixin, không thì view chết.
 4. models.Constraint (khai báo, Odoo 19) → _sql_constraints
 5. aggregator= → group_operator=
 6. res.groups.privilege KHÔNG tồn tại; privilege_id → category_id,
    user_ids → users, res.groups không có sequence.
 7. Odoo 17 bắt mọi field dùng trong invisible/readonly/required/
    context/domain phải được KHAI TRONG CHÍNH PHẠM VI VIEW đó (form cha
    và lưới lồng tính riêng).
 8. view_mode 'list' → 'tree' (cả XML lẫn Python).
 9. res.users.group_ids → groups_id
10. Một số chỗ lẻ: xem PATCHES_LE cuối file.
"""
import ast
import io
import keyword
import os
import re
import shutil
import sys
import xml.etree.ElementTree as ET

ISLAND = [
    're_loan', 're_guarantee', 're_loan_account', 're_lease',
    're_bank_sync', 're_lease_loan_bridge', 're_loan_dashboard',
    're_loan_menu_reorg', 're_base', 're_party', 're_integration_hub',
    'vn_administrative_units',
]

MOD_ATTRS = ('invisible', 'readonly', 'required', 'column_invisible',
             'context', 'domain')
SCOPE_TAGS = {'form', 'tree', 'kanban', 'search', 'calendar'}
IDENT = re.compile(r'\b([a-z_][a-z0-9_]*)\b')
# Tên KHÔNG phải field: từ khoá python, biến ngữ cảnh Odoo, và tham số
# của relativedelta (days=, months=… trông y hệt tên field sau khi bóc
# chuỗi ra khỏi biểu thức).
NOT_FIELDS = {
    'True', 'False', 'None', 'and', 'or', 'not', 'in', 'is', 'if', 'else',
    'context', 'uid', 'parent', 'id', 'active_id', 'today', 'now', 'get',
    'context_today', 'datetime', 'time', 'relativedelta', 'len', 'set',
    'strftime', 'days', 'months', 'years', 'weeks', 'hours', 'minutes',
    'seconds', 'value',
}
RECORD_RE = re.compile(
    r'<record\b[^>]*\bid="(?P<rid>[^"]+)"[^>]*>.*?</record>', re.S)
OPEN_TAG_RE = re.compile(
    r'<(form|tree|kanban|search|calendar)\b[^>]*?>')

log = []


def note(msg):
    log.append(msg)
    print(msg)


# ----------------------------------------------------------------------
def walk_files(root, ext):
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d != '__pycache__']
        for f in sorted(fn):
            if f.endswith(ext):
                yield os.path.join(dp, f)


def sub_in_files(root, ext, pairs, label):
    n = 0
    for p in walk_files(root, ext):
        s = io.open(p, encoding='utf-8').read()
        o = s
        for a, b in pairs:
            s = s.replace(a, b) if isinstance(a, str) else a.sub(b, s)
        if s != o:
            io.open(p, 'w', encoding='utf-8').write(s)
            n += 1
    note('  %-46s %s file' % (label, n))


# ----------------------------------------------------------------------
def step_copy(src, dst):
    if os.path.exists(dst):
        shutil.rmtree(dst)
    os.makedirs(dst)
    for m in ISLAND:
        s = os.path.join(src, m)
        if not os.path.isdir(s):
            raise SystemExit('Không thấy module %s trong %s' % (m, src))
        shutil.copytree(s, os.path.join(dst, m),
                        ignore=shutil.ignore_patterns('__pycache__'))
    note('  chép %s module' % len(ISLAND))


def step_version(dst):
    n = 0
    for p in walk_files(dst, '__manifest__.py'):
        s = io.open(p, encoding='utf-8').read()
        s2 = re.sub(r"('version'\s*:\s*')19\.0\.", r"\g<1>17.0.", s)
        if s2 != s:
            io.open(p, 'w', encoding='utf-8').write(s2)
            n += 1
    note('  %-46s %s manifest' % ('version 19.0.* -> 17.0.*', n))
    k = 0
    for dp, dn, _fn in os.walk(dst):
        for d in list(dn):
            if os.path.basename(dp) == 'migrations' and d.startswith('19.0.'):
                os.rename(os.path.join(dp, d),
                          os.path.join(dp, '17.0.' + d[5:]))
                k += 1
    note('  %-46s %s thư mục' % ('đổi tên migrations/19.0.* -> 17.0.*', k))


def step_list_tag(dst):
    sub_in_files(dst, '.xml', [
        (re.compile(r'<list(\s|>)'), r'<tree\1'),
        ('</list>', '</tree>'),
    ], '<list> -> <tree>')


def activity_models(dst):
    """Model nào có mail.activity.mixin — để biết chatter có activity."""
    out = set()
    pat_name = re.compile(r"_name\s*=\s*['\"]([\w.]+)['\"]")
    for p in walk_files(dst, '.py'):
        s = io.open(p, encoding='utf-8').read()
        if 'mail.activity.mixin' not in s:
            continue
        for blk in re.split(r'\nclass ', s):
            if 'mail.activity.mixin' in blk:
                m = pat_name.search(blk)
                if m:
                    out.add(m.group(1))
    return out


def step_xpath_list(dst):
    """Biểu thức xpath trỏ tới phần tử `list` cũng phải đổi sang `tree`.

    Đổi thẻ <list> mà quên đổi xpath thì view kế thừa không tìm thấy
    điểm neo và Odoo báo lỗi nạp — không phải lỗi cú pháp nên
    kiểm cú pháp không bắt được.
    """
    n = 0
    for p in walk_files(dst, '.xml'):
        s = io.open(p, encoding='utf-8').read()
        if 'expr=' not in s:
            continue

        def fix_expr(m):
            v = re.sub(r'(?<=/)list\b', 'tree', m.group(1))
            v = re.sub(r'^list\b', 'tree', v)
            return 'expr="%s"' % v

        s2 = re.sub(r'expr="([^"]*)"', fix_expr, s)
        if s2 != s:
            io.open(p, 'w', encoding='utf-8').write(s2)
            n += 1
    note('  %-46s %s file' % ('xpath //list -> //tree', n))


def step_chatter(dst):
    acts = activity_models(dst)
    note('  %-46s %s model' % ('model có mail.activity.mixin', len(acts)))
    n = 0
    for p in walk_files(dst, '.xml'):
        s = io.open(p, encoding='utf-8').read()
        if '<chatter/>' not in s and '<chatter />' not in s:
            continue

        def repl_record(m):
            blk = m.group(0)
            mm = re.search(r'<field name="model">([\w.]+)</field>', blk)
            model = mm.group(1) if mm else ''
            parts = ['<field name="message_follower_ids"/>']
            if model in acts:
                parts.append('<field name="activity_ids"/>')
            parts.append('<field name="message_ids"/>')
            block = ('<div class="oe_chatter">%s</div>' % ''.join(parts))
            return re.sub(r'<chatter\s*/>', block, blk)

        s2 = RECORD_RE.sub(repl_record, s)
        if s2 != s:
            io.open(p, 'w', encoding='utf-8').write(s2)
            n += 1
    note('  %-46s %s file' % ('<chatter/> -> oe_chatter', n))


def step_company_groups(dst):
    """Field bị khoá theo nhóm quyền không dùng được trong domain (17).

    Odoo khai sẵn domain cho journal_id/account_id tham chiếu tới
    company_id. Nếu view chỉ khai company_id kèm
    groups="base.group_multi_company" thì Odoo 17 từ chối nạp view:
    người ngoài nhóm đó không có field để mà tính domain.

    Cách xử đã có sẵn trong chính codebase (xem chú thích ở
    re_loan_credit_contract_views.xml về currency_id): thêm một bản sao
    VÔ ĐIỀU KIỆN, ẩn đi. Bản có groups vẫn giữ để hiển thị.
    """
    n = 0
    for p in walk_files(dst, '.xml'):
        s = io.open(p, encoding='utf-8').read()
        if 'company_id' not in s or 'groups=' not in s:
            continue

        def fix_record(m):
            blk = m.group(0)
            if 'name="company_id"' not in blk:
                return blk
            # đã có bản không giới hạn nhóm thì thôi
            for fm in re.finditer(r'<field\s+name="company_id"[^>]*/?>', blk):
                if 'groups=' not in fm.group(0):
                    return blk
            gm = re.search(r'(\s*)<field\s+name="company_id"[^>]*groups=[^>]*>',
                           blk)
            if not gm:
                return blk
            ind = gm.group(1)
            twin = '%s<field name="company_id" invisible="1"/>' % ind
            return blk[:gm.start()] + twin + blk[gm.start():]

        s2 = RECORD_RE.sub(fix_record, s)
        if s2 != s:
            io.open(p, 'w', encoding='utf-8').write(s2)
            n += 1
    note('  %-46s %s file' % ('company_id: thêm bản sao vô điều kiện', n))


def step_constraints(dst):
    pat = re.compile(
        r'^(?P<ind>[ \t]+)_(?P<name>\w+)\s*=\s*models\.Constraint\('
        r'\s*(?P<body>.*?)\)\s*$', re.S | re.M)
    n = 0
    for p in walk_files(dst, '.py'):
        s = io.open(p, encoding='utf-8').read()
        if 'models.Constraint' not in s:
            continue
        out, pos = [], 0
        for m in pat.finditer(s):
            ind, name = m.group('ind'), m.group('name')
            body = m.group('body').strip()
            out.append(s[pos:m.start()])
            out.append('%s_sql_constraints = [\n%s    (%r, %s),\n%s]'
                       % (ind, ind, name, body, ind))
            pos = m.end()
        out.append(s[pos:])
        io.open(p, 'w', encoding='utf-8').write(''.join(out))
        n += 1
    note('  %-46s %s file' % ('models.Constraint -> _sql_constraints', n))


def step_misc_py(dst):
    sub_in_files(dst, '.py', [
        ('aggregator=', 'group_operator='),
        ("'group_ids'", "'groups_id'"),
        ('.group_ids', '.groups_id'),
        ("'view_mode': 'list", "'view_mode': 'tree"),
        ('"view_mode": "list', '"view_mode": "tree'),
    ], 'aggregator / group_ids / view_mode (py)')


def step_view_mode_xml(dst):
    sub_in_files(dst, '.xml', [
        (re.compile(r'(<field name="view_mode">)([^<]*)list([^<]*)(</field>)'),
         r'\1\2tree\3\4'),
        (re.compile(r"('view_mode':\s*)'list'"), r"\1'tree'"),
    ], "view_mode 'list' -> 'tree' (xml)")


def step_security(dst):
    n = 0
    for p in walk_files(dst, '.xml'):
        s = io.open(p, encoding='utf-8').read()
        if 'res.groups' not in s and 'privilege' not in s:
            continue
        o = s
        privmap = {}
        for m in re.finditer(
                r'<record id="(?P<pid>[\w.]+)" model="res\.groups\.privilege">'
                r'(?P<body>.*?)</record>\s*', s, re.S):
            cm = re.search(r'<field name="category_id" ref="([\w.]+)"/>',
                           m.group('body'))
            privmap[m.group('pid')] = cm.group(1) if cm else None
        for pid in privmap:
            s = re.sub(
                r'\s*<record id="%s" model="res\.groups\.privilege">.*?'
                r'</record>' % re.escape(pid), '', s, flags=re.S)

        def to_category(m):
            ref = m.group(1)
            cat = privmap.get(ref) or privmap.get(ref.split('.')[-1])
            return '<field name="category_id" ref="%s"/>' % (cat or ref)

        s = re.sub(r'<field name="privilege_id" ref="([\w.]+)"/>',
                   to_category, s)
        s = re.sub(r'<field name="user_ids"(\s+eval=)',
                   r'<field name="users"\1', s)
        s = re.sub(
            r'(<record[^>]*model="res\.groups">.*?</record>)',
            lambda m: re.sub(r'\s*<field name="sequence">[^<]*</field>',
                             '', m.group(1)),
            s, flags=re.S)
        if s != o:
            io.open(p, 'w', encoding='utf-8').write(s)
            n += 1
    note('  %-46s %s file' % ('privilege / user_ids / sequence', n))


# ----------------------------------------------------------------------
def scopes_in(root_el):
    """Các phạm vi view theo THỨ TỰ TÀI LIỆU: (thẻ gốc, phần tử của nó)."""
    out = []

    def walk(el, own):
        own.append(el)
        for ch in el:
            if ch.tag in SCOPE_TAGS:
                sub = []
                out.append((ch, sub))
                walk(ch, sub)
            else:
                walk(ch, own)

    first = []
    out.append((root_el, first))
    walk(root_el, first)
    return out


def fields_used(elements):
    used = set()
    for el in elements:
        for a in MOD_ATTRS:
            v = el.get(a)
            if not v or v in ('1', '0', 'True', 'False'):
                continue
            t = re.sub(r"'[^']*'", ' ', v)
            t = re.sub(r'"[^"]*"', ' ', t)
            t = re.sub(r'\w+\.\w+', ' ', t)      # parent.x, obj.attr
            for tok in IDENT.findall(t):
                if tok not in NOT_FIELDS and not keyword.iskeyword(tok):
                    used.add(tok)
    return used


def step_inject_fields(dst):
    """Khai bổ sung field dùng trong modifier — theo TỪNG phạm vi view.

    Bỏ qua view kế thừa: view cha có thể đã khai, và chèn vào giữa một
    xpath là hỏng cấu trúc. Những chỗ đó xử tay ở PATCHES_LE.
    """
    total = 0
    for p in walk_files(dst, '.xml'):
        try:
            tree = ET.parse(p)
        except ET.ParseError:
            continue
        need = {}
        for rec in tree.getroot().iter('record'):
            if rec.get('model') != 'ir.ui.view':
                continue
            if rec.find("./field[@name='inherit_id']") is not None:
                continue
            arch = rec.find("./field[@name='arch']")
            if arch is None or len(arch) == 0:
                continue
            per = []
            for sroot, els in scopes_in(list(arch)[0]):
                declared = {e.get('name') for e in els
                            if e.tag == 'field' and e.get('name')}
                per.append((sroot.tag,
                            sorted(fields_used(els) - declared)))
            if any(miss for _tag, miss in per):
                need[rec.get('id')] = per
        if not need:
            continue
        s = io.open(p, encoding='utf-8').read()
        out, pos = [], 0
        for m in RECORD_RE.finditer(s):
            rid = m.group('rid')
            if rid not in need:
                continue
            per, blk = need[rid], m.group(0)
            opens = list(OPEN_TAG_RE.finditer(blk))
            if len(opens) != len(per):
                note('  !! bỏ qua %s (phạm vi %s != thẻ %s)'
                     % (rid, len(per), len(opens)))
                continue
            newblk, last = '', 0
            for (tag, miss), om in zip(per, opens):
                if not miss:
                    continue
                attr = 'column_invisible' if tag == 'tree' else 'invisible'
                newblk += blk[last:om.end()] + ''.join(
                    '<field name="%s" %s="1"/>' % (x, attr) for x in miss)
                last = om.end()
                total += len(miss)
            newblk += blk[last:]
            out.append(s[pos:m.start()])
            out.append(newblk)
            pos = m.end()
        out.append(s[pos:])
        io.open(p, 'w', encoding='utf-8').write(''.join(out))
    note('  %-46s %s field' % ('khai bổ sung field trong modifier', total))


# ----------------------------------------------------------------------
# Các chỗ lẻ không quy về luật chung được. Mỗi mục ghi RÕ VÌ SAO, để lần
# sau chạy lại còn biết chỗ nào đã lỗi thời mà bỏ đi.
PATCHES_LE = [
    (
        're_loan_account/views/re_loan_facility_views.xml',
        '''            <xpath expr="//field[@name=\'note\']" position="before">
''',
        '''            <xpath expr="//field[@name=\'note\']" position="before">
                <field name="company_id" invisible="1"/>
''',
        'Odoo 17 bắt company_id phải có trong view vì domain của '
        'loan_journal_id (do chính Odoo khai) tham chiếu tới nó; '
        'view kế thừa nên bộ chèn tự động cố ý bỏ qua',
    ),
]


def step_patches_le(dst):
    n = 0
    for rel, old, new, why in PATCHES_LE:
        if old is None:
            continue
        p = os.path.join(dst, rel)
        if not os.path.exists(p):
            continue
        s = io.open(p, encoding='utf-8').read()
        if old in s:
            io.open(p, 'w', encoding='utf-8').write(s.replace(old, new, 1))
            n += 1
            note('    vá lẻ: %s (%s)' % (rel, why))
    note('  %-46s %s chỗ' % ('vá lẻ', n))


def step_check_syntax(dst):
    bad = 0
    for p in walk_files(dst, '.py'):
        try:
            ast.parse(io.open(p, encoding='utf-8').read())
        except SyntaxError as e:
            note('  !! lỗi cú pháp %s: %s' % (p.replace(dst, ''), e))
            bad += 1
    for p in walk_files(dst, '.xml'):
        try:
            ET.parse(p)
        except ET.ParseError as e:
            note('  !! lỗi XML %s: %s' % (p.replace(dst, ''), e))
            bad += 1
    note('  %-46s %s lỗi' % ('kiểm cú pháp', bad))
    return bad


def main():
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    src, dst = sys.argv[1], sys.argv[2]
    note('Port Odoo 19 -> 17')
    note('  nguồn: %s' % src)
    note('  đích : %s' % dst)
    step_copy(src, dst)
    step_version(dst)
    step_list_tag(dst)
    step_xpath_list(dst)
    step_chatter(dst)
    step_company_groups(dst)
    step_constraints(dst)
    step_misc_py(dst)
    step_view_mode_xml(dst)
    step_security(dst)
    step_inject_fields(dst)
    step_patches_le(dst)
    bad = step_check_syntax(dst)
    note('XONG' if not bad else 'XONG (còn %s lỗi cú pháp)' % bad)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
