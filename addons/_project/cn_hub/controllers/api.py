# -*- coding: utf-8 -*-
"""API connector: Odoo tổng thầu ↔ Hub. Auth bằng shared API key
(system parameter cn_hub.api_key) qua header X-CN-API-KEY."""
import json

from odoo import http
from odoo.http import request


def _authorized():
    key = request.httprequest.headers.get('X-CN-API-KEY')
    expected = request.env['ir.config_parameter'].sudo().get_param(
        'cn_hub.api_key')
    return bool(expected) and key == expected


class CnApi(http.Controller):

    @http.route('/cn/api/tender/publish', type='http', auth='public',
                methods=['POST'], csrf=False)
    def publish_tender(self, **kw):
        if not _authorized():
            return request.make_json_response({'error': 'unauthorized'},
                                              status=401)
        try:
            data = json.loads(request.httprequest.data or b'{}')
        except Exception:
            return request.make_json_response({'error': 'bad json'},
                                              status=400)
        ref = data.get('ref')
        if not ref:
            return request.make_json_response({'error': 'ref required'},
                                              status=400)
        Tender = request.env['cn.tender'].sudo()
        vals = {
            'name': data.get('name') or ref,
            'ref': ref,
            'gc_source': data.get('gc_source'),
            'specialty': data.get('specialty'),
            'description': data.get('description'),
            'budget': data.get('budget') or 0.0,
            'deadline': data.get('deadline') or False,
            'state': 'open',
        }
        gc_name = data.get('gc_name')
        if gc_name:
            Partner = request.env['res.partner'].sudo()
            gc = Partner.search([('name', '=', gc_name)], limit=1) \
                or Partner.create({'name': gc_name, 'is_company': True})
            vals['gc_partner_id'] = gc.id
        existing = Tender.search([('ref', '=', ref)], limit=1)
        if existing:
            existing.write(vals)
            tender = existing
        else:
            tender = Tender.create(vals)
        return request.make_json_response(
            {'ok': True, 'tender_id': tender.id, 'ref': ref})

    @http.route('/cn/api/tender/<string:ref>/bids', type='http',
                auth='public', methods=['GET'], csrf=False)
    def tender_bids(self, ref, **kw):
        if not _authorized():
            return request.make_json_response({'error': 'unauthorized'},
                                              status=401)
        tender = request.env['cn.tender'].sudo().search(
            [('ref', '=', ref)], limit=1)
        if not tender:
            return request.make_json_response({'error': 'not found'},
                                              status=404)
        bids = [{
            'contractor': b.contractor_id.name,
            'contractor_vat': b.contractor_id.vat or '',
            'price': b.price,
            'state': b.state,
            'note': b.note or '',
            'date_submit': str(b.date_submit or ''),
        } for b in tender.bid_ids]
        return request.make_json_response(
            {'ok': True, 'ref': ref, 'tender': tender.name, 'bids': bids})
