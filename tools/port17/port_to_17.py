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

    python3 tools/port17/port_to_17.py <thư mục _common nguồn> <thư mục đích> \
        [--prev <thư mục addons của bản đã giao lần trước>]

Luôn truyền --prev khi sinh bản giao: script dừng nếu có module đổi mã
mà không tăng phiên bản (bên nhận sẽ bỏ sót nó khi nâng cấp).
Và sinh từ COMMIT, không từ thư mục làm việc:
    git archive HEAD addons/_common | tar -x -C /tmp/src19_head

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
10. account.payment: `memo` (Odoo 18+) vốn tên là `ref` ở 17. Sai
    khoá này KHÔNG lộ ở bước kiểm cú pháp — chỉ nổ lúc create.
11. Một số chỗ lẻ: xem PATCHES_LE cuối file.
12. File phải viết lại hẳn cho 17 (JS định dạng ngày): tools/port17/files17/.

Sau đó là HỒ SƠ ĐỐI TÁC (đối tác xb_partner, dự án project.project) —
khác biệt MÔI TRƯỜNG khách, không phải khác biệt phiên bản. Xem
PARTNER_EDITS và step_partner_project.
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


def step_account_payment_api(dst):
    """account.payment: `memo` (Odoo 18+) trở lại `ref` (Odoo 17).

    Odoo 18 đổi tên `account.payment.ref` thành `memo`. Trên 17 tạo
    phiếu chi với khoá `memo` thì nổ KeyError NGAY LÚC CREATE, không
    phải lỗi cú pháp nên `step_check_syntax` không bắt được — chỉ lộ
    ra khi chạy test hoặc khi người dùng bấm nút.

    Chỉ đổi khoá trong dict truyền vào create(), không đụng chữ "memo"
    ở chỗ khác.
    """
    sub_in_files(dst, '.py', [
        (re.compile(r"(\n\s*)'memo':"), r"\1'ref':"),
        (re.compile(r'(\n\s*)"memo":'), r'\1"ref":'),
    ], "account.payment: 'memo' -> 'ref'")


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


# ----------------------------------------------------------------------
# FILE RIÊNG CHO ODOO 17 — ghi đè NGUYÊN FILE từ tools/port17/files17/.
# Dùng khi khác biệt không vá được bằng thay chuỗi (viết lại cả logic).
#
#  - re_base/static/src/js/date_format_override.js: bản 19 vá
#    DateTimeField.defaultProps.numeric — prop này KHÔNG có ở Odoo 17,
#    OWL từ chối field và làm vỡ cả backend. Bản 17 vá cách hiển thị
#    (getFormattedValue). Do đối tác phát hiện và sửa trên repo của họ
#    (15/09/2026); bộ kiểm Python không bắt được lỗi JS này.
FILES17 = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'files17')


def step_files17(dst):
    n = 0
    for dp, _dn, fn in os.walk(FILES17):
        for f in fn:
            src = os.path.join(dp, f)
            rel = os.path.relpath(src, FILES17)
            if not os.path.isdir(os.path.join(dst, rel.split(os.sep)[0])):
                continue
            target = os.path.join(dst, rel)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copyfile(src, target)
            n += 1
    note('  %-46s %s file' % ('ghi đè file riêng Odoo 17', n))


# ----------------------------------------------------------------------
# HỒ SƠ TRIỂN KHAI CỦA ĐỐI TÁC (bản Odoo 17 bàn giao)
#
# Khác các bước trên (khác biệt PHIÊN BẢN Odoo), phần này là khác biệt
# MÔI TRƯỜNG của khách: khách chạy bộ module riêng của đối tác. Tách riêng để
# còn biết chỗ nào là "Odoo 17", chỗ nào là "nhà đối tác".
#
#  1. Đối tác: Đối tác thay re_party bằng xb_partner_extend (có is_bank,
#     parent_company_id, quan hệ đối tác) và vn_administrative_units bằng
#     xb_partner (res.country.ward, res.bank.partner_id). Danh mục ngân
#     hàng đã có sẵn ở môi trường của họ nên bỏ dữ liệu ngân hàng + demo
#     (demo tham chiếu re_party). Chép đúng theo sửa của đối tác ở PR #2.
#  2. Dự án: Khách quản lý dự án bằng Project của Odoo (project.project),
#     không dùng re.project của re_base. Mọi trường dự án trỏ sang
#     project.project (anh Đại chốt 19/09/2026).
#
# CHẶT: không tìm thấy đoạn cần thay là DỪNG. Nguồn 19 đổi mà bước này
# lặng lẽ bỏ qua thì bản giao sẽ đè mất sửa của đối tác — đúng thứ phần
# này sinh ra để tránh.
PARTNER_EDITS = [
    ('re_loan/__manifest__.py',
     "        'mail',\n        're_party',\n        're_base',",
     "        'mail',\n        'xb_partner_extend',\n        're_base',",
     're_party → xb_partner_extend'),
    ('re_loan/__manifest__.py',
     "        'data/re_loan_vn_banks_data.xml',\n",
     "        # data/re_loan_vn_banks_data.xml — bỏ ở bản đối tác: danh mục "
     "ngân hàng đã có từ xb_partner\n",
     'bỏ dữ liệu ngân hàng'),
    ('re_loan/__manifest__.py',
     re.compile(r"    'demo': \[\n(?:        '[^']+',\n)+    \],\n"),
     "    # demo — bỏ ở bản đối tác: dữ liệu mẫu tham chiếu re_party\n",
     'bỏ demo'),
    ('re_guarantee/__manifest__.py',
     "        'mail',\n        're_party',\n",
     "        'mail',\n",
     'bỏ phụ thuộc re_party'),
    ('re_loan/views/res_partner_views.xml',
     re.compile(r'    <!-- % phí KW theo NH.*?</record>', re.S),
     '''    <!-- Phí KW / thẩm định giá trên form đối tác xb_partner_extend. -->
    <record id="view_partner_form_re_loan_fee" model="ir.ui.view">
        <field name="name">res.partner.form.re.loan.fee</field>
        <field name="model">res.partner</field>
        <field name="inherit_id" ref="xb_partner_extend.view_partner_form_inherit"/>
        <field name="arch" type="xml">
            <xpath expr="//field[@name='is_bank']" position="after">
                <field name="kw_fee_rate" invisible="not is_bank"/>
                <field name="is_appraiser"/>
            </xpath>
        </field>
    </record>''',
     'form đối tác gắn vào xb_partner_extend'),
    ('re_base/__manifest__.py',
     "        'web',\n        'vn_administrative_units',\n",
     "        'web',\n        'xb_partner',\n",
     'vn_administrative_units → xb_partner'),
    ('re_base/__manifest__.py',
     "  Applied via JS patch on DateTimeField default props.",
     "  Applied via ``res.lang`` data and a DateTimeField display patch\n"
     "  (Odoo 17 has no ``numeric`` widget prop).",
     'mô tả định dạng ngày (bản 17)'),
    ('re_base/__manifest__.py',
     "``vn_administrative_units`` dependency",
     "``xb_partner`` dependency",
     'mô tả địa chỉ'),
    ('re_base/models/re_project.py',
     """        'vau.ward', string='Ward / Phường-Xã',
        domain="[('state_id', '=', state_id)]",""",
     """        'res.country.ward', string='Ward / Phường-Xã',
        domain="[('district_id.state_id', '=', state_id)]",""",
     'phường/xã theo xb_partner'),
    ('re_base/models/re_project.py',
     "            if project.ward_id and project.ward_id.state_id != project.state_id:",
     """            if (project.ward_id and project.state_id
                    and project.ward_id.district_id.state_id != project.state_id):""",
     'onchange phường/xã theo xb_partner'),
]

# Module có trường trỏ dự án — thêm phụ thuộc 'project' khi đổi sang
# project.project. re_base giữ nguyên: nó ĐỊNH NGHĨA re.project.
PROJECT_OWNER = 're_base'


def step_partner_profile(dst):
    n = 0
    for rel, old, new, why in PARTNER_EDITS:
        p = os.path.join(dst, rel)
        s = io.open(p, encoding='utf-8').read()
        if isinstance(old, str):
            if s.count(old) != 1:
                raise SystemExit(
                    'HỒ SƠ ĐỐI TÁC: không tìm thấy (hoặc thấy nhiều lần) '
                    'đoạn cần thay ở %s — %s. Nguồn 19 đã đổi: cập nhật '
                    'PARTNER_EDITS trước khi giao.' % (rel, why))
            s = s.replace(old, new)
        else:
            s, k = old.subn(new, s, count=1)
            if k != 1:
                raise SystemExit(
                    'HỒ SƠ ĐỐI TÁC: không khớp mẫu ở %s — %s.' % (rel, why))
        io.open(p, 'w', encoding='utf-8').write(s)
        n += 1
    note('  %-46s %s chỗ' % ('hồ sơ đối tác: đối tác / địa chỉ', n))


def step_partner_project(dst):
    fields_n = files_n = 0
    touched = set()
    for m in ISLAND:
        if m == PROJECT_OWNER:
            continue
        root = os.path.join(dst, m)
        for p in walk_files(root, '.py'):
            s = io.open(p, encoding='utf-8').read()
            o = s
            k = s.count("'re.project'")
            s = s.replace("'re.project'", "'project.project'")
            if '/tests/' in p:
                # project.project không có 'code' như re.project.
                s = re.sub(
                    r"(\['project\.project'\]\.create\(\{\s*'name':\s*"
                    r"'[^']*'),\s*'code':\s*'[^']*'", r"\1", s)
            if s != o:
                io.open(p, 'w', encoding='utf-8').write(s)
                fields_n += k
                files_n += 1
                touched.add(m)
        for p in walk_files(root, '.csv'):
            s = io.open(p, encoding='utf-8').read()
            s2 = s.replace('re_base.model_re_project',
                           'project.model_project_project')
            if s2 != s:
                io.open(p, 'w', encoding='utf-8').write(s2)
                files_n += 1
                touched.add(m)
    for m in sorted(touched):
        p = os.path.join(dst, m, '__manifest__.py')
        s = io.open(p, encoding='utf-8').read()
        if "'project'" in s:
            continue
        s2, k = re.subn(r"('depends'\s*:\s*\[\n)", r"\1        'project',\n",
                        s, count=1)
        if k != 1:
            raise SystemExit('HỒ SƠ ĐỐI TÁC: không thêm được depends '
                             'project cho %s' % m)
        io.open(p, 'w', encoding='utf-8').write(s2)
    if fields_n < 7:
        raise SystemExit('HỒ SƠ ĐỐI TÁC: chỉ đổi được %s chỗ re.project '
                         '(kỳ vọng ≥ 7) — kiểm lại nguồn.' % fields_n)
    note('  %-46s %s chỗ / %s file (%s)' % (
        'hồ sơ đối tác: dự án → project.project', fields_n, files_n,
        ', '.join(sorted(touched))))


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


def _module_digest(root):
    """Nội dung một module, bỏ __pycache__ và khoảng trắng cuối file."""
    out = {}
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d != '__pycache__']
        for f in fn:
            p = os.path.join(dp, f)
            with open(p, 'rb') as fh:
                out[os.path.relpath(p, root)] = fh.read().rstrip()
    return out


def _manifest_version(root):
    s = io.open(os.path.join(root, '__manifest__.py'), encoding='utf-8').read()
    m = re.search(r"'version'\s*:\s*'([^']+)'", s)
    return m.group(1) if m else None


def step_version_guard(dst, prev):
    """Module đổi mã mà KHÔNG tăng phiên bản → dừng.

    Odoo chỉ báo "cần nâng cấp" (và chỉ chạy migration) khi số phiên bản
    trong manifest lớn hơn bản đang cài. Đổi mã mà giữ nguyên số thì bên
    nhận bấm Nâng cấp theo danh sách Odoo gợi ý sẽ BỎ SÓT module đó — đã
    dính ở bản 2026-09-19: re_lease đổi trường dự án sang project.project
    mà vẫn 17.0.1.4.2, nên môi trường khách nâng cấp mọi module trừ nó.

    `prev` = thư mục addons của bản đã giao lần trước (repo đối tác).
    """
    stale = []
    for m in sorted(os.listdir(dst)):
        a, b = os.path.join(prev, m), os.path.join(dst, m)
        if not os.path.isdir(a) or not os.path.isfile(
                os.path.join(b, '__manifest__.py')):
            continue
        if _module_digest(a) != _module_digest(b) and \
                _manifest_version(a) == _manifest_version(b):
            stale.append('%s (%s)' % (m, _manifest_version(b)))
    if stale:
        raise SystemExit(
            'Module đổi mã mà KHÔNG tăng phiên bản so với bản đã giao: %s. '
            'Tăng version trong manifest ở nguồn 19 rồi chạy lại.'
            % ', '.join(stale))
    note('  %-46s 0 module' % 'đổi mã mà không tăng phiên bản')


def main():
    args = sys.argv[1:]
    prev = None
    if '--prev' in args:
        i = args.index('--prev')
        prev = args[i + 1]
        del args[i:i + 2]
    if len(args) != 2:
        raise SystemExit(__doc__)
    src, dst = args
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
    step_account_payment_api(dst)
    step_view_mode_xml(dst)
    step_security(dst)
    step_inject_fields(dst)
    step_patches_le(dst)
    step_files17(dst)
    step_partner_profile(dst)
    step_partner_project(dst)
    bad = step_check_syntax(dst)
    if prev:
        step_version_guard(dst, prev)
    note('XONG' if not bad else 'XONG (còn %s lỗi cú pháp)' % bad)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
