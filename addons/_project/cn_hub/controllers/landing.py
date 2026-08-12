# -*- coding: utf-8 -*-
"""Landing công khai Realty Pro Network tại `/`.

Odoo mặc định điều hướng `/` thẳng vào backend (`/odoo`) — khách vãng lai
(nhà thầu chưa có tài khoản) sẽ thấy màn hình đăng nhập ERP và bỏ đi. Ở đây
ghi đè: **chưa đăng nhập → trang giới thiệu**; đã đăng nhập → giữ nguyên
hành vi gốc (nội bộ vào backend, portal vào /my).

Chỉ hiện gói thầu `visibility='public'` — KHÔNG bao giờ lộ gói mời riêng,
và KHÔNG hiện giá gói (xem cn.tender.visibility).
"""
from odoo import _, http
from odoo.http import request
from odoo.addons.web.controllers.home import Home

PREVIEW_LIMIT = 3


class CnHubHome(Home):

    @http.route('/', type='http', auth='public')
    def index(self, s_action=None, db=None, **kw):
        if request.session.uid:
            # Đã đăng nhập → hành vi gốc của Odoo (backend / portal)
            return super().index(s_action=s_action, db=db, **kw)
        return request.render('cn_hub.landing', self._cn_landing_values())

    # ------------------------------------------------------------------
    def _cn_public_domain(self):
        """Gói thầu được phép hiện công khai."""
        return [('state', '=', 'open'), ('visibility', '=', 'public')]

    def _cn_landing_values(self):
        Tender = request.env['cn.tender'].sudo()
        Partner = request.env['res.partner'].sudo()
        domain = self._cn_public_domain()
        # Số liệu THẬT — không bịa. Đếm đúng cái khách nhìn thấy được.
        gcs = Tender.search(
            [('state', 'in', ('open', 'closed', 'awarded'))]
        ).mapped('gc_partner_id')
        return {
            'tenders': Tender.search(
                domain, order='deadline asc, id desc', limit=PREVIEW_LIMIT),
            'stat_tenders': Tender.search_count(domain),
            'stat_contractors': Partner.search_count(
                [('cn_tax_code', '!=', False)]),
            'stat_gcs': len(gcs),
            # Form đăng ký MST riêng (1 MST = 1 công ty) — KHÔNG dùng
            # /web/signup gốc nữa vì nó không thu Mã số thuế.
            'signup_url': '/dang-ky',
        }


class CnHubTenders(http.Controller):
    """Trang gói thầu CÔNG KHAI `/goi-thau` — không cần đăng nhập.

    Đây là mồi câu nhà thầu: chỉ hiện thông tin an toàn (tên gói · tổng thầu
    · chuyên môn · mô tả · ngày mở · hạn nộp). KHÔNG bao giờ hiện giá gói,
    KHÔNG cho tải hồ sơ mời thầu — muốn xem phải được mời hoặc được duyệt.
    Lọc làm ở SERVER (không tin tham số từ trình duyệt).
    """

    @http.route('/goi-thau', type='http', auth='public', website=False)
    def goi_thau(self, q=None, specialty=None, sort=None, **kw):
        Tender = request.env['cn.tender'].sudo()
        base = [('state', '=', 'open'), ('visibility', '=', 'public')]
        domain = list(base)
        q = (q or '').strip()
        if q:
            domain += ['|', ('name', 'ilike', q), ('description', 'ilike', q)]
        specialty = (specialty or '').strip()
        if specialty:
            domain.append(('specialty', '=', specialty))
        order = 'deadline desc, id desc' if sort == 'late' else 'deadline asc, id desc'
        tenders = Tender.search(domain, order=order)
        # danh sách chuyên môn lấy từ DỮ LIỆU THẬT, không hardcode
        specialties = sorted({
            t.specialty for t in Tender.search(base) if t.specialty})
        return request.render('cn_hub.tender_list', {
            'tenders': tenders,
            'specialties': specialties,
            'q': q, 'specialty': specialty, 'sort': sort or 'soon',
            'count': len(tenders),
            'total': Tender.search_count(base),
            'signup_url': '/dang-ky',
        })


class CnHubApply(http.Controller):
    """Nhà thầu tự đăng ký tham gia một gói thầu CÔNG KHAI.

    Khác với luồng tổng thầu mời (mời = duyệt sẵn), đơn tự đăng ký vào ở
    trạng thái **chờ duyệt**: nhà thầu thấy gói nhưng chưa mở được hồ sơ mời
    thầu và chưa nộp được hồ sơ dự thầu cho tới khi tổng thầu của gói duyệt.
    """

    @http.route('/goi-thau/<int:tender_id>/tham-gia', type='http',
                auth='user', methods=['GET', 'POST'], website=False)
    def tham_gia(self, tender_id, **kw):
        # auth='user' → khách chưa đăng nhập tự bị đẩy sang /web/login rồi
        # quay lại đây. Nhà thầu đăng ký mới sẽ qua /dang-ky trước.
        partner = request.env.user.partner_id.commercial_partner_id
        tender = request.env['cn.tender'].sudo().search(
            [('id', '=', tender_id), ('state', '=', 'open'),
             ('visibility', '=', 'public')], limit=1)
        if not tender:
            # Gói kín / đã đóng / không tồn tại → không lộ gì thêm
            return request.redirect('/')

        Invite = request.env['cn.tender.invite'].sudo()
        # unique(tender_id, email) → khớp theo email trước, rồi tới partner
        inv = Invite.search(
            ['&', ('tender_id', '=', tender.id),
             '|', ('email', '=', request.env.user.login),
             ('partner_id', '=', partner.id)], limit=1)
        created = False
        if not inv:
            inv = Invite.create({
                'tender_id': tender.id,
                'partner_id': partner.id,
                'partner_name': partner.name,
                'email': request.env.user.login,
                'source': 'applied',
                'approval': 'pending',
                'state': 'registered',
            })
            created = True
            tender.message_post(body=_(
                '<b>%s</b> đã đăng ký tham gia gói thầu (chờ duyệt). '
                'Hồ sơ năng lực: %s%% hoàn thiện.',
                partner.name, partner.cn_profile_progress or 0))
            inv._send_tpl('cn_hub.mail_template_apply_new')
        return request.render('cn_hub.apply_done', {
            'tender': tender,
            'invite': inv,
            'company': partner,
            'created': created,
            'progress_pct': '%d%%' % int(partner.cn_profile_progress or 0),
        })
