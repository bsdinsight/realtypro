import datetime
try:
    proj = env['re.project'].search([('code', '=', 'BVABC')], limit=1)
    ct = env['rp.contract'].search(
        [('name', '=', 'HĐ Tổng thầu Xây dựng khối nhà chính')], limit=1)
    anphu = env['res.partner'].search(
        [('name', '=', 'Tổng thầu Xây dựng An Phú')], limit=1)
    Diary = env['rp.site.diary']
    d1 = datetime.date(2026, 7, 13)
    if not Diary.search([('contract_id', '=', ct.id), ('date', '=', d1)]):
        Diary.create({
            'date': d1, 'project_id': proj.id, 'contract_id': ct.id,
            'weather_am': 'sunny', 'weather_pm': 'light_rain',
            'materials_note': 'Nhập 120 cọc BTCT D600 (đợt 3); '
                              '45 tấn thép CB500V; 2 xe bồn bê tông B25.',
            'issues': 'Khu vực trục 7-9 vướng đường ống nước ngầm hiện '
                      'trạng chưa di dời — chậm ép cọc phân khu B.',
            'instructions': 'TVGS yêu cầu bổ sung biện pháp che chắn '
                            'bụi phía cổng số 2 trước 16/07.',
            'manpower_ids': [
                (0, 0, {'contractor_id': anphu.id, 'trade': 'Đội ép cọc',
                        'headcount': 18}),
                (0, 0, {'contractor_id': anphu.id, 'trade': 'Đội cốt thép',
                        'headcount': 22}),
                (0, 0, {'contractor_id': anphu.id, 'trade': 'Trắc đạc + ATLĐ',
                        'headcount': 6}),
            ],
            'equipment_ids': [
                (0, 0, {'name': 'Robot ép cọc 860T', 'quantity': 2,
                        'status': 'working'}),
                (0, 0, {'name': 'Cẩu bánh xích 55T', 'quantity': 1,
                        'status': 'working'}),
                (0, 0, {'name': 'Máy toàn đạc điện tử', 'quantity': 2,
                        'status': 'working'}),
            ],
            'work_ids': [
                (0, 0, {'description': 'Ép cọc đại trà phân khu A — '
                                       'trục 1-6 khối Nội trú',
                        'progress_note': 'Ép 46 cọc D600 (lũy kế 512/1.250)'}),
                (0, 0, {'description': 'Gia công lồng thép cọc khoan nhồi',
                        'progress_note': '12 lồng D1000'}),
            ],
            'state': 'confirmed',
            'confirmed_by_id': 2, 'confirmed_date': '2026-07-13 11:30:00',
        })
    d2 = datetime.date(2026, 7, 14)
    if not Diary.search([('contract_id', '=', ct.id), ('date', '=', d2)]):
        Diary.create({
            'date': d2, 'project_id': proj.id, 'contract_id': ct.id,
            'weather_am': 'cloudy', 'weather_pm': 'sunny',
            'manpower_ids': [
                (0, 0, {'contractor_id': anphu.id, 'trade': 'Đội ép cọc',
                        'headcount': 20}),
                (0, 0, {'contractor_id': anphu.id, 'trade': 'Đội đào đất',
                        'headcount': 15}),
            ],
            'equipment_ids': [
                (0, 0, {'name': 'Robot ép cọc 860T', 'quantity': 2,
                        'status': 'working'}),
                (0, 0, {'name': 'Máy đào PC200', 'quantity': 3,
                        'status': 'working'}),
                (0, 0, {'name': 'Xe ben 15T', 'quantity': 8,
                        'status': 'working'}),
            ],
            'work_ids': [
                (0, 0, {'description': 'Ép cọc đại trà phân khu A (tiếp)',
                        'progress_note': 'Ép 52 cọc D600 (lũy kế 564/1.250)'}),
                (0, 0, {'description': 'Đào đất hố móng phân khu A — lớp 1',
                        'progress_note': '2.800 m³ vận chuyển đổ thải'}),
            ],
            'state': 'submitted',
        })
    Punch = env['rp.site.punch']
    st_ng = env['rp.structure'].search(
        [('project_id', '=', proj.id), ('code', '=', 'NT-NG')], limit=1)
    punches = [
        ('Cọc P-A0512 ép lệch tim 45mm vượt dung sai', 'critical',
         'Phân khu A, trục 3-B', '2026-07-18', 'open',
         'Lệch tim 45mm > dung sai 20mm theo TCVN 9394. Yêu cầu tư vấn '
         'thiết kế đánh giá, có thể phải ép cọc bù.'),
        ('Lồng thép cọc nhồi thiếu con kê bảo vệ', 'major',
         'Bãi gia công lồng thép', '2026-07-16', 'in_progress',
         ' 4/12 lồng kiểm tra thiếu con kê bê tông — nguy cơ lớp bảo vệ '
         'không đạt 50mm.'),
        ('Rào chắn hố móng phân khu A hư hỏng đoạn 12m', 'minor',
         'Hố móng phân khu A, phía Nam', '2026-07-15', 'fixed',
         'Đã dựng lại rào + biển cảnh báo, chờ TVGS nghiệm thu lại.'),
    ]
    for name, sev, loc, dl, state, desc in punches:
        if not Punch.search([('name', '=', name)]):
            vals = {'name': name, 'project_id': proj.id,
                    'contract_id': ct.id, 'structure_id': st_ng.id,
                    'responsible_id': anphu.id, 'severity': sev,
                    'location': loc, 'deadline': dl, 'state': state,
                    'description': desc}
            if state == 'fixed':
                vals['fixed_date'] = '2026-07-14'
            Punch.create(vals)
    Insp = env['rp.site.safety.inspection']
    if not Insp.search([('project_id', '=', proj.id)]):
        Insp.create({
            'date': d1, 'project_id': proj.id, 'contract_id': ct.id,
            'result': 'pass_note', 'state': 'done',
            'line_ids': [
                (0, 0, {'name': 'PPE — mũ, giày, áo phản quang', 'result': 'ok'}),
                (0, 0, {'name': 'Rào chắn hố móng, biển cảnh báo',
                        'result': 'not_ok',
                        'note': 'Hư 12m phía Nam — đã lập punch PL'}),
                (0, 0, {'name': 'Kiểm định robot ép cọc còn hiệu lực', 'result': 'ok'}),
                (0, 0, {'name': 'Điện thi công — tủ RCD, dây treo cao', 'result': 'ok'}),
            ],
            'findings': 'Rào chắn hố móng phía Nam hỏng 12m — chuyển '
                        'punch list theo dõi khắc phục.'})
    Tb = env['rp.site.toolbox']
    if not Tb.search([('project_id', '=', proj.id)]):
        Tb.create({'name': 'An toàn ép cọc & làm việc cạnh hố sâu',
                   'date': d2, 'project_id': proj.id, 'contract_id': ct.id,
                   'contractor_id': anphu.id, 'attendee_count': 41,
                   'notes': 'Phổ biến khoảng cách an toàn quanh robot ép '
                            'cọc; quy định lên xuống hố móng bằng thang '
                            'chuyên dụng; ký cam kết ATLĐ đầu tuần.'})
    Inc = env['rp.site.incident']
    if not Inc.search([('project_id', '=', proj.id)]):
        Inc.create({'name': 'Xe ben lùi sát mép hố móng — near-miss',
                    'date': '2026-07-13 08:40:00', 'project_id': proj.id,
                    'contract_id': ct.id, 'incident_type': 'near_miss',
                    'location': 'Hố móng phân khu A, phía Nam',
                    'people_involved': 'Lái xe ben BKS 29H-xxx.xx',
                    'description': 'Xe ben lùi đổ đất sát mép hố móng tại '
                                   'đoạn rào chắn hỏng, cách mép 0,5m.',
                    'immediate_action': 'Dừng xe, cắm cọc tiêu tạm, bố trí '
                                        'người xi nhan.',
                    'corrective_action': 'Sửa rào chắn (punch PL); quy định '
                                         'xe đổ đất cách mép hố ≥ 2m; kẻ '
                                         'vạch giới hạn.',
                    'state': 'investigating'})
    env.cr.commit()
    print('SEED SITE OK: diary=%s punch=%s insp=%s toolbox=%s incident=%s'
          % (Diary.search_count([('project_id', '=', proj.id)]),
             Punch.search_count([('project_id', '=', proj.id)]),
             Insp.search_count([('project_id', '=', proj.id)]),
             Tb.search_count([('project_id', '=', proj.id)]),
             Inc.search_count([('project_id', '=', proj.id)])))
    # smoke quyền user thường (nghiant uid 5)
    u = env['rp.site.diary'].with_user(5)
    assert u.env.su is False
    print('ACL user5 read:', u.search_count([]) >= 0)
except Exception as e:
    env.cr.rollback()
    import traceback
    print('FAIL:', traceback.format_exc().splitlines()[-1])
