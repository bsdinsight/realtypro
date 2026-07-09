# -*- coding: utf-8 -*-
"""Portal nhà thầu: xem gói thầu mở + nộp/cập nhật hồ sơ dự thầu."""
from odoo import http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal


class CnPortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        partner = request.env.user.partner_id
        values['cn_tender_count'] = request.env['cn.tender'].search_count(
            [('state', '=', 'open')])
        values['cn_bid_count'] = request.env['cn.bid'].search_count(
            [('contractor_id', '=', partner.id)])
        return values

    @http.route(['/my/tenders'], type='http', auth='user', website=True)
    def cn_my_tenders(self, **kw):
        tenders = request.env['cn.tender'].search(
            [('state', '=', 'open')], order='deadline')
        return request.render('cn_hub.portal_my_tenders', {
            'tenders': tenders, 'page_name': 'cn_tender',
        })

    @http.route(['/my/tenders/<int:tender_id>'], type='http',
                auth='user', website=True)
    def cn_tender_detail(self, tender_id, **kw):
        tender = request.env['cn.tender'].browse(tender_id)
        if not tender.exists() or tender.state not in (
                'open', 'closed', 'awarded'):
            return request.redirect('/my/tenders')
        partner = request.env.user.partner_id
        existing = request.env['cn.bid'].search([
            ('tender_id', '=', tender_id),
            ('contractor_id', '=', partner.id)], limit=1)
        return request.render('cn_hub.portal_tender_detail', {
            'tender': tender, 'existing_bid': existing,
            'page_name': 'cn_tender',
        })

    @http.route(['/my/tenders/<int:tender_id>/bid'], type='http',
                auth='user', website=True, methods=['POST'])
    def cn_submit_bid(self, tender_id, **post):
        partner = request.env.user.partner_id
        tender = request.env['cn.tender'].sudo().browse(tender_id)
        if not tender.exists() or tender.state != 'open':
            return request.redirect('/my/tenders')
        try:
            price = float(post.get('price') or 0)
        except (ValueError, TypeError):
            price = 0.0
        vals = {'price': price, 'note': post.get('note')}
        Bid = request.env['cn.bid'].sudo()
        existing = Bid.search([
            ('tender_id', '=', tender_id),
            ('contractor_id', '=', partner.id)], limit=1)
        if existing:
            existing.write(vals)
        else:
            Bid.create(dict(vals, tender_id=tender_id,
                            contractor_id=partner.id))
        return request.redirect('/my/bids')

    @http.route(['/my/bids'], type='http', auth='user', website=True)
    def cn_my_bids(self, **kw):
        partner = request.env.user.partner_id
        bids = request.env['cn.bid'].search(
            [('contractor_id', '=', partner.id)], order='date_submit desc')
        return request.render('cn_hub.portal_my_bids', {
            'bids': bids, 'page_name': 'cn_bid',
        })
