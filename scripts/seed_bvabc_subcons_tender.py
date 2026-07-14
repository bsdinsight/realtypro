# -*- coding: utf-8 -*-
"""Seed demo gói thầu Bệnh viện ABC trên subcons — đủ để bấm Chấm thầu ra xếp hạng.
Idempotent theo tên gói. Chạy: odoo shell -d subcons.
"""
import base64
import datetime

TY = 1_000_000_000.0
DUMMY = base64.b64encode(b'demo document').decode()
today = datetime.date.today()

Tender = env['cn.tender']
Partner = env['res.partner']
NAME = 'Gói thầu Xây lắp khối nhà chính — Bệnh viện ABC'

t = Tender.search([('name', '=', NAME)], limit=1)
if not t:
    gc = Partner.search([('name', '=', 'Ban QLDA Bệnh viện ABC')], limit=1) or \
        Partner.create({'name': 'Ban QLDA Bệnh viện ABC', 'is_company': True})
    t = Tender.create({
        'name': NAME, 'ref': 'GT-BVABC-KC', 'gc_partner_id': gc.id,
        'specialty': 'Xây lắp công trình y tế', 'budget': 150 * TY,
        'date_open': today, 'deadline': today + datetime.timedelta(days=20),
        'description': 'Thi công xây lắp khối nhà chính bệnh viện đa khoa: '
                       'kết cấu, hoàn thiện, cơ điện MEP, khí y tế, PCCC.',
        'state': 'open',
        'eval_method': 'tech_combined', 'tech_weight': 20, 'price_weight': 80,
        'tech_threshold': 70, 'criteria_template': 'hospital',
        'cap_auto_check': True, 'cap_duration_months': 18, 'cap_revenue_k': 1.5,
        'cap_finance_ratio': 3.0, 'cap_similar_pct': 70, 'cap_similar_count': 1,
        'cap_min_personnel': 2, 'cap_min_equipment': 2, 'cap_require_cert': True,
    })
    t.action_load_tech_criteria()
    t.action_add_default_reqs()
    # hồ sơ mời thầu (dossier)
    Doc = env['cn.tender.document']
    for nm, cat in [('Bảng khối lượng mời thầu (BOQ)', 'boq'),
                    ('Bản vẽ thiết kế kỹ thuật', 'drawing'),
                    ('Chỉ dẫn kỹ thuật & điều kiện HĐ', 'spec')]:
        Doc.create({'tender_id': t.id, 'name': nm, 'category': cat,
                    'attachment': DUMMY, 'filename': nm + '.pdf'})

# (tên NT, DT bq tỷ, nguồn lực tỷ, HĐ tương tự tỷ, #nhân sự, #thiết bị,
#  hạng chứng chỉ, giá dự thầu tỷ, điểm KT)
CONTRACTORS = [
    ('Tổng thầu Xây dựng An Phú',   200, 40, 120, 4, 5, '1', 148, 88),
    ('Công ty CP Xây lắp Bình Minh',160, 30, 110, 3, 3, '2', 142, 78),
    ('Công ty Xây dựng Hồng Hà',    150, 26, 105, 2, 2, '2', 138, 72),
    ('Công ty TNHH Tân Tiến',        80, 10,  50, 1, 0, False, 130, 60),
]
Inv = env['cn.tender.invite']
Bid = env['cn.bid']
BidDoc = env['cn.bid.document']
Score = env['cn.bid.tech.score']

for name, rev, fin, sim, npe, neq, cert, price, tech in CONTRACTORS:
    p = Partner.search([('name', '=', name)], limit=1)
    if not p:
        p = Partner.create({
            'name': name, 'is_company': True, 'cn_is_contractor': True,
            'cn_tax_code': '0100' + str(abs(hash(name)) % 1000000).zfill(6),
            'cn_legal_rep': 'Giám đốc ' + name.split()[-1],
            'cn_avg_revenue': rev * TY, 'cn_financial_resource': fin * TY,
            'cn_net_asset': fin * 2 * TY, 'cn_independent_accounting': True,
            'cn_not_banned': True, 'cn_not_bankrupt': True,
            'cn_registered_egp': True, 'cn_tax_compliant': True,
        })
        # PoQ
        env['cn.contractor.experience'].create({
            'partner_id': p.id, 'contract_name': 'BV/CT tương tự đã thi công',
            'owner_name': 'Chủ đầu tư trước', 'value': sim * TY,
            'role': 'independent', 'work_type': 'civil', 'work_grade': 'Cấp II',
            'accepted': True})
        for i in range(npe):
            env['cn.contractor.personnel'].create({
                'partner_id': p.id,
                'position': 'Chỉ huy trưởng' if i == 0 else 'Cán bộ kỹ thuật',
                'name': 'Nhân sự %d' % (i + 1), 'years_exp': 8 + i,
                'cchn_grade': cert or '3', 'mobilization': 'permanent'})
        for i in range(neq):
            env['cn.contractor.equipment'].create({
                'partner_id': p.id, 'name': ['Máy đào', 'Cẩu tháp', 'Trạm trộn',
                'Máy ép cọc', 'Xe bơm bê tông'][i % 5], 'quantity': 1 + i,
                'ownership': 'owned'})
        for yr in (today.year - 1, today.year - 2, today.year - 3):
            env['cn.contractor.revenue.year'].create({
                'partner_id': p.id, 'year': yr, 'revenue': rev * TY})
        if cert:
            env['cn.contractor.certificate'].create({
                'partner_id': p.id, 'field_area': 'construction',
                'work_type': 'civil', 'grade': cert, 'cert_number': 'CC-' + cert,
                'issuer': 'Sở Xây dựng', 'issue_date': today - datetime.timedelta(days=365),
                'expiry_date': today + datetime.timedelta(days=365 * 8)})

    # thư mời
    if not Inv.search([('tender_id', '=', t.id), ('partner_id', '=', p.id)]):
        Inv.create({'tender_id': t.id, 'partner_id': p.id, 'partner_name': name,
                    'email': 'contact@%s.vn' % name.split()[-1].lower(),
                    'state': 'submitted'})
    # hồ sơ dự thầu
    b = Bid.search([('tender_id', '=', t.id), ('contractor_id', '=', p.id)], limit=1)
    if not b:
        b = Bid.create({'tender_id': t.id, 'contractor_id': p.id,
                        'price': price * TY, 'is_submitted': True,
                        'submitted_date': datetime.datetime.now(),
                        'eligible': True, 'note': 'Hồ sơ dự thầu %s' % name})
        # tài liệu theo mỗi yêu cầu bắt buộc
        for req in t.doc_req_ids.filtered('required'):
            BidDoc.create({'bid_id': b.id, 'name': req.name,
                           'doc_type': req.doc_type, 'req_id': req.id,
                           'attachment': DUMMY, 'filename': req.name + '.pdf'})
    # chấm điểm kỹ thuật
    b._sync_tech_scores()
    b.tech_score_ids.filtered(lambda s: not s.score).write({'score': tech})

env.cr.commit()
print('SEED OK: tender id=%s | criteria=%s | reqs=%s | bids=%s' % (
    t.id, len(t.tech_criterion_ids), len(t.doc_req_ids), len(t.bid_ids)))
for b in t.bid_ids.sorted('price'):
    print('  %-32s giá=%.0f tỷ | KT%%=%.0f đạtKT=%s | năng lực(auto)=%s' % (
        b.contractor_id.name, b.price / TY, b.tech_score_pct,
        b.tech_passed, b.capacity_auto))
