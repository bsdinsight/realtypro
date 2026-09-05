# -*- coding: utf-8 -*-
"""
Realty Party — res.partner inherit shared by every RealtyPro database.

The same physical partner record can appear in Sales (as a customer),
Project (as a contractor), and Living (as a resident). Webhook sync
between the three databases joins on a stable identity field — most
commonly tax code (legal entity) or national ID (individual). Both are
indexed and validated here.
"""
import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


# Vietnamese national ID formats (CMND old 9-digit, CCCD new 12-digit).
RE_CMND = re.compile(r'^\d{9}$')
RE_CCCD = re.compile(r'^\d{12}$')
# Vietnamese tax code: 10 digits OR 10-3 digits (branch).
RE_TAX_CODE = re.compile(r'^\d{10}(-\d{3})?$')


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # ------------------------------------------------------------------
    # VN identity fields
    # ------------------------------------------------------------------
    vn_national_id = fields.Char(
        string='National ID (CMND/CCCD)',
        help='Vietnamese national identity card number. 9 digits for old '
             'CMND, 12 digits for new CCCD.',
        tracking=True,
    )
    vn_national_id_issue_date = fields.Date(
        string='ID Issue Date', tracking=True,
    )
    vn_national_id_issue_place = fields.Char(
        string='ID Issue Place',
        help='Issuing authority and location, e.g. "Cục CSQLHC về TTXH".',
    )
    passport_number = fields.Char(
        string='Passport Number', tracking=True,
        help='For foreign nationals.',
    )
    vn_tax_code = fields.Char(
        string='Tax Code (MST)', tracking=True,
        help='Vietnamese tax code. 10 digits for primary entity; '
             'add a 3-digit suffix (e.g. 0123456789-001) for branches.',
    )

    # ------------------------------------------------------------------
    # Canonical identity keys — never shown, never typed
    # ------------------------------------------------------------------
    # Users type "079 123 456 789" and "079123456789" for the same person.
    # Comparing the raw strings finds nothing, so every duplicate check and
    # every cross-database sync must run on a canonical value instead.
    # Phone and email already have Odoo's `phone_sanitized` /
    # `email_normalized`; these two close the remaining gap. Indexed
    # because they are the join key, not a display field.
    vn_national_id_norm = fields.Char(
        string='National ID (canonical)', compute='_compute_identity_norm',
        store=True, index=True, copy=False, readonly=True,
        help='Digits only, generated from National ID. Used for duplicate '
             'detection and cross-database matching.',
    )
    vn_tax_code_norm = fields.Char(
        string='Tax Code (canonical)', compute='_compute_identity_norm',
        store=True, index=True, copy=False, readonly=True,
        help='Tax code with separators stripped, branch suffix kept.',
    )

    # Set when a duplicate was created ON PURPOSE, with a reason. Only this
    # exempts a record from the tax-code uniqueness guard below — two
    # ordinary records still cannot collide.
    identity_dup_ack = fields.Boolean(
        string='Duplicate accepted', copy=False, tracking=True,
        help='Ticked when someone deliberately kept a record that matches '
             'an existing partner. Requires a reason.',
    )
    identity_dup_reason = fields.Char(
        string='Reason for duplicate', copy=False, tracking=True,
    )
    phone_secondary = fields.Char(
        string='Secondary Phone',
        help='Spouse / household contact / alternate number.',
    )

    # ------------------------------------------------------------------
    # VN-specific permanent address
    # ------------------------------------------------------------------
    # The standard res.partner address (street/state_id/country_id/...) is
    # treated as the partner's MAILING / CURRENT address. Vietnamese sale
    # contracts (HĐMB) additionally require the PERMANENT address as
    # written on the citizen's CCCD ("Nơi thường trú"), which can differ
    # from where they currently live. Stored as freeform multi-line text
    # so it can be rendered verbatim into HĐMB Word templates without
    # restructuring (province / ward / street).
    vn_permanent_address = fields.Text(
        string='Permanent Address (Thường trú)',
        help='Permanent address as written on the citizen ID (CCCD/CMND). '
             'Used verbatim in HĐMB and other legal documents. Leave '
             'empty if same as the standard address above.',
    )

    # ------------------------------------------------------------------
    # Family / personal relationships
    # ------------------------------------------------------------------
    relationship_ids = fields.One2many(
        're.partner.relationship', 'partner_id',
        string='Relationships',
        help='Declared family / personal relationships of this partner. '
             'Required when this partner is a Buyer or Co-owner on an '
             'HĐMB sale contract.',
    )

    # ------------------------------------------------------------------
    # RealtyPro role flags (non-exclusive)
    # ------------------------------------------------------------------
    is_re_customer = fields.Boolean(
        string='Property Customer',
        help='Buys / has bought a unit. Flagged automatically when a '
             'sale operations record (booking, contract) is linked.',
    )
    is_re_vendor = fields.Boolean(
        string='Vendor',
        help='Generic vendor (supplier of materials, services, etc.).',
    )
    is_re_contractor = fields.Boolean(
        string='Contractor',
        help='Construction contractor or subcontractor for Realty Project.',
    )
    is_re_resident = fields.Boolean(
        string='Resident',
        help='Owns or rents a unit and uses Realty Living services.',
    )
    is_re_broker = fields.Boolean(
        string='Broker / Salesperson',
        help='Salesperson, internal or external, who can earn commission.',
    )
    is_re_distributor = fields.Boolean(
        string='Distributor (NPP)',
        help='Distribution partner with portal access.',
    )
    is_bank = fields.Boolean(
        string='Bank / Lender',
        help='This partner is a bank or lender (bên cho vay). Used to '
             'filter the lender field on credit contracts (re_loan).',
    )
    is_contractor = fields.Boolean(
        string='Nhà thầu / Contractor',
        help='This partner is a contractor (NT — nhà thầu xây dựng). '
             'Used to filter contractor_id field on rp.contract, '
             'rp.tender.package, etc. Chuẩn Odoo dùng res.partner cho '
             'mọi nghiệp vụ kế toán; flag này thay cho rp.contractor '
             'model riêng.',
    )

    # ------------------------------------------------------------------
    # Corporate group structure (tập đoàn mẹ - con)
    # ------------------------------------------------------------------
    # Distinct from Odoo's native parent_id (contact hierarchy). This is
    # the GROUP parent used by intercompany lending: a parent company
    # borrows from a bank and on-lends to its subsidiaries.
    parent_company_id = fields.Many2one(
        'res.partner', string='Parent Company (Group)',
        domain="[('is_company', '=', True), ('id', '!=', id)]",
        help='Corporate group parent. Use for tập đoàn structures where a '
             'parent company on-lends to subsidiaries. Independent of the '
             'standard contact hierarchy (parent_id).',
    )
    subsidiary_ids = fields.One2many(
        'res.partner', 'parent_company_id', string='Subsidiaries',
    )

    # ------------------------------------------------------------------
    # Normalization
    # ------------------------------------------------------------------
    @staticmethod
    def norm_national_id(value):
        """Digits only. Keeps leading zeros, so it must stay a string."""
        return re.sub(r'\D', '', value or '') or False

    @staticmethod
    def norm_tax_code(value):
        """Strip spaces and dots; keep the dash of a branch code.

        `0123456789-001` and `0123456789 - 001` are the same tax code, but
        `0123456789` (parent) and `0123456789-001` (branch) are NOT — the
        dash carries meaning and must survive.
        """
        v = re.sub(r'[^\d-]', '', (value or '').strip())
        return v or False

    @api.depends('vn_national_id', 'vn_tax_code')
    def _compute_identity_norm(self):
        for rec in self:
            rec.vn_national_id_norm = self.norm_national_id(rec.vn_national_id)
            rec.vn_tax_code_norm = self.norm_tax_code(rec.vn_tax_code)

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------
    @api.constrains('vn_national_id')
    def _check_vn_national_id(self):
        # Kiểm tra trên giá trị ĐÃ CHUẨN HOÁ, không phải chuỗi người gõ.
        # Người dùng gõ "079 123 456 789" là chuyện bình thường; bắt lỗi
        # cách gõ chỉ khiến họ bỏ trống ô CCCD — mà đó lại là khoá nhận
        # diện chắc chắn nhất mình có.
        for rec in self:
            v = self.norm_national_id(rec.vn_national_id) or ''
            if v and not (RE_CMND.fullmatch(v) or RE_CCCD.fullmatch(v)):
                raise ValidationError(_(
                    "National ID '%s' is not a valid Vietnamese CMND "
                    "(9 digits) or CCCD (12 digits)."
                ) % v)

    @api.constrains('vn_tax_code')
    def _check_vn_tax_code(self):
        for rec in self:
            v = self.norm_tax_code(rec.vn_tax_code) or ''
            if v and not RE_TAX_CODE.fullmatch(v):
                raise ValidationError(_(
                    "Tax code '%s' is invalid. Use 10 digits, or "
                    "10-3 digits for a branch (e.g. 0123456789-001)."
                ) % v)

    # Soft uniqueness scoped per company. Allow duplicates ACROSS
    # companies (a partner shared in multiple Odoo companies can repeat)
    # but disallow within a company.
    #
    # A record that carries `identity_dup_ack` is exempt: keeping the guard
    # as an outright ban means there is no way to record the real-world
    # cases where the same tax code legitimately appears twice, and people
    # work around a ban by mistyping the tax code — which destroys the join
    # key this constraint exists to protect. Two ordinary records still
    # cannot collide; only a deliberate, reasoned exception can.
    # So trên giá trị canonical, không so chuỗi thô: "0123456789" và
    # "0123456789 " là cùng một mã số thuế, ràng buộc trên chuỗi thô cho
    # cả hai cùng tồn tại và khoá định danh mất tác dụng.
    _vn_tax_code_company_uniq = models.Constraint(
        'EXCLUDE (company_id WITH =, vn_tax_code_norm WITH =) '
        'WHERE (vn_tax_code_norm IS NOT NULL AND vn_tax_code_norm <> \'\' '
        'AND identity_dup_ack IS NOT TRUE)',
        'A partner with this tax code already exists in this company.',
    )
