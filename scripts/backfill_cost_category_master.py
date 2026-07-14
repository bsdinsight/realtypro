import re as _re
import unicodedata

def norm(t):
    t = unicodedata.normalize('NFD', (t or '').lower())
    t = ''.join(c for c in t if unicodedata.category(c) != 'Mn')
    return _re.sub(r'[^a-z0-9]+', ' ', t.replace('đ', 'd')).strip()

try:
    Master = env['rp.cost.category.master']
    Cat = env['rp.cost.category']
    Master._ensure_seeded()
    masters = Master.search([])
    by_code = {(m.code or '').strip(): m for m in masters if m.code}
    by_name = {}
    for m in masters:
        by_name.setdefault(norm(m.name), m)
    total = matched = 0
    for c in Cat.search([('master_category_id', '=', False)]):
        total += 1
        m = by_code.get((c.code or '').strip()) or by_name.get(norm(c.name))
        if m:
            c.master_category_id = m.id
            matched += 1
    env.cr.commit()
    print('MASTER: %s ma chuan' % len(masters))
    print('BACKFILL: %s/%s category du an da map, %s dac thu du an'
          % (matched, total, total - matched))
    for p in env['re.project'].search([]):
        n_all = Cat.search_count([('project_id', '=', p.id)])
        n_spec = Cat.search_count([('project_id', '=', p.id),
                                   ('master_category_id', '=', False)])
        if n_all:
            print('  %-12s: %s ma, %s dac thu' % (p.code, n_all, n_spec))
except Exception as e:
    env.cr.rollback()
    import traceback
    print('FAIL:', traceback.format_exc().splitlines()[-1])
