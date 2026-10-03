# -*- coding: utf-8 -*-
"""Khiếu nại demo cho dự án điện gió: hai chiều, có cả ca mất quyền.

Ba hồ sơ dựng theo đúng chuỗi sự việc đã có trong lịch và sổ giao diện:

1. Nhà thầu móng xin gia hạn vì hãng giao lồng bu-lông neo chậm — thông
   báo ĐÚNG hạn, được chấp thuận, ra phụ lục.
2. Nhà thầu lắp dựng xin gia hạn + chi phí chờ cẩu vì tua-bin lô 1 về
   chậm 42 ngày — thông báo TRỄ 9 ngày, đang xem xét, để demo đúng chỗ
   nhà thầu hay mất quyền.
3. Chủ đầu tư khiếu nại hãng tua-bin về chính 42 ngày chậm đó — nền để
   lập biên bản phạt chậm.
"""
import datetime as dt


def out(*a):
    print('@@', *a)


Claim = env['rp.claim']
C = env['rp.contract']
sup = C.search([('project_id', '=', 18), ('name', 'like', 'HĐ cung cấp tua-bin')])
bop = C.search([('project_id', '=', 18), ('name', 'like', 'HĐ xây lắp hạ tầng')])
ere = C.search([('project_id', '=', 18), ('name', 'like', 'HĐ lắp dựng tua-bin')])
iface_bolt = env['rp.interface'].search([
    ('project_id', '=', 18), ('name', 'like', 'lồng bu-lông neo')], limit=1)
Task = env['project.task']
t_nacelle = Task.search([('rp_contract_id', '=', sup.id),
                         ('name', 'like', 'Sản xuất nacelle lô 1')], limit=1)
t_erect = Task.search([('rp_contract_id', '=', ere.id),
                       ('name', 'like', 'Lắp 3 đoạn tháp WTG-01')], limit=1)
t_rebar = Task.search([('rp_contract_id', '=', bop.id),
                       ('name', 'like', 'Cốt thép, cốp pha & lồng bu-lông neo WTG-01')],
                      limit=1)

if Claim.search_count([('project_id', '=', 18)]):
    out('đã có khiếu nại, bỏ qua')
else:
    c1 = Claim.create({
        'name': 'Xin gia hạn do hãng giao lồng bu-lông neo chậm',
        'contract_id': bop.id,
        'direction': 'from_contractor',
        'claim_type': 'eot',
        'cause': 'owner_supply',
        'interface_id': iface_bolt.id if iface_bolt else False,
        'task_ids': [(6, 0, t_rebar.ids)] if t_rebar else False,
        'date_event': dt.date(2026, 7, 4),
        'notice_days': 28,
        'date_notice': dt.date(2026, 7, 20),
        'eot_days_claimed': 32,
        'description': '<p>Theo hợp đồng, chủ đầu tư chịu trách nhiệm '
                       'điều phối hãng cấp lồng bu-lông neo. Hạng mục '
                       'này chỉ sẵn sàng 05/08/2026 trong khi công tác '
                       'cốt thép móng WTG-01 cần từ 04/07/2026.</p>',
    })
    c1.action_notify()
    c1.action_submit()
    c1.eot_days_granted = 25
    c1.decision_note = ('Chấp thuận 25/32 ngày: 7 ngày thuộc phần nhà '
                        'thầu chưa huy động đủ nhân lực cốt thép.')
    c1.action_agree()
    out('KN1', c1.code, c1.state, '| gia hạn', c1.eot_days_granted,
        '| thông báo đúng hạn:', c1.notice_ok)
    c1.action_create_amendment()
    out('   phụ lục:', c1.amendment_id.name, '| ngày mới',
        c1.amendment_id.new_date_end)

    c2 = Claim.create({
        'name': 'Xin gia hạn và chi phí chờ cẩu do tua-bin lô 1 về chậm',
        'contract_id': ere.id,
        'direction': 'from_contractor',
        'claim_type': 'eot_cost',
        'cause': 'interface',
        'task_ids': [(6, 0, t_erect.ids)] if t_erect else False,
        'date_event': dt.date(2026, 11, 21),
        'notice_days': 28,
        'date_notice': dt.date(2026, 12, 28),
        'eot_days_claimed': 42,
        'amount_claimed': 4_200_000_000.0,
        'description': '<p>Cẩu bánh xích 750 tấn đã huy động theo lịch '
                       'gốc và phải chờ tại công trường. Yêu cầu gia hạn '
                       '42 ngày và chi phí chờ 100 triệu/ngày.</p>',
    })
    c2.action_notify()
    c2.action_submit()
    c2.action_review()
    out('KN2', c2.code, c2.state, '| thông báo đúng hạn:', c2.notice_ok,
        '| trễ', c2.notice_late_days, 'ngày (hạn', c2.notice_deadline, ')')

    c3 = Claim.create({
        'name': 'Khiếu nại hãng tua-bin chậm giao lô 1 (42 ngày)',
        'contract_id': sup.id,
        'direction': 'from_owner',
        'claim_type': 'cost',
        'cause': 'contractor_fault',
        'task_ids': [(6, 0, t_nacelle.ids)] if t_nacelle else False,
        'date_event': dt.date(2026, 10, 21),
        'notice_days': 28,
        'date_notice': dt.date(2026, 10, 28),
        'amount_claimed': 0.0,
        'description': '<p>Dây chuyền nacelle lô 1 chậm 42 ngày so với '
                       'kế hoạch gốc, kéo theo toàn bộ chuỗi lắp dựng và '
                       'mốc COD. Bảo lưu quyền áp dụng điều khoản phạt '
                       'chậm tiến độ.</p>',
    })
    c3.action_notify()
    c3.action_submit()
    out('KN3', c3.code, c3.state, '| chiều', c3.direction)

env.cr.commit()

# --- Phạt chậm: xem số dự kiến rồi lập biên bản cho hãng tua-bin -----
sup.invalidate_recordset()
out('HĐ hãng tua-bin: mốc HĐ', sup.date_end, '| đã gia hạn',
    sup.eot_days_granted, '| mốc sau gia hạn', sup.date_completion_adjusted)
out('   về đích theo lịch', sup.ld_forecast_end, '| chậm',
    sup.ld_days_late, 'ngày | phạt dự kiến',
    '{:,.0f}'.format(sup.ld_amount_exposure),
    '| chạm trần:', sup.ld_capped)
bop.invalidate_recordset()
out('HĐ xây lắp BOP: mốc HĐ', bop.date_end, '| đã gia hạn',
    bop.eot_days_granted, '| mốc sau gia hạn', bop.date_completion_adjusted,
    '| chậm', bop.ld_days_late, 'ngày')

if not sup.ld_assessment_ids and sup.ld_days_late:
    res = sup.action_create_ld_assessment()
    a = env['rp.ld.assessment'].browse(res['res_id'])
    a.note = ('Chốt theo lịch cập nhật ngày 02/10/2026. Hãng chưa nộp hồ '
              'sơ khiếu nại gia hạn nào được chấp thuận.')
    out('biên bản', a.name, '| chậm', a.days_late, 'ngày | tiền',
        '{:,.0f}'.format(a.amount), '| chạm trần:', a.capped)
env.cr.commit()
out('xong')
