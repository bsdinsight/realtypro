# -*- coding: utf-8 -*-
"""Bridge: BL chiếm hạn mức của facility có purpose='bank_guarantee'.

2 entity cùng chiếm hạn mức facility purpose='bank_guarantee':
  - re.bank.guarantee (chứng thư BL chính thức) state issued/extended
  - re.guarantee.request (đề nghị BL) state active

Phân loại theo PURPOSE (mục đích) — không theo facility_type — vì NH
có thể cấp BL trên facility revolving/term với purpose=bank_guarantee.

Khi tất toán đề nghị BL (state=settled) → khôi phục hạn mức.
"""
from odoo import api, fields, models


class ReLoanFacility(models.Model):
    _inherit = 're.loan.facility'

    guarantee_ids = fields.One2many(
        're.bank.guarantee', 'facility_id',
        string='Chứng thư BL')
    guarantee_count = fields.Integer(compute='_compute_guarantee_stats')
    guarantee_total_outstanding = fields.Monetary(
        string='Tổng BL đang hiệu lực',
        compute='_compute_guarantee_stats', store=True,
        help='Σ giá trị BL state ∈ (issued, extended). Chiếm hạn mức.')

    guarantee_request_ids = fields.One2many(
        're.guarantee.request', 'facility_id',
        string='Đề nghị BL')
    guarantee_request_count = fields.Integer(
        compute='_compute_guarantee_request_stats')
    guarantee_request_outstanding = fields.Monetary(
        string='Tổng Đề nghị BL đang hiệu lực',
        compute='_compute_guarantee_request_stats', store=True,
        help='Σ giá trị đề nghị BL state=active. Chiếm hạn mức.')

    @api.depends('guarantee_ids', 'guarantee_ids.state',
                 'guarantee_ids.amount')
    def _compute_guarantee_stats(self):
        for rec in self:
            rec.guarantee_count = len(rec.guarantee_ids)
            active = rec.guarantee_ids.filtered(
                lambda g: g.state in ('issued', 'extended'))
            rec.guarantee_total_outstanding = sum(active.mapped('amount'))

    @api.depends('guarantee_request_ids', 'guarantee_request_ids.state',
                 'guarantee_request_ids.amount')
    def _compute_guarantee_request_stats(self):
        for rec in self:
            rec.guarantee_request_count = len(rec.guarantee_request_ids)
            active = rec.guarantee_request_ids.filtered(
                lambda r: r.state == 'active')
            rec.guarantee_request_outstanding = sum(active.mapped('amount'))

    # ------------------------------------------------------------------
    # Override amount_used: với facility purpose=bank_guarantee, cộng
    # thêm:
    #   - guarantee_request_outstanding: đề nghị BL state=active
    #     (chưa phát hành chứng thư)
    #   - guarantee_total_outstanding: chứng thư BL state ∈
    #     (issued, extended) — chứng thư settled không chiếm.
    # Đề nghị state=issued đã có chứng thư → chứng thư chiếm thay (không
    # double-count vì request_outstanding chỉ filter state=active).
    # ------------------------------------------------------------------
    @api.depends('purpose',
                 'guarantee_request_ids',
                 'guarantee_request_ids.state',
                 'guarantee_request_ids.amount',
                 'guarantee_ids',
                 'guarantee_ids.state',
                 'guarantee_ids.amount')
    def _compute_amount_used(self):
        super()._compute_amount_used()
        for rec in self:
            if rec.purpose == 'bank_guarantee':
                rec.amount_used += rec.guarantee_request_outstanding
                rec.amount_used += rec.guarantee_total_outstanding

    def action_view_guarantees(self):
        self.ensure_one()
        return {
            'name': 'Chứng thư BL — %s' % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 're.bank.guarantee',
            'view_mode': 'list,form',
            'domain': [('facility_id', '=', self.id)],
            'context': {
                'default_facility_id': self.id,
                'default_issuing_bank_partner_id':
                    self.credit_contract_id.partner_id.id,
            },
        }

    def action_view_guarantee_requests(self):
        self.ensure_one()
        return {
            'name': 'Đề nghị BL — %s' % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 're.guarantee.request',
            'view_mode': 'list,form',
            'domain': [('facility_id', '=', self.id)],
            'context': {
                'default_facility_id': self.id,
            },
        }
