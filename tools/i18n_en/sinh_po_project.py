# -*- coding: utf-8 -*-
"""Đổ bản dịch màn Dự án vào .po của từng module, GỘP với phần đã có."""
import io, json, os, re, sys
import po_lib as P

ADDONS = ['/Users/bsd/projects/realtypro-cnbuild/addons/_common',
          '/Users/bsd/projects/realtypro-cnbuild/addons/_project']
CHO_THAY = re.compile(r'%\(?[a-zA-Z_0-9]*\)?[0-9.]*[sdfr]|%%|\{[a-zA-Z_0-9]*\}')
RE_XMLID = re.compile(r'#:\s*\S+:([a-z0-9_]+)\.')
RE_CODE = re.compile(r'#:\s*code:addons/([a-z0-9_]+)/')

def mod_cua_ref(d):
    g = RE_CODE.match(d) or RE_XMLID.match(d)
    return g.group(1) if g else None

def thu_muc(mod):
    for g in ADDONS:
        d = os.path.join(g, mod)
        if os.path.isfile(os.path.join(d, '__manifest__.py')):
            return d
    return None

def go(s):
    return s.replace('\\n', '\n').replace('\\t', '\t').replace('\\\\', '\\')

idx = json.load(io.open('idx_project.json', encoding='utf-8'))
dich = {}
for d in io.open('dich_project.tsv', encoding='utf-8'):
    d = d.rstrip('\n')
    if not d.strip():
        continue
    k, _, en = d.partition('\t')
    if k in idx:
        dich[idx[k]] = go(en)
print('bản dịch:', len(dich), '/', len(idx))

loi = 0
for vi, en in dich.items():
    if sorted(CHO_THAY.findall(vi)) != sorted(CHO_THAY.findall(en)):
        loi += 1
        print('!! LỆCH:', vi[:70], '|', en[:70])
if loi:
    sys.exit('dừng: %d chỗ lệch' % loi)

muc = P.doc_muc('rp_en.po')
theo_mod = {}
for m in muc:
    if m['msgid'] not in dich:
        continue
    nhom = {}
    for d in m['tham_chieu']:
        if d.startswith('#:'):
            mo = mod_cua_ref(d)
            if mo:
                nhom.setdefault(mo, []).append(d)
    for mo, refs in nhom.items():
        theo_mod.setdefault(mo, []).append({
            'tham_chieu': ['#. module: %s' % mo] + refs,
            'msgid': m['msgid'], 'msgstr': dich[m['msgid']]})

tong, bo = 0, []
for mo, ms in sorted(theo_mod.items()):
    d = thu_muc(mo)
    if not d:
        bo.append(mo); continue
    i18n = os.path.join(d, 'i18n')
    if not os.path.isdir(i18n):
        os.makedirs(i18n)
    po = os.path.join(i18n, 'en_GB.po')
    cu = P.doc_muc(po) if os.path.exists(po) else []
    co = {('\n'.join(x['tham_chieu']), x['msgid']) for x in cu}
    them = [x for x in ms if ('\n'.join(x['tham_chieu']), x['msgid']) not in co]
    P.ghi_po(po, mo, cu + them)
    tong += len(them)
    print('   %-22s +%3d  (tổng %d)' % (mo, len(them), len(cu) + len(them)))
print('\nthêm %d mục' % tong)
if bo:
    print('BỎ QUA (ngoài repo):', bo)
