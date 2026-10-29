print('@@@BATDAU')
import io
bang = {}
for dong in io.open('/tmp/dich_du_lieu_ke_hoach_bao_tri.tsv', encoding='utf-8'):
    dong = dong.rstrip('\n')
    if not dong.strip():
        continue
    p = dong.split('\t')
    if len(p) != 3:
        print('!! dòng sai:', dong[:50]); continue
    bang.setdefault(p[0], {})[p[1]] = p[2]
print('bảng dịch:', {k: len(v) for k, v in bang.items()})
for model, cap in bang.items():
    dat = thieu = 0
    chua = set()
    for r in env[model].with_context(active_test=False).search([]):
        vi = r.with_context(lang='vi_VN').name or ''
        if vi in cap:
            r.with_context(lang='en_GB').write({'name': cap[vi]})
            dat += 1
        elif any(ord(c) > 127 for c in vi):
            thieu += 1; chua.add(vi[:55])
    print('%-14s đặt %3d · thiếu %d' % (model, dat, thieu))
    for t in sorted(chua)[:6]:
        print('   !! %s' % t)
env.cr.commit()
print('đã commit')
