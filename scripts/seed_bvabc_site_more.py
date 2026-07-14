# -*- coding: utf-8 -*-
"""Top-up Site Management BVABC lên 10 bản ghi mỗi model.
Chạy SAU seed_bvabc_site.py. Idempotent theo tên/ngày. User = admin(2).
"""
import datetime

D = datetime.date
ADMIN = 2

try:
    proj = env['re.project'].search([('code', '=', 'BVABC')], limit=1)
    def contract(name_part):
        return env['rp.contract'].search(
            [('project_id', '=', proj.id), ('name', 'ilike', name_part)],
            limit=1)
    ct_tt = contract('Tổng thầu')
    ct_mep = contract('Cơ điện MEP')
    ct_ht = contract('Hạ tầng')
    anphu = env['res.partner'].search([('name', '=', 'Tổng thầu Xây dựng An Phú')], limit=1)
    minhlong = env['res.partner'].search([('name', '=', 'Công ty Cơ điện Minh Long')], limit=1)
    binhminh = env['res.partner'].search([('name', '=', 'Công ty CP Xây lắp Bình Minh')], limit=1)
    st = lambda code: env['rp.structure'].search(
        [('project_id', '=', proj.id), ('code', '=', code)], limit=1)

    # ── 1. Nhật ký (+8 → 10) ───────────────────────────────────────────
    Diary = env['rp.site.diary']
    diaries = [
        # (contract, date, wam, wpm, state, manpower[(partner,trade,n)], equip[(name,qty,status)], works[(desc,note)])
        (ct_tt, D(2026, 7, 6), 'sunny', 'sunny', 'confirmed',
         [(anphu, 'Đội trắc đạc', 6), (anphu, 'Đội chuẩn bị mặt bằng', 14)],
         [('Máy toàn đạc điện tử', 2, 'working'), ('Máy ủi D5', 1, 'working')],
         [('Định vị tim cọc phân khu A khối Nội trú', '184 tim cọc'),
          ('San gạt đường công vụ nội bộ', '450 md')]),
        (ct_tt, D(2026, 7, 7), 'sunny', 'cloudy', 'confirmed',
         [(anphu, 'Đội ép cọc', 16), (anphu, 'Đội trắc đạc', 4)],
         [('Robot ép cọc 860T', 1, 'working'), ('Cẩu bánh xích 55T', 1, 'working')],
         [('Ép cọc thử P-TN01..P-TN04 khối Nội trú', '4 cọc thử D600'),
          ('Lắp dựng hàng rào + cổng công trường số 2', 'Hoàn thành 100%')]),
        (ct_tt, D(2026, 7, 8), 'light_rain', 'light_rain', 'confirmed',
         [(anphu, 'Đội ép cọc', 12), (anphu, 'Đội cốt thép', 18)],
         [('Robot ép cọc 860T', 1, 'idle'), ('Máy cắt uốn thép', 4, 'working')],
         [('Dừng ép cọc 2h do mưa — bảo dưỡng robot', 'An toàn thiết bị'),
          ('Gia công lồng thép cọc nhồi D1000', '8 lồng')]),
        (ct_tt, D(2026, 7, 9), 'cloudy', 'sunny', 'confirmed',
         [(anphu, 'Đội ép cọc', 18), (anphu, 'Đội khoan nhồi', 10)],
         [('Robot ép cọc 860T', 2, 'working'), ('Máy khoan nhồi SR-285', 1, 'working')],
         [('Ép cọc đại trà phân khu A', 'Ép 38 cọc D600 (lũy kế 380)'),
          ('Khoan nhồi trụ TN-C1, TN-C2', '2 cọc D1000, sâu 42m')]),
        (ct_tt, D(2026, 7, 10), 'sunny', 'sunny', 'confirmed',
         [(anphu, 'Đội ép cọc', 20), (anphu, 'Đội khoan nhồi', 12), (anphu, 'ATLĐ', 4)],
         [('Robot ép cọc 860T', 2, 'working'), ('Máy khoan nhồi SR-285', 1, 'working'),
          ('Xe bồn bê tông', 6, 'working')],
         [('Ép cọc đại trà phân khu A', 'Ép 44 cọc (lũy kế 424)'),
          ('Đổ bê tông cọc nhồi TN-C1', '68 m³ B30')]),
        (ct_tt, D(2026, 7, 11), 'sunny', 'heavy_rain', 'confirmed',
         [(anphu, 'Đội ép cọc', 20), (anphu, 'Đội đào đất', 8)],
         [('Robot ép cọc 860T', 2, 'working'), ('Máy đào PC200', 2, 'working')],
         [('Ép cọc đại trà phân khu A', 'Ép 42 cọc (lũy kế 466) — chiều dừng do mưa to'),
          ('Đào mở móng khu thang máy', '600 m³')]),
        (ct_mep, D(2026, 7, 13), 'sunny', 'light_rain', 'confirmed',
         [(minhlong, 'Đội ống chờ', 9), (minhlong, 'Đội khảo sát shopdrawing', 4)],
         [('Máy hàn ống', 3, 'working'), ('Máy khoan rút lõi', 2, 'working')],
         [('Đặt ống chờ điện + nước xuyên đài móng', '96 vị trí phân khu A'),
          ('Trình shopdrawing tuyến ống trục kỹ thuật', 'Nộp TVGS đợt 1')]),
        (ct_ht, D(2026, 7, 13), 'sunny', 'sunny', 'submitted',
         [(binhminh, 'Đội san nền', 11), (binhminh, 'Đội thoát nước', 7)],
         [('Máy ủi D5', 1, 'working'), ('Lu rung 12T', 2, 'working'),
          ('Máy đào PC120', 1, 'broken')],
         [('San nền khu bãi xe + đường vành đai', '3.200 m²'),
          ('Lắp cống hộp thoát nước D800 tuyến N1', '84 md')]),
    ]
    n_d = 0
    for ct, dt, wam, wpm, state, mans, eqs, works in diaries:
        if Diary.search([('contract_id', '=', ct.id), ('date', '=', dt)]):
            continue
        vals = {
            'date': dt, 'project_id': proj.id, 'contract_id': ct.id,
            'weather_am': wam, 'weather_pm': wpm, 'user_id': ADMIN,
            'state': state,
            'manpower_ids': [(0, 0, {'contractor_id': p.id, 'trade': t,
                                     'headcount': n}) for p, t, n in mans],
            'equipment_ids': [(0, 0, {'name': nm, 'quantity': q,
                                      'status': s}) for nm, q, s in eqs],
            'work_ids': [(0, 0, {'description': d, 'progress_note': pn})
                         for d, pn in works],
        }
        if state == 'confirmed':
            vals.update({'confirmed_by_id': ADMIN,
                         'confirmed_date': str(dt) + ' 11:00:00'})
        Diary.create(vals)
        n_d += 1

    # ── 2. Punch (+7 → 10) ─────────────────────────────────────────────
    Punch = env['rp.site.punch']
    punches = [
        ('Ống chờ xuyên đài sai cao độ trục 5-6', ct_mep, minhlong, 'NT-ME',
         'major', 'Phân khu A, trục 5-6', D(2026, 7, 20), 'in_progress',
         'Sai cao độ 60mm so shopdrawing đã duyệt — phải đục xử lý trước khi đổ bê tông đài.', None, None),
        ('Mối hàn lồng thép không đủ chiều dài neo', ct_tt, anphu, 'NT-NG',
         'major', 'Bãi gia công lồng thép', D(2026, 7, 17), 'open',
         'Kiểm tra xác suất 3/10 mối nối hàn < 10d theo TCVN. Yêu cầu hàn bổ sung toàn bộ lô.', None, None),
        ('Bê tông lót móng rỗ tổ ong cục bộ', ct_tt, anphu, 'NT-NG',
         'minor', 'Hố móng khu thang máy', D(2026, 7, 11), 'closed',
         'Rỗ cục bộ 0,4 m² — đục tẩy, vệ sinh, đổ bù vữa không co ngót.',
         D(2026, 7, 10), D(2026, 7, 12)),
        ('Cẩu bánh xích hết hạn dán tem kiểm định', ct_tt, anphu, 'NT-NG',
         'major', 'Khu ép cọc phân khu A', D(2026, 7, 14), 'fixed',
         'Tem kiểm định hết hạn 05/07 — dừng thiết bị, xuất trình giấy kiểm định mới + dán tem.',
         D(2026, 7, 13), None),
        ('Đèn chiếu sáng tạm bãi thép hỏng 4 bộ', ct_tt, anphu, 'NT-NG',
         'minor', 'Bãi gia công thép', D(2026, 7, 10), 'closed',
         'Thay 4 bộ đèn pha LED 200W, bổ sung 2 bộ dự phòng.',
         D(2026, 7, 9), D(2026, 7, 10)),
        ('Màng chống thấm không đúng chủng loại phê duyệt', ct_tt, anphu, 'NT-NG',
         'critical', 'Kho vật tư công trường', D(2026, 7, 12), 'open',
         'Lô màng khò nóng 3mm nhập về khác mã đã duyệt trong trình mẫu — dừng nhập kho, chờ đổi trả.', None, None),
        ('Tủ điện thi công thiếu RCD chống giật', ct_mep, minhlong, 'NT-ME',
         'critical', 'Tủ điện tạm T3 — khu khoan nhồi', D(2026, 7, 12), 'in_progress',
         'Tủ T3 đấu tạm không qua RCD 30mA — cắt điện tủ, lắp bổ sung ngay.', None, None),
    ]
    n_p = 0
    for name, ct, resp, stc, sev, loc, dl, state, desc, fx, cl in punches:
        if Punch.search([('name', '=', name)]):
            continue
        vals = {'name': name, 'project_id': proj.id, 'contract_id': ct.id,
                'structure_id': st(stc).id if st(stc) else False,
                'responsible_id': resp.id, 'severity': sev, 'location': loc,
                'deadline': dl, 'state': state, 'description': desc,
                'assigned_user_id': ADMIN}
        if fx:
            vals['fixed_date'] = fx
        if cl:
            vals['closed_date'] = cl
        Punch.create(vals)
        n_p += 1

    # ── 3. Kiểm tra an toàn (+9 → 10) ──────────────────────────────────
    Insp = env['rp.site.safety.inspection']
    LINES_STD = [
        'PPE — mũ, giày, áo phản quang', 'Rào chắn hố móng, biển cảnh báo',
        'Điện thi công — tủ RCD, dây treo cao', 'Kiểm định thiết bị nâng',
        'Vệ sinh công trường, lối đi thông thoáng']
    insps = [
        (D(2026, 7, 1), ct_tt, 'pass', 'done', {}),
        (D(2026, 7, 3), ct_tt, 'pass_note', 'done',
         {'Vệ sinh công trường, lối đi thông thoáng':
          ('not_ok', 'Thép vụn rơi vãi lối đi bãi gia công')}),
        (D(2026, 7, 5), ct_tt, 'pass', 'done', {}),
        (D(2026, 7, 7), ct_tt, 'fail', 'done',
         {'Điện thi công — tủ RCD, dây treo cao':
          ('not_ok', 'Dây điện rải sát mặt đất khu ép cọc'),
          'PPE — mũ, giày, áo phản quang':
          ('not_ok', '3 công nhân không cài quai mũ')}),
        (D(2026, 7, 8), ct_tt, 'pass_note', 'done',
         {'Kiểm định thiết bị nâng':
          ('not_ok', 'Cẩu bánh xích tem kiểm định hết hạn — lập punch')}),
        (D(2026, 7, 9), ct_mep, 'pass', 'done', {}),
        (D(2026, 7, 10), ct_tt, 'pass', 'done', {}),
        (D(2026, 7, 11), ct_ht, 'pass_note', 'done',
         {'Rào chắn hố móng, biển cảnh báo':
          ('not_ok', 'Thiếu biển cảnh báo tuyến đào cống N1')}),
        (D(2026, 7, 14), ct_mep, 'pass', 'draft', {}),
    ]
    n_i = 0
    for dt, ct, result, state, overrides in insps:
        if Insp.search([('date', '=', dt), ('contract_id', '=', ct.id)]):
            continue
        lines = []
        finds = []
        for ln in LINES_STD:
            res, note = overrides.get(ln, ('ok', False))
            lines.append((0, 0, {'name': ln, 'result': res,
                                 'note': note or False}))
            if res == 'not_ok':
                finds.append(note)
        Insp.create({'date': dt, 'project_id': proj.id,
                     'contract_id': ct.id, 'inspector_id': ADMIN,
                     'result': result, 'state': state,
                     'line_ids': lines,
                     'findings': '; '.join(finds) if finds else False})
        n_i += 1

    # ── 4. Toolbox (+9 → 10) ───────────────────────────────────────────
    Tb = env['rp.site.toolbox']
    tbs = [
        (D(2026, 7, 1), ct_tt, anphu, 'Nội quy công trường & PPE bắt buộc', 52),
        (D(2026, 7, 3), ct_tt, anphu, 'An toàn điện thi công mùa mưa', 47),
        (D(2026, 7, 6), ct_tt, anphu, 'An toàn thiết bị nâng — cẩu bánh xích', 44),
        (D(2026, 7, 7), ct_mep, minhlong, 'An toàn hàn cắt — phòng cháy', 18),
        (D(2026, 7, 8), ct_tt, anphu, 'Làm việc trong mưa bão — quy trình dừng việc', 40),
        (D(2026, 7, 9), ct_ht, binhminh, 'An toàn máy lu, máy ủi — người xi nhan', 22),
        (D(2026, 7, 10), ct_tt, anphu, 'Chống say nắng, bố trí nước uống điểm nghỉ', 46),
        (D(2026, 7, 11), ct_mep, minhlong, 'Khóa an toàn tủ điện — LOTO cơ bản', 16),
        (D(2026, 7, 13), ct_ht, binhminh, 'An toàn đào hào sâu — chống sạt vách', 20),
    ]
    n_t = 0
    for dt, ct, ctr, topic, att in tbs:
        if Tb.search([('date', '=', dt), ('contract_id', '=', ct.id)]):
            continue
        Tb.create({'name': topic, 'date': dt, 'project_id': proj.id,
                   'contract_id': ct.id, 'contractor_id': ctr.id,
                   'presenter_id': ADMIN, 'attendee_count': att,
                   'notes': 'Phổ biến đầu giờ, toàn bộ công nhân ký danh sách tham dự.'})
        n_t += 1

    # ── 5. Sự cố (+9 → 10) ─────────────────────────────────────────────
    Inc = env['rp.site.incident']
    incs = [
        ('Vấp dây điện rải sát đất khu ép cọc', '2026-07-07 09:15:00', ct_tt,
         'near_miss', 'Khu ép cọc phân khu A', 'Công nhân đội ép cọc',
         'Công nhân vấp dây nguồn robot ép cọc, không ngã.',
         'Treo cao dây nguồn lên giá đỡ.', 'Chuẩn hóa tuyến dây nguồn thiết bị; đưa vào checklist kiểm tra.', 'closed'),
        ('Vật rơi từ lồng thép khi cẩu chuyển', '2026-07-08 14:20:00', ct_tt,
         'near_miss', 'Bãi gia công lồng thép', 'Đội cốt thép',
         'Con kê rơi từ lồng thép đang cẩu, rơi cách công nhân 1,5m.',
         'Dừng cẩu, kiểm tra buộc chằng.', 'Quy định buộc chằng phụ kiện trước khi cẩu; căng dây cảnh giới vùng cẩu.', 'closed'),
        ('Trượt chân mép hào thoát nước', '2026-07-09 10:05:00', ct_ht,
         'minor', 'Tuyến cống N1', 'Công nhân đội thoát nước',
         'Trượt chân xuống hào sâu 1,2m — trầy xước nhẹ cẳng tay, sơ cứu tại chỗ.',
         'Sơ cứu, băng vết xước, tiếp tục làm việc.', 'Lắp thang lên xuống hào cách 15m; rải cát chống trơn.', 'closed'),
        ('Kẹt tay khi tháo cốp pha bệ đỡ', '2026-07-10 16:40:00', ct_tt,
         'minor', 'Khu bệ đỡ robot ép cọc', 'Công nhân đội ván khuôn',
         'Kẹt ngón tay khi tháo tấm cốp pha — dập nhẹ, sơ cứu.',
         'Sơ cứu tại chỗ, theo dõi.', 'Phổ biến thao tác tháo ván khuôn 2 người; bổ sung găng chống dập.', 'closed'),
        ('Xe bồn bê tông lùi không có xi nhan', '2026-07-10 08:30:00', ct_tt,
         'near_miss', 'Cổng số 2', 'Lái xe bồn',
         'Xe bồn lùi vào vị trí đổ không có người xi nhan, suýt chạm giàn giáo.',
         'Dừng xe, bố trí người xi nhan.', 'Quy định bắt buộc người xi nhan với mọi xe lùi trong công trường.', 'closed'),
        ('Chập tủ điện tạm khu văn phòng', '2026-07-11 07:50:00', ct_mep,
         'near_miss', 'Văn phòng công trường', 'Nhân viên văn phòng',
         'Ổ cắm quá tải gây khét, aptomat nhảy kịp — không cháy.',
         'Cắt điện, thay ổ cắm, kiểm tra tải.', 'Kiểm tra định kỳ tải tủ văn phòng; cấm dùng bếp điện trong văn phòng.', 'investigating'),
        ('Gió giật làm rơi tấm tôn hàng rào', '2026-07-11 15:10:00', ct_tt,
         'near_miss', 'Hàng rào phía Đông', 'Không có người tại vị trí',
         'Mưa dông gió giật, 2 tấm tôn rào bung rơi vào trong công trường.',
         'Thu hồi, gia cố lại toàn tuyến rào.', 'Gia cố xương rào + kiểm tra trước mùa mưa bão.', 'closed'),
        ('Công nhân khoan nhồi giẫm đinh', '2026-07-13 09:30:00', ct_tt,
         'lost_time', 'Khu tập kết ván khuôn cũ', 'Công nhân đội khoan nhồi',
         'Giẫm đinh xuyên đế giày vải (không phải giày bảo hộ) — nghỉ 2 ngày, tiêm phòng.',
         'Đưa đi trạm y tế, tiêm uốn ván.', 'Cấm giày vải vào công trường — chốt kiểm tra PPE tại cổng; dọn sạch ván cũ có đinh.', 'investigating'),
        ('Rò rỉ dầu thủy lực máy đào', '2026-07-13 13:45:00', ct_ht,
         'near_miss', 'Tuyến đường vành đai', 'Lái máy PC120',
         'Vỡ ống thủy lực, dầu loang ~2m² — nguy cơ trượt và ô nhiễm.',
         'Dừng máy, rải cát thấm dầu, thu gom.', 'Máy PC120 dừng sửa chữa (đã ghi nhật ký); kiểm tra ống thủy lực toàn bộ xe máy.', 'reported'),
    ]
    n_c = 0
    for name, dt, ct, typ, loc, who, desc, act, corr, state in incs:
        if Inc.search([('name', '=', name)]):
            continue
        Inc.create({'name': name, 'date': dt, 'project_id': proj.id,
                    'contract_id': ct.id, 'incident_type': typ,
                    'location': loc, 'people_involved': who,
                    'description': desc, 'immediate_action': act,
                    'corrective_action': corr, 'state': state})
        n_c += 1

    env.cr.commit()
    print('TOP-UP: +%s diary, +%s punch, +%s insp, +%s toolbox, +%s incident'
          % (n_d, n_p, n_i, n_t, n_c))
    for m, lbl in [('rp.site.diary', 'Nhật ký'), ('rp.site.punch', 'Punch'),
                   ('rp.site.safety.inspection', 'Kiểm tra AT'),
                   ('rp.site.toolbox', 'Toolbox'),
                   ('rp.site.incident', 'Sự cố')]:
        print('%-12s: %s' % (lbl, env[m].search_count(
            [('project_id', '=', proj.id)])))
except Exception:
    env.cr.rollback()
    import traceback
    print('FAIL:', traceback.format_exc().splitlines()[-1])
