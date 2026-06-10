# -*- coding: utf-8 -*-
"""
Tài sản thế chấp (collateral) — master.

Tài sản thuộc công ty thành viên (hoặc bên thứ ba) dùng đảm bảo cho khoản vay.
Có nhiều lần định giá; giá trị hiện hành lấy định giá mới nhất. Một tài sản có
thể thế chấp cho nhiều khoản (multi-pledge).
"""
from odoo import api, fields, models


class ReLoanCollateral(models.Model):
    _name = 're.loan.collateral'
    _description = 'Tài sản thế chấp'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(string='Tên tài sản', required=True, tracking=True)
    code = fields.Char(string='Mã', copy=False)
    type_id = fields.Many2one(
        're.loan.collateral.type', string='Loại tài sản', required=True,
        tracking=True)
    owner_company_id = fields.Many2one(
        'res.company', string='Công ty sở hữu',
        default=lambda self: self.env.company,
        help='Công ty thành viên sở hữu tài sản.')
    owner_partner_id = fields.Many2one(
        'res.partner', string='Chủ sở hữu (bên thứ ba)',
        help='Điền nếu tài sản thuộc bên thứ ba bảo lãnh.')
    legal_info = fields.Text(string='Thông tin pháp lý',
                             help='Sổ đỏ/sổ hồng, đăng ký, số seri...')
    description = fields.Text(string='Mô tả')

    company_id = fields.Many2one(
        'res.company', string='Công ty', required=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', string='Loại tiền', required=True,
        default=lambda self: self.env.company.currency_id)

    valuation_ids = fields.One2many(
        're.loan.collateral.valuation', 'collateral_id', string='Định giá')
    value_current = fields.Monetary(
        string='Giá trị hiện hành', compute='_compute_value_current',
        store=True, help='Lấy theo lần định giá mới nhất.')

    pledge_ids = fields.One2many(
        're.loan.collateral.pledge', 'collateral_id', string='Thế chấp')
    pledge_count = fields.Integer(
        string='Số lần thế chấp', compute='_compute_pledge_stats')
    active_pledge_count = fields.Integer(
        string='Số thế chấp đang hiệu lực',
        compute='_compute_pledge_stats', store=True)
    total_secured = fields.Monetary(
        string='Giá trị đã đem thế chấp',
        compute='_compute_pledge_stats', store=True,
        help='Σ giá trị đảm bảo của các thế chấp đang hiệu lực '
             '(qua tất cả HĐTD, các NH).')
    value_available = fields.Monetary(
        string='Giá trị còn lại có thể thế chấp',
        compute='_compute_pledge_stats', store=True,
        help='= Giá trị hiện hành − Đã đem thế chấp. Số tiền tối đa '
             'có thể đem TS này thế chấp thêm cho HĐTD khác (cùng NH '
             'hoặc NH khác).')
    coverage_percent = fields.Float(
        string='% đã thế chấp',
        compute='_compute_pledge_stats', store=True,
        help='= Đã đem thế chấp / Giá trị hiện hành × 100.')

    state = fields.Selection(
        [('available', 'Sẵn sàng — chưa thế chấp'),
         ('partial_pledged', 'Thế chấp 1 phần — còn dư'),
         ('fully_pledged', 'Đã thế chấp hết'),
         ('over_pledged', 'Quá thế chấp (cảnh báo)'),
         ('disposed', 'Đã thanh lý')],
        string='Trạng thái',
        compute='_compute_state', store=True,
        help='Trạng thái phản ánh giá trị còn lại của TS:\n'
             '• Sẵn sàng: chưa thế chấp lần nào\n'
             '• Thế chấp 1 phần: đã có thế chấp, còn giá trị thể thế '
             'chấp thêm — vd BĐS 10 tỷ đã đem 6 tỷ thế chấp BIDV, '
             'còn 4 tỷ có thể thế chấp NH khác\n'
             '• Đã thế chấp hết: Σ đảm bảo ≈ giá trị TS\n'
             '• Quá thế chấp: Σ đảm bảo > giá trị (cảnh báo — sai sót)\n'
             '• Đã thanh lý: TS đã bán, không dùng nữa')

    active = fields.Boolean(default=True)

    @api.depends('valuation_ids.date', 'valuation_ids.amount')
    def _compute_value_current(self):
        for rec in self:
            latest = rec.valuation_ids.sorted('date', reverse=True)[:1]
            rec.value_current = latest.amount if latest else 0.0

    @api.depends('pledge_ids.state', 'pledge_ids.secured_amount',
                 'value_current')
    def _compute_pledge_stats(self):
        for rec in self:
            active = rec.pledge_ids.filtered(lambda p: p.state == 'active')
            rec.pledge_count = len(rec.pledge_ids)
            rec.active_pledge_count = len(active)
            rec.total_secured = sum(active.mapped('secured_amount'))
            rec.value_available = rec.value_current - rec.total_secured
            # Trả về dạng fraction (0..1) để widget="percentage" trên view
            # tự nhân 100 + thêm dấu %. Vd 0.4762 → "47.62%".
            if rec.value_current:
                rec.coverage_percent = (
                    rec.total_secured / rec.value_current)
            else:
                rec.coverage_percent = 0.0

    @api.depends('total_secured', 'value_current', 'active_pledge_count',
                 'active')
    def _compute_state(self):
        for rec in self:
            if not rec.active:
                rec.state = 'disposed'
                continue
            if rec.active_pledge_count == 0:
                rec.state = 'available'
            elif rec.total_secured > rec.value_current + 0.01:
                rec.state = 'over_pledged'
            elif rec.total_secured >= rec.value_current - 0.01:
                rec.state = 'fully_pledged'
            else:
                rec.state = 'partial_pledged'
