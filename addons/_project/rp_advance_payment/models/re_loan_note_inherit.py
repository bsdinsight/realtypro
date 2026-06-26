# -*- coding: utf-8 -*-
"""Inherit re.loan.note: extend _mark_dossier_invoices_paid để xử lý
Tạm ứng khi KW activate.

Logic mới:
  - Dossier có advance_payment_id → set advance state='paid' (KHÔNG
    register payment invoice nào vì chưa có invoice)
  - Dossier có invoice_id → giữ logic cũ (register payment vào invoice)
"""
import logging

from odoo import _, models

_logger = logging.getLogger(__name__)


class ReLoanNote(models.Model):
    _inherit = 're.loan.note'

    def _collect_dossier_invoice_amounts(self):
        """Override: chỉ collect invoice dossiers, BỎ QUA advance dossiers.

        Advance dossiers xử lý riêng trong _mark_dossier_advances_paid().
        """
        self.ensure_one()
        inv_amounts = {}
        for disb in self.disbursement_ids:
            for dossier in disb.dossier_line_ids:
                # Skip advance dossiers — xử lý riêng
                if dossier.is_advance_payment:
                    continue
                if dossier.invoice_id and dossier.amount > 0:
                    inv_amounts.setdefault(dossier.invoice_id, 0.0)
                    inv_amounts[dossier.invoice_id] += dossier.amount
        return inv_amounts

    def _collect_dossier_advances(self):
        """Gom các Tạm ứng cần mark 'paid' từ dossier của KW này.

        Trả về list rp.advance.payment records (deduped).
        """
        self.ensure_one()
        advances = self.env['rp.advance.payment']
        for disb in self.disbursement_ids:
            for dossier in disb.dossier_line_ids:
                if dossier.advance_payment_id:
                    advances |= dossier.advance_payment_id
                    # Back-link dossier ↔ advance
                    if not dossier.advance_payment_id.disbursement_dossier_id:
                        dossier.advance_payment_id.disbursement_dossier_id = dossier
        return advances

    def _mark_dossier_invoices_paid(self):
        """Override để cũng mark Tạm ứng paid khi KW activate."""
        # Gọi logic cũ cho invoice dossiers
        super()._mark_dossier_invoices_paid()
        # Logic mới: xử lý advance dossiers
        self.ensure_one()
        advances = self._collect_dossier_advances()
        marked_count = 0
        for advance in advances:
            if advance.state != 'approved':
                _logger.warning(
                    "Tạm ứng %s state=%s, KHÔNG mark paid (cần 'approved').",
                    advance.name, advance.state)
                self.message_post(body=_(
                    "Cảnh báo: Tạm ứng <b>%(n)s</b> đang ở trạng thái "
                    "%(s)s — không thể auto mark 'Đã thanh toán'. "
                    "Cần phê duyệt Tạm ứng trước.",
                    n=advance.name, s=advance.state))
                continue
            advance.action_mark_paid()
            marked_count += 1
        if marked_count:
            self.message_post(body=_(
                "Đã đánh dấu %(n)s Tạm ứng 'Đã thanh toán' từ KW giải ngân.",
                n=marked_count))
