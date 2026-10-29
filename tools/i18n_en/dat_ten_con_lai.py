print('@@@BATDAU')
BANG = {
    ('stock.route', 11): 'PV50 Solar site store: Receive in 1 step (stock)',
    ('stock.route', 5):  'Savannakhet site store: Receive in 1 step (stock)',
    ('stock.route', 9):  'Wind Farm 123 site store: Receive in 1 step (stock)',
    ('stock.route', 2):  'AMI central store: Receive in 1 step (stock)',
    ('stock.route', 12): 'PV50 Solar site store: Deliver in 1 step (ship)',
    ('stock.route', 10): 'Wind Farm 123 site store: Deliver in 1 step (ship)',
    ('stock.route', 6):  'Savannakhet site store: Deliver in 1 step (ship)',
    ('stock.route', 3):  'AMI central store: Deliver in 1 step (ship)',
    ('stock.warehouse', 1): 'AMI central store',
    ('stock.warehouse', 2): 'Savannakhet site store',
    ('stock.warehouse', 4): 'Wind Farm 123 site store',
    ('stock.warehouse', 5): 'PV50 Solar site store',
    ('eam.season', 1): 'Savannakhet rainy season',
    ('eam.season', 5): 'Đắk Lắk dry season',
    ('eam.storage.care.plan', 3): 'Recharge the battery to 100%',
    ('eam.storage.care.plan', 5): 'Check the cradle, tarpaulin and support points',
    ('eam.storage.care.plan', 1): 'Turn the shaft in and out 10 times to spread the oil',
    ('eam.storage.care.plan', 2): 'Turn the rotor + measure insulation resistance',
    ('eam.storage.care.plan', 4): 'Check the seals, top up the preservation grease',
    ('eam.import.template', 1): 'Daily operations report — solar PV',
    ('eam.import.template', 7): 'SCADA export file — wind',
    ('eam.shift.note', 14): 'End-of-day work not finished',
    ('eam.shift.note', 3): 'Clean the station 05 control cabinet',
}
COT = {'eam.om.contract': 'title'}
dat = 0
for (mn, rid), en in BANG.items():
    r = env[mn].with_context(active_test=False).browse(rid)
    if not r.exists():
        print('!! %s#%s không còn' % (mn, rid)); continue
    col = COT.get(mn, 'name')
    if env[mn]._fields[col].translate:
        r.with_context(lang='en_GB').write({col: en})
    else:
        r.write({col: en})
    dat += 1
# hợp đồng O&M: tiêu đề theo mẫu
for rid, en in [(6, 'PV50 Solar operation & maintenance — 2026'),
                (3, 'Wind Farm 123 operation & maintenance — 2026')]:
    r = env['eam.om.contract'].browse(rid)
    if r.exists():
        r.write({'title': en}); dat += 1
env.cr.commit()
print('đã đặt %d tên' % dat)
