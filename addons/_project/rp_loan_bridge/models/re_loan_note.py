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

    def _outstanding_by_contract(self):
        """Trả {contract_id: dư nợ gốc}; khoá 0 = không gắn hợp đồng.

        Song song với `_outstanding_by_project()` của trục dự án: dư nợ là
        số CÒN LẠI sau khi trả gốc, mà trả gốc không gắn hợp đồng nào —
        nên phân bổ theo TỶ TRỌNG số tiền các dòng giải ngân (bỏ dòng đã
        huỷ). KW không có dòng giải ngân nào → dồn hết vào khoá 0.
        """
        self.ensure_one()
        out = self.principal_outstanding or 0.0
        if not out:
            return {}
        lines = self.disbursement_ids.filtered(
            lambda d: d.state != 'cancelled' and d.amount)
        total = sum(lines.mapped('amount'))
        if not total:
            return {0: out}
        res = {}
        for d in lines:
            key = d.contract_id.id or 0
            res[key] = res.get(key, 0.0) + out * (d.amount / total)
        return res

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

    def _collect_dossier_invoice_amounts(self):
        """Map {invoice: Σ dossier.amount} qua chuỗi:
        re.loan.note → disbursement_ids → dossier_line_ids → invoice_id.

        Cùng 1 hóa đơn xuất hiện ở nhiều dossier → cộng dồn. Đây là
        SỐ TIỀN NH thực chuyển kỳ này, KHÔNG phải full residual.
        """
        self.ensure_one()
        inv_amounts = {}
        for disb in self.disbursement_ids:
            for dossier in disb.dossier_line_ids:
                if dossier.invoice_id and dossier.amount > 0:
                    inv_amounts.setdefault(dossier.invoice_id, 0.0)
                    inv_amounts[dossier.invoice_id] += dossier.amount
        return inv_amounts

    def _mark_dossier_invoices_paid(self):
        """Auto-post draft + register payment theo SỐ TIỀN DOSSIER.

        Workflow:
          1. Gom {invoice: Σ dossier.amount} trong hồ sơ giải ngân
          2. Invoice draft → action_post() (skip nếu lỗi)
          3. Invoice posted + (not_paid/partial) → register payment với
             amount = MIN(Σ dossier.amount, amount_residual)
             → partial nếu Σ < residual, paid nếu Σ ≥ residual
          4. Log message_post lên KW + lên từng invoice
        """
        self.ensure_one()
        inv_amounts = self._collect_dossier_invoice_amounts()
        if not inv_amounts:
            return
        invoices = self.env['account.move'].browse(
            [inv.id for inv in inv_amounts])

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

        # Register payment riêng từng invoice với amount đúng số dossier
        today = fields.Date.context_today(self)
        paid_count = 0
        for inv, dossier_amount in inv_amounts.items():
            if inv.state != 'posted':
                continue
            if inv.payment_state not in ('not_paid', 'partial'):
                continue
            # Clamp về residual để không over-pay
            pay_amount = min(dossier_amount, inv.amount_residual)
            if pay_amount <= 0:
                continue
            try:
                wizard = self.env['account.payment.register'].with_context(
                    active_model='account.move',
                    active_ids=[inv.id],
                ).create({
                    'payment_date': today,
                    'amount': pay_amount,
                    'group_payment': True,
                })
                wizard.action_create_payments()
                paid_count += 1
                inv.message_post(body=_(
                    "Tự động thanh toán %(amt)s khi KW <b>%(n)s</b> "
                    "kích hoạt (số tiền NH chuyển kỳ này theo hồ sơ "
                    "giải ngân, KHÔNG phải full hóa đơn).",
                    amt='{:,.0f}'.format(pay_amount),
                    n=self.name or ''))
            except Exception as e:
                _logger.warning(
                    "Register payment fail cho invoice %s (amount=%s) "
                    "khi KW %s kích hoạt: %s",
                    inv.display_name, pay_amount, self.name, e)
                self.message_post(body=_(
                    "Cảnh báo: không thanh toán tự động được hóa đơn "
                    "<b>%(inv)s</b> (số tiền %(amt)s). Lỗi: %(err)s. "
                    "Kiểm tra journal NH hoặc thanh toán tay.",
                    inv=inv.display_name,
                    amt='{:,.0f}'.format(pay_amount),
                    err=str(e)))
        if paid_count:
            self.message_post(body=_(
                "Đã thanh toán %(n)s hóa đơn HĐ nhà thầu theo số tiền "
                "dossier khi KW kích hoạt.",
                n=paid_count))
