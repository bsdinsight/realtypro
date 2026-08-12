# -*- coding: utf-8 -*-
"""Đăng ký nhà thầu bằng MÃ SỐ THUẾ tại `/dang-ky`.

Luật định danh: **1 MST = 1 công ty = 1 tài khoản gốc**. Người đăng ký đầu
tiên của một MST trở thành *quản trị viên công ty*; ai nhập trùng MST sẽ
KHÔNG tạo được tài khoản mới mà được hướng dẫn liên hệ quản trị viên đó
(đây là điểm mấu chốt của form này).

Network là một sàn duy nhất (gộp nhà thầu + nhà cung ứng) nên công ty chọn
NHIỀU vai trò (thi công/vật tư/nhân công/nội thất/dịch vụ) ngay khi đăng ký
— khai hồ sơ một lần, dùng cho mọi gói.

Mọi kiểm tra đều làm LẠI ở server: đây là endpoint công khai, không tin
dữ liệu từ trình duyệt.
"""
import re

from odoo import _, http
from odoo.exceptions import UserError
from odoo.http import request

from odoo.addons.auth_signup.controllers.main import AuthSignupHome

from ..models.cn_contractor import MST_RE, normalize_mst

EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
MIN_PWD = 8


class CnHubSignup(http.Controller):

    # ------------------------------------------------------------------
    @http.route('/dang-ky', type='http', auth='public', methods=['GET', 'POST'],
                website=False)
    def dang_ky(self, **post):
        invite = self._get_invite(post.get('invite'))
        if request.session.uid:
            # đã đăng nhập: nếu tới từ lời mời thì nhận luôn rồi vào gói
            if invite:
                return request.redirect('/cn/invite/%s' % invite.access_token)
            return request.redirect('/my')
        qcontext = self._values(post)
        if invite:
            qcontext.update({
                'invite': invite,
                'email': invite.email,          # khoá theo email được mời
                'tender': invite.tender_id,
                'gc_name': invite.tender_id.gc_partner_id.name or '',
                'deadline_txt': (invite.tender_id.deadline.strftime('%d/%m/%Y')
                                 if invite.tender_id.deadline else ''),
            })
        tpl = 'cn_hub.signup_invite' if invite else 'cn_hub.signup'
        if request.httprequest.method == 'GET':
            return request.render(tpl, qcontext)

        # ---- POST: kiểm tra lại toàn bộ ở server ----
        mst = normalize_mst(qcontext['mst'])
        qcontext['mst'] = mst
        dup = self._find_company(mst)
        if dup:
            # Không báo lỗi cụt — chỉ đường cho họ. Khi tới từ lời mời thì
            # chỉ cần ĐĂNG NHẬP là nhận được lời mời (khác luồng tự đăng ký).
            qcontext['dup_company'] = dup.name
            qcontext['dup_mst'] = dup.cn_tax_code
            return request.render(tpl, qcontext)

        errors = self._validate(qcontext, invite=invite)
        if errors:
            qcontext['errors'] = errors
            return request.render(tpl, qcontext)

        try:
            company = self._create_account(qcontext)
            if invite:
                # ĐƯỢC MỜI = DUYỆT SẴN (khác tự đăng ký phải chờ tổng thầu)
                invite.sudo().write({
                    'partner_id': company.id,
                    'partner_name': company.name,
                    'approval': 'approved',
                    'state': 'registered',
                })
                invite.tender_id.sudo().message_post(body=_(
                    '<b>%s</b> đã đăng ký từ thư mời và được mở gói ngay.',
                    company.name))
        except UserError as e:
            qcontext['errors'] = {'global': str(e)}
            return request.render(tpl, qcontext)
        except Exception as e:  # noqa: BLE001
            request.env.cr.rollback()
            qcontext['errors'] = {'global': _(
                'Không tạo được tài khoản: %s', e)}
            return request.render(tpl, qcontext)

        # Đăng nhập luôn cho khỏi bắt gõ lại mật khẩu
        try:
            request.session.authenticate(request.env, {
                'type': 'password',
                'login': qcontext['email'],
                'password': qcontext['password'],
            })
        except Exception:  # noqa: BLE001
            return request.redirect('/web/login')
        if invite:
            return request.redirect('/my/tenders/%s' % invite.tender_id.id)
        return request.redirect('/dang-ky/hoan-tat')

    @http.route('/loi-moi/<string:token>', type='http', auth='public',
                website=False)
    def loi_moi(self, token, **kw):
        """Trang lời mời — điểm đến của link trong thư mời.

        Đã đăng nhập → nhận lời mời rồi vào gói luôn. Chưa → sang
        `/dang-ky?invite=<token>` (form CÓ Mã số thuế). Trước đây link mời
        trỏ thẳng signup gốc Odoo nên nhà thầu được mời tạo được tài khoản
        KHÔNG có MST — lách luật '1 MST = 1 công ty'.
        """
        invite = self._get_invite(token)
        if not invite:
            return request.redirect('/')
        if request.session.uid:
            return request.redirect('/cn/invite/%s' % token)
        return request.redirect('/dang-ky?invite=%s' % token)

    @http.route('/dang-ky/hoan-tat', type='http', auth='user', website=False)
    def dang_ky_hoan_tat(self, **kw):
        partner = request.env.user.partner_id
        company = partner.parent_id or partner
        pct = int(company.cn_profile_progress or 0)
        # Tính sẵn chuỗi có '%' ở đây: dùng '%' trong biểu thức QWeb sẽ vỡ
        # ("ValueError: incomplete format").
        return request.render('cn_hub.signup_done', {
            'company': company,
            'progress_pct': '%d%%' % pct,
            'progress_style': 'width:%d%%' % pct,
        })

    # ------------------------------------------------------------------
    @http.route('/dang-ky/kiem-tra-mst', type='jsonrpc', auth='public',
                methods=['POST'], csrf=False)
    def kiem_tra_mst(self, mst=None, **kw):
        """Kiểm tra MST khi người dùng rời ô nhập — để hiện bảng 'công ty đã
        có' ngay, không bắt họ điền hết form rồi mới báo."""
        mst = normalize_mst(mst or '')
        if not mst or not MST_RE.match(mst):
            return {'valid': False}
        p = self._find_company(mst)
        return {
            'valid': True,
            'exists': bool(p),
            'company': p.name if p else '',
            'mst': mst,
        }

    # ------------------------------------------------------------------
    def _get_invite(self, token):
        if not token:
            return None
        return request.env['cn.tender.invite'].sudo().search(
            [('access_token', '=', token)], limit=1) or None

    def _find_company(self, mst):
        if not mst:
            return None
        return request.env['res.partner'].sudo().search(
            [('cn_tax_code', '=', mst)], limit=1) or None

    def _values(self, post):
        get = lambda k: (post.get(k) or '').strip()  # noqa: E731
        return {
            'company': get('company'), 'mst': get('mst'),
            'contact': get('contact'), 'email': get('email').lower(),
            'phone': get('phone'),
            'password': post.get('password') or '',
            'password2': post.get('password2') or '',
            'agree': bool(post.get('agree')),
            'roles': request.httprequest.form.getlist('roles'),
            'all_roles': request.env['cn.role'].sudo().search([]),
            'errors': {}, 'dup_company': None,
        }

    def _validate(self, v, invite=None):
        e = {}
        if not v['company']:
            e['company'] = _('Chưa nhập tên công ty.')
        if not v['mst']:
            e['mst'] = _('Chưa nhập mã số thuế.')
        elif not MST_RE.match(v['mst']):
            e['mst'] = _('Mã số thuế phải là 10 chữ số, hoặc dạng '
                         'xxxxxxxxxx-xxx (chi nhánh).')
        if not v['contact']:
            e['contact'] = _('Chưa nhập người liên hệ.')
        if not v['email']:
            e['email'] = _('Chưa nhập email.')
        elif not EMAIL_RE.match(v['email']):
            e['email'] = _('Email chưa đúng định dạng.')
        elif request.env['res.users'].sudo().search_count(
                [('login', '=', v['email'])]):
            e['email'] = _('Email này đã có tài khoản. Bạn hãy đăng nhập.')
        if invite and v['email'] != (invite.email or '').lower():
            # ô email readonly — lệch nghĩa là bị sửa ở client
            e['email'] = _('Email phải trùng với email được mời.')
        if not v['phone']:
            e['phone'] = _('Chưa nhập số điện thoại.')
        if len(v['password']) < MIN_PWD:
            e['password'] = _('Mật khẩu tối thiểu %s ký tự.', MIN_PWD)
        elif v['password'] != v['password2']:
            e['password2'] = _('Mật khẩu xác nhận chưa khớp.')
        if not v['roles']:
            e['roles'] = _('Chọn ít nhất một vai trò công ty bạn cung cấp.')
        if not v['agree']:
            e['agree'] = _('Bạn cần đồng ý với điều khoản.')
        return e

    def _create_account(self, v):
        Partner = request.env['res.partner'].sudo()
        roles = request.env['cn.role'].sudo().search(
            [('code', 'in', v['roles'])])
        company = Partner.create({
            'name': v['company'],
            'is_company': True,
            'cn_tax_code': v['mst'],
            'phone': v['phone'],
            'email': v['email'],
            'cn_role_ids': [(6, 0, roles.ids)],
        })
        # signup() của auth_signup: tạo user portal theo template (đúng nhóm),
        # tôn trọng cấu hình auth_signup.invitation_scope.
        request.env['res.users'].sudo().signup({
            'name': v['contact'],
            'login': v['email'],
            'password': v['password'],
            'email': v['email'],
        })
        user = request.env['res.users'].sudo().search(
            [('login', '=', v['email'])], limit=1)
        # Người đăng ký ĐẦU TIÊN của MST = quản trị viên công ty
        user.partner_id.write({
            'parent_id': company.id,
            'phone': v['phone'],
            'function': _('Quản trị viên tài khoản'),
        })
        return company


class CnHubNativeSignup(AuthSignupHome):
    """Chặn cửa hậu: signup gốc Odoo KHÔNG thu Mã số thuế.

    Mọi lối vào /web/signup (link "Don't have an account?" ở trang đăng nhập,
    link cũ, bookmark...) đều phải quay về /dang-ky — nếu không nhà thầu vẫn
    tạo được tài khoản thiếu MST, phá luật "1 MST = 1 công ty" ngay từ cửa
    khác. Giữ lại ?invite / ?redirect nếu có.
    """

    @http.route()
    def web_auth_signup(self, *args, **kw):
        url = '/dang-ky'
        token = kw.get('invite') or kw.get('token')
        if token:
            url += '?invite=%s' % token
        return request.redirect(url)
