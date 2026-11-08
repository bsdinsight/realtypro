#!/usr/bin/env python3
"""Bắt hai lớp lỗi CHỈ nổ khi cài mới, không môi trường đang chạy nào thấy.

Vì sao cần: cả hai lớp đều dựa vào thứ tự, và trên bản ĐÃ CÀI thì bản ghi
đã nằm sẵn trong cơ sở dữ liệu nên không ai vấp. Chúng chỉ nổ đúng lúc
dựng bản cho khách MỚI — tức đúng lúc bán hàng. Ngày 2026-10-23 nâng bản
demo đã vấp cả hai, mỗi lỗi mất một lượt chạy mới lộ ra lỗi kế tiếp.

**Lỗi 1 — thứ tự tệp trong `data` của manifest.** Tệp nạp trước tham
chiếu xmlid khai ở tệp nạp sau:

    ValueError: External ID not found in the system:
    rp_schedule.view_rp_schedule_baseline_form

Gặp ở `rp_receivable` và 7 module khai `views/rp_doc_filing_views.xml`
ở đầu danh sách trong khi tệp đó kế thừa các form khai ở cuối.

**Lỗi 2 — thứ tự GHÉP view con, theo `(priority, id)`.** View con A xpath
vào phần tử do view con B (module khác) chèn vào CÙNG form cha. Để
priority mặc định thì thứ tự rơi vào `id`, tức phụ thuộc lịch sử cài đặt:
môi trường này chạy, môi trường kia chết.

    Không thể định vị phần tử
    '<xpath expr="//button[@name='action_open_project_gantt']">'

Gặp ở `rp_energy` (xpath vào nút do `rp_schedule` chèn). Cách chữa: ghim
`priority` của view phụ thuộc cao hơn view mà nó dựa vào.

Dùng:  python3 tools/check_install_order.py addons
Trả mã thoát 1 nếu có vấn đề — cắm thẳng vào CI được.
"""
import ast
import io
import os
import re
import sys

from lxml import etree

PRIORITY_MAC_DINH = 16

# Phần tử mang name= mà xpath hay trỏ tới.
RX_XPATH_NAME = re.compile(r"""@name\s*=\s*['"]([^'"]+)['"]""")
# Mọi chỗ một tệp XML trỏ tới xmlid khác. Bản đầu chỉ dò `ref="…"` nên
# bỏ lọt `<menuitem parent="…" action="…">`, `eval="ref('…')"` và
# `name="%(…)d"` trên nút — và lọt đúng lỗi cài mới của eam_core
# (menu con trỏ tới menu cha khai ở tệp nạp sau), 08/11/2026.
RX_REF = re.compile(
    r"""\b(?:ref|parent|action)=["']([\w.]+)["']"""
    r"""|\bref\(\s*["']([\w.]+)["']\s*\)"""
    r"""|%\(([\w.]+)\)d""")
# `<menuitem id=…>` cũng là nơi KHAI xmlid. Thiếu nó thì menu cha khai
# bằng menuitem không bao giờ được ghi nhận, nên không so được thứ tự.
RX_REC_ID = re.compile(
    r'<(?:record|template|menuitem)\b[^>]*\bid="([\w.]+)"')
RX_COMMENT = re.compile(r'<!--.*?-->', re.S)


def doc_xml(path):
    """Nội dung tệp XML đã BỎ chú thích.

    Tham chiếu nằm trong chú thích không được nạp, nên không được tính —
    re_core có ba menu trỏ sang re_document/re_vendor đã comment lại, và
    bản quét không bỏ chú thích báo nhầm thành thiếu phụ thuộc.
    """
    return RX_COMMENT.sub('', io.open(path, encoding='utf-8').read())


def doc_data(mod_dir):
    """Danh sách tệp trong khoá `data` của manifest, giữ nguyên thứ tự."""
    p = os.path.join(mod_dir, '__manifest__.py')
    if not os.path.exists(p):
        return None
    try:
        return ast.literal_eval(io.open(p, encoding='utf-8').read()).get(
            'data', [])
    except (ValueError, SyntaxError):
        return None


# ----------------------------------------------------------------------
# Lỗi 1: xmlid tham chiếu ở tệp nạp TRƯỚC tệp khai nó
# ----------------------------------------------------------------------
def kiem_thu_tu_tep(goc, mod, data):
    van_de = []
    khai = {}
    for vt, rel in enumerate(data):
        p = os.path.join(goc, mod, rel)
        if rel.endswith('.xml') and os.path.exists(p):
            s = doc_xml(p)
            for rid in RX_REC_ID.findall(s):
                khai.setdefault(rid, vt)
    for vt, rel in enumerate(data):
        p = os.path.join(goc, mod, rel)
        if not (rel.endswith('.xml') and os.path.exists(p)):
            continue
        s = doc_xml(p)
        refs = {next(g for g in m if g) for m in RX_REF.findall(s)}
        for r in refs:
            ngan = r.split('.', 1)[1] if r.startswith(mod + '.') else r
            if '.' in ngan:
                continue                      # xmlid của module khác
            vt_khai = khai.get(ngan)
            if vt_khai is not None and vt_khai > vt:
                van_de.append(
                    '%s: %s tham chiếu %s — khai ở %s (nạp SAU). '
                    'Đưa tệp khai lên trước trong manifest.'
                    % (mod, rel, ngan, data[vt_khai]))
    return van_de


# ----------------------------------------------------------------------
# Lỗi 2: view con xpath vào phần tử do view con KHÁC chèn
# ----------------------------------------------------------------------
def doc_views(goc):
    """{xmlid: {module, parent, priority, ten_phan_tu, xpath_name}}"""
    views = {}
    for mod in sorted(os.listdir(goc)):
        data = doc_data(os.path.join(goc, mod))
        if data is None:
            continue
        for rel in data:
            p = os.path.join(goc, mod, rel)
            if not (rel.endswith('.xml') and os.path.exists(p)):
                continue
            try:
                cay = etree.parse(p).getroot()
            except etree.XMLSyntaxError:
                continue
            for rec in cay.iter('record'):
                if rec.get('model') != 'ir.ui.view':
                    continue
                xid = rec.get('id') or ''
                if '.' not in xid:
                    xid = '%s.%s' % (mod, xid)
                parent = prio = arch = None
                for f in rec.findall('field'):
                    ten = f.get('name')
                    if ten == 'inherit_id':
                        parent = f.get('ref')
                    elif ten == 'priority':
                        try:
                            prio = int((f.text or '').strip())
                        except ValueError:
                            prio = None
                    elif ten == 'arch':
                        arch = f
                if arch is None:
                    continue
                # tên phần tử view này KHAI (để biết nó cấp cái gì)
                khai = {e.get('name') for e in arch.iter()
                        if e.get('name') and e.tag != 'xpath'}
                # tên phần tử view này TRỎ TỚI qua xpath
                tro = set()
                for e in arch.iter('xpath'):
                    tro |= set(RX_XPATH_NAME.findall(e.get('expr') or ''))
                views[xid] = {
                    'module': mod, 'parent': parent,
                    'priority': PRIORITY_MAC_DINH if prio is None else prio,
                    'ghim_prio': prio is not None,
                    'khai': khai, 'tro': tro, 'tep': rel,
                }
    return views


def kiem_thu_tu_ghep_view(views):
    van_de = []
    for xid, v in sorted(views.items()):
        if not v['parent'] or not v['tro']:
            continue
        cha = views.get(v['parent'])
        if cha is None:
            continue          # view cha của Odoo lõi — không soi được
        anh_em = [(x, w) for x, w in views.items()
                  if w['parent'] == v['parent'] and x != xid]
        for ten in sorted(v['tro']):
            if ten in cha['khai']:
                continue      # phần tử có sẵn trong view cha: an toàn
            cap = [(x, w) for x, w in anh_em if ten in w['khai']]
            for x, w in cap:
                if v['priority'] <= w['priority']:
                    van_de.append(
                        '%s (%s): xpath tới @name=%r — phần tử đó do %s '
                        'chèn, KHÔNG có sẵn trong view cha %s. Hai view '
                        'cùng priority %s nên thứ tự ghép rơi vào id, tức '
                        'phụ thuộc lịch sử cài đặt. Ghim priority cho %s '
                        'cao hơn %s.'
                        % (xid, v['tep'], ten, x, v['parent'],
                           v['priority'], xid, w['priority']))
    return van_de


# ----------------------------------------------------------------------
# Lỗi 3: trỏ tới xmlid của module KHÔNG nằm trong chuỗi phụ thuộc
# ----------------------------------------------------------------------
# Gặp 08/11/2026 khi cài mới bản demo EPCOne: eam_om_contract chỉ khai
# depends eam_core, nhưng bảng phân quyền dùng re_base.group_re_user.
# Trên DB đang chạy thì re_base tình cờ đã cài trước nên không ai thấy;
# cài mới thì Odoo nạp eam_om_contract trước re_base và chết:
#
#     No matching record found for external id 're_base.group_re_user'
#
# Chỉ xét module CỦA MÌNH (có trong thư mục quét). Thế là đủ chính xác:
# module lõi Odoo không bao giờ phụ thuộc ngược về module của mình, nên
# chuỗi phụ thuộc đi qua module lõi không thể dẫn tới một module BSD.
RX_GROUPS = re.compile(r"""\bgroups=["']([^"']+)["']""")


def doc_manifest(mod_dir):
    p = os.path.join(mod_dir, '__manifest__.py')
    if not os.path.exists(p):
        return None
    try:
        return ast.literal_eval(io.open(p, encoding='utf-8').read())
    except (ValueError, SyntaxError):
        return None


def tham_chieu_trong_tep(path):
    """Mọi xmlid một tệp dữ liệu (XML hoặc CSV) trỏ tới."""
    if path.endswith('.csv'):
        s = io.open(path, encoding='utf-8').read()
        dong = s.splitlines()
        if not dong:
            return set()
        cot = [i for i, c in enumerate(dong[0].split(','))
               if c.strip().endswith(':id')]
        out = set()
        for d in dong[1:]:
            o = d.split(',')
            out |= {o[i].strip() for i in cot if i < len(o) and o[i].strip()}
        return out
    s = doc_xml(path)
    out = {next(g for g in m if g) for m in RX_REF.findall(s)}
    for g in RX_GROUPS.findall(s):
        out |= {x.strip().lstrip('!') for x in g.split(',') if x.strip()}
    return out


def kiem_phu_thuoc(manifests):
    """manifests = {module: (thư mục, manifest)}."""
    cache = {}

    def chuoi(mod):
        if mod in cache:
            return cache[mod]
        cache[mod] = set()                     # chặn vòng lặp
        kq = set()
        for d in manifests[mod][1].get('depends', []):
            kq.add(d)
            if d in manifests:
                kq |= chuoi(d)
        cache[mod] = kq
        return kq

    van_de = []
    for mod, (thu_muc, man) in sorted(manifests.items()):
        if not man.get('installable', True):
            continue
        thieu = {}
        for rel in man.get('data', []):
            p = os.path.join(thu_muc, rel)
            if not (rel.endswith(('.xml', '.csv')) and os.path.exists(p)):
                continue
            for ref in tham_chieu_trong_tep(p):
                if '.' not in ref:
                    continue
                m = ref.split('.', 1)[0]
                if m == mod or m not in manifests or m in chuoi(mod):
                    continue
                thieu.setdefault(m, set()).add('%s (%s)' % (ref, rel))
        for m, chung in sorted(thieu.items()):
            vi_du = sorted(chung)
            van_de.append(
                '%s: dùng %s nhưng KHÔNG khai %s trong depends (kể cả bắc '
                'cầu) — cài mới sẽ chết nếu %s chưa có. Ví dụ: %s%s'
                % (mod, m, m, m, vi_du[0],
                   ' và %d chỗ khác' % (len(vi_du) - 1)
                   if len(vi_du) > 1 else ''))
    return van_de


def main():
    # Nhận NHIỀU thư mục addons: một DB thật nạp mã từ nhiều repo (bản
    # tenants nạp cả realtypro-cnbuild lẫn realtypro-enterprise), và
    # phụ thuộc chéo giữa hai repo chỉ thấy được khi quét chung.
    goc_list = sys.argv[1:] or ['addons']
    thu_muc = [os.path.join(g, d) for g in goc_list
               for d in sorted(os.listdir(g))
               if os.path.isdir(os.path.join(g, d))]
    van_de = []
    views = {}
    manifests = {}
    for goc in thu_muc:
        for mod in sorted(os.listdir(goc)):
            man = doc_manifest(os.path.join(goc, mod))
            if man is None:
                continue
            manifests.setdefault(mod, (os.path.join(goc, mod), man))
            data = man.get('data', [])
            if data:
                van_de += kiem_thu_tu_tep(goc, mod, data)
        views.update(doc_views(goc))
    van_de += kiem_thu_tu_ghep_view(views)
    van_de += kiem_phu_thuoc(manifests)

    if van_de:
        print('Thứ tự nạp/ghép có vấn đề — cài MỚI sẽ chết (%d):'
              % len(van_de))
        for v in van_de:
            print('  •', v)
        return 1
    print('Thứ tự nạp tệp và ghép view: không có vấn đề '
          '(%d view đã soi).' % len(views))
    return 0


if __name__ == '__main__':
    sys.exit(main())
