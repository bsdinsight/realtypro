# -*- coding: utf-8 -*-
"""Inherit re.loan.note: thêm allocation_ids + tổng phân bổ +
auto-pay hóa đơn HĐ nhà thầu khi KW kích hoạt."""
import logging

from markupsafe import Markup

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class ReLoanNote(models.Model):
    _inherit = 're.loan.note'

    allocation_ids = fields.One2many(
        'rp.loan.allocation', 'note_id', string='Phân bổ công trình')
    # Phiếu chi do CHÍNH khế ước này sinh ra khi kích hoạt. Ghi thẳng
    # quan hệ thay vì dò ngược từ hoá đơn: một hoá đơn có thể được trả
    # bởi nhiều nguồn, dò ngược sẽ gom nhầm phiếu chi của người khác —
    # mà đây là danh sách dùng để SỬA NGÀY, gom nhầm là sửa nhầm sổ.
    dossier_payment_ids = fields.Many2many(
        'account.payment', 'rp_loan_note_dossier_payment_rel',
        'note_id', 'payment_id',
        string='Phiếu chi từ hồ sơ giải ngân', copy=False)
    dossier_payment_count = fields.Integer(
        compute='_compute_dossier_stats')
    dossier_doc_count = fields.Integer(
        string='Số hoá đơn/tạm ứng đã giải ngân',
        compute='_compute_dossier_stats')
    allocation_count = fields.Integer(compute='_compute_allocation_stats')
    allocation_total_principal = fields.Monetary(
        string='Σ phân bổ gốc', compute='_compute_allocation_stats',
        store=True)
    allocation_total_interest = fields.Monetary(
        string='Σ phân bổ lãi', compute='_compute_allocation_stats',
        store=True)

    def _dossier_lines(self):
        """Các hồ sơ giải ngân của KW, bỏ đợt giải ngân đã huỷ."""
        self.ensure_one()
        return self.disbursement_ids.filtered(
            lambda d: d.state != 'cancelled').mapped('dossier_line_ids')

    @api.depends('dossier_payment_ids',
                 'disbursement_ids.state',
                 'disbursement_ids.dossier_line_ids.invoice_id')
    def _compute_dossier_stats(self):
        Dossier = self.env['rp.loan.disbursement.dossier']
        has_advance = 'advance_payment_id' in Dossier._fields
        for rec in self:
            lines = rec._dossier_lines()
            docs = set(lines.mapped('invoice_id').ids)
            if has_advance:
                docs |= {('a', i) for i in
                         lines.mapped('advance_payment_id').ids}
            rec.dossier_doc_count = len(docs)
            rec.dossier_payment_count = len(rec.dossier_payment_ids)

    def action_view_dossier_payments(self):
        """Danh sách phiếu chi các hoá đơn/tạm ứng KW này đã giải ngân.

        Trên từng phiếu chi, nút "Hoá đơn" sẵn có của Odoo dẫn tới hoá
        đơn được đối trừ.
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Phiếu chi — KW %s') % (self.name or ''),
            'res_model': 'account.payment',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.dossier_payment_ids.ids)],
            'context': {'create': False},
        }

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

    # ------------------------------------------------------------------
    # Điều chỉnh ngày kích hoạt → kéo theo ngày thanh toán chứng từ
    # ------------------------------------------------------------------
    def _activation_date_impact_note(self):
        base = super()._activation_date_impact_note()
        n = len(self.dossier_payment_ids)
        if n:
            base += _(" %s phiếu chi hoá đơn sẽ được ghi lại ngày.", n)
        return base

    def _after_activation_date_changed(self, old_date, new_date):
        res = super()._after_activation_date_changed(old_date, new_date)
        for rec in self:
            rec._redate_dossier_payments(new_date)
        return res

    def _redate_dossier_payments(self, new_date):
        """Ghi lại ngày cho các phiếu chi KW này đã sinh.

        Bút toán đã ghi sổ không đổi ngày được, nên phải đưa về nháp
        rồi ghi sổ lại. Ngày ghi vào CHÍNH phiếu chi (`payment.date`),
        không ghi vào bút toán: trong Odoo 19 đây là hai cột riêng, ghi
        vào bút toán thì phiếu chi vẫn giữ ngày cũ và hai chỗ lệch nhau.
        Phiếu chi tự đẩy ngày xuống bút toán.

        Đối trừ với hoá đơn thực tế SỐNG SÓT qua vòng nháp → ghi sổ,
        nhưng vẫn đối chiếu lại trước/sau và chỉ nối lại phần bị mất —
        không nối mù, vì nối nhầm tài khoản còn tệ hơn lệch ngày.
        Kỳ kế toán đã khoá thì bước về nháp hỏng: KHÔNG nuốt lỗi, ghi
        rõ phiếu nào còn giữ ngày cũ để kế toán xử lý riêng.
        """
        self.ensure_one()
        done, failed = [], []
        for pay in self.dossier_payment_ids:
            move = pay.move_id
            if not move or pay.date == new_date:
                continue
            linked_before = (pay.reconciled_bill_ids
                             | pay.reconciled_invoice_ids)
            try:
                was_posted = move.state == 'posted'
                if was_posted:
                    move.button_draft()
                pay.date = new_date
                if was_posted:
                    move.action_post()
                lost = linked_before - (pay.reconciled_bill_ids
                                        | pay.reconciled_invoice_ids)
                if lost:
                    self._reconcile_payment_with(pay, lost)
                done.append(pay.display_name)
            except Exception as e:          # noqa: BLE001 - báo, không nuốt
                _logger.warning(
                    "Không đổi được ngày phiếu chi %s của KW %s: %s",
                    pay.display_name, self.name, e)
                failed.append((pay.display_name, str(e)))
        if done:
            self.message_post(body=Markup(_(
                "Đã ghi lại ngày <b>%(d)s</b> cho %(n)s phiếu chi: "
                "%(l)s.")) % {
                    'd': new_date, 'n': len(done), 'l': ', '.join(done)})
        for name, err in failed:
            self.message_post(body=Markup(_(
                "<b>Chưa đổi được</b> ngày phiếu chi %(p)s (vẫn giữ "
                "ngày cũ). Lý do: %(e)s. Kiểm tra khoá sổ kỳ kế toán "
                "rồi sửa tay phiếu này.")) % {'p': name, 'e': err})

    @api.model
    def _reconcile_payment_with(self, payment, invoices):
        """Nối lại đối trừ phiếu chi ↔ hoá đơn sau khi ghi sổ lại.

        Chỉ đụng tới tài khoản CÓ MẶT Ở CẢ HAI bên và thuộc nhóm phải
        thu/phải trả — đủ để loại các dòng chi phí, tài sản… tình cờ
        cũng đang mở đối trừ.
        """
        def _open(move):
            return move.line_ids.filtered(
                lambda l: not l.reconciled and l.account_id.reconcile
                and l.account_id.account_type in (
                    'asset_receivable', 'liability_payable'))

        pay_lines = _open(payment.move_id)
        if not pay_lines:
            return
        for inv in invoices:
            inv_lines = _open(inv)
            for account in pay_lines.account_id & inv_lines.account_id:
                (pay_lines + inv_lines).filtered(
                    lambda l: l.account_id == account).reconcile()

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

        # Register payment riêng từng invoice với amount đúng số dossier.
        # NGÀY THANH TOÁN = ngày kích hoạt KW, không phải ngày bấm nút:
        # tiền về tay nhà thầu vào ngày ngân hàng kích hoạt, và nhập bù
        # hồ sơ của tuần trước là chuyện thường ngày.
        pay_date = self._get_interest_start_date() \
            or fields.Date.context_today(self)
        paid_count = 0
        created_payments = self.env['account.payment']
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
                    'payment_date': pay_date,
                    'amount': pay_amount,
                    'group_payment': True,
                })
                created_payments |= wizard._create_payments()
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
        if created_payments:
            self.dossier_payment_ids = [(4, p.id) for p in created_payments]
        if paid_count:
            self.message_post(body=_(
                "Đã thanh toán %(n)s hóa đơn HĐ nhà thầu theo số tiền "
                "dossier khi KW kích hoạt (ngày thanh toán %(d)s).",
                n=paid_count, d=pay_date))
