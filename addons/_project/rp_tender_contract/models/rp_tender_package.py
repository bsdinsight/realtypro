# -*- coding: utf-8 -*-
"""Bridge: rp.tender.package × rp.contract.

Override action_contract → auto-tạo rp.contract draft từ winning bidder.
Add reverse O2M contract_ids để tracking từ gói thầu.
"""

from odoo import api, fields, models
from odoo.exceptions import UserError


class RpTenderPackage(models.Model):
    _inherit = 'rp.tender.package'

    # Reverse từ rp.contract.tender_package_id (Required M2O)
    contract_ids = fields.One2many(
        'rp.contract', 'tender_package_id',
        string='HĐ ký từ gói thầu',
    )
    contract_count = fields.Integer(
        compute='_compute_contract_count', store=False,
    )
    primary_contract_id = fields.Many2one(
        'rp.contract', compute='_compute_primary_contract',
        store=False,
        help='HĐ chính ký từ gói thầu (HĐ đầu tiên, không phải '
             'phụ lục).',
    )

    @api.depends('contract_ids')
    def _compute_contract_count(self):
        for pkg in self:
            pkg.contract_count = len(pkg.contract_ids)

    @api.depends('contract_ids')
    def _compute_primary_contract(self):
        for pkg in self:
            pkg.primary_contract_id = pkg.contract_ids[:1]

    def action_contract(self):
        """Override: auto-tạo rp.contract draft khi đi từ awarded
        → contracted.

        - Đã có HĐ (contract_ids) → skip create, chỉ chuyển state
        - Chưa có HĐ → tạo 1 HĐ draft với:
            name = '{pkg.code}-HD' hoặc 'HD-{pkg.id}'
            tender_package_id = pkg.id
            contractor_id = pkg.contractor_id
            contract_value_pretax = pkg.contract_amount
            contract_date = pkg.date_award_signed or today
            state = 'draft'
        """
        today = fields.Date.context_today(self)
        Contract = self.env['rp.contract']
        for pkg in self:
            if pkg.state != 'awarded':
                continue
            pkg._require_fields({
                'contract_amount': 'Giá trị HĐ ký',
            })
            if not pkg.date_award_signed:
                pkg.date_award_signed = today

            # Tạo HĐ nếu chưa có
            if not pkg.contract_ids:
                if not pkg.contractor_id:
                    raise UserError(
                        'Gói thầu chưa có nhà thầu trúng — không thể '
                        'tạo HĐ.')
                name = (f'{pkg.code}-HD' if pkg.code
                        else f'HD-PKG{pkg.id}')
                Contract.create({
                    'name': name,
                    'tender_package_id': pkg.id,
                    'contractor_id': pkg.contractor_id.id,
                    'contract_value_pretax': pkg.contract_amount,
                    'contract_date': pkg.date_award_signed,
                    'state': 'draft',
                })

            pkg.state = 'contracted'

    def action_open_contracts(self):
        """Mở list HĐ của gói thầu (cho stat button)."""
        self.ensure_one()
        if self.contract_count == 1:
            return {
                'type': 'ir.actions.act_window',
                'name': f'HĐ — {self.name}',
                'res_model': 'rp.contract',
                'view_mode': 'form',
                'res_id': self.contract_ids[0].id,
            }
        return {
            'type': 'ir.actions.act_window',
            'name': f'HĐ ký từ — {self.name}',
            'res_model': 'rp.contract',
            'view_mode': 'list,form',
            'domain': [('tender_package_id', '=', self.id)],
            'context': {'default_tender_package_id': self.id},
        }
