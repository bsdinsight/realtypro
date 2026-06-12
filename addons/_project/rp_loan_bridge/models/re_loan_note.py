# -*- coding: utf-8 -*-
"""Inherit re.loan.note: thêm allocation_ids + tổng phân bổ +
auto-pay hóa đơn HĐ nhà thầu khi KW kích hoạt."""
import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class ReLoanNote(models.Model):
    _inherit = 're.loan.note'

    allocation_ids = fields.One2many(
        'rp.loan.allocation', 'note_id', string='Phân bổ công trình')
    allocation_count = fields.Integer(compute='_compute_allocation_stats')
    allocation_total_principal = fields.Monetary(
        string='Σ phân bổ gốc', compute='_compute_allocation_stats',
        store=True)
    allocation_total_interest = fields.Monetary(
        string='Σ phân bổ lãi', compute='_compute_allocation_stats',
        store=True)

    @api.depends('allocation_ids.amount_allocated', 'allocation_ids.base')
    def _compute_allocation_stats(self):
        for rec in self:
            rec.allocation_count = len(rec.allocation_ids)
            principal = 0.0
            interest = 0.0
            for a in rec.allocation_ids:
                if a.base == 'principal':
                    principal += a.amount_allocated
                elif a.base == 'interest':
                    interest += a.amount_allocated
                else:  # both → chia đôi (ước lượng)
                    principal += a.amount_allocated * 0.5
                    interest += a.amount_allocated * 0.5
            rec.allocation_total_principal = principal
            rec.allocation_total_interest = interest

    # ------------------------------------------------------------------
    # Override action_activate: KW kích hoạt → đánh dấu invoice Đã TT
    # ------------------------------------------------------------------
    def action_activate(self):
        """Sau khi KW active, register payment cho tất cả hóa đơn HĐ
        nhà thầu trong hồ sơ giải ngân.

        Chuẩn NH VN: NH duyệt KW = NH đã chuyển tiền trực tiếp về TK
        nhà thầu, hóa đơn coi như đã thanh toán bởi loan disbursement.
        """
        res = super().action_activate()
        for rec in self.filtered(lambda n: n.state == 'active'):
            rec._mark_dossier_invoices_paid()
        return res

    def _collect_dossier_invoices(self):
        """Gom tất cả account.move qua chuỗi:
        re.loan.note → disbursement_ids → dossier_line_ids → invoice_id.
        """
        self.ensure_one()
        invoices = self.env['account.move']
        for disb in self.disbursement_ids:
            for dossier in disb.dossier_line_ids:
                if dossier.invoice_id:
                    invoices |= dossier.invoice_id
        return invoices

    def _mark_dossier_invoices_paid(self):
        """Auto-post draft + register payment posted invoices.

        Workflow:
          1. Gom tất cả invoice trong hồ sơ giải ngân
          2. Invoice draft → action_post() (skip nếu lỗi)
          3. Invoice posted + (not_paid/partial) → register payment
             qua wizard account.payment.register
          4. Log message_post lên KW + lên từng invoice
        """
        self.ensure_one()
        invoices = self._collect_dossier_invoices()
        if not invoices:
            return

        # Auto-post draft trước
        draft = invoices.filtered(lambda m: m.state == 'draft')
        for inv in draft:
            try:
                inv.action_post()
            except Exception as e:
                _logger.warning(
                    "Không post được HĐ %s khi KW %s kích hoạt: %s",
                    inv.display_name, self.name, e)
                self.message_post(body=_(
                    "Không post được hóa đơn <b>%(n)s</b>: %(err)s. "
                    "Cần điền đủ thông tin rồi thanh toán tay sau.",
                    n=inv.display_name, err=str(e)))

        # Register payment trên invoice đã posted + chưa thanh toán đủ
        payable = invoices.filtered(
            lambda m: m.state == 'posted'
                      and m.payment_state in ('not_paid', 'partial'))
        if not payable:
            return
        today = fields.Date.context_today(self)
        try:
            wizard = self.env['account.payment.register'].with_context(
                active_model='account.move',
                active_ids=payable.ids,
            ).create({
                'payment_date': today,
                'group_payment': False,  # 1 payment / invoice
            })
            wizard.action_create_payments()
            self.message_post(body=_(
                "Đã thanh toán %(n)s hóa đơn HĐ nhà thầu qua KW "
                "kích hoạt (NH chuyển tiền trực tiếp về nhà thầu).",
                n=len(payable)))
            for inv in payable:
                inv.message_post(body=_(
                    "Tự động thanh toán khi KW <b>%(n)s</b> kích hoạt.",
                    n=self.name or ''))
        except Exception as e:
            _logger.warning(
                "Register payment fail cho %s invoice khi KW %s "
                "kích hoạt: %s", len(payable), self.name, e)
            self.message_post(body=_(
                "Cảnh báo: không thanh toán tự động được "
                "(%(n)s hóa đơn). Lỗi: %(err)s. "
                "Kiểm tra journal NH hoặc thanh toán tay.",
                n=len(payable), err=str(e)))
