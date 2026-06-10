# -*- coding: utf-8 -*-
"""
Bridge milestone ↔ BBNT ↔ Hóa đơn.

Workflow tại mỗi đợt thanh toán:
  Bước 1: Click "Tạo BBNT" → mở dialog tạo BBNT cho đợt đó
          → CĐT phê duyệt BBNT
  Bước 2: Sau khi BBNT approved → "Tạo hóa đơn" enable
          → mở dialog tạo vendor bill cho đợt đó
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class RpContractPaymentMilestone(models.Model):
    _inherit = 'rp.contract.payment.milestone'

    # --- BBNT cho đợt thanh toán ---
    acceptance_id = fields.Many2one(
        'rp.progress.acceptance', string='BBNT của đợt',
        copy=False, ondelete='set null',
        help='1 đợt thanh toán = 1 BBNT.')
    acceptance_state = fields.Selection(
        related='acceptance_id.state', string='Trạng thái BBNT',
        readonly=True, store=True)

    # --- Hóa đơn cho đợt thanh toán ---
    invoice_ids = fields.One2many(
        'account.move', 'payment_milestone_id',
        string='Hóa đơn đợt này',
        domain=[('move_type', 'in',
                 ['in_invoice', 'in_refund'])])
    invoice_count = fields.Integer(
        compute='_compute_invoice_stats')
    invoice_amount_total = fields.Monetary(
        string='Σ giá trị hóa đơn',
        compute='_compute_invoice_stats', store=True)

    @api.depends('invoice_ids', 'invoice_ids.amount_total',
                 'invoice_ids.state')
    def _compute_invoice_stats(self):
        for rec in self:
            posted = rec.invoice_ids.filtered(
                lambda m: m.state == 'posted')
            rec.invoice_count = len(rec.invoice_ids)
            rec.invoice_amount_total = sum(
                posted.mapped('amount_total'))

    # ==================================================================
    # Bước 1: Tạo BBNT cho đợt thanh toán
    # ==================================================================
    def action_create_acceptance(self):
        self.ensure_one()
        if self.acceptance_id:
            # Đã có BBNT — mở để xem/sửa
            return {
                'type': 'ir.actions.act_window',
                'name': self.acceptance_id.name,
                'res_model': 'rp.progress.acceptance',
                'res_id': self.acceptance_id.id,
                'view_mode': 'form',
                'target': 'new',
            }
        # Chưa có — mở dialog tạo mới
        return {
            'type': 'ir.actions.act_window',
            'name': _('Tạo BBNT cho %s') % self.name,
            'res_model': 'rp.progress.acceptance',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_contract_id': self.contract_id.id,
                'default_payment_milestone_id': self.id,
            },
        }

    # ==================================================================
    # Bước 2: Tạo Hóa đơn (chỉ sau khi BBNT approved)
    # ==================================================================
    def action_create_invoice(self):
        self.ensure_one()
        if not self.acceptance_id:
            raise UserError(_(
                "Cần tạo BBNT cho đợt thanh toán này trước khi tạo "
                "hóa đơn."))
        if self.acceptance_id.state != 'approved':
            raise UserError(_(
                "BBNT của đợt này chưa được CĐT duyệt (state=%s). "
                "Cần duyệt BBNT trước khi tạo hóa đơn.",
                self.acceptance_id.state))
        # Tạo dự thảo vendor bill — contractor_id giờ là res.partner
        # (sau refactor) nên dùng trực tiếp, không qua .partner_id.
        contractor_partner = self.contract_id.contractor_id
        if not contractor_partner:
            raise UserError(_(
                "HĐ chưa có nhà thầu. Cần điền Nhà thầu trên HĐ "
                "trước khi tạo hóa đơn."))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Tạo hóa đơn cho %s') % self.name,
            'res_model': 'account.move',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_move_type': 'in_invoice',
                'default_partner_id': contractor_partner.id,
                'default_payment_milestone_id': self.id,
                'default_ref': _(
                    'Hóa đơn đợt %(m)s — HĐ %(c)s — BBNT %(b)s',
                    m=self.name,
                    c=self.contract_id.name,
                    b=self.acceptance_id.name),
            },
        }

    def action_view_invoices(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Hóa đơn đợt %s') % self.name,
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('payment_milestone_id', '=', self.id)],
            'context': {
                'default_payment_milestone_id': self.id,
                'default_move_type': 'in_invoice',
            },
        }
