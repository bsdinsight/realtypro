# -*- coding: utf-8 -*-
"""Seed BOQ chi tiết (rp.boq.line) cho 10 hạng mục dự án BVABC trên dev.
Tổng BOQ mỗi hạng mục ≈ khái toán của hạng mục đó (chuỗi số liệu nhất quán).
Idempotent theo (structure, description). Chạy: odoo shell -d dev < file.
"""
TY = 1_000_000_000.0
TR = 1_000_000.0
K = 1_000.0

proj = env['re.project'].search([('code', '=', 'BVABC')], limit=1)
assert proj, 'Chua co du an BVABC'

UOM = env['rp.progress.uom']
_uom_cache = {}
def uom(name):
    if name not in _uom_cache:
        r = UOM.search([('name', '=', name)], limit=1)
        if not r:
            vals = {'name': name}
            if 'code' in UOM._fields:
                vals['code'] = name
            r = UOM.create(vals)
        _uom_cache[name] = r
    return _uom_cache[name]

def cat(code):
    return env['rp.cost.category'].search(
        [('project_id', '=', proj.id), ('code', '=', code)], limit=1)

S = env['rp.structure']
L = env['rp.boq.line']

# hạng mục -> (cat_code, [(đầu việc, ĐVT, KL, đơn giá)])
BOQ = {
    'Phần ngầm & móng cọc': ('3', [
        ('Cọc khoan nhồi D1000 (kể cả bentonite, hạ lồng thép)', 'md', 8400, 3.2 * TR),
        ('Ép cọc BTCT D600 đại trà', 'md', 12000, 1.05 * TR),
        ('Đào đất hố móng, vận chuyển đổ thải', 'm³', 85000, 180 * K),
        ('Bê tông đài móng & giằng móng B25', 'm³', 9500, 2.45 * TR),
        ('Cốt thép móng CB400V/CB500V', 'tấn', 1900, 17.5 * TR),
        ('Chống thấm vách + đáy tầng hầm', 'm²', 18000, 480 * K),
    ]),
    'Kết cấu thân khối điều trị': ('3', [
        ('Bê tông cột, vách, dầm, sàn B30', 'm³', 62000, 2.55 * TR),
        ('Cốt thép kết cấu thân CB500V', 'tấn', 7100, 17.8 * TR),
        ('Ván khuôn hệ nhôm + giàn giáo', 'm²', 26000, 260 * K),
        ('Xây tường gạch block bê tông khí', 'm²', 42000, 210 * K),
    ]),
    'Hoàn thiện kiến trúc': ('3', [
        ('Ốp lát gạch kháng khuẩn khu điều trị', 'm²', 95000, 620 * K),
        ('Trần thạch cao + trần panel y tế', 'm²', 88000, 450 * K),
        ('Sơn nước + sơn kháng khuẩn', 'm²', 210000, 85 * K),
        ('Cửa panel phòng sạch + cửa gỗ kỹ thuật', 'bộ', 2400, 12.5 * TR),
        ('Vách ngăn compact + panel kháng khuẩn', 'm²', 36000, 950 * K),
        ('Thiết bị vệ sinh (lavabo, bồn cầu, tay vịn y tế)', 'bộ', 1550, 12.5 * TR),
    ]),
    'Mặt đứng & vách kính': ('3', [
        ('Vách kính unitized + khung nhôm', 'm²', 22000, 2.1 * TR),
        ('Lam chắn nắng nhôm định hình', 'm²', 8000, 1.2 * TR),
        ('Tấm ốp nhôm alu mặt đứng', 'm²', 6000, 700 * K),
    ]),
    'Cơ điện (MEP)': ('3', [
        ('Hệ thống điện động lực + tủ phân phối', 'hệ', 1, 48 * TY),
        ('Điều hòa trung tâm Chiller/VRV + thông gió', 'hệ', 1, 52 * TY),
        ('Hệ thống cấp thoát nước trong nhà', 'hệ', 1, 24 * TY),
        ('Thang máy bệnh viện (giường bệnh + khách)', 'bộ', 12, 2.2 * TY),
        ('Hệ thống quản lý tòa nhà BMS', 'hệ', 1, 9.6 * TY),
    ]),
    'PCCC & chống sét': ('3', [
        ('Hệ sprinkler + bơm chữa cháy + họng nước', 'hệ', 1, 22 * TY),
        ('Báo cháy địa chỉ toàn công trình', 'hệ', 1, 12 * TY),
        ('Chống sét lan truyền + tiếp địa', 'hệ', 1, 6 * TY),
    ]),
    'Hệ thống khí y tế': ('4', [
        ('Trạm oxy trung tâm + đường ống', 'hệ', 1, 34 * TY),
        ('Hệ thống hút chân không y tế', 'hệ', 1, 18 * TY),
        ('Hệ thống khí nén y tế', 'hệ', 1, 14 * TY),
        ('Ổ khí đầu giường (oxy/hút/khí nén)', 'bộ', 700, 20 * TR),
    ]),
    'Thiết bị y tế chuyên dụng': ('4', [
        ('Máy cộng hưởng từ MRI 1.5T', 'bộ', 1, 28 * TY),
        ('Máy CT 128 lát cắt', 'bộ', 2, 21 * TY),
        ('X-quang kỹ thuật số DR', 'bộ', 6, 3.5 * TY),
        ('Phòng mổ hybrid (đèn, bàn mổ, tháp phẫu thuật)', 'phòng', 2, 45 * TY),
        ('Monitor + máy thở hồi sức', 'bộ', 180, 450 * TR),
        ('Hệ thống nội soi chẩn đoán + can thiệp', 'bộ', 8, 4.75 * TY),
    ]),
    'Hạ tầng kỹ thuật ngoài nhà': ('5', [
        ('Đường nội bộ + sân bãi bê tông nhựa', 'm²', 45000, 850 * K),
        ('Cấp thoát nước ngoài nhà', 'md', 12000, 1.8 * TR),
        ('Trạm biến áp 2×2000kVA + máy phát dự phòng', 'trạm', 2, 7.5 * TY),
        ('Chiếu sáng ngoài nhà', 'bộ', 420, 18 * TR),
        ('Trạm xử lý nước thải y tế 500m³/ngđ', 'trạm', 1, 7.59 * TY),
    ]),
    'Cảnh quan & sân vườn': ('6', [
        ('Cây xanh bóng mát + cây cảnh', 'cây', 1200, 4.5 * TR),
        ('Thảm cỏ + vườn trị liệu', 'm²', 25000, 620 * K),
        ('Tiểu cảnh, ghế nghỉ, mái che lối đi', 'hệ', 1, 9.1 * TY),
    ]),
}

created = updated = 0
for sname, (ccode, lines) in BOQ.items():
    st = S.search([('project_id', '=', proj.id), ('name', '=', sname)], limit=1)
    c = cat(ccode)
    if not st or not c:
        print('BO QUA (thieu hang muc/nhom):', sname)
        continue
    for seq, (desc, u, qty, price) in enumerate(lines, start=1):
        vals = {'structure_id': st.id, 'category_id': c.id,
                'sequence': seq * 10, 'description': desc,
                'uom_id': uom(u).id, 'quantity': qty, 'unit_price': price}
        ex = L.search([('structure_id', '=', st.id),
                       ('description', '=', desc)], limit=1)
        if ex:
            ex.write(vals)
            updated += 1
        else:
            L.create(vals)
            created += 1
env.cr.commit()

print('BOQ SEED OK: %s dong moi, %s cap nhat' % (created, updated))
print('%-32s %14s %14s' % ('HANG MUC', 'BOQ (ty)', 'KHAI TOAN (ty)'))
total = 0.0
for sname in BOQ:
    st = S.search([('project_id', '=', proj.id), ('name', '=', sname)], limit=1)
    if not st:
        continue
    boq = sum(L.search([('structure_id', '=', st.id)]).mapped('amount'))
    est = sum(env['rp.structure.estimate.line'].search(
        [('structure_id', '=', st.id)]).mapped('amount'))
    total += boq
    print('%-32s %14.2f %14.2f' % (sname[:32], boq / TY, est / TY))
print('TONG BOQ: %.2f ty' % (total / TY))
