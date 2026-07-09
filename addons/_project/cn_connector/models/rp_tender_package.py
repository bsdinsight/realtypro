# -*- coding: utf-8 -*-
"""Gói thầu: công bố lên Construction Network + đồng bộ hồ sơ dự thầu."""
import requests

from odoo import _, fields, models
from odoo.exceptions import UserError


class RpTenderPackage(models.Model):
    _inherit = 'rp.tender.package'

    cn_published = fields.Boolean(string='Đã công bố lên Network',
                                  readonly=True, copy=False)
    cn_ref = fields.Char(string='Mã trên Network', readonly=True, copy=False)

    def _cn_config(self):
        icp = self.env['ir.config_parameter'].sudo()
        url = (icp.get_param('cn_connector.hub_url') or '').rstrip('/')
        key = icp.get_param('cn_connector.api_key') or ''
        if not url or not key:
            raise UserError(_(
                'Chưa cấu hình Construction Network URL / API key '
                '(Cấu hình → Cài đặt).'))
        return url, key

    def action_publish_to_network(self):
        self.ensure_one()
        url, key = self._cn_config()
        ref = self.cn_ref or ('PKG%s' % self.id)
        specialty = ''
        if self.selection_method:
            specialty = dict(
                self._fields['selection_method'].selection).get(
                self.selection_method, '')
        payload = {
            'ref': ref,
            'name': self.name,
            'gc_name': (self.company_id or self.env.company).name,
            'gc_source': self.env.cr.dbname,
            'specialty': specialty,
            'budget': 0.0,
            'deadline': (str(self.deadline_contract)
                         if self.deadline_contract else False),
        }
        try:
            resp = requests.post(
                url + '/cn/api/tender/publish', json=payload,
                headers={'X-CN-API-KEY': key}, timeout=25)
            data = resp.json()
        except Exception as e:  # noqa: BLE001
            raise UserError(_('Lỗi gọi Network: %s', e))
        if not data.get('ok'):
            raise UserError(_('Network từ chối: %s', data))
        self.write({'cn_published': True, 'cn_ref': ref})
        self.message_post(body=_(
            'Đã công bố gói thầu lên Construction Network (mã %s).', ref))
        return True

    def action_sync_bids(self):
        self.ensure_one()
        url, key = self._cn_config()
        ref = self.cn_ref or ('PKG%s' % self.id)
        try:
            resp = requests.get(
                '%s/cn/api/tender/%s/bids' % (url, ref),
                headers={'X-CN-API-KEY': key}, timeout=25)
            data = resp.json()
        except Exception as e:  # noqa: BLE001
            raise UserError(_('Lỗi gọi Network: %s', e))
        if not data.get('ok'):
            raise UserError(_('Network trả lỗi: %s', data))
        Partner = self.env['res.partner']
        Contractor = self.env['rp.contractor']
        Bidder = self.env['rp.tender.bidder']
        n = 0
        for b in data.get('bids', []):
            cname = b.get('contractor')
            if not cname:
                continue
            partner = Partner.search([('name', '=', cname)], limit=1) \
                or Partner.create({'name': cname, 'is_company': True})
            contractor = Contractor.search(
                [('partner_id', '=', partner.id)], limit=1) or Contractor.create({
                    'partner_id': partner.id,
                    'contractor_type': 'general',
                    'state': 'approved'})
            bidder = self.bidder_ids.filtered(
                lambda x: x.contractor_id == contractor)
            vals = {
                'package_id': self.id,
                'contractor_id': contractor.id,
                'price_offered': b.get('price') or 0.0,
                'status': 'submitted',
            }
            if bidder:
                bidder.write(vals)
            else:
                Bidder.create(vals)
            n += 1
        self.message_post(body=_(
            'Đồng bộ %s hồ sơ dự thầu từ Construction Network.', n))
        return True
