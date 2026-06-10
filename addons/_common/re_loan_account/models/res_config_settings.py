# -*- coding: utf-8 -*-
"""Settings page — bind company-level loan accounts vào res.config.settings."""
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    loan_account_principal_id = fields.Many2one(
        related='company_id.loan_account_principal_id', readonly=False)
    loan_account_bank_id = fields.Many2one(
        related='company_id.loan_account_bank_id', readonly=False)
    loan_account_interest_payable_id = fields.Many2one(
        related='company_id.loan_account_interest_payable_id', readonly=False)
    loan_account_interest_expense_id = fields.Many2one(
        related='company_id.loan_account_interest_expense_id', readonly=False)
    loan_account_interest_capitalized_id = fields.Many2one(
        related='company_id.loan_account_interest_capitalized_id',
        readonly=False)
    loan_journal_id = fields.Many2one(
        related='company_id.loan_journal_id', readonly=False)
