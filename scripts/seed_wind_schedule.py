# -*- coding: utf-8 -*-
"""Nạp lịch thi công chi tiết cho dự án điện gió demo (7 hợp đồng).

Cần dự án + 7 hợp đồng đã có sẵn (khớp theo tên ở CMAP). Lịch do
seed_wind_schedule_data.py sinh ra bằng forward pass FS, nên mọi ngày
đều nhất quán với quan hệ phụ thuộc; baseline là lần tính KHÔNG có độ
trễ, kế hoạch hiện hành là lần tính CÓ độ trễ.

Chạy trong odoo shell (copy cả hai file vào /tmp của container):
    exec(open('/tmp/seed_wind_schedule.py', encoding='utf-8').read())
"""
import datetime as dt

# Bộ sinh lịch nằm ở file bên cạnh; nạp bằng exec để chạy được cả khi
# copy riêng hai file vào container (odoo shell không import được package
# ngoài addons path).
import os
HERE = os.path.dirname(os.path.abspath(__file__)) \
    if '__file__' in dir() else '/tmp'
ns = {}
for cand in (os.path.join(HERE, 'seed_wind_schedule_data.py'),
             '/tmp/seed_wind_schedule_data.py', '/tmp/wind_sched.py'):
    if os.path.exists(cand):
        exec(open(cand, encoding='utf-8').read(), ns)
        break
else:
    raise FileNotFoundError('không tìm thấy seed_wind_schedule_data.py')
rows = ns['build']()
TODAY = dt.date(2026, 10, 2)

PROJECT_ID = 18
CMAP = {
    'SUP': 'HĐ cung cấp tua-bin',
    'LOG': 'HĐ vận chuyển siêu trường',
    'ERE': 'HĐ lắp dựng tua-bin',
    'BOP': 'HĐ xây lắp hạ tầng',
    'CAB': 'HĐ thi công cáp ngầm',
    'SUB': 'HĐ trạm nâng áp',
    'OHL': 'HĐ thi công đường dây',
}
Contract = env['rp.contract']
Task = env['project.task']

contracts = {}
for ckey, frag in CMAP.items():
    c = Contract.search([('project_id', '=', PROJECT_ID),
                         ('name', 'like', frag)])
    if len(c) != 1:
        raise ValueError('Không khớp 1 hợp đồng cho %s: %s'
                         % (ckey, c.mapped('name')))
    contracts[ckey] = c
    print('@@ HĐ', ckey, '->', c.name, '| nhà thầu:',
          c.contractor_id.name if c.contractor_id else '-')

old = Task.search([('rp_contract_id.project_id', '=', PROJECT_ID)])
print('@@ xoá lịch cũ:', len(old), 'việc')
old.unlink()


def progress_of(start, end):
    if end < TODAY:
        return 100.0
    if start > TODAY:
        return 0.0
    span = (end - start).days + 1
    done = (TODAY - start).days + 1
    return round(min(max(done * 100.0 / span, 0.0), 95.0), 1)


# Dòng tổng lấy % theo bình quân có trọng số thời lượng của việc con.
leaf_by_key = {r['key']: r for r in rows if not r['is_group']}
vals_list = []
for r in rows:
    c = contracts[r['contract']]
    if r['is_group']:
        pre = r['key'] + '.'
        kids = [v for k, v in leaf_by_key.items() if k.startswith(pre)]
        tot = sum((k['end'] - k['start']).days + 1 for k in kids) or 1
        pg = round(sum(progress_of(k['start'], k['end'])
                       * ((k['end'] - k['start']).days + 1)
                       for k in kids) / tot, 1)
    else:
        pg = progress_of(r['start'], r['end'])
    vals_list.append({
        'name': r['name'],
        'project_id': c._get_or_create_schedule_project().id,
        'rp_contract_id': c.id,
        'wbs_code': r['wbs'],
        'planned_start': r['start'],
        'planned_end': r['end'],
        'baseline_start': r['bstart'],
        'baseline_end': r['bend'],
        'baseline_set_date': dt.datetime(2026, 2, 10, 9, 0, 0),
        'is_milestone': r['milestone'],
        'progress_percent': pg,
        'external_uid': 'ABC-' + r['key'],
    })

created = Task.create(vals_list)
print('@@ đã tạo', len(created), 'việc')
by_key = {t.external_uid[4:]: t for t in created}

n_link = 0
for r in rows:
    if not r['preds']:
        continue
    t = by_key[r['key']]
    ids = [by_key[p].id for p in r['preds'] if p in by_key]
    if ids:
        t.predecessor_ids = [(6, 0, ids)]
        n_link += len(ids)
print('@@ đã nối', n_link, 'quan hệ phụ thuộc')

env.cr.commit()

prj = env['re.project'].browse(PROJECT_ID)
prj.invalidate_recordset()
print('@@ dự án:', prj.schedule_task_count, 'việc /',
      prj.schedule_contract_count, 'hợp đồng')
print('@@ về đích dự báo', prj.schedule_forecast_end,
      '| baseline', prj.schedule_baseline_end,
      '| trượt baseline', prj.schedule_slip_days)
print('@@ mốc phải xong', prj.schedule_deadline,
      '| trễ so mốc', prj.schedule_deadline_slip)

res = Task.rp_compute_project_critical_path(PROJECT_ID)
crit = Task.browse([k for k, v in res.items() if v['critical']])
print('@@ đường găng toàn dự án:', len(crit), '/', len(res), 'việc lá')
for t in crit.sorted(lambda x: x.planned_start)[:45]:
    print('@@ GANG %-10s %-46s %s → %s  TF=%d'
          % (t.rp_contract_id.name.split('(')[0][3:18], t.name[:46],
             t.planned_start, t.planned_end, t.project_float))
env.cr.commit()
print('@@ xong')
