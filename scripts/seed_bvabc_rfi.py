# -*- coding: utf-8 -*-
"""Seed 10 RFI + 10 Chỉ thị + 10 Trình duyệt cho BVABC (dev).
Đan chéo với nhật ký/punch/sự cố đã seed. Idempotent theo name. User=admin(2).
"""
import datetime

D = datetime.date
A = 2

try:
    proj = env['re.project'].search([('code', '=', 'BVABC')], limit=1)
    def ct(part):
        return env['rp.contract'].search(
            [('project_id', '=', proj.id), ('name', 'ilike', part)], limit=1)
    tt, mep, ht, tbyt = ct('Tổng thầu'), ct('Cơ điện MEP'), ct('Hạ tầng'), ct('Thiết bị y tế')
    def st(code):
        r = env['rp.structure'].search(
            [('project_id', '=', proj.id), ('code', '=', code)], limit=1)
        return r.id if r else False

    # ── RFI ────────────────────────────────────────────────────────────
    RFI = env['rp.rfi']
    rfis = [
        # (name, contract, structure, recipient, question, sub_date, deadline, imp_sched, imp_cost, state, answer)
        ('Di dời đường ống nước ngầm hiện trạng trục 7-9', tt, 'NT-NG', 'owner',
         'Khu vực trục 7-9 vướng ống cấp nước D400 hiện trạng chưa di dời (đã ghi nhật ký 13/07). Đề nghị CĐT xác nhận phương án + thời điểm di dời để tiếp tục ép cọc phân khu B.',
         D(2026, 7, 9), D(2026, 7, 12), True, True, 'submitted', False),
        ('Xác nhận cấp bê tông đài móng khu thang máy: B30 hay B35', tt, 'NT-NG', 'designer',
         'Bản vẽ KC-04 rev.1 ghi B30, thuyết minh kết cấu trang 12 ghi B35. Đề nghị làm rõ.',
         D(2026, 7, 8), D(2026, 7, 11), True, False, 'answered',
         'Áp dụng B35 cho đài khu thang máy theo thuyết minh; bản vẽ KC-04 sẽ phát hành rev.2 trong tuần.'),
        ('Cao độ hoàn thiện sảnh chính lệch 50mm giữa bản vẽ KT và KC', tt, 'KB-HT', 'designer',
         'KT-11 ghi +0.450, KC-02 ghi +0.400 tại cùng vị trí sảnh chính khối Khám. Xin xác nhận cao độ chuẩn.',
         D(2026, 7, 11), D(2026, 7, 18), True, True, 'submitted', False),
        ('Chi tiết ốp chì phòng CT — độ dày và phạm vi ốp', tt, 'CLS-HT', 'designer',
         'Spec ghi "ốp chì theo yêu cầu thiết bị" nhưng chưa có bản vẽ chi tiết. Đề nghị cung cấp độ dày chì (2mm hay 2.5mm) và phạm vi ốp (tường/cửa/trần).',
         D(2026, 7, 5), D(2026, 7, 10), False, True, 'closed',
         'Ốp chì 2.5mm toàn bộ 4 mặt tường + cửa chì chuyên dụng; trần không ốp. Bản vẽ CT-CLS-08 đã phát hành.'),
        ('Chủng loại màng chống thấm thay thế do khan hàng', tt, 'NT-NG', 'supervisor',
         'Màng khò nóng mã đã duyệt tạm hết hàng đến 25/07. Đề nghị TVGS xem xét mã tương đương (đã trình mẫu SUB kèm theo) để không chậm chống thấm tầng hầm.',
         D(2026, 7, 12), D(2026, 7, 16), True, False, 'submitted', False),
        ('Vị trí ống chờ MEP xuyên đài xung đột với thép chủ', mep, 'NT-ME', 'designer',
         'Tại trục 5-6, ống chờ D168 xuyên đài trùng vị trí 2 cây thép chủ D32. Đề nghị thiết kế xác nhận phương án dịch ống hay gia cường bổ sung.',
         D(2026, 7, 10), D(2026, 7, 14), True, False, 'answered',
         'Dịch ống chờ 150mm về phía trục 6, bổ sung 2 thép gia cường D16 quanh lỗ mở theo detail KC-DT-05.'),
        ('Tiêu chuẩn ống đồng khí y tế: ASTM B819 Type L hay Type K', mep, 'NT-KY', 'owner',
         'Spec khí y tế chỉ ghi "ống đồng y tế theo ASTM B819". Đề nghị CĐT/TV xác nhận Type L hay Type K cho tuyến trục chính (ảnh hưởng đơn giá).',
         D(2026, 7, 12), D(2026, 7, 20), False, True, 'submitted', False),
        ('Cao độ đấu nối cống thoát N1 với hạ tầng ngoài ranh', ht, 'HT', 'owner',
         'Cống hiện trạng ngoài ranh sâu hơn thiết kế 300mm. Xin xác nhận cao độ đấu nối cuối tuyến N1.',
         D(2026, 7, 6), D(2026, 7, 9), False, False, 'closed',
         'Chấp thuận hạ cao độ cuối tuyến N1 xuống -1.85m, bổ sung 1 hố ga chuyển bậc theo bản vẽ HT-N1-03A.'),
        ('Yêu cầu tải trọng và chống rung sàn đặt máy MRI', tbyt, 'CLS-TB', 'designer',
         'Nhà cung cấp MRI yêu cầu sàn chịu 12 kN/m² + cách rung. Bản vẽ kết cấu khu CLS hiện ghi 8 kN/m². Đề nghị xác nhận phương án gia cường.',
         D(2026, 7, 13), D(2026, 7, 21), True, True, 'submitted', False),
        ('Làm rõ ranh giới bàn giao mặt bằng đợt 2 phân khu B', tt, 'NT-NG', 'owner',
         'Đề nghị CĐT xác nhận ranh bàn giao đợt 2 có bao gồm dải 12m giáp đường nội bộ phía Nam không.',
         False, D(2026, 7, 25), False, False, 'draft', False),
    ]
    n_r = 0
    for (name, c, s, rcp, q, sd, dl, isch, icost, state, ans) in rfis:
        if RFI.search([('name', '=', name)]):
            continue
        # structure key có thể là mã item hoặc tên nhóm HT
        sid = st(s) if s and '-' in s else False
        if s == 'HT':
            r = env['rp.structure'].search(
                [('project_id', '=', proj.id),
                 ('name', '=', 'Hạ tầng kỹ thuật ngoài nhà')], limit=1)
            sid = r.id if r else False
        vals = {'name': name, 'project_id': proj.id, 'contract_id': c.id,
                'structure_id': sid, 'recipient': rcp, 'question': q,
                'requested_by_id': A, 'deadline': dl,
                'impact_schedule': isch, 'impact_cost': icost,
                'state': state}
        if sd:
            vals['submitted_date'] = sd
        if ans:
            vals.update({'answer': ans, 'answered_by_id': A,
                         'answered_date': (sd or dl) + datetime.timedelta(days=2)})
        RFI.create(vals)
        n_r += 1

    # ── Chỉ thị công trường ────────────────────────────────────────────
    SI = env['rp.site.instruction']
    sis = [
        # (name, contract, desc, issued, deadline, cost, state, done_date, done_note)
        ('Bổ sung biện pháp che chắn bụi phía cổng số 2', tt,
         'Lắp lưới chắn bụi cao 2m + phun sương giờ cao điểm tại cổng số 2 trước 16/07 (theo ý kiến TVGS trong nhật ký 13/07).',
         D(2026, 7, 13), D(2026, 7, 16), False, 'issued', False, False),
        ('Tạm dừng ép cọc phân khu B chờ di dời ống ngầm', tt,
         'Dừng toàn bộ ép cọc trục 7-9 phân khu B từ 10/07 đến khi CĐT hoàn tất di dời ống cấp nước D400 (tham chiếu RFI di dời ống ngầm).',
         D(2026, 7, 10), False, True, 'issued', False, False),
        ('Gia cố toàn tuyến hàng rào phía Đông trước mùa mưa bão', tt,
         'Gia cố xương rào, bắt vít lại toàn bộ tấm tôn tuyến rào phía Đông; hoàn thành trước 15/07 (sau sự cố gió giật 11/07).',
         D(2026, 7, 11), D(2026, 7, 15), False, 'done', D(2026, 7, 13),
         'Đã gia cố 320md rào: hàn bổ sung xương ngang, bắt lại vít toàn tuyến, thay 8 tấm tôn hỏng.'),
        ('Bố trí người xi nhan bắt buộc cho mọi xe lùi trong công trường', tt,
         'Từ 10/07, mọi phương tiện lùi trong phạm vi công trường phải có người xi nhan (sau near-miss xe bồn 10/07).',
         D(2026, 7, 10), D(2026, 7, 11), False, 'closed', D(2026, 7, 11),
         'Đã phân công 4 người xi nhan theo ca, phổ biến trong toolbox meeting 11/07.'),
        ('Di chuyển vị trí cổng ra vào của xe bồn bê tông', tt,
         'Chuyển luồng xe bồn từ cổng 1 sang cổng 2 để tách dòng xe với khu văn phòng; làm đường tạm dẫn hướng.',
         D(2026, 7, 8), D(2026, 7, 12), True, 'done', D(2026, 7, 12),
         'Đã mở luồng cổng 2, rải đá cấp phối 80md đường tạm, lắp biển hướng dẫn.'),
        ('Tăng tần suất tưới nước chống bụi đường công vụ', ht,
         'Tưới nước đường công vụ tối thiểu 4 lần/ngày trong giai đoạn nắng nóng.',
         D(2026, 7, 9), False, False, 'issued', False, False),
        ('Lắp bổ sung RCD 30mA cho toàn bộ tủ điện tạm trong 48h', mep,
         'Kiểm tra và lắp RCD 30mA cho 100% tủ điện thi công (sau phát hiện tủ T3 thiếu RCD — punch PL).',
         D(2026, 7, 12), D(2026, 7, 14), False, 'done', D(2026, 7, 13),
         'Đã lắp RCD cho 9/9 tủ điện tạm, test nhả dòng rò đạt toàn bộ.'),
        ('Kiểm định lại cẩu bánh xích trước khi tái sử dụng', tt,
         'Cẩu bánh xích 55T chỉ được vận hành lại sau khi xuất trình giấy kiểm định mới + dán tem (punch tem kiểm định hết hạn).',
         D(2026, 7, 8), D(2026, 7, 13), False, 'closed', D(2026, 7, 13),
         'Đã kiểm định lại, tem mới hiệu lực đến 07/2027; TVGS xác nhận cho vận hành.'),
        ('Chuyển ca đổ bê tông khối lớn sang ban đêm', tt,
         'Các mẻ đổ >100m³ chuyển sang 20h-4h để tránh nắng nóng ảnh hưởng chất lượng bê tông; bổ sung chiếu sáng + phụ cấp ca đêm.',
         D(2026, 7, 12), False, True, 'issued', False, False),
        ('Che phủ bãi thép tránh mưa chống gỉ', tt,
         'Toàn bộ thép thanh tại bãi gia công phải kê cao 300mm + phủ bạt; kiểm tra hằng ngày trong mùa mưa.',
         False, D(2026, 7, 18), False, 'draft', False, False),
    ]
    n_s = 0
    for (name, c, desc, isd, dl, cost, state, dd, dn) in sis:
        if SI.search([('name', '=', name)]):
            continue
        vals = {'name': name, 'project_id': proj.id, 'contract_id': c.id,
                'description': desc, 'issued_by_id': A, 'deadline': dl,
                'cost_impact': cost, 'state': state}
        if isd:
            vals['issued_date'] = isd
        if dd:
            vals['done_date'] = dd
        if dn:
            vals['done_note'] = dn
        SI.create(vals)
        n_s += 1

    # ── Trình duyệt (Submittal) ────────────────────────────────────────
    SUB = env['rp.submittal']
    subs = [
        # (name, type, contract, structure, sub_date, deadline, rev, state, note)
        ('Shopdrawing ống chờ MEP xuyên đài — đợt 1', 'shopdrawing', mep, 'NT-ME',
         D(2026, 7, 13), D(2026, 7, 18), 1, 'approved_cond',
         'Duyệt kèm điều kiện: cập nhật vị trí ống trục 5-6 theo trả lời RFI (dịch 150mm + gia cường D16).'),
        ('Mẫu màng chống thấm khò nóng 3mm (mã thay thế)', 'material', tt, 'NT-NG',
         D(2026, 7, 12), D(2026, 7, 15), 1, 'rejected',
         'Từ chối: chứng chỉ CO/CQ chưa khớp lô hàng thực tế nhập về. Trình lại kèm CO/CQ đúng lô.'),
        ('Mẫu gạch ốp kháng khuẩn khu điều trị nội trú', 'material', tt, 'NT-HT',
         D(2026, 7, 6), D(2026, 7, 10), 1, 'approved',
         'Đạt yêu cầu kháng khuẩn JIS Z 2801, màu sắc theo bảng vật liệu đã duyệt.'),
        ('Panel phòng sạch & phụ kiện khu Cận lâm sàng', 'material', tt, 'CLS-HT',
         D(2026, 7, 13), D(2026, 7, 19), 1, 'submitted', False),
        ('Chứng chỉ xuất xưởng (mill cert) thép CB500V — lô 3', 'material', tt, 'NT-KC',
         D(2026, 7, 9), D(2026, 7, 11), 1, 'approved',
         'Mill cert khớp mác thép và lô hàng; mẫu thử kéo đạt.'),
        ('Biện pháp thi công ép cọc gần ranh giới phía Nam', 'method', tt, 'NT-NG',
         D(2026, 7, 5), D(2026, 7, 9), 2, 'approved',
         'Duyệt bản rev.2 sau khi bổ sung quan trắc lún nhà liền kề tần suất 2 lần/ngày.'),
        ('Shopdrawing lồng thép cọc khoan nhồi D1000', 'shopdrawing', tt, 'NT-NG',
         D(2026, 7, 8), D(2026, 7, 12), 1, 'approved_cond',
         'Duyệt kèm điều kiện: bổ sung chi tiết con kê định vị 4 phía theo góp ý punch thiếu con kê.'),
        ('Mẫu ống đồng khí y tế + phụ kiện đầu nối', 'material', mep, 'NT-KY',
         D(2026, 7, 13), D(2026, 7, 22), 1, 'submitted', False),
        ('Biện pháp đào hào sâu tuyến N1 — chống sạt vách', 'method', ht, 'HT',
         D(2026, 7, 8), D(2026, 7, 11), 1, 'approved',
         'Duyệt: văng chống thép + thang lên xuống mỗi 15m, đúng nội dung toolbox 13/07.'),
        ('Mock-up phòng bệnh chuẩn 2 giường (tầng 3 khối Nội trú)', 'mockup', tt, 'NT-HT',
         False, D(2026, 7, 30), 1, 'draft', False),
    ]
    n_b = 0
    for (name, typ, c, s, sd, dl, rev, state, note) in subs:
        if SUB.search([('name', '=', name)]):
            continue
        sid = st(s) if s and '-' in s else False
        if s == 'HT':
            r = env['rp.structure'].search(
                [('project_id', '=', proj.id),
                 ('name', '=', 'Hạ tầng kỹ thuật ngoài nhà')], limit=1)
            sid = r.id if r else False
        vals = {'name': name, 'submittal_type': typ, 'project_id': proj.id,
                'contract_id': c.id, 'structure_id': sid,
                'submitted_by_id': A, 'deadline': dl, 'revision': rev,
                'state': state}
        if sd:
            vals['submitted_date'] = sd
        if state in ('approved', 'approved_cond', 'rejected'):
            vals.update({'reviewed_by_id': A,
                         'reviewed_date': sd + datetime.timedelta(days=2),
                         'review_note': note})
        SUB.create(vals)
        n_b += 1

    env.cr.commit()
    print('SEED RFI OK: +%s rfi, +%s chi thi, +%s trinh duyet' % (n_r, n_s, n_b))
    print('Tong: RFI=%s SI=%s SUB=%s' % (
        RFI.search_count([('project_id', '=', proj.id)]),
        SI.search_count([('project_id', '=', proj.id)]),
        SUB.search_count([('project_id', '=', proj.id)])))
except Exception:
    env.cr.rollback()
    import traceback
    print('FAIL:', traceback.format_exc().splitlines()[-1])
