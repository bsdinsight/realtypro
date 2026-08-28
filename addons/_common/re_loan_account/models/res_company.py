# -*- coding: utf-8 -*-
"""Per-company default accounts cho nghiệp vụ vay (VAS TT 200)."""
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    loan_account_principal_id = fields.Many2one(
        'account.account', string='TK Vay (Loan Principal)',
        check_company=True,
        help='Tài khoản nợ vay (vd TK 3411 Vay ngắn hạn / 3412 Vay dài hạn).')
    loan_account_bank_id = fields.Many2one(
        'account.account', string='TK Tiền gửi NH (Bank)',
        check_company=True,
        help='Tài khoản tiền gửi ngân hàng (vd TK 1121).')
    loan_account_interest_payable_id = fields.Many2one(
        'account.account', string='TK Lãi vay phải trả',
        check_company=True,
        help='Tài khoản phải trả lãi vay (vd TK 33531).')
    loan_account_interest_expense_id = fields.Many2one(
        'account.account', string='TK CP lãi vay (Expense)',
        check_company=True,
        help='Khi lãi vay KHÔNG capitalize — vào CP tài chính '
             '(vd TK 635).')
    loan_account_interest_capitalized_id = fields.Many2one(
        'account.account', string='TK XDCB dở dang (Capitalized)',
        check_company=True,
        help='Khi lãi vay capitalize vào dự án xây dựng '
             '(vd TK 241 — VAS TT 200 §54).')
    # ── Chênh lệch tỷ giá khoản vay ngoại tệ (TT 200 Điều 69) ──
    loan_account_fx_diff_id = fields.Many2one(
        'account.account', string='TK Chênh lệch tỷ giá',
        check_company=True,
        help='Tài khoản chênh lệch tỷ giá đánh giá lại cuối kỳ '
             '(vd TK 4131). Bắt buộc để chạy Đánh giá lại tỷ giá.')
    loan_account_fx_loss_id = fields.Many2one(
        'account.account', string='TK Lỗ tỷ giá (kết chuyển)',
        check_company=True,
        help='Nơi kết chuyển phần LỖ tỷ giá cuối kỳ — chi phí tài chính '
             '(vd TK 635). Chỉ cần khi dùng nút Kết chuyển.')
    loan_account_fx_gain_id = fields.Many2one(
        'account.account', string='TK Lãi tỷ giá (kết chuyển)',
        check_company=True,
        help='Nơi kết chuyển phần LÃI tỷ giá cuối kỳ — doanh thu tài '
             'chính (vd TK 515). Chỉ cần khi dùng nút Kết chuyển.')

    loan_journal_id = fields.Many2one(
        'account.journal', string='Sổ Nhật ký Vay',
        check_company=True,
        domain="[('type','in',['general','bank'])]",
        help='Journal để post bút toán nghiệp vụ vay. Khuyến nghị 1 '
             'journal riêng "Loan Journal" type general.')
