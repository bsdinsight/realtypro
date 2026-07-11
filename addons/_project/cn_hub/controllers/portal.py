# -*- coding: utf-8 -*-
"""Portal nhà thầu — quy trình mời thầu:

- Chỉ thấy gói được MỜI (invitation-gated).
- Tải hồ sơ mời thầu (dossier).
- Nộp báo giá + upload nhiều tài liệu theo checklist yêu cầu.
- Link nhận thư mời /cn/invite/<token> (đăng nhập hoặc đăng ký rồi vào thẳng).
"""
import base64

from odoo import http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal


class CnPortal(CustomerPortal):

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _cn_partner(self):
        return request.env.user.partner_id

    def _cn_invited_tenders(self):
        """Các gói mà partner hiện tại được mời (recordset cn.tender)."""
        partner = self._cn_partner()
        invites = request.env['cn.tender.invite'].sudo().search(
            [('partner_id', '=', partner.id)])
        return invites.mapped('tender_id')

    def _cn_is_invited(self, tender_id):
        partner = self._cn_partner()
        return bool(request.env['cn.tender.invite'].sudo().search_count(
            [('tender_id', '=', tender_id), ('partner_id', '=', partner.id)]))

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        partner = self._cn_partner()
        invited = self._cn_invited_tenders().filtered(
            lambda t: t.state in ('open', 'closed', 'awarded'))
        values['cn_tender_count'] = len(invited)
        values['cn_bid_count'] = request.env['cn.bid'].search_count(
            [('contractor_id', '=', partner.id)])
        return values

    # ------------------------------------------------------------------
    # Danh sách gói được mời
    # ------------------------------------------------------------------
    @http.route(['/my/tenders'], type='http', auth='user', website=True)
    def cn_my_tenders(self, **kw):
        tenders = self._cn_invited_tenders().filtered(
            lambda t: t.state in ('open', 'closed', 'awarded')).sorted(
            key=lambda t: (t.deadline or fields_max(), t.id))
        return request.render('cn_hub.portal_my_tenders', {
            'tenders': tenders, 'page_name': 'cn_tender',
        })

    @http.route(['/my/tenders/<int:tender_id>'], type='http',
                auth='user', website=True)
    def cn_tender_detail(self, tender_id, **kw):
        if not self._cn_is_invited(tender_id):
            return request.redirect('/my/tenders')
        tender = request.env['cn.tender'].sudo().browse(tender_id)
        if not tender.exists() or tender.state not in (
                'open', 'closed', 'awarded'):
            return request.redirect('/my/tenders')
        partner = self._cn_partner()
        existing = request.env['cn.bid'].sudo().search([
            ('tender_id', '=', tender_id),
            ('contractor_id', '=', partner.id)], limit=1)
        # đánh dấu đã xem
        invite = request.env['cn.tender.invite'].sudo().search([
            ('tender_id', '=', tender_id),
            ('partner_id', '=', partner.id)], limit=1)
        if invite and invite.state in ('draft', 'invited', 'registered'):
            invite.state = 'viewed'
        # map req_id -> tài liệu đã nộp (để hiện trạng thái)
        submitted = {}
        if existing:
            for d in existing.document_ids:
                if d.req_id:
                    submitted[d.req_id.id] = d
        return request.render('cn_hub.portal_tender_detail', {
            'tender': tender, 'existing_bid': existing,
            'submitted_docs': submitted, 'page_name': 'cn_tender',
        })

    # ------------------------------------------------------------------
    # Tải hồ sơ mời thầu (dossier)
    # ------------------------------------------------------------------
    @http.route(['/my/tenders/<int:tender_id>/dossier/<int:doc_id>'],
                type='http', auth='user', website=True)
    def cn_dossier_download(self, tender_id, doc_id, **kw):
        if not self._cn_is_invited(tender_id):
            return request.redirect('/my/tenders')
        doc = request.env['cn.tender.document'].sudo().browse(doc_id)
        if not doc.exists() or doc.tender_id.id != tender_id or not doc.attachment:
            return request.redirect('/my/tenders/%s' % tender_id)
        data = base64.b64decode(doc.attachment)
        fname = doc.filename or (doc.name + '.dat')
        return request.make_response(data, headers=[
            ('Content-Type', 'application/octet-stream'),
            ('Content-Disposition', http.content_disposition(fname)),
            ('Content-Length', len(data)),
        ])

    # ------------------------------------------------------------------
    # Nộp / cập nhật hồ sơ dự thầu (giá + nhiều tài liệu)
    # ------------------------------------------------------------------
    @http.route(['/my/tenders/<int:tender_id>/bid'], type='http',
                auth='user', website=True, methods=['POST'])
    def cn_submit_bid(self, tender_id, **post):
        partner = self._cn_partner()
        tender = request.env['cn.tender'].sudo().browse(tender_id)
        if (not tender.exists() or tender.state != 'open'
                or not self._cn_is_invited(tender_id)):
            return request.redirect('/my/tenders')

        try:
            price = float(post.get('price') or 0)
        except (ValueError, TypeError):
            price = 0.0

        Bid = request.env['cn.bid'].sudo()
        bid = Bid.search([('tender_id', '=', tender_id),
                          ('contractor_id', '=', partner.id)], limit=1)
        vals = {'price': price, 'note': post.get('note')}
        if bid:
            bid.write(vals)
        else:
            bid = Bid.create(dict(vals, tender_id=tender_id,
                                  contractor_id=partner.id))

        BidDoc = request.env['cn.bid.document'].sudo()
        files = request.httprequest.files

        # 1 file cho mỗi tài liệu yêu cầu (input name req_<id>)
        for req in tender.doc_req_ids:
            f = files.get('req_%s' % req.id)
            if not f or not f.filename:
                continue
            data = base64.b64encode(f.read())
            dvals = {
                'name': req.name, 'doc_type': req.doc_type,
                'req_id': req.id, 'attachment': data, 'filename': f.filename,
            }
            existing = bid.document_ids.filtered(lambda d: d.req_id.id == req.id)
            if existing:
                existing[0].write(dvals)
            else:
                BidDoc.create(dict(dvals, bid_id=bid.id))

        # tài liệu bổ sung (nhiều file, input name extra_files)
        for f in files.getlist('extra_files'):
            if not f or not f.filename:
                continue
            data = base64.b64encode(f.read())
            BidDoc.create({
                'bid_id': bid.id, 'name': f.filename, 'doc_type': 'other',
                'attachment': data, 'filename': f.filename,
            })

        # đánh dấu thư mời đã nộp
        invite = request.env['cn.tender.invite'].sudo().search([
            ('tender_id', '=', tender_id),
            ('partner_id', '=', partner.id)], limit=1)
        if invite:
            invite.state = 'submitted'

        return request.redirect('/my/tenders/%s?submitted=1' % tender_id)

    @http.route(['/my/bids'], type='http', auth='user', website=True)
    def cn_my_bids(self, **kw):
        partner = self._cn_partner()
        bids = request.env['cn.bid'].search(
            [('contractor_id', '=', partner.id)], order='date_submit desc')
        return request.render('cn_hub.portal_my_bids', {
            'bids': bids, 'page_name': 'cn_bid',
        })

    # ------------------------------------------------------------------
    # Nhận thư mời: đăng nhập/đăng ký rồi vào thẳng gói
    # ------------------------------------------------------------------
    @http.route(['/cn/invite/<string:token>'], type='http',
                auth='public', website=True, sitemap=False)
    def cn_invite_accept(self, token, **kw):
        invite = request.env['cn.tender.invite'].sudo().search(
            [('access_token', '=', token)], limit=1)
        if not invite:
            return request.redirect('/my')
        user = request.env.user
        if user and not user._is_public():
            # đã đăng nhập → gắn partner (nếu chưa) + đánh dấu, vào gói
            if not invite.partner_id:
                invite.partner_id = user.partner_id
            if invite.state in ('draft', 'invited'):
                invite.state = 'registered'
            return request.redirect('/my/tenders/%s' % invite.tender_id.id)
        # chưa đăng nhập → tới trang đăng nhập/đăng ký
        return request.redirect(invite._signup_url())


def fields_max():
    """Ngày lớn để đẩy gói không có hạn nộp xuống cuối khi sort."""
    import datetime
    return datetime.date(9999, 12, 31)
