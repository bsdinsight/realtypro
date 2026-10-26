print('@@@BATDAU')
# Chuỗi và bậc đo do SCRIPT SEED tạo, không có xmlid → không xuất ra .po
# được. Ghi thẳng giá trị en_GB; ngữ cảnh lang='en_GB' chỉ đặt bản dịch,
# giữ nguyên en_US (bản gốc tiếng Việt).
BAN = {
    'eam.chain': {
        'Chuỗi đo DG123': 'DG123 metering chain',
        'Chuỗi đo chính': 'Main metering chain',
    },
    'eam.chain.node': {
        'Đầu ra tua-bin': 'Turbine output',
        'Thanh cái trạm nâng': 'Step-up substation busbar',
        'Sau máy biến áp nâng': 'After the step-up transformer',
        'Điểm đấu nối EVN': 'EVN connection point',
        'Đầu vào một chiều': 'DC input',
        'Đầu ra bộ biến tần': 'Inverter output',
        'Thanh cái trung thế': 'MV busbar',
        'Ranh giới giao nhận': 'Delivery point boundary',
        'Điện năng AC cho tỷ số hiệu suất': 'AC energy for the performance ratio',
        'Công-tơ bán điện': 'Sales meter',
        'Điện tự dùng': 'Auxiliary consumption',
        'Tiêu thụ ban đêm': 'Overnight consumption',
    },
}
dat = thieu = 0
for model, bang in BAN.items():
    for r in env[model].with_context(active_test=False).search([]):
        vi = r.with_context(lang='vi_VN').name
        if vi in bang:
            r.with_context(lang='en_GB').write({'name': bang[vi]})
            dat += 1
        else:
            thieu += 1
            print('!! chưa có bản dịch cho %r (%s)' % (vi, model))
env.cr.commit()
print('đặt %d bản dịch, thiếu %d' % (dat, thieu))
print('--- đọc lại ---')
for model in BAN:
    for r in env[model].with_context(active_test=False).search([]):
        print('  %-16s %-36r %r' % (model, r.with_context(lang='vi_VN').name,
                                    r.with_context(lang='en_GB').name))
