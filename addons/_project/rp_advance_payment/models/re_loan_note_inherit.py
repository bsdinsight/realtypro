# -*- coding: utf-8 -*-
"""Inherit re.loan.note: extend _mark_dossier_invoices_paid để xử lý
Tạm ứng khi KW activate.

Logic mới:
  - Dossier có advance_payment_id → set advance state='paid' (KHÔNG
    register payment invoice nào vì chưa có invoice)
  - Dossier có invoice_id → giữ logic cũ (register payment vào invoice)
"""
import logging

from markupsafe import Markup

from odoo import _, fields, models
from odoo.tools import clean_context

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

    def _activation_date_impact_note(self):
        base = super()._activation_date_impact_note()
        n = len(self._dossier_advances().filtered(
            lambda a: a.date_paid))
        if n:
            base += _(" %s tạm ứng sẽ được ghi lại ngày thanh toán.", n)
        return base

    def _after_activation_date_changed(self, old_date, new_date):
        """Ngày kích hoạt đổi → ngày thanh toán tạm ứng đổi theo.

        Tạm ứng không đi qua bút toán nào nên chỉ là ghi lại một ô
        ngày — không có đối trừ để gỡ như phía hoá đơn.
        """
        res = super()._after_activation_date_changed(old_date, new_date)
        for rec in self:
            advances = rec._dossier_advances().filtered(
                lambda a: a.date_paid and a.date_paid != new_date)
            if not advances:
                continue
            advances.write({'date_paid': new_date})
            for adv in advances:
                adv.message_post(body=Markup(_(
                    "Ngày thanh toán đổi theo ngày kích hoạt mới của "
                    "KW <b>%(n)s</b>: %(o)s → <b>%(d)s</b>.")) % {
                        'n': rec.name or '', 'o': old_date or '—',
                        'd': new_date})
            rec.message_post(body=Markup(_(
                "Đã ghi lại ngày thanh toán <b>%(d)s</b> cho %(n)s "
                "tạm ứng.")) % {'d': new_date, 'n': len(advances)})
        return res

    def _dossier_advances(self):
        """Tạm ứng của KW — chỉ ĐỌC, không tạo back-link như
        _collect_dossier_advances (hàm kia ghi dữ liệu, không gọi được
        từ trong compute)."""
        self.ensure_one()
        return self._dossier_lines().mapped('advance_payment_id')

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
            # Ngày thanh toán tạm ứng = ngày kích hoạt KW, không phải
            # ngày bấm nút (xem _paid_date của rp.advance.payment).
            eligible.with_context(
                advance_paid_date=self._get_interest_start_date()
            )._update_paid_state()
            full = eligible.filtered(lambda a: a.state == 'paid')
            partial = eligible.filtered(
                lambda a: a.state == 'partial_paid')
            self.message_post(body=_(
                "Cập nhật thanh toán Tạm ứng từ KW giải ngân: "
                "%(f)s đủ, %(p)s một phần.",
                f=len(full), p=len(partial)))
        self._create_advance_dossier_payments()

    def _create_advance_dossier_payments(self):
        """Sinh phiếu chi cho phần tạm ứng ngân hàng giải ngân (969).

        Team khách hàng chốt 2026-09-11: "ngân hàng giải ngân thẳng
        vào tài khoản của NCC để tránh doanh nghiệp nhận tiền rồi
        chiếm dụng vốn mà không thanh toán cho NCC như khế ước".

        Vì sao cần: bút toán giải ngân của khế ước chỉ ghi
        Nợ Ngân hàng / Có 3411 — mới là chặng tiền ngân hàng rót vào.
        Chặng tiền đi tiếp tới nhà cung cấp không có chứng từ nào. Hai
        bút toán ghép lại mới ra đúng bản chất: Nợ 331 / Có 3411.

        Một hồ sơ giải ngân → một phiếu chi. Liên kết giữ ở
        `dossier.payment_id`, vừa là khoá chống sinh trùng khi kích
        hoạt lại khế ước.

        KHÔNG chặn kích hoạt khế ước nếu chưa cấu hình tài khoản: kích
        hoạt là nghiệp vụ tín dụng, không phải nghiệp vụ kế toán. Ghi
        một dòng nhắc rồi thôi.
        """
        self.ensure_one()
        Settings = self.env['res.config.settings'].sudo()
        account = Settings._advance_payment_account()
        journal = Settings._advance_payment_journal()
        pay_date = self._get_interest_start_date() \
            or fields.Date.context_today(self)
        pending = self.env['rp.loan.disbursement.dossier']
        for disb in self.disbursement_ids.filtered(
                lambda d: d.state == 'disbursed'):
            pending |= disb.dossier_line_ids.filtered(
                lambda dl: dl.advance_payment_id and dl.amount > 0
                and not dl.payment_id)
        if not pending:
            return
        if not account or not journal:
            self.message_post(body=_(
                "%(n)s hồ sơ giải ngân tạm ứng CHƯA sinh được phiếu "
                "chi: %(why)s. Khai ở Vay > Cấu hình > Tham số phân hệ "
                "Vay, mục \"Kế toán Tạm ứng\", rồi kích hoạt lại hoặc "
                "ghi nhận tay.",
                n=len(pending),
                why=_("chưa khai TK trả trước người bán")
                if not account else _("chưa có sổ nhật ký chi")))
            return
        created = self.env['account.payment']
        for dl in pending:
            advance = dl.advance_payment_id
            partner = advance.partner_id or dl.disbursement_id \
                .beneficiary_partner_id
            if not partner:
                continue
            # clean_context: xem chú thích cùng loại ở re_guarantee —
            # `default_*` của bản ghi đang mở sẽ đè lên account.payment
            # và làm số phiếu chi thành câu diễn giải.
            payment = self.env['account.payment'].with_context(
                clean_context(self.env.context)).create({
                'payment_type': 'outbound',
                'partner_type': 'supplier',
                'partner_id': partner.id,
                'amount': dl.amount,
                'date': pay_date,
                'journal_id': journal.id,
                'destination_account_id': account.id,
                'memo': _("Tạm ứng %(a)s — NH giải ngân theo KW %(n)s",
                          a=advance.name or '', n=self.name or ''),
                'advance_payment_id': advance.id,
                'advance_dossier_id': dl.id,
            })
            payment.action_post()
            dl.payment_id = payment
            created |= payment
            advance.message_post(body=_(
                "Ngân hàng giải ngân %(amt)s ₫ thẳng cho %(p)s theo "
                "KW %(n)s — phiếu chi %(pay)s.",
                amt='{:,.0f}'.format(dl.amount),
                p=partner.display_name, n=self.name or '',
                pay=payment.name))
        if created:
            self.message_post(body=_(
                "Đã sinh %(n)s phiếu chi tạm ứng (NH trả thẳng cho nhà "
                "cung cấp), tổng %(t)s ₫.",
                n=len(created),
                t='{:,.0f}'.format(sum(created.mapped('amount')))))
