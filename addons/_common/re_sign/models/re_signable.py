# -*- coding: utf-8 -*-
"""Mixin cho mọi chứng từ ký được.

Model nào muốn ký chỉ cần thêm ``re.signable`` vào ``_inherit`` rồi viết
``_sign_payload()``. Viết cái đó là việc PHẢI nghĩ, không phải thủ tục:
nó quyết định chữ ký bảo chứng cho những gì. Bỏ sót một trường quyết
định (số ngày gia hạn, số tiền) thì sửa trường đó xong chữ ký vẫn báo
hợp lệ — tệ hơn là không có chữ ký, vì giờ có cả một tấm ảnh nói rằng
đã duyệt.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ReSignable(models.AbstractModel):
    _name = 're.signable'
    _description = 'Chứng từ ký được'

    signature_ids = fields.One2many(
        're.signature', 'res_id', string='Chữ ký',
        domain=lambda self: [('res_model', '=', self._name)])
    sign_count = fields.Integer(
        string='Số chữ ký', compute='_compute_sign_state')
    sign_state = fields.Selection(
        [('unsigned', 'Chưa ký'),
         ('signed', 'Đã ký'),
         ('broken', 'Đã sửa sau khi ký')],
        string='Tình trạng ký', compute='_compute_sign_state')
    sign_warning = fields.Char(
        string='Cảnh báo chữ ký', compute='_compute_sign_state')

    # ------------------------------------------------------------------
    def _sign_payload(self):
        """Chuỗi chuẩn tắc của phần NỘI DUNG CHỊU TRÁCH NHIỆM.

        Bắt buộc ghi đè. Không ghi đè thì chữ ký không bảo chứng gì, nên
        ở đây báo lỗi thẳng chứ không trả về một giá trị mặc định nghe
        có vẻ an toàn.
        """
        raise NotImplementedError(
            'Model %s kế thừa re.signable thì phải khai _sign_payload()'
            % self._name)

    def _compute_sign_state(self):
        for rec in self:
            chu_ky = rec.signature_ids
            rec.sign_count = len(chu_ky)
            if not chu_ky:
                rec.sign_state = 'unsigned'
                rec.sign_warning = False
                continue
            hong = chu_ky.filtered(lambda s: not s.is_valid)
            if hong:
                rec.sign_state = 'broken'
                rec.sign_warning = _(
                    '%(n)s trên %(t)s chữ ký không còn hợp lệ — nội dung '
                    'chứng từ đã bị sửa sau khi ký. Phải huỷ chữ ký cũ và '
                    'ký lại thì mới có giá trị.',
                    n=len(hong), t=len(chu_ky))
            else:
                rec.sign_state = 'signed'
                rec.sign_warning = False

    # ------------------------------------------------------------------
    # Ma trận phê duyệt
    # ------------------------------------------------------------------
    def _approval_amount(self):
        """Giá trị dùng để khớp ngưỡng trong luật phê duyệt.

        Ghi đè ở từng chứng từ. Mặc định 0 nghĩa là mọi luật có cận dưới
        đều không áp — an toàn, vì thà không đòi chữ ký còn hơn đòi nhầm
        rồi chặn một chứng từ lẽ ra trôi được.
        """
        return 0.0

    def _approval_project(self):
        """Dự án của chứng từ, để lọc luật theo dự án."""
        self.ensure_one()
        if 'project_id' in self._fields:
            return self.project_id
        return self.env['re.project'].browse()

    approval_rule_ids = fields.Many2many(
        're.approval.rule', string='Bước duyệt áp dụng',
        compute='_compute_approval')
    approval_missing = fields.Char(
        string='Còn thiếu chữ ký', compute='_compute_approval')
    approval_ok = fields.Boolean(
        string='Đủ chữ ký theo luật', compute='_compute_approval')

    def _compute_approval(self):
        from odoo.addons.re_sign.models.re_signature import VAI
        ten_vai = dict(VAI)
        Rule = self.env['re.approval.rule']
        for rec in self:
            luat = Rule._luat_cho(rec)
            rec.approval_rule_ids = luat
            # Chỉ tính chữ ký CÒN HỢP LỆ. Chữ ký đã vỡ vì sửa nội dung
            # mà vẫn tính là đủ thì cả ma trận này thành trang trí.
            da_ky = set(rec.signature_ids.filtered('is_valid').mapped('role'))
            thieu = [ten_vai.get(r.role, r.role)
                     for r in luat if r.required and r.role not in da_ky]
            # Bỏ trùng mà GIỮ thứ tự — hai luật cùng vai thì chỉ nhắc một
            # lần, nhưng thứ tự phải theo thứ tự cấu hình.
            seen, gon = set(), []
            for v in thieu:
                if v not in seen:
                    seen.add(v); gon.append(v)
            rec.approval_missing = ', '.join(gon)
            rec.approval_ok = not gon

    def _check_approval(self):
        """Gọi từ hành động DUYỆT của chứng từ.

        Mức siết đọc từ tham số ``re_sign.approval_enforce``:
        ``off`` bỏ qua, ``warn`` ghi nhật ký rồi cho đi tiếp (mặc định),
        ``block`` chặn hẳn. Mặc định là ``warn`` có chủ đích: bật
        ``block`` ngay từ đầu trên một hệ đang chạy sẽ chặn đứng những
        chứng từ cũ vốn chưa bao giờ cần chữ ký.
        """
        muc = self.env['ir.config_parameter'].sudo().get_param(
            're_sign.approval_enforce', 'warn')
        if muc == 'off':
            return True
        for rec in self:
            if rec.approval_ok:
                continue
            thong_diep = _(
                'Chưa đủ chữ ký theo luật phê duyệt — còn thiếu: %s.'
            ) % rec.approval_missing
            if muc == 'block':
                raise UserError(thong_diep)
            if hasattr(rec, 'message_post'):
                rec.message_post(body=thong_diep)
        return True

    # ------------------------------------------------------------------
    def action_open_sign_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Ký duyệt — %s') % self.display_name,
            'res_model': 're.sign.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_res_model': self._name,
                'default_res_id': self.id,
            },
        }

    def action_view_signatures(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Chữ ký — %s') % self.display_name,
            'res_model': 're.signature',
            'view_mode': 'list,form',
            'domain': [('res_model', '=', self._name),
                       ('res_id', '=', self.id)],
            'target': 'current',
        }

    def action_huy_chu_ky(self):
        """Huỷ toàn bộ chữ ký của chứng từ này.

        Sửa nội dung rồi ký lại là chuyện bình thường; cái không bình
        thường là để chữ ký cũ nằm lại cạnh nội dung mới.
        """
        self.ensure_one()
        if not self.signature_ids:
            raise UserError(_('Chứng từ này chưa có chữ ký nào.'))
        n = len(self.signature_ids)
        self.signature_ids.unlink()
        if hasattr(self, 'message_post'):
            self.message_post(body=_('Đã huỷ %s chữ ký.') % n)
        return True
