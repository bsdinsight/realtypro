# -*- coding: utf-8 -*-
"""Mở rộng quy trình mời thầu: hồ sơ mời thầu, checklist tài liệu yêu cầu,
thư mời (dùng signup-token Odoo), và tài liệu nhà thầu nộp kèm hồ sơ dự thầu.
"""
import uuid

from odoo import _, api, fields, models
from odoo.exceptions import UserError

# Phân loại tài liệu dùng chung (hồ sơ mời thầu + tài liệu nhà thầu nộp)
DOC_TYPES = [
    # Hồ sơ hành chính - pháp lý (theo mẫu HSMT xây lắp)
    ('bid_letter', 'Đơn dự thầu'),
    ('joint_agreement', 'Thỏa thuận liên danh'),
    ('guarantee', 'Bảo lãnh dự thầu'),
    ('business_reg', 'ĐKKD / GCN đăng ký DN'),
    ('capacity_cert', 'Chứng chỉ năng lực hoạt động XD'),
    # Đề xuất kỹ thuật
    ('capability', 'Hồ sơ năng lực'),
    ('method', 'Biện pháp/phương án thi công'),
    ('schedule', 'Tiến độ thi công'),
    ('safety', 'Giải pháp chất lượng, ATLĐ, môi trường'),
    ('subcontractor', 'Kê khai thầu phụ'),
    # Đề xuất tài chính
    ('quote', 'Báo giá / đơn giá dự thầu'),
    ('price_detail', 'Bảng giá chi tiết (khối lượng - đơn giá)'),
    # Năng lực - tài chính
    ('financial_report', 'Báo cáo tài chính / kiểm toán'),
    ('credit_commitment', 'Cam kết cung cấp tín dụng'),
    # Chung
    ('boq', 'Bảng khối lượng (BOQ)'),
    ('drawing', 'Bản vẽ'),
    ('spec', 'Chỉ dẫn kỹ thuật'),
    ('condition', 'Điều kiện hợp đồng'),
    ('other', 'Khác'),
]


class CnTenderDocument(models.Model):
    """Hồ sơ MỜI thầu — tài liệu do bên mời thầu (GC/CĐT) cung cấp."""
    _name = 'cn.tender.document'
    _description = 'Tài liệu hồ sơ mời thầu'
    _order = 'sequence, id'

    tender_id = fields.Many2one(
        'cn.tender', string='Gói thầu', required=True, ondelete='cascade',
        index=True)
    sequence = fields.Integer(default=10)
    name = fields.Char(string='Tên tài liệu', required=True)
    category = fields.Selection(DOC_TYPES, string='Loại', default='other')
    attachment = fields.Binary(string='Tệp', attachment=True, required=True)
    filename = fields.Char(string='Tên tệp')
    note = fields.Char(string='Ghi chú')


class CnTenderDocReq(models.Model):
    """Checklist tài liệu YÊU CẦU nhà thầu phải nộp."""
    _name = 'cn.tender.doc.req'
    _description = 'Tài liệu yêu cầu nộp'
    _order = 'sequence, id'

    tender_id = fields.Many2one(
        'cn.tender', string='Gói thầu', required=True, ondelete='cascade',
        index=True)
    sequence = fields.Integer(default=10)
    name = fields.Char(string='Tài liệu yêu cầu', required=True)
    doc_type = fields.Selection(DOC_TYPES, string='Loại', default='other')
    required = fields.Boolean(string='Bắt buộc', default=True)
    note = fields.Char(string='Hướng dẫn')


class CnTenderInvite(models.Model):
    """Thư mời thầu gửi tới một nhà thầu (theo email)."""
    _name = 'cn.tender.invite'
    _description = 'Thư mời thầu'
    _inherit = ['mail.thread']
    _order = 'id desc'

    tender_id = fields.Many2one(
        'cn.tender', string='Gói thầu', required=True, ondelete='cascade',
        index=True)
    partner_id = fields.Many2one(
        'res.partner', string='Nhà thầu', index=True,
        help='Hồ sơ nhà thầu trên Network (tạo/khớp theo email khi gửi mời).')
    partner_name = fields.Char(string='Tên nhà thầu')
    email = fields.Char(string='Email', required=True)
    access_token = fields.Char(
        string='Mã mời', default=lambda self: uuid.uuid4().hex, copy=False,
        index=True, readonly=True)
    invite_url = fields.Char(string='Link thư mời', compute='_compute_invite_url')
    state = fields.Selection(
        [('draft', 'Nháp'),
         ('invited', 'Đã gửi mời'),
         ('registered', 'Đã đăng ký'),
         ('viewed', 'Đã xem gói'),
         ('submitted', 'Đã nộp hồ sơ'),
         ('declined', 'Từ chối')],
        string='Trạng thái', default='draft', required=True, tracking=True)
    invited_date = fields.Datetime(string='Ngày gửi mời', copy=False)
    company_id = fields.Many2one(related='tender_id.company_id', store=True)

    _uniq_invite = models.Constraint(
        'unique(tender_id, email)',
        'Mỗi email chỉ mời 1 lần trên mỗi gói thầu.')

    @api.depends('access_token')
    def _compute_invite_url(self):
        base = self.env['ir.config_parameter'].sudo().get_param(
            'web.base.url', '')
        for rec in self:
            rec.invite_url = (
                '%s/cn/invite/%s' % (base, rec.access_token)
                if rec.access_token else False)

    # ------------------------------------------------------------------
    def _ensure_partner(self):
        """Tạo/khớp res.partner theo email + đánh dấu là nhà thầu."""
        self.ensure_one()
        if self.partner_id:
            return self.partner_id
        Partner = self.env['res.partner'].sudo()
        partner = Partner.search([('email', '=', self.email)], limit=1)
        if not partner:
            partner = Partner.create({
                'name': self.partner_name or self.email,
                'email': self.email,
                'is_company': True,
                'cn_is_contractor': True,
            })
        elif not partner.cn_is_contractor:
            partner.cn_is_contractor = True
        self.partner_id = partner
        return partner

    def _signup_url(self):
        """URL để nhà thầu đăng ký/đăng nhập rồi vào thẳng gói.

        Odoo 19: dùng ``_get_signup_url_for_action(url=redirect)`` — tự sinh
        signup token (nếu partner chưa có user + đã signup_prepare) và chèn
        redirect; partner đã có user thì ra URL đăng nhập kèm redirect.
        """
        self.ensure_one()
        partner = self.partner_id.sudo()
        redirect = '/my/tenders/%s' % self.tender_id.id
        if not partner.user_ids:
            partner.signup_prepare()
        urls = partner.with_context(signup_valid=True)._get_signup_url_for_action(
            url=redirect)
        return urls.get(partner.id) or (partner.get_base_url() + redirect)

    def action_send_invite(self):
        template = self.env.ref(
            'cn_hub.mail_template_tender_invite', raise_if_not_found=False)
        for rec in self:
            partner = rec._ensure_partner()
            # chuẩn bị signup cho nhà thầu chưa có tài khoản
            if not partner.user_ids:
                partner.sudo().signup_prepare()
            if template:
                # force_send=False → vào hàng đợi, tự gửi khi có SMTP
                template.send_mail(rec.id, force_send=False)
            rec.write({
                'state': 'invited',
                'invited_date': fields.Datetime.now(),
            })
        return True

    def action_open_tender(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'cn.tender',
            'res_id': self.tender_id.id,
            'view_mode': 'form',
        }


class CnBidDocument(models.Model):
    """Tài liệu nhà thầu NỘP kèm hồ sơ dự thầu."""
    _name = 'cn.bid.document'
    _description = 'Tài liệu hồ sơ dự thầu'
    _order = 'sequence, id'

    bid_id = fields.Many2one(
        'cn.bid', string='Hồ sơ dự thầu', required=True, ondelete='cascade',
        index=True)
    req_id = fields.Many2one(
        'cn.tender.doc.req', string='Đáp ứng yêu cầu', ondelete='set null')
    sequence = fields.Integer(default=10)
    name = fields.Char(string='Tên tài liệu', required=True)
    doc_type = fields.Selection(DOC_TYPES, string='Loại', default='other')
    attachment = fields.Binary(string='Tệp', attachment=True, required=True)
    filename = fields.Char(string='Tên tệp')
    upload_date = fields.Datetime(
        string='Ngày tải lên', default=fields.Datetime.now)
