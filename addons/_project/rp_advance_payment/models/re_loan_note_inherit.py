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
        # Bug #19 tài liệu nghiệp vụ: KHÔNG mark 'paid' vô điều kiện — 1 Tạm ứng có
        # thể thanh toán qua NHIỀU dossier, mỗi dossier 1 phần. Dùng
        # _update_paid_state(): so Σ tiền dossier đã giải ngân với giá
        # trị tạm ứng → paid (đủ) / partial_paid (một phần).
        eligible = advances.filtered(
            lambda a: a.state in ('approved', 'partial_paid', 'paid'))
        for advance in advances - eligible:
            _logger.warning(
                "Tạm ứng %s state=%s, bỏ qua (cần approved/partial).",
                advance.name, advance.state)
            self.message_post(body=_(
                "Cảnh báo: Tạm ứng <b>%(n)s</b> đang ở trạng thái "
                "%(s)s — không thể cập nhật thanh toán. Cần phê "
                "duyệt Tạm ứng trước.",
                n=advance.name, s=advance.state))
        if eligible:
            eligible._update_paid_state()
            full = eligible.filtered(lambda a: a.state == 'paid')
            partial = eligible.filtered(
                lambda a: a.state == 'partial_paid')
            self.message_post(body=_(
                "Cập nhật thanh toán Tạm ứng từ KW giải ngân: "
                "%(f)s đủ, %(p)s một phần.",
                f=len(full), p=len(partial)))
