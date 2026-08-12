# -*- coding: utf-8 -*-
"""Inherit account.move: auto-fill bank account của nhà cung cấp +
related project_id để group hóa đơn HĐ nhà thầu theo Dự án → Nhà thầu."""
from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    # Related project_id từ HĐ nhà thầu (via payment milestone) — dùng
    # để group hóa đơn HĐ nhà thầu theo Dự án (khách hàng #5):
    #   Dự án → Nhà thầu → Hóa đơn
    # Trước đây là related READONLY qua mốc thanh toán → hoá đơn nhập tay
    # (không qua mốc) KHÔNG có dự án ⇒ công nợ NCC theo dự án bị thiếu.
    # Nay: vẫn tự điền theo mốc, nhưng CHO SỬA TAY (anh Đại 2026-08-10).
    contract_id = fields.Many2one(
        'rp.contract',
        string='HĐ nhà thầu',
        compute='_compute_rp_contract_project', store=True, readonly=False,
        help='HĐ nhà thầu của hóa đơn này. Tự điền khi hoá đơn phát sinh '
             'từ mốc thanh toán; hoá đơn nhập tay thì chọn ở đây.')
    project_id = fields.Many2one(
        're.project',
        string='Dự án',
        compute='_compute_rp_contract_project', store=True, readonly=False,
        help='Dự án của hoá đơn. Tự lấy theo HĐ nhà thầu / mốc thanh '
             'toán; hoá đơn không gắn hợp đồng thì chọn tay — cần có dự '
             'án thì công nợ mới vào đúng phiếu Nhu cầu vốn.')

    supplier_credit_state = fields.Selection(
        [('source', 'Được trả chậm — là nguồn vốn'),
         ('overdue', 'QUÁ HẠN — không tính là nguồn'),
         ('paid', 'Đã thanh toán'),
         ('na', 'Chưa vào sổ')],
        string='Công nợ NCC', compute='_compute_supplier_credit_state',
        help='Hoá đơn CHƯA đến hạn = nguồn vốn, trừ vào ④ Nhu cầu vốn dự '
             'án. QUÁ HẠN thì không tính là nguồn mà là cảnh báo với '
             'ngân hàng. Muốn vào được phiếu Nhu cầu vốn thì hoá đơn '
             'PHẢI có Dự án.')

    @api.depends('state', 'payment_state', 'invoice_date_due', 'move_type')
    def _compute_supplier_credit_state(self):
        today = fields.Date.context_today(self)
        for mv in self:
            if mv.move_type != 'in_invoice' or mv.state != 'posted':
                mv.supplier_credit_state = 'na'
            elif mv.payment_state in ('paid', 'reversed'):
                mv.supplier_credit_state = 'paid'
            elif mv.invoice_date_due and mv.invoice_date_due < today:
                mv.supplier_credit_state = 'overdue'
            else:
                mv.supplier_credit_state = 'source'

    @api.depends('payment_milestone_id', 'contract_id')
    def _compute_rp_contract_project(self):
        for mv in self:
            ms = mv.payment_milestone_id
            if ms and ms.contract_id:
                mv.contract_id = ms.contract_id
                mv.project_id = ms.contract_id.project_id
            else:
                # giữ nguyên số user đã chọn tay
                mv.contract_id = mv.contract_id
                mv.project_id = (mv.contract_id.project_id
                                 if mv.contract_id else mv.project_id)

    @api.onchange('partner_id')
    def _onchange_partner_id_set_bank(self):
        """Khi pick nhà cung cấp, auto-fill TK nhận tiền:

        - Có >=1 TK NH → set sẵn TK đầu tiên (user vẫn đổi được qua
          dropdown nếu có nhiều TK)
        - 0 TK → giữ rỗng, user click vào field 'Ngân hàng người nhận'
          → 'Tạo và sửa' để mở form res.partner.bank với
          default_partner_id đã set sẵn

        Chỉ áp dụng cho vendor bill (in_invoice, in_refund). Customer
        invoice không cần TK NH bên đối tác.
        """
        if self.move_type not in ('in_invoice', 'in_refund'):
            return
        if not self.partner_id:
            self.partner_bank_id = False
            return
        accounts = self.partner_id.bank_ids
        if accounts:
            # Pick first — chuẩn Odoo sort theo sequence, default thường
            # là TK chính.
            self.partner_bank_id = accounts[:1]
        else:
            self.partner_bank_id = False
