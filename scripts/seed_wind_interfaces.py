# -*- coding: utf-8 -*-
"""Làm sổ giao diện demo giống sổ thật, không chỉ là bản sao của lịch.

Chạy SAU khi đã quét giao diện từ lịch (nút trên form dự án), trong
odoo shell:

    exec(open('/tmp/seed_wind_interfaces.py', encoding='utf-8').read())


Quét từ lịch cho ra các điểm giao ĐÃ được khai trong lịch nên điểm nào
cũng khớp ngày. Sổ thật thì khác: luôn có vài điểm giao mà không ai nối
vào lịch — và đúng những điểm đó mới gây vỡ tiến độ. Ở đây thêm một ca
kinh điển của điện gió (lồng bu-lông neo do hãng cấp, nhà thầu móng chờ)
cùng trạng thái thực tế cho các điểm đã qua.
"""
import datetime as dt


def out(*a):
    print('@@', *a)


TODAY = dt.date(2026, 10, 2)
Task = env['project.task']
Interface = env['rp.interface']
prj = env['re.project'].browse(18)

sup = env['rp.contract'].search([('project_id', '=', 18),
                                 ('name', 'like', 'HĐ cung cấp tua-bin')])
bop = env['rp.contract'].search([('project_id', '=', 18),
                                 ('name', 'like', 'HĐ xây lắp hạ tầng')])
ere = env['rp.contract'].search([('project_id', '=', 18),
                                 ('name', 'like', 'HĐ lắp dựng tua-bin')])
out('HĐ:', sup.name, '|', bop.name, '|', ere.name)

# --- 1. Việc của hãng mà lịch gốc bỏ sót: lồng bu-lông neo -----------
anchor = Task.search([('rp_contract_id', '=', sup.id),
                      ('wbs_code', '=', '2.7')], limit=1)
if not anchor:
    anchor = Task.create({
        'name': 'Chế tạo & giao lồng bu-lông neo (12 bộ)',
        'project_id': sup._get_or_create_schedule_project().id,
        'rp_contract_id': sup.id,
        'wbs_code': '2.7',
        'planned_start': dt.date(2026, 5, 8),
        'planned_end': dt.date(2026, 8, 5),
        'baseline_start': dt.date(2026, 5, 8),
        'baseline_end': dt.date(2026, 8, 5),
        'baseline_set_date': dt.datetime(2026, 2, 10, 9, 0, 0),
        'progress_percent': 100.0,
        'external_uid': 'ABC-SUP:2.7',
    })
    out('đã thêm việc', anchor.name, anchor.planned_start, '→',
        anchor.planned_end)

rebar = Task.search([('rp_contract_id', '=', bop.id),
                     ('name', 'like', 'Cốt thép, cốp pha & lồng bu-lông neo WTG-01')],
                    limit=1)
out('việc chờ:', rebar.name, rebar.planned_start)

MANUAL = [
    {
        'name': 'Hãng giao lồng bu-lông neo & dưỡng định vị cho nhà thầu móng',
        'from_contract_id': sup.id, 'to_contract_id': bop.id,
        'from_task_id': anchor.id, 'to_task_id': rebar.id,
        'interface_type': 'physical', 'criticality': 'critical',
        'state': 'disputed',
        'description': '<p>Giao tại công trường: 12 bộ lồng bu-lông neo, '
                       'dưỡng định vị và chứng chỉ vật liệu. Nghiệm thu '
                       'khi đủ số lượng, đúng dung sai định vị ±2 mm và '
                       'có biên bản kiểm tra kích thước.</p>',
        'date_required': rebar.planned_start,
        'date_promised': anchor.planned_end,
    },
    {
        'name': 'Hãng giao hồ sơ tải trọng & giao diện móng — tháp',
        'from_contract_id': sup.id, 'to_contract_id': bop.id,
        'from_task_id': Task.search([('rp_contract_id', '=', sup.id),
                                     ('wbs_code', '=', '1.3')], limit=1).id,
        'to_task_id': Task.search([('rp_contract_id', '=', bop.id),
                                   ('wbs_code', '=', '3.1.1')], limit=1).id,
        'interface_type': 'document', 'criticality': 'high',
        'state': 'closed',
        'description': '<p>Bản tính tải trọng thiết kế và bản vẽ giao '
                       'diện móng — tháp, có chữ ký kiểm tra của hãng. '
                       'Thiếu hồ sơ này thì không chốt được thiết kế '
                       'móng.</p>',
    },
]

created = Interface
for vals in MANUAL:
    dup = Interface.search([('project_id', '=', 18),
                            ('from_task_id', '=', vals['from_task_id']),
                            ('to_task_id', '=', vals['to_task_id'])], limit=1)
    if dup:
        out('đã có:', dup.code, dup.name[:50])
        continue
    vals['project_id'] = 18
    created |= Interface.create(vals)
for i in created:
    out('thêm [%s] %s | dư địa %+d ngày | mâu thuẫn: %s'
        % (i.code, i.name[:52], i.gap_days, i.is_conflict))

# --- 2. Trạng thái thực tế cho các điểm giao quét từ lịch -------------
ifs = Interface.search([('project_id', '=', 18), ('state', '=', 'identified')])
n_closed = n_prog = n_agree = 0
for i in ifs:
    ready = i.schedule_ready_date
    if not ready:
        continue
    if ready < TODAY:
        i.write({'state': 'closed', 'date_actual': ready,
                 'date_required': i.schedule_need_date,
                 'date_promised': ready})
        n_closed += 1
    elif (ready - TODAY).days <= 90:
        i.write({'state': 'in_progress',
                 'date_required': i.schedule_need_date,
                 'date_promised': ready})
        n_prog += 1
    else:
        i.write({'state': 'agreed',
                 'date_required': i.schedule_need_date,
                 'date_promised': ready})
        n_agree += 1
out('cập nhật trạng thái: đóng %s, đang làm %s, đã chốt %s'
    % (n_closed, n_prog, n_agree))

# --- 3. Ghi chú tranh chấp cho điểm giao tua-bin lô 1 -----------------
late = Interface.search([
    ('project_id', '=', 18),
    ('name', 'like', 'Kiểm tra cấu kiện & biên bản bàn giao WTG-01')], limit=1)
if late:
    late.write({'state': 'disputed', 'criticality': 'critical'})
    late.message_post(body=(
        'Hãng thông báo dây chuyền nacelle lô 1 chậm 42 ngày. Nhà thầu '
        'lắp dựng đã huy động cẩu 750 tấn theo lịch cũ và yêu cầu tính '
        'chi phí chờ. Chốt phương án trước khi điều chỉnh lịch.'))
    out('ghi tranh chấp:', late.code, late.name[:60])

env.cr.commit()
prj.invalidate_recordset()
out('TỔNG: %s giao diện | chưa đóng %s | mâu thuẫn %s'
    % (prj.interface_count, prj.interface_open_count,
       prj.interface_conflict_count))
by_state = {}
for i in Interface.search([('project_id', '=', 18)]):
    by_state[i.state] = by_state.get(i.state, 0) + 1
out('theo trạng thái:', by_state)
out('xong')
