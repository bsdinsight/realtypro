# -*- coding: utf-8 -*-
"""Tái cấu trúc hạng mục BVABC theo KHỐI CHỨC NĂNG bệnh viện (2 tầng):
subzone = khối chức năng (CĐT view), hạng mục = bộ môn thi công trong khối.
Khái toán giữ nguyên tổng 1.620 tỷ; BOQ dựng lại theo item mới; re-link
HĐ/BBNT/lịch thi công; xoá 8 item bộ môn cũ + subzone KC cũ.
Chạy: odoo shell -d dev < file. Idempotent theo code.
"""
TY = 1_000_000_000.0
TR = 1_000_000.0
K = 1_000.0

proj = env['re.project'].search([('code', '=', 'BVABC')], limit=1)
assert proj, 'Chua co BVABC'

SZ = env['re.subzone']
S = env['rp.structure']
EL = env['rp.structure.estimate.line']
BL = env['rp.boq.line']
UOM = env['rp.progress.uom']

def cat(code):
    return env['rp.cost.category'].search(
        [('project_id', '=', proj.id), ('code', '=', code)], limit=1)

_u = {}
def uom(name):
    if name not in _u:
        r = UOM.search([('name', '=', name)], limit=1)
        if not r:
            v = {'name': name}
            if 'code' in UOM._fields:
                v['code'] = name
            r = UOM.create(v)
        _u[name] = r
    return _u[name]

# ── 1. Subzone = khối chức năng ─────────────────────────────────────────
SUBZONES = [
    ('BVABC-KB',  'Khối Khám bệnh & Ngoại trú (OPD)'),
    ('BVABC-NT',  'Khối Điều trị Nội trú (IPD)'),
    ('BVABC-CLS', 'Khối Cận lâm sàng & Chẩn đoán hình ảnh'),
    ('BVABC-PT',  'Khối Phẫu thuật – Hồi sức (OT/ICU)'),
    ('BVABC-HC',  'Khối Hành chính – Hậu cần – CSSD'),
    ('BVABC-TN',  'Khoa Truyền nhiễm'),
    ('BVABC-CC',  'Chi phí chung & dự phòng'),
]
sz = {}
for code, name in SUBZONES:
    r = SZ.search([('project_id', '=', proj.id), ('code', '=', code)], limit=1)
    if not r:
        r = SZ.create({'project_id': proj.id, 'code': code, 'name': name})
    sz[code] = r
sz['BVABC-HT'] = SZ.search(
    [('project_id', '=', proj.id), ('code', '=', 'BVABC-HT')], limit=1)

# ── 2. Hạng mục bộ môn theo khối + khái toán (cat, tỷ) ──────────────────
# (code, tên, type, subzone, cat, tỷ)
ITEMS = [
    ('KB-NG', 'Phần ngầm & móng — Khối Khám',        'foundation',     'BVABC-KB', '3', 30),
    ('KB-KC', 'Kết cấu thân — Khối Khám',             'structure_body', 'BVABC-KB', '3', 60),
    ('KB-HT', 'Hoàn thiện — Khối Khám',               'interior',       'BVABC-KB', '3', 55),
    ('KB-ME', 'Cơ điện MEP & PCCC — Khối Khám',       'mep',            'BVABC-KB', '3', 40),
    ('KB-KY', 'Khí y tế — Khối Khám',                 'utility',        'BVABC-KB', '4', 10),
    ('KB-TB', 'Thiết bị y tế — Khối Khám',            'hospital',       'BVABC-KB', '4', 40),
    ('NT-NG', 'Phần ngầm & móng — Khối Nội trú',      'foundation',     'BVABC-NT', '3', 50),
    ('NT-KC', 'Kết cấu thân — Khối Nội trú',          'structure_body', 'BVABC-NT', '3', 120),
    ('NT-HT', 'Hoàn thiện — Khối Nội trú',            'interior',       'BVABC-NT', '3', 80),
    ('NT-MD', 'Mặt đứng & vách kính — Khối Nội trú',  'facade',         'BVABC-NT', '3', 45),
    ('NT-ME', 'Cơ điện MEP & PCCC — Khối Nội trú',    'mep',            'BVABC-NT', '3', 60),
    ('NT-KY', 'Khí y tế — Khối Nội trú',              'utility',        'BVABC-NT', '4', 35),
    ('NT-TB', 'Thiết bị y tế — Khối Nội trú',         'hospital',       'BVABC-NT', '4', 35),
    ('CLS-XD', 'Xây dựng & kết cấu — Khối Cận lâm sàng', 'structure_body', 'BVABC-CLS', '3', 65),
    ('CLS-HT', 'Hoàn thiện phòng chì & phòng sạch',   'interior',       'BVABC-CLS', '3', 35),
    ('CLS-ME', 'Cơ điện MEP & lọc khí — Khối CLS',    'mep',            'BVABC-CLS', '3', 30),
    ('CLS-KY', 'Khí y tế — Khối Cận lâm sàng',        'utility',        'BVABC-CLS', '4', 10),
    ('CLS-TB', 'Chẩn đoán hình ảnh & xét nghiệm',     'hospital',       'BVABC-CLS', '4', 140),
    ('PT-XD', 'Xây dựng & hoàn thiện phòng mổ',       'hospital',       'BVABC-PT', '3', 55),
    ('PT-ME', 'MEP & phòng sạch OT/ICU',              'mep',            'BVABC-PT', '3', 30),
    ('PT-KY', 'Khí y tế — Khối Phẫu thuật',           'utility',        'BVABC-PT', '4', 22),
    ('PT-TB', 'Thiết bị phòng mổ & hồi sức',          'hospital',       'BVABC-PT', '4', 65),
    ('HC-XD', 'Xây dựng khối hành chính – hậu cần',   'structure_body', 'BVABC-HC', '3', 65),
    ('HC-ME', 'Cơ điện MEP — Khối Hậu cần',           'mep',            'BVABC-HC', '3', 18),
    ('HC-TB', 'Thiết bị hậu cần (CSSD, giặt là, bếp)','utility',        'BVABC-HC', '4', 15),
    ('TN-XD', 'Xây dựng khoa truyền nhiễm',           'hospital',       'BVABC-TN', '3', 30),
    ('TN-ME', 'MEP & phòng áp lực âm',                'mep',            'BVABC-TN', '3', 12),
    ('TN-TB', 'Thiết bị y tế — Khoa Truyền nhiễm',    'hospital',       'BVABC-TN', '4', 8),
]
IT = {}
for code, name, stype, szc, ccode, ty in ITEMS:
    st = S.search([('project_id', '=', proj.id), ('code', '=', code)], limit=1)
    vals = {'project_id': proj.id, 'code': code, 'name': name,
            'subzone_id': sz[szc].id, 'structure_level': 'item',
            'structure_type': stype, 'planned_curve': 's_curve',
            'state': 'confirmed'}
    if st:
        st.write(vals)
    else:
        st = S.create(vals)
    IT[code] = st
    c = cat(ccode)
    ex = EL.search([('structure_id', '=', st.id), ('category_id', '=', c.id)], limit=1)
    if ex:
        ex.amount = ty * TY
    else:
        EL.create({'structure_id': st.id, 'category_id': c.id, 'amount': ty * TY})
env.cr.commit()
print('B1: %s khoi + %s hang muc bo mon OK' % (len(SUBZONES), len(ITEMS)))

# ── 3. BOQ theo item mới (tổng khớp khái toán item) ─────────────────────
BOQ = {
 'KB-NG': [('Cọc khoan nhồi D800', 'md', 2000, 3.2*TR), ('Ép cọc BTCT D500', 'md', 3200, 1.05*TR),
           ('Đào đất hố móng', 'm³', 22000, 180*K), ('Bê tông đài & giằng móng B25', 'm³', 2500, 2.45*TR),
           ('Cốt thép móng', 'tấn', 520, 17.5*TR), ('Chống thấm tầng hầm', 'm²', 2200, 480*K)],
 'KB-KC': [('Bê tông cột dầm sàn B30', 'm³', 12300, 2.55*TR), ('Cốt thép thân CB500V', 'tấn', 1420, 17.8*TR),
           ('Ván khuôn + giàn giáo', 'm²', 8000, 260*K), ('Xây tường block', 'm²', 6100, 210*K)],
 'KB-HT': [('Ốp lát gạch kháng khuẩn', 'm²', 26000, 620*K), ('Trần thạch cao + panel', 'm²', 24000, 450*K),
           ('Sơn kháng khuẩn', 'm²', 60000, 85*K), ('Cửa kỹ thuật + panel', 'bộ', 700, 12.5*TR),
           ('Vách compact + panel', 'm²', 10000, 950*K), ('Thiết bị vệ sinh', 'bộ', 380, 12.5*TR)],
 'KB-ME': [('Hệ thống điện & tủ phân phối', 'hệ', 1, 12*TY), ('Điều hòa không khí + thông gió', 'hệ', 1, 14*TY),
           ('Cấp thoát nước', 'hệ', 1, 6*TY), ('Thang máy', 'bộ', 4, 1.3*TY), ('PCCC sprinkler + báo cháy', 'hệ', 1, 2.8*TY)],
 'KB-KY': [('Nhánh oxy trung tâm', 'hệ', 1, 5*TY), ('Ổ khí đầu giường/phòng khám', 'bộ', 150, 20*TR), ('Hút chân không', 'hệ', 1, 2*TY)],
 'KB-TB': [('X-quang DR', 'bộ', 2, 3.5*TY), ('Siêu âm tổng quát', 'bộ', 10, 900*TR),
           ('Nội soi chẩn đoán', 'bộ', 2, 4.75*TY), ('Thiết bị phòng khám chuyên khoa', 'hệ', 1, 14.5*TY)],
 'NT-NG': [('Cọc khoan nhồi D1000', 'md', 3500, 3.2*TR), ('Ép cọc BTCT D600', 'md', 5000, 1.05*TR),
           ('Đào đất hố móng', 'm³', 36000, 180*K), ('Bê tông đài & giằng móng B25', 'm³', 4200, 2.45*TR),
           ('Cốt thép móng', 'tấn', 800, 17.5*TR), ('Chống thấm tầng hầm', 'm²', 5800, 480*K)],
 'NT-KC': [('Bê tông cột vách dầm sàn B30', 'm³', 24500, 2.55*TR), ('Cốt thép thân CB500V', 'tấn', 2850, 17.8*TR),
           ('Ván khuôn hệ nhôm', 'm²', 15000, 260*K), ('Xây tường block', 'm²', 13800, 210*K)],
 'NT-HT': [('Ốp lát gạch kháng khuẩn', 'm²', 36000, 620*K), ('Trần thạch cao + panel y tế', 'm²', 34000, 450*K),
           ('Sơn kháng khuẩn', 'm²', 90000, 85*K), ('Cửa buồng bệnh + kỹ thuật', 'bộ', 1100, 12.5*TR),
           ('Vách compact + panel', 'm²', 14000, 950*K), ('Thiết bị vệ sinh + tay vịn', 'bộ', 620, 12.5*TR)],
 'NT-MD': [('Vách kính unitized', 'm²', 16500, 2.1*TR), ('Lam chắn nắng nhôm', 'm²', 6200, 1.2*TR),
           ('Tấm ốp alu', 'm²', 4200, 700*K)],
 'NT-ME': [('Hệ thống điện & tủ tầng', 'hệ', 1, 18*TY), ('Điều hòa trung tâm + thông gió', 'hệ', 1, 20*TY),
           ('Cấp thoát nước', 'hệ', 1, 9*TY), ('Thang máy giường bệnh', 'bộ', 8, 1.3*TY), ('BMS', 'hệ', 1, 2.6*TY)],
 'NT-KY': [('Trạm oxy trung tâm + đường ống', 'hệ', 1, 14*TY), ('Hút chân không y tế', 'hệ', 1, 8*TY),
           ('Khí nén y tế', 'hệ', 1, 6*TY), ('Ổ khí đầu giường', 'bộ', 350, 20*TR)],
 'NT-TB': [('Monitor theo dõi bệnh nhân', 'bộ', 120, 150*TR), ('Giường bệnh + giường ICU', 'bộ', 500, 24*TR),
           ('Thiết bị khoa phòng nội trú', 'hệ', 1, 5*TY)],
 'CLS-XD': [('Kết cấu BTCT khối CLS', 'm³', 14500, 2.55*TR), ('Cốt thép', 'tấn', 1300, 17.8*TR),
            ('Móng & nền chống rung', 'm³', 2000, 2.45*TR)],
 'CLS-HT': [('Ốp chì phòng X-quang/CT', 'm²', 1200, 6.5*TR), ('Panel phòng sạch xét nghiệm', 'm²', 9000, 1.9*TR),
            ('Sàn vinyl kháng khuẩn', 'm²', 12000, 550*K), ('Trần panel', 'm²', 7800, 450*K)],
 'CLS-ME': [('Hệ thống điện + UPS thiết bị', 'hệ', 1, 10*TY), ('ĐHKK lọc HEPA', 'hệ', 1, 12*TY),
            ('Cấp thoát nước + xử lý', 'hệ', 1, 4*TY), ('PCCC khu thiết bị', 'hệ', 1, 4*TY)],
 'CLS-KY': [('Khí nén + oxy khu CLS', 'hệ', 1, 6*TY), ('Ổ khí', 'bộ', 100, 20*TR), ('Hút chân không', 'hệ', 1, 2*TY)],
 'CLS-TB': [('Máy cộng hưởng từ MRI 1.5T', 'bộ', 1, 28*TY), ('Máy CT 128 lát cắt', 'bộ', 2, 21*TY),
            ('X-quang DR', 'bộ', 6, 3.5*TY), ('Dây chuyền xét nghiệm sinh hóa – huyết học', 'hệ', 1, 22*TY),
            ('Siêu âm chuyên sâu', 'bộ', 12, 900*TR), ('Nội soi can thiệp', 'bộ', 4, 4.05*TY)],
 'PT-XD': [('Kết cấu & xây phòng mổ', 'm³', 12000, 2.55*TR), ('Hoàn thiện panel phòng mổ', 'm²', 9500, 1.9*TR),
           ('Sàn dẫn điện kháng khuẩn', 'm²', 6000, 1.06*TR)],
 'PT-ME': [('Phòng sạch & HVAC áp suất OT/ICU', 'hệ', 1, 18*TY), ('Điện UPS + IPS y tế', 'hệ', 1, 8*TY),
           ('Cấp thoát nước + xử lý', 'hệ', 1, 4*TY)],
 'PT-KY': [('Oxy + khí mê phòng mổ', 'hệ', 1, 9*TY), ('Hút trung tâm', 'hệ', 1, 6*TY),
           ('Khí nén y tế', 'hệ', 1, 4*TY), ('Pendant khí trần phòng mổ', 'bộ', 30, 100*TR)],
 'PT-TB': [('Phòng mổ hybrid', 'phòng', 1, 30*TY), ('Bàn mổ + đèn mổ', 'phòng', 8, 1.5*TY),
           ('Máy thở + monitor hồi sức', 'bộ', 40, 450*TR), ('C-arm di động', 'bộ', 2, 2.5*TY)],
 'HC-XD': [('Kết cấu + xây khối hành chính', 'm³', 18000, 2.55*TR), ('Hoàn thiện văn phòng – hậu cần', 'm²', 30000, 550*K),
           ('Mái + chống thấm', 'm²', 6000, 450*K)],
 'HC-ME': [('Điện + chiếu sáng', 'hệ', 1, 8*TY), ('ĐHKK', 'hệ', 1, 6*TY), ('Cấp thoát nước', 'hệ', 1, 4*TY)],
 'HC-TB': [('Dây chuyền tiệt khuẩn CSSD', 'hệ', 1, 8*TY), ('Hệ thống giặt là', 'hệ', 1, 4*TY),
           ('Bếp dinh dưỡng', 'hệ', 1, 3*TY)],
 'TN-XD': [('Xây dựng khoa truyền nhiễm (tách biệt)', 'm³', 8500, 2.55*TR), ('Hoàn thiện buồng cách ly', 'm²', 4400, 1.9*TR)],
 'TN-ME': [('HVAC áp lực âm buồng cách ly', 'hệ', 1, 7*TY), ('Điện nước độc lập', 'hệ', 1, 5*TY)],
 'TN-TB': [('Máy thở', 'bộ', 10, 450*TR), ('Monitor', 'bộ', 15, 150*TR), ('Thiết bị buồng cách ly', 'hệ', 1, 1.25*TY)],
}
OLD_KEYS = ['Phần ngầm & móng cọc', 'Kết cấu thân khối điều trị', 'Hoàn thiện kiến trúc',
            'Mặt đứng & vách kính', 'Cơ điện (MEP)', 'PCCC & chống sét',
            'Hệ thống khí y tế', 'Thiết bị y tế chuyên dụng']
old_items = S.search([('project_id', '=', proj.id), ('name', 'in', OLD_KEYS)])
BL.search([('structure_id', 'in', old_items.ids)]).unlink()
for code, lines in BOQ.items():
    st = IT[code]
    for seq, (desc, u, qty, price) in enumerate(lines, start=1):
        ex = BL.search([('structure_id', '=', st.id), ('description', '=', desc)], limit=1)
        vals = {'structure_id': st.id, 'category_id': EL.search(
                    [('structure_id', '=', st.id)], limit=1).category_id.id,
                'sequence': seq * 10, 'description': desc,
                'uom_id': uom(u).id, 'quantity': qty, 'unit_price': price}
        if ex:
            ex.write(vals)
        else:
            BL.create(vals)
env.cr.commit()
print('B2: BOQ moi cho %s item OK' % len(BOQ))

# ── 4. Re-link BBNT, lịch thi công, chi phí chung, HĐ ───────────────────
old = {n: S.search([('project_id', '=', proj.id), ('name', '=', n)], limit=1)
       for n in OLD_KEYS}
remap = {
    'Phần ngầm & móng cọc': IT['NT-NG'], 'Kết cấu thân khối điều trị': IT['NT-KC'],
    'Hoàn thiện kiến trúc': IT['NT-HT'], 'Mặt đứng & vách kính': IT['NT-MD'],
    'Cơ điện (MEP)': IT['NT-ME'], 'PCCC & chống sét': IT['NT-ME'],
    'Hệ thống khí y tế': IT['NT-KY'], 'Thiết bị y tế chuyên dụng': IT['NT-TB'],
}
AccL = env['rp.progress.acceptance.line']
Task = env['project.task']
for oname, new_st in remap.items():
    ost = old.get(oname)
    if not ost:
        continue
    if 'structure_id' in AccL._fields:
        AccL.search([('structure_id', '=', ost.id)]).write({'structure_id': new_st.id})
    Task.search([('rp_structure_id', '=', ost.id)]).write({'rp_structure_id': new_st.id})
cpc = S.search([('project_id', '=', proj.id), ('name', '=', 'Chi phí chung dự án')], limit=1)
if cpc:
    cpc.write({'subzone_id': sz['BVABC-CC'].id})

def link(cname, codes, extra_names=()):
    c = env['rp.contract'].search([('name', '=', cname)], limit=1)
    if not c:
        return
    ids = [IT[k].id for k in codes]
    for n in extra_names:
        r = S.search([('project_id', '=', proj.id), ('name', '=', n)], limit=1)
        if r:
            ids.append(r.id)
    c.write({'structure_ids': [(6, 0, ids)]})

link('HĐ Tổng thầu Xây dựng khối nhà chính',
     ['KB-NG', 'KB-KC', 'KB-HT', 'NT-NG', 'NT-KC', 'NT-HT', 'NT-MD',
      'CLS-XD', 'CLS-HT', 'PT-XD', 'HC-XD', 'TN-XD'])
link('HĐ Cơ điện MEP toàn công trình',
     ['KB-ME', 'NT-ME', 'CLS-ME', 'PT-ME', 'HC-ME', 'TN-ME',
      'KB-KY', 'NT-KY', 'CLS-KY', 'PT-KY'])
link('HĐ Cung cấp & lắp đặt Thiết bị y tế',
     ['KB-TB', 'NT-TB', 'CLS-TB', 'PT-TB', 'HC-TB', 'TN-TB'])
link('HĐ Hạ tầng kỹ thuật & cảnh quan', [],
     ('Hạ tầng kỹ thuật ngoài nhà', 'Cảnh quan & sân vườn'))
link('HĐ Sửa chữa Khoa Khám bệnh', ['KB-HT'])
env.cr.commit()
print('B3: re-link BBNT/lich/HD OK')

# ── 5. Xoá item bộ môn cũ + subzone KC ──────────────────────────────────
old_items = S.search([('project_id', '=', proj.id), ('name', 'in', OLD_KEYS)])
EL.search([('structure_id', 'in', old_items.ids)]).unlink()
BL.search([('structure_id', 'in', old_items.ids)]).unlink()
old_items.unlink()
szkc = SZ.search([('project_id', '=', proj.id), ('code', '=', 'BVABC-KC')], limit=1)
if szkc and not S.search_count([('subzone_id', '=', szkc.id)]):
    szkc.unlink()
env.cr.commit()
print('B4: xoa cay cu OK')

# ── 6. Tổng hợp ─────────────────────────────────────────────────────────
print('===== TONG HOP THEO KHOI =====')
tot = 0.0
for szc in ['BVABC-KB', 'BVABC-NT', 'BVABC-CLS', 'BVABC-PT', 'BVABC-HC',
            'BVABC-TN', 'BVABC-HT', 'BVABC-CC']:
    z = SZ.search([('project_id', '=', proj.id), ('code', '=', szc)], limit=1)
    items = S.search([('subzone_id', '=', z.id)])
    est = sum(EL.search([('structure_id', 'in', items.ids)]).mapped('amount'))
    boq = sum(BL.search([('structure_id', 'in', items.ids)]).mapped('amount'))
    tot += est
    print('%-14s | %2d hm | KT %8.1f ty | BOQ %8.2f ty' % (
        szc, len(items), est / TY, boq / TY))
print('TONG KHAI TOAN: %.1f ty' % (tot / TY))
