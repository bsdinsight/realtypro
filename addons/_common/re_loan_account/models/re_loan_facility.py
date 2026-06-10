# -*- coding: utf-8 -*-
"""Per-facility account overrides (vd vay VND vs ngoại tệ cần TK riêng)."""
from odoo import fields, models


class ReLoanFacility(models.Model):
    _inherit = 're.loan.facility'

    loan_account_principal_id = fields.Many2one(
        'account.account', string='TK Vay (override)',
        check_company=True,
        help='Override TK Vay riêng cho facility này (mặc định lấy '
             'từ company).')
    loan_account_bank_id = fields.Many2one(
        'account.account', string='TK Tiền gửi NH (override)',
        check_company=True)
    loan_account_interest_payable_id = fields.Many2one(
        'account.account', string='TK Lãi phải trả (override)',
        check_company=True)
    loan_account_interest_expense_id = fields.Many2one(
        'account.account', string='TK CP lãi vay (override)',
        check_company=True)
    loan_account_interest_capitalized_id = fields.Many2one(
        'account.account', string='TK XDCB capitalize (override)',
        check_company=True)
    loan_journal_id = fields.Many2one(
        'account.journal', string='Sổ Nhật ký (override)',
        check_company=True,
        domain="[('type','in',['general','bank'])]")
