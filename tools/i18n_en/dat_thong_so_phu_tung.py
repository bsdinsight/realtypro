# -*- coding: utf-8 -*-
"""Bản tiếng Anh cho THÔNG SỐ KỸ THUẬT phụ tùng (`eam.part.spec`).

Ba cột đều ghi: tên thông số, giá trị, đơn vị. Cột `value` phải ghi
không phải vì nó có chữ ("Sợi thuỷ tinh + carbon"), mà vì **dấu phân
cách số**: bản Việt viết `1.800 mm`, người đọc tiếng Anh hiểu là
1,8 mm — sai một nghìn lần trên đường kính ổ trục chính, và sai êm ru.

Trường `product.template.eam_spec_key` là trường TÍNH gom các thông số
đã đánh dấu "quyết định" để hiện ngay trên danh sách. Không ghi thẳng
vào nó: ghi nguồn rồi gọi tính lại, nếu không lần tính sau sẽ đạp lên.
"""
print('@@@BATDAU')

# id: (tên EN, giá trị EN, đơn vị EN)
B = {
    41: ('Voltage', '24', 'V'),
    42: ('Capacity', '60', 'Ah'),
    43: ('Number of axes', '3', ''),
    9:  ('Power', '6,500', 'kVA'),
    10: ('DC-link voltage', '1,100', 'V'),
    11: ('Protection class', 'IP54', ''),
    29: ('Filtration rating', '10', 'µm'),
    30: ('Flow rate', '120', 'l/min'),
    50: ('Power', '3', 'kVA'),
    51: ('Backup time', '30', 'minutes'),
    52: ('Pressure', '220', 'bar'),
    53: ('Flow rate', '18', 'l/min'),
    36: ('Measuring range', '0 … 360', '°'),
    37: ('Output signal', '4-20', 'mA'),
    33: ('Measuring range', '0 … 75', 'm/s'),
    34: ('Output signal', '4-20', 'mA'),
    35: ('De-icing heater', 'Yes', ''),
    20: ('Length', '82', 'm'),
    21: ('Mass', '24,800', 'kg'),
    22: ('Material', 'Glass fibre + carbon', ''),
    56: ('Brushes per set', '12', 'pcs'),
    57: ('Material', 'Graphite carbon', ''),
    23: ('Viscosity', 'ISO VG 320', ''),
    24: ('Standard', 'DIN 51517-3 CLP', ''),
    25: ('Pour point', '-42', '°C'),
    26: ('Viscosity index', '≥ 160', ''),
    1:  ('Gear ratio', '1:119.3', ''),
    2:  ('Transmitted power', '6,240', 'kW'),
    3:  ('Oil type', 'ISO VG 320 synthetic', ''),
    4:  ('Mass', '18,500', 'kg'),
    31: ('Filtration rating', '5', 'µm'),
    32: ('Working pressure', '210', 'bar'),
    38: ('Pads per set', '6', 'pcs'),
    39: ('New thickness', '25', 'mm'),
    40: ('Minimum thickness', '8', 'mm'),
    12: ('Power', '7', 'MVA'),
    13: ('Transformation ratio', '6.6/33', 'kV'),
    14: ('Vector group', 'Dyn11', ''),
    15: ('Short-circuit voltage', '8', '%'),
    5:  ('Power', '6,240', 'kW'),
    6:  ('Voltage', '690', 'V'),
    7:  ('Insulation class', 'F', ''),
    8:  ('Rated speed', '1,200', 'rpm'),
    27: ('Type', 'Lithium complex EP2', ''),
    28: ('Temperature range', '-30 … +140', '°C'),
    44: ('Power', '0.75', 'kW'),
    45: ('Gearbox ratio', '1:1,600', ''),
    16: ('Inner diameter', '1,800', 'mm'),
    17: ('Outer diameter', '2,300', 'mm'),
    18: ('Width', '375', 'mm'),
    19: ('Dynamic load rating', '12,500', 'kN'),
    46: ('Protection type', 'Distance 21', ''),
    47: ('Auxiliary voltage', '110', 'VDC'),
    48: ('Fibre ports', '8', ''),
    49: ('Standard', '1000Base-LX', ''),
    54: ('Signal rings', '24', ''),
    55: ('Power rings', '6', ''),
}

S = env['eam.part.spec']
thieu = [i for i in B if not S.browse(i).exists()]
if thieu:
    print('!! không còn bản ghi:', thieu)
con = [r.id for r in S.search([]) if r.id not in B]
if con:
    print('!! bản ghi CHƯA có bản dịch:', con)

dat = 0
for rid, (ten, gt, dv) in B.items():
    r = S.browse(rid)
    if not r.exists():
        continue
    r.with_context(lang='en_GB').write(
        {'name': ten, 'value': gt, 'uom_label': dv or False})
    dat += 1
env.cr.commit()
print('đã đặt %d thông số' % dat)

# Bắt trường tính gom lại dưới ngữ cảnh en_GB.
P = env['product.template'].with_context(lang='en_GB')
rs = P.search([('eam_spec_ids', '!=', False)])
rs.invalidate_recordset(['eam_spec_key'])
rs._compute_spec_key()
env.cr.commit()
print('đã tính lại Thông số quyết định cho %d phụ tùng' % len(rs))
for p in rs[:4]:
    print('   %-34s %s' % (p.name[:34], p.eam_spec_key))
