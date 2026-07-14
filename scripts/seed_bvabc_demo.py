proj = env['re.project'].search([('code', '=', 'BVABC')], limit=1)
if not proj:
    proj = env['re.project'].create({'name': 'Bệnh Viện ABC', 'code': 'BVABC'})
    env.cr.commit()
print('PROJECT OK:', proj.id, proj.code, '| categories:',
      env['rp.cost.category'].search_count([('project_id', '=', proj.id)]))
# -*- coding: utf-8 -*-
"""Seed dữ liệu demo cho dự án Bệnh Viện ABC (project code BVABC) trên DB dev.
Idempotent: search-before-create theo (project, code/name). Chia mục, commit
sau mỗi mục; mục lỗi in traceback ngắn nhưng KHÔNG kéo sập mục khác.
Chạy: odoo shell -d dev  (đọc file này qua stdin).
"""
import traceback

PROJECT_CODE = 'BVABC'
log = []

def section(title, fn):
    try:
        fn()
        env.cr.commit()
        log.append('OK   | %s' % title)
    except Exception as e:
        env.cr.rollback()
        log.append('FAIL | %s | %s: %s' % (title, type(e).__name__, str(e)[:160]))
        log.append('       ' + traceback.format_exc().splitlines()[-1])

proj = env['re.project'].search([('code', '=', PROJECT_CODE)], limit=1)
assert proj, 'Chưa có dự án %s' % PROJECT_CODE
company = env.company
cur = company.currency_id
uom_unit = env.ref('uom.product_uom_unit')
T = 1_000_000_000.0  # 1 tỷ

def goc(model, domain, vals):
    """get_or_create"""
    rec = env[model].search(domain, limit=1)
    if rec:
        return rec
    return env[model].create(vals)

def cat(code):
    return env['rp.cost.category'].search(
        [('project_id', '=', proj.id), ('code', '=', code)], limit=1)

# ───────────────────────── A. Subzone + Hạng mục + Khái toán ─────────────
STRUCTS = {}  # key -> record

def sec_structures():
    sz_main = goc('re.subzone',
        [('project_id', '=', proj.id), ('code', '=', 'BVABC-KC')],
        {'project_id': proj.id, 'code': 'BVABC-KC', 'name': 'Khối công trình chính'})
    sz_infra = goc('re.subzone',
        [('project_id', '=', proj.id), ('code', '=', 'BVABC-HT')],
        {'project_id': proj.id, 'code': 'BVABC-HT', 'name': 'Hạ tầng & phụ trợ'})

    # (key, name, structure_type, subzone, [(cat_code, amount_ty)])
    rows = [
        ('mong',   'Phần ngầm & móng cọc',        'foundation',     sz_main, [('3', 120)]),
        ('ket_cau','Kết cấu thân khối điều trị',  'structure_body', sz_main, [('3', 300)]),
        ('hoan_thien','Hoàn thiện kiến trúc',     'interior',       sz_main, [('3', 200)]),
        ('mat_dung','Mặt đứng & vách kính',        'facade',         sz_main, [('3', 60)]),
        ('mep',    'Cơ điện (MEP)',               'mep',            sz_main, [('3', 160)]),
        ('pccc',   'PCCC & chống sét',            'utility',        sz_main, [('3', 40)]),
        ('khi_yte','Hệ thống khí y tế',           'utility',        sz_main, [('4', 80)]),
        ('tb_yte', 'Thiết bị y tế chuyên dụng',   'hospital',       sz_main, [('4', 300)]),
        ('ha_tang','Hạ tầng kỹ thuật ngoài nhà',  'infrastructure', sz_infra,[('5', 90)]),
        ('canh_quan','Cảnh quan & sân vườn',       'landscape',      sz_infra,[('6', 30)]),
        ('chi_phi_chung','Chi phí chung dự án',    'other',          sz_infra,
            [('1', 50), ('2', 20), ('7', 60), ('8', 25), ('9', 20), ('11', 65)]),
    ]
    EL = env['rp.structure.estimate.line']
    for key, name, stype, sz, lines in rows:
        st = goc('rp.structure',
            [('project_id', '=', proj.id), ('name', '=', name)],
            {'project_id': proj.id, 'subzone_id': sz.id, 'name': name,
             'structure_level': 'item', 'structure_type': stype,
             'planned_curve': 's_curve', 'state': 'confirmed'})
        STRUCTS[key] = st
        for ccode, amt_ty in lines:
            c = cat(ccode)
            if not c:
                continue
            ex = EL.search([('structure_id', '=', st.id), ('category_id', '=', c.id)], limit=1)
            vals = {'structure_id': st.id, 'category_id': c.id, 'amount': amt_ty * T}
            if ex:
                ex.amount = amt_ty * T
            else:
                EL.create(vals)

# ───────────────────────── B. Nhà thầu ───────────────────────────────────
CONTRACTORS = {}

def sec_contractors():
    data = [
        ('an_phu',   'Tổng thầu Xây dựng An Phú',        'general'),
        ('binh_minh','Công ty CP Xây lắp Bình Minh',     'general'),
        ('minh_long','Công ty Cơ điện Minh Long',        'general'),
        ('dong_duong','Công ty Thiết bị Y tế Đông Dương','supplier'),
        ('nhat_minh','Công ty TNHH Bảo trì Nhật Minh',   'subcontractor'),
    ]
    for key, name, ctype in data:
        partner = goc('res.partner', [('name', '=', name)],
                      {'name': name, 'is_company': True})
        c = goc('rp.contractor', [('partner_id', '=', partner.id)],
                {'partner_id': partner.id, 'contractor_type': ctype, 'state': 'approved'})
        CONTRACTORS[key] = c

# ───────────────────────── C. Gói thầu + Dự thầu ─────────────────────────
PKGS = {}

def sec_packages():
    # (key, code, name, method, value_ty, winner_key, [other_bidders], bid_status_map)
    data = [
        ('xd',   'GT-XD-01', 'Gói thầu Xây dựng khối nhà chính', 'open',              600, 'an_phu',  ['binh_minh']),
        ('mep',  'GT-ME-01', 'Gói thầu Cơ điện MEP',            'open',              160, 'minh_long',['an_phu']),
        ('tbyt', 'GT-TB-01', 'Gói thầu Thiết bị y tế',          'competitive_offer', 300, 'dong_duong',['binh_minh']),
        ('htcq', 'GT-HT-01', 'Gói thầu Hạ tầng & cảnh quan',    'open',              120, 'binh_minh',['an_phu']),
        ('sc',   'GT-SC-01', 'Gói sửa chữa Khoa Khám bệnh (chỉ định thầu)', 'direct',   8, 'nhat_minh', []),
    ]
    Bidder = env['rp.tender.bidder']
    for key, code, name, method, val_ty, winner, others in data:
        pkg = goc('rp.tender.package',
            [('project_id', '=', proj.id), ('code', '=', code)],
            {'project_id': proj.id, 'code': code, 'name': name,
             'selection_method': method, 'currency_id': cur.id, 'state': 'contracted'})
        PKGS[key] = (pkg, winner, val_ty)
        # bidders
        allb = [(winner, 'awarded', val_ty)] + [(o, 'qualified', val_ty * 1.04) for o in others]
        for ckey, status, price in allb:
            c = CONTRACTORS[ckey]
            ex = Bidder.search([('package_id', '=', pkg.id), ('contractor_id', '=', c.id)], limit=1)
            vals = {'package_id': pkg.id, 'contractor_id': c.id, 'partner_id': c.partner_id.id,
                    'status': status, 'price_offered': price * T}
            if ex:
                ex.write(vals)
            else:
                Bidder.create(vals)

# ───────────────────────── D. HĐ tổng thầu + sửa chữa ────────────────────
CONTRACTS = {}

def sec_contracts():
    import datetime
    d0 = datetime.date(2026, 1, 15)
    # key -> (pkg_key, name, advance%, retention%, months_offset)
    data = [
        ('xd',  'HĐ Tổng thầu Xây dựng khối nhà chính', 15, 5, 0),
        ('mep', 'HĐ Cơ điện MEP toàn công trình',        10, 5, 1),
        ('tbyt','HĐ Cung cấp & lắp đặt Thiết bị y tế',   20, 5, 2),
        ('htcq','HĐ Hạ tầng kỹ thuật & cảnh quan',       10, 5, 1),
        ('sc',  'HĐ Sửa chữa Khoa Khám bệnh',            0,  0, 3),
    ]
    C = env['rp.contract']
    for key, name, adv, ret, moff in data:
        pkg, winner, val_ty = PKGS[key]
        ct = CONTRACTORS[winner]
        start = d0.replace(month=((d0.month - 1 + moff) % 12) + 1)
        vals = {'name': name, 'tender_package_id': pkg.id, 'contractor_id': ct.partner_id.id,
                'contract_value_pretax': val_ty * T, 'company_id': company.id,
                'state': 'executing', 'advance_percent': adv, 'retention_percent': ret,
                'date_start': start}
        ex = C.search([('name', '=', name)], limit=1)
        if ex:
            ex.write({k: v for k, v in vals.items() if k not in ('tender_package_id',)})
            CONTRACTS[key] = ex
        else:
            CONTRACTS[key] = C.create(vals)

# ───────────────────────── E. Tạm ứng ────────────────────────────────────
def sec_advances():
    import datetime
    A = env['rp.advance.payment']
    data = [
        ('xd',  'TU-BVABC-01', 90, 'paid',     datetime.date(2026, 2, 1)),
        ('tbyt','TU-BVABC-02', 60, 'paid',     datetime.date(2026, 3, 5)),
        ('mep', 'TU-BVABC-03', 16, 'approved', datetime.date(2026, 3, 20)),
        ('sc',  'TU-BVABC-04', 2,  'to_approve',datetime.date(2026, 4, 10)),
    ]
    for key, name, amt_ty, state, dreq in data:
        ct = CONTRACTS.get(key)
        if not ct:
            continue
        vals = {'name': name, 'amount': amt_ty * T, 'company_id': company.id,
                'currency_id': cur.id, 'date_request': dreq, 'state': state,
                'partner_id': ct.contractor_id.id}
        if 'contract_id' in A._fields:
            vals['contract_id'] = ct.id
        ex = A.search([('name', '=', name)], limit=1)
        if ex:
            ex.write(vals)
        else:
            A.create(vals)

# ───────────────────────── F. Lịch thi công (project.task) ───────────────
def sec_schedule():
    import datetime
    ct = CONTRACTS.get('xd')
    if not ct or 'project.task' not in env:
        return
    proj_task = ct._get_or_create_schedule_project() if hasattr(ct, '_get_or_create_schedule_project') else None
    if not proj_task:
        return
    Task = env['project.task']
    tasks = [
        ('WBS1', 'Thi công phần ngầm & móng',      'mong',     datetime.date(2026,1,20), datetime.date(2026,4,30), 100, False),
        ('WBS2', 'Thi công kết cấu thân',          'ket_cau',  datetime.date(2026,5,1),  datetime.date(2026,11,30),70,  False),
        ('WBS3', 'Cất nóc khối điều trị',          'ket_cau',  datetime.date(2026,11,30),datetime.date(2026,11,30),0,  True),
        ('WBS4', 'Hoàn thiện kiến trúc',           'hoan_thien',datetime.date(2026,10,1),datetime.date(2027,4,30), 20,  False),
        ('WBS5', 'Lắp đặt MEP',                    'mep',      datetime.date(2026,9,1),  datetime.date(2027,3,31), 15,  False),
    ]
    for wbs, name, skey, ps, pe, prog, ms in tasks:
        st = STRUCTS.get(skey)
        vals = {'name': name, 'project_id': proj_task.id, 'wbs_code': wbs,
                'rp_contract_id': ct.id, 'planned_start': ps, 'planned_end': pe,
                'progress_percent': prog, 'is_milestone': ms}
        if st:
            vals['rp_structure_id'] = st.id
        ex = Task.search([('rp_contract_id', '=', ct.id), ('wbs_code', '=', wbs)], limit=1)
        if ex:
            ex.write(vals)
        else:
            Task.create(vals)

# ───────────────────────── G. Nghiệm thu khối lượng (BBNT) ───────────────
def sec_acceptance():
    import datetime
    if 'rp.progress.acceptance' not in env:
        return
    ct = CONTRACTS.get('xd')
    if not ct:
        return
    Acc = env['rp.progress.acceptance']
    AccL = env['rp.progress.acceptance.line']
    # 1 biên bản nghiệm thu đợt 1 (phần ngầm)
    ref = 'BBNT-BVABC-01'
    acc = Acc.search([('contract_id', '=', ct.id)], limit=1)
    if not acc:
        vals = {'contract_id': ct.id, 'state': 'draft'}
        if 'name' in Acc._fields:
            vals['name'] = ref
        if 'date' in Acc._fields:
            vals['date'] = datetime.date(2026, 5, 5)
        acc = Acc.create(vals)
    # lines (unit_price, uom_id required)
    line_data = [
        ('Bê tông cọc khoan nhồi D1000', 1200.0, 2_800_000.0),
        ('Đài & giằng móng',             850.0,  2_500_000.0),
        ('Bê tông sàn tầng hầm',         3200.0, 1_900_000.0),
    ]
    st = STRUCTS.get('mong')
    for desc, qty, price in line_data:
        dom = [('acceptance_id', '=', acc.id)]
        if 'name' in AccL._fields:
            dom.append(('name', '=', desc))
        ex = AccL.search(dom, limit=1)
        if ex:
            continue
        vals = {'acceptance_id': acc.id, 'unit_price': price, 'uom_id': uom_unit.id}
        for fn, fv in (('name', desc), ('qty', qty), ('quantity', qty),
                       ('qty_accepted', qty), ('structure_id', st.id if st else False)):
            if fn in AccL._fields and fv is not False:
                vals[fn] = fv
        AccL.create(vals)

section('A. Subzone + Hạng mục + Khái toán', sec_structures)
section('B. Nhà thầu', sec_contractors)
section('C. Gói thầu + Dự thầu', sec_packages)
section('D. HĐ tổng thầu + sửa chữa', sec_contracts)
section('E. Tạm ứng', sec_advances)
section('F. Lịch thi công', sec_schedule)
section('G. Nghiệm thu khối lượng', sec_acceptance)

print('\n===== KẾT QUẢ SEED =====')
for l in log:
    print(l)
print('\n===== TỔNG HỢP =====')
print('Khái toán tổng:', '{:,.0f}'.format(sum(env['rp.structure.estimate.line'].search([('project_id','=',proj.id)]).mapped('amount'))))
print('Hạng mục:', env['rp.structure'].search_count([('project_id','=',proj.id)]))
print('Gói thầu:', env['rp.tender.package'].search_count([('project_id','=',proj.id)]))
print('HĐ nhà thầu:', env['rp.contract'].search_count([('project_id','=',proj.id)]))
print('Tạm ứng:', env['rp.advance.payment'].search_count([('contract_id.project_id','=',proj.id)]) if 'contract_id' in env['rp.advance.payment']._fields else '?')
proj = env['re.project'].search([('code', '=', 'BVABC')], limit=1)
S = env['rp.structure']
def sids(names):
    out = []
    for n in names:
        r = S.search([('project_id', '=', proj.id), ('name', '=', n)], limit=1)
        if r:
            out.append(r.id)
    return out
plan = {
    'HĐ Tổng thầu Xây dựng khối nhà chính': (['Phần ngầm & móng cọc', 'Kết cấu thân khối điều trị', 'Hoàn thiện kiến trúc', 'Mặt đứng & vách kính'], '2030-07-31'),
    'HĐ Cơ điện MEP toàn công trình': (['Cơ điện (MEP)', 'PCCC & chống sét', 'Hệ thống khí y tế'], '2029-12-31'),
    'HĐ Cung cấp & lắp đặt Thiết bị y tế': (['Thiết bị y tế chuyên dụng'], '2030-03-31'),
    'HĐ Hạ tầng kỹ thuật & cảnh quan': (['Hạ tầng kỹ thuật ngoài nhà', 'Cảnh quan & sân vườn'], '2027-06-30'),
    'HĐ Sửa chữa Khoa Khám bệnh': (['Hoàn thiện kiến trúc'], '2026-09-30'),
}
for cname, (snames, dend) in plan.items():
    c = env['rp.contract'].search([('name', '=', cname)], limit=1)
    if c:
        c.write({'structure_ids': [(6, 0, sids(snames))], 'date_end': dend})
Cat = env['rp.cost.category']
for seq, (code, name) in enumerate([('VT', 'Vật tư'), ('NC', 'Nhân công'),
        ('MTC', 'Máy thi công'), ('TP', 'Thầu phụ'), ('CPC', 'Chi phí chung')], 1):
    if not Cat.search([('project_id', '=', proj.id), ('code', '=', code)]):
        Cat.create({'project_id': proj.id, 'code': code, 'name': name,
                    'sequence': 100 + seq * 10})
env.cr.commit()
print('POSTSTEP OK: HĐ gắn hạng mục + date_end + 5 nhóm chi phí AI')
