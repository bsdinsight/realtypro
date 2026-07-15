# -*- coding: utf-8 -*-
"""Kế hoạch thanh toán của CĐT theo tiến độ → kế hoạch dòng tiền THU.

Trên HĐ với CĐT, tổng thầu lập lịch các đợt CĐT sẽ thanh toán (tạm ứng,
theo sản lượng từng đợt, giữ lại bảo hành, quyết toán). Đây là nguồn để
dựng kế hoạch dòng tiền thu — biết tháng nào thu bao nhiêu từ CĐT.

Vòng đời mỗi đợt: Kế hoạch → Đã xuất hoá đơn → Đã thu (một phần/đủ).
"""
from odoo import _, api, fields, models


class RpOwnerPaymentMilestone(models.Model):
    _name = 'rp.owner.payment.milestone'
    _description = 'Kế hoạch thanh toán của CĐT (theo tiến độ)'
    _order = 'due_date, sequence, id'

    contract_id = fields.Many2one(
        'rp.owner.contract', string='HĐ với CĐT', required=True,
        ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    name = fields.Char(string='Nội dung đợt', required=True,
                       help='Vd: "Đợt 1 — tạm ứng 10%", "Đợt 2 — theo sản lượng".')
    milestone_type = fields.Selection(
        [('advance', 'Tạm ứng'),
         ('progress', 'Theo sản lượng'),
         ('retention', 'Giữ lại bảo hành'),
         ('final', 'Quyết toán'),
         ('other', 'Khác')],
        string='Loại', default='progress', required=True)
    percent = fields.Float(string='% giá trị HĐ')
    amount = fields.Monetary(
        string='Số tiền (kế hoạch)',
        help='Số tiền dự kiến CĐT thanh toán đợt này. Nhập % để tự tính.')
    due_date = fields.Date(string='Dự kiến thu', index=True)

    invoice_id = fields.Many2one(
        'account.move', string='Hoá đơn phát hành', copy=False,
        domain="[('move_type', '=', 'out_invoice')]")
    amount_received = fields.Monetary(
        string='Đã thu', compute='_compute_received', store=True,
        help='Số tiền đã thu qua hoá đơn của đợt này.')
    state = fields.Selection(
        [('planned', 'Kế hoạch'),
         ('invoiced', 'Đã xuất hoá đơn'),
         ('received', 'Đã thu'),
         ('cancelled', 'Huỷ')],
        string='Trạng thái', default='planned', required=True, copy=False)

    project_id = fields.Many2one(
        related='contract_id.project_id', store=True, readonly=True)
    owner_id = fields.Many2one(
        related='contract_id.owner_id', store=True, readonly=True,
        string='Chủ đầu tư')
    currency_id = fields.Many2one(
        related='contract_id.currency_id', store=True, readonly=True)
    company_id = fields.Many2one(
        related='contract_id.company_id', store=True, readonly=True)
    note = fields.Char(string='Ghi chú')

    @api.onchange('percent')
    def _onchange_percent(self):
        for rec in self:
            if rec.percent and rec.contract_id:
                rec.amount = rec.contract_id.contract_value_total \
                    * rec.percent / 100.0

    @api.depends('invoice_id.amount_total', 'invoice_id.amount_residual',
                 'invoice_id.state')
    def _compute_received(self):
        for rec in self:
            inv = rec.invoice_id
            if inv and inv.state == 'posted':
                rec.amount_received = inv.amount_total - inv.amount_residual
            else:
                rec.amount_received = 0.0
            # tự nâng trạng thái khi đã thu đủ
            if rec.state in ('invoiced', 'received'):
                if inv and inv.amount_residual <= 0.01 and inv.state == 'posted':
                    rec.state = 'received'
                elif rec.state == 'received':
                    rec.state = 'invoiced'

    # ------------------------------------------------------------------
    def action_create_invoice(self):
        """Phát hành hoá đơn cho CĐT (out_invoice) từ đợt kế hoạch này."""
        self.ensure_one()
        if self.invoice_id:
            return self.action_view_invoice()
        c = self.contract_id
        income = self.env['account.account'].search(
            [('account_type', '=', 'income'),
             ('company_ids', 'in', c.company_id.id)], limit=1) \
            or self.env['account.account'].search(
            [('account_type', '=', 'income')], limit=1)
        inv = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': c.owner_id.id,
            'invoice_date': fields.Date.context_today(self),
            'invoice_date_due': self.due_date,
            'owner_contract_id': c.id,
            'owner_milestone_id': self.id,
            'ref': _('Hoá đơn %(m)s — HĐ %(c)s', m=self.name, c=c.name),
            'invoice_line_ids': [(0, 0, {
                'name': _('%(m)s — %(c)s (%(p)s)',
                          m=self.name, c=c.name, p=c.project_id.name),
                'quantity': 1,
                'price_unit': self.amount,
                'account_id': income.id if income else False,
            })],
        })
        self.invoice_id = inv.id
        self.state = 'invoiced'
        return {
            'type': 'ir.actions.act_window',
            'name': _('Hoá đơn phát hành CĐT'),
            'res_model': 'account.move',
            'res_id': inv.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_invoice(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Hoá đơn phát hành CĐT'),
            'res_model': 'account.move',
            'res_id': self.invoice_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
