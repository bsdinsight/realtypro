# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class RpCostReconcile(models.Model):
    """Đối chiếu một khoản tiền qua ba đời của nó: khái toán → dự toán →
    hợp đồng.

    Ba con số này cùng đo một thứ nhưng sinh ra ở ba lúc khác nhau, với
    độ tin cậy khác hẳn nhau, và hầu như không bao giờ ai đặt chúng cạnh
    nhau — vì chúng nằm ở ba phân hệ. Đặt cạnh nhau thì lộ ra ba thứ mà
    bảng nào đứng riêng cũng không nói được:

    * **Khái toán có mà dự toán không có** — khoản đã hứa với hội đồng
      nhưng chưa ai bóc khối lượng. Tiền đất, tư vấn, lãi vay vốn hoá,
      dự phòng rơi hết vào đây, vì BOQ theo định nghĩa không chứa chúng.
    * **Dự toán có mà hợp đồng không có** — phần việc đã bóc nhưng chưa
      ký với ai. Đây là rủi ro giá: bóc theo mặt bằng giá cũ, ký theo
      mặt bằng giá lúc ký.
    * **Hợp đồng vượt dự toán** — ký cao hơn số bóc, nghĩa là dự toán
      sai hoặc phạm vi đã nở ra mà chưa cập nhật lại.

    Quy ước để ba cột so được với nhau:

    * Tất cả đều **trước thuế**. Khái toán và BOQ vốn trước thuế; hợp
      đồng lấy ``contract_value_pretax`` chứ không lấy tổng có VAT.
    * Hợp đồng **cộng cả phát sinh đã duyệt**, vì cam kết thật của chủ
      đầu tư là giá ký cộng phần đã đồng ý thêm, không phải giá ký.
    * Một hợp đồng phủ một gói thầu trải nhiều nhóm chi phí thì giá trị
      hợp đồng **chia theo tỷ trọng BOQ** của gói đó. Không có cách nào
      chính xác hơn: hợp đồng trọn gói không khai theo nhóm chi phí.

    Bảng dựng lại mỗi lần mở màn hình, không giữ số cũ.
    """
    _name = 'rp.cost.reconcile'
    _description = 'Đối chiếu khái toán — dự toán — hợp đồng'
    _order = 'project_id, root_category_id, category_id'
    _rec_name = 'category_id'

    project_id = fields.Many2one(
        're.project', string='Dự án', required=True,
        ondelete='cascade', index=True)
    category_id = fields.Many2one(
        'rp.cost.category', string='Nhóm chi phí', ondelete='cascade',
        index=True)
    root_category_id = fields.Many2one(
        'rp.cost.category', string='Nhóm gốc', ondelete='cascade',
        index=True)
    currency_id = fields.Many2one('res.currency', string='Tiền tệ')
    concept_id = fields.Many2one(
        'rp.concept.estimate', string='Bản khái toán')

    amount_concept = fields.Monetary(string='Khái toán')
    amount_estimate = fields.Monetary(string='Dự toán (Σ BOQ)')
    amount_contract = fields.Monetary(string='Hợp đồng đã ký')
    amount_variation = fields.Monetary(
        string='Trong đó phát sinh đã duyệt')

    diff_estimate = fields.Monetary(
        string='Lệch dự toán − khái toán', compute='_compute_lech',
        store=True)
    diff_contract = fields.Monetary(
        string='Lệch hợp đồng − dự toán', compute='_compute_lech',
        store=True)
    diff_total = fields.Monetary(
        string='Lệch', compute='_compute_lech', store=True,
        help='Hợp đồng đã ký trừ khái toán — đầu chuỗi so với cuối chuỗi.')
    pct_total = fields.Float(
        string='Lệch %', compute='_compute_lech', store=True,
        digits=(16, 1))
    tinh_trang = fields.Selection(
        [('chua_boc', 'Khái toán có, chưa bóc dự toán'),
         ('chua_ky', 'Đã bóc, chưa ký hợp đồng'),
         ('vuot', 'Hợp đồng vượt dự toán'),
         ('lech_boc', 'Dự toán lệch khái toán'),
         ('khop', 'Khớp'),
         ('ngoai', 'Ngoài khái toán')],
        string='Tình trạng', compute='_compute_lech', store=True)

    @api.depends('amount_concept', 'amount_estimate', 'amount_contract')
    def _compute_lech(self):
        for r in self:
            kt, dt, hd = (r.amount_concept, r.amount_estimate,
                          r.amount_contract)
            r.diff_estimate = dt - kt
            r.diff_contract = hd - dt
            r.diff_total = hd - kt
            r.pct_total = (hd - kt) / kt * 100.0 if kt else 0.0
            if not kt and (dt or hd):
                r.tinh_trang = 'ngoai'
            elif kt and not dt and not hd:
                r.tinh_trang = 'chua_boc'
            elif dt and not hd:
                r.tinh_trang = 'chua_ky'
            # Ký cao hơn số bóc quá 1% mới coi là vượt — dưới mức đó là
            # chênh làm tròn và chênh tỷ trọng khi chia giá trị hợp đồng.
            elif dt and hd > dt * 1.01:
                r.tinh_trang = 'vuot'
            # Bóc ra lệch số ước quá 5%. Ở mức nhóm con, nguyên nhân hay
            # gặp nhất KHÔNG phải tiền sai mà là người lập khái toán và
            # người bóc BOQ xếp cùng một đầu việc vào hai nhóm khác nhau
            # — gom lên nhóm gốc là hai bên triệt tiêu nhau. Vẫn phải báo,
            # vì hai bên không nói chung một thứ tiếng thì mọi so sánh
            # chi tiết về sau đều lệch.
            elif kt and abs(dt - kt) > kt * 0.05:
                r.tinh_trang = 'lech_boc'
            else:
                r.tinh_trang = 'khop'

    # ------------------------------------------------------------------
    @api.model
    def rp_dung_lai(self, project_ids=None):
        """Dựng lại bảng đối chiếu. Xoá sạch rồi tính lại, không vá.

        Chạy bằng sudo: bảng là kết quả tính, người xem chỉ được đọc —
        không ai nên sửa tay một ô trong báo cáo đối chiếu.
        """
        self = self.sudo()
        DA = self.env['re.project']
        da = DA.browse(project_ids) if project_ids else DA.search([])
        self.sudo().search([('project_id', 'in', da.ids)]).unlink()
        KT = self.env['rp.concept.estimate']
        HD = self.env['rp.contract']
        bo_qua = {'draft', 'cancel', 'cancelled', 'rejected'}
        dong = []
        for p in da:
            o = {}

            def o_cua(cat):
                return o.setdefault(cat.id if cat else False, {
                    'cat': cat, 'kt': 0.0, 'dt': 0.0, 'hd': 0.0, 'ps': 0.0})

            # 1) khái toán — chỉ lấy bản ĐÃ DUYỆT mới nhất. Bản nháp
            #    không phải cam kết với ai nên không đem ra đối chiếu.
            kt = KT.search([('project_id', '=', p.id),
                            ('state', '=', 'approved')],
                           order='version desc', limit=1)
            for d in kt.line_ids:
                o_cua(d.category_id)['kt'] += d.amount_total

            # 2) dự toán = Σ BOQ
            for b in self.env['rp.boq.line'].search(
                    [('project_id', '=', p.id)]):
                o_cua(b.category_id)['dt'] += b.amount

            # 3) hợp đồng — chia theo tỷ trọng BOQ của gói
            for c in HD.search([('project_id', '=', p.id)]):
                if c.state in bo_qua:
                    continue
                gia = c.contract_value_pretax + c.variation_approved_amount
                ps = c.variation_approved_amount
                dong_goi = self.env['rp.boq.line'].search(
                    [('package_id', '=', c.tender_package_id.id)]
                ) if c.tender_package_id else self.env['rp.boq.line']
                tong_goi = sum(dong_goi.mapped('amount'))
                if not tong_goi:
                    # Gói chưa bóc BOQ thì không quy được về nhóm nào —
                    # vẫn phải hiện ra chứ không được nuốt mất tiền.
                    o_cua(False)['hd'] += gia
                    o_cua(False)['ps'] += ps
                    continue
                for b in dong_goi:
                    if not b.amount:
                        continue
                    t = b.amount / tong_goi
                    o_cua(b.category_id)['hd'] += gia * t
                    o_cua(b.category_id)['ps'] += ps * t

            for v in o.values():
                c = v['cat']
                if not any((v['kt'], v['dt'], v['hd'])):
                    continue
                dong.append({
                    'project_id': p.id,
                    'category_id': c.id if c else False,
                    'root_category_id': ((c.root_id.id or c.id)
                                         if c else False),
                    'currency_id': p.currency_id.id,
                    'concept_id': kt.id or False,
                    'amount_concept': v['kt'],
                    'amount_estimate': v['dt'],
                    'amount_contract': v['hd'],
                    'amount_variation': v['ps'],
                })
        self.create(dong)
        return len(dong)

    @api.model
    def rp_mo_man_hinh(self):
        self.rp_dung_lai()
        act = self.env['ir.actions.act_window']._for_xml_id(
            'rp_progress.action_rp_cost_reconcile')
        return act


class RpPackageReconcile(models.Model):
    """Đối chiếu ở cấp GÓI THẦU: số bóc so với số đã ký.

    Bảng đối chiếu theo nhóm chi phí không trả lời chính xác được câu
    "gói nào ký thiếu so với số bóc", vì hợp đồng trọn gói phải chia về
    nhóm theo tỷ trọng BOQ — nên một gói ký thiếu sẽ bị **rải đều** phần
    hụt ra mọi nhóm của nó thay vì chỉ đúng chỗ.

    Ở cấp gói thì không phải chia gì cả: BOQ của gói và giá hợp đồng của
    gói đều là số có sẵn. Vì vậy đây mới là chỗ đọc ra được phần phạm vi
    đã bóc mà chưa ai ký, và phần ký cao hơn số bóc.

    Hai cột cùng quy ước với bảng theo nhóm chi phí: đều TRƯỚC THUẾ, và
    cam kết = giá ký cộng phát sinh đã duyệt.
    """
    _name = 'rp.package.reconcile'
    _description = 'Đối chiếu theo gói thầu — số bóc so với số đã ký'
    _order = 'project_id, package_id'
    _rec_name = 'package_id'

    project_id = fields.Many2one(
        're.project', string='Dự án', required=True,
        ondelete='cascade', index=True)
    package_id = fields.Many2one(
        'rp.tender.package', string='Gói thầu', ondelete='cascade',
        index=True)
    contract_ids = fields.Many2many(
        'rp.contract', string='Hợp đồng')
    contractor_id = fields.Many2one(
        'res.partner', string='Nhà thầu')
    structure_codes = fields.Char(string='Phạm vi hợp đồng khai')
    currency_id = fields.Many2one('res.currency', string='Tiền tệ')

    amount_boq = fields.Monetary(string='BOQ đã bóc')
    amount_contract = fields.Monetary(string='Hợp đồng trước thuế')
    amount_variation = fields.Monetary(string='Phát sinh đã duyệt')
    amount_committed = fields.Monetary(
        string='Đã cam kết', compute='_compute_lech', store=True,
        help='Giá ký cộng phát sinh đã duyệt — cam kết thật của chủ '
             'đầu tư, không phải giá ký.')
    amount_accepted = fields.Monetary(string='Đã nghiệm thu')
    amount_paid = fields.Monetary(string='Đã thanh toán')

    diff_amount = fields.Monetary(
        string='Hụt / vượt', compute='_compute_lech', store=True,
        help='Đã cam kết trừ BOQ đã bóc. Âm = phần đã bóc nhưng chưa ký '
             'với ai.')
    diff_percent = fields.Float(
        string='Hụt / vượt %', compute='_compute_lech', store=True,
        digits=(16, 1))
    tinh_trang = fields.Selection(
        [('chua_ky', 'Đã bóc, chưa ký hợp đồng'),
         ('hut', 'Hợp đồng chưa phủ hết phạm vi đã bóc'),
         ('vuot', 'Ký cao hơn số bóc'),
         ('ngoai', 'Có hợp đồng, chưa bóc BOQ'),
         ('khop', 'Khớp')],
        string='Tình trạng', compute='_compute_lech', store=True)

    @api.depends('amount_boq', 'amount_contract', 'amount_variation')
    def _compute_lech(self):
        for r in self:
            cam = r.amount_contract + r.amount_variation
            r.amount_committed = cam
            r.diff_amount = cam - r.amount_boq
            r.diff_percent = ((cam - r.amount_boq) / r.amount_boq * 100.0
                              if r.amount_boq else 0.0)
            if r.amount_boq and not cam:
                r.tinh_trang = 'chua_ky'
            elif cam and not r.amount_boq:
                r.tinh_trang = 'ngoai'
            # Ngưỡng 0,5%: dưới mức đó là làm tròn, không phải chuyện
            # phải đi hỏi ai.
            elif cam < r.amount_boq * 0.995:
                r.tinh_trang = 'hut'
            elif cam > r.amount_boq * 1.005:
                r.tinh_trang = 'vuot'
            else:
                r.tinh_trang = 'khop'

    @api.model
    def rp_dung_lai(self, project_ids=None):
        self = self.sudo()
        DA = self.env['re.project']
        da = DA.browse(project_ids) if project_ids else DA.search([])
        self.search([('project_id', 'in', da.ids)]).unlink()
        HD = self.env['rp.contract']
        B = self.env['rp.boq.line']
        bo_qua = {'draft', 'cancel', 'cancelled', 'rejected'}
        dong = []
        for p in da:
            hd_het = HD.search([('project_id', '=', p.id)]).filtered(
                lambda c: c.state not in bo_qua)
            goi_het = self.env['rp.tender.package'].search(
                [('project_id', '=', p.id)])
            # Hợp đồng không gắn gói nào vẫn phải hiện, nếu không là
            # giấu mất một khoản cam kết.
            for g in list(goi_het) + [self.env['rp.tender.package']]:
                hd = (hd_het.filtered(lambda c: c.tender_package_id == g)
                      if g else
                      hd_het.filtered(lambda c: not c.tender_package_id))
                boq = (sum(B.search([('package_id', '=', g.id)]).mapped(
                    'amount')) if g else 0.0)
                if not boq and not hd:
                    continue
                dong.append({
                    'project_id': p.id,
                    'package_id': g.id or False,
                    'contract_ids': [(6, 0, hd.ids)],
                    'contractor_id': hd[:1].contractor_id.id or False,
                    'structure_codes': ', '.join(
                        hd.structure_ids.mapped('code')) or False,
                    'currency_id': p.currency_id.id,
                    'amount_boq': boq,
                    'amount_contract': sum(
                        hd.mapped('contract_value_pretax')),
                    'amount_variation': sum(
                        hd.mapped('variation_approved_amount')),
                    'amount_accepted': sum(
                        hd.mapped('acceptance_value_to_date')),
                    'amount_paid': sum(hd.mapped('amount_paid')),
                })
        self.create(dong)
        return len(dong)

    @api.model
    def rp_mo_man_hinh(self):
        self.rp_dung_lai()
        return self.env['ir.actions.act_window']._for_xml_id(
            'rp_progress.action_rp_package_reconcile')
