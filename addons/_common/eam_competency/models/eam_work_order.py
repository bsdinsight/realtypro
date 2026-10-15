# -*- coding: utf-8 -*-
"""Cổng năng lực trên lệnh công việc.

Chặn TRƯỚC khi làm, chỉ BÁO sau khi đã làm
------------------------------------------
Cổng đặt ở ``action_bat_dau``: kiểm tổ được phân công trước khi bắt đầu.
Đó là lúc chặn còn có tác dụng — chặn xong thì đổi người, hoặc đi gia
hạn chứng chỉ, hoặc hoãn một ngày.

Ở ``action_xong`` thì **chỉ ghi nhận, không chặn**. Việc đã làm rồi;
chặn đóng lệnh vì người làm thiếu chứng chỉ không làm việc đó chưa xảy
ra — nó chỉ khiến người ta **sửa dòng giờ công cho khớp**, và thế là mất
luôn bản ghi thật về ai đã ở trên trụ. Thà có một lệnh đóng được kèm nốt
cảnh báo trong nhật ký, còn hơn một sổ giờ công đã bị gọt.

Kiểm theo NGÀY LÀM, không theo hôm nay
--------------------------------------
Hôm nay chứng chỉ còn hạn, lệnh xếp làm ba tuần nữa, tới lúc làm thì đã
quá hạn — mà cổng đã cho qua từ hôm kiểm. Nên hiệu lực được soi tại
``ngày dự kiến bắt đầu``, và khi lệnh đã chạy thì tại ngày bắt đầu thật.

Mức siết mặc định là CẢNH BÁO
-----------------------------
Bật chặn hẳn ngay trên một hệ đang chạy sẽ dừng công việc vốn hôm qua
vẫn làm bình thường, chỉ vì dữ liệu chứng chỉ chưa kịp nhập. Nên mặc
định ``warn``, và khách bật ``block`` khi đã nhập xong hồ sơ — cùng cách
ma trận phê duyệt của ``re_sign`` đã làm.
"""
from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class EamWorkOrder(models.Model):
    _inherit = 'eam.work.order'

    skill_ids = fields.Many2many(
        'hr.skill', 'eam_wo_skill_rel', 'wo_id', 'skill_id',
        string='Năng lực yêu cầu',
        help='Chứng chỉ, giấy phép, kỹ năng mà người làm PHẢI có. Lấy sẵn '
             'từ kế hoạch bảo trì khi lệnh sinh tự động.')
    crew_ids = fields.Many2many(
        'hr.employee', 'eam_wo_crew_rel', 'wo_id', 'employee_id',
        string='Tổ được phân công', tracking=True,
        help='Khai TRƯỚC khi bắt đầu. Đây là danh sách bị cổng năng lực '
             'soi — dòng giờ công ghi sau chỉ được ghi nhận, không chặn.')
    crew_gap = fields.Text(
        string='Năng lực còn thiếu', compute='_compute_crew_gap')
    crew_gap_missing = fields.Integer(
        string='Số chỗ thiếu hẳn', compute='_compute_crew_gap')
    crew_gap_expired = fields.Integer(
        string='Số chỗ hết hạn', compute='_compute_crew_gap')
    crew_ok = fields.Boolean(
        string='Tổ đủ năng lực', compute='_compute_crew_gap')

    # ------------------------------------------------------------------
    def _ngay_kiem(self):
        """Ngày dùng để soi hiệu lực chứng chỉ."""
        self.ensure_one()
        d = self.date_start or self.date_planned_start
        return d.date() if d else fields.Date.context_today(self)

    def _thieu_nang_luc(self, nhan_vien, ngay=None):
        """Phân loại chỗ thiếu của một nhóm nhân viên.

        Trả về ``(thieu, het_han)`` — mỗi cái là danh sách
        ``(nhân viên, kỹ năng, ngày hết hạn)``.
        """
        self.ensure_one()
        ngay = ngay or self._ngay_kiem()
        if not self.skill_ids:
            return [], []
        ES = self.env['hr.employee.skill'].sudo()
        thieu, het = [], []
        for nv in nhan_vien:
            co = ES.search([('employee_id', '=', nv.id),
                            ('skill_id', 'in', self.skill_ids.ids)])
            theo_kn = {}
            for s in co:
                theo_kn.setdefault(s.skill_id.id, []).append(s)
            for kn in self.skill_ids:
                ds = theo_kn.get(kn.id) or []
                if not ds:
                    thieu.append((nv, kn, False))
                    continue
                if any(s._hieu_luc_ngay(ngay) for s in ds):
                    continue
                # Có giấy nhưng không có hiệu lực vào ngày làm. Lấy ngày
                # hết hạn MUỘN NHẤT để người xếp lịch biết cần gia hạn
                # tới đâu.
                han = max([s.valid_to for s in ds if s.valid_to]
                          or [False])
                het.append((nv, kn, han))
        return thieu, het

    @api.depends('crew_ids', 'skill_ids', 'date_planned_start', 'date_start')
    def _compute_crew_gap(self):
        for o in self:
            o.crew_gap = False
            o.crew_gap_missing = o.crew_gap_expired = 0
            o.crew_ok = True
            if not o.skill_ids or not o.crew_ids:
                continue
            thieu, het = o._thieu_nang_luc(o.crew_ids)
            o.crew_gap_missing = len(thieu)
            o.crew_gap_expired = len(het)
            o.crew_ok = not (thieu or het)
            dong = []
            if het:
                dong.append(_(
                    'HẾT HẠN (lỗi xếp lịch đào tạo — gia hạn được trong '
                    'tuần):'))
                dong += ['  · %s — %s%s' % (
                    nv.name, kn.name,
                    _(' (hết hạn %s)') % han if han else '')
                    for nv, kn, han in het]
            if thieu:
                dong.append(_(
                    'THIẾU HẲN (lỗi kế hoạch nhân lực — mất hàng tháng để '
                    'bù, hoặc phải thuê ngoài):'))
                dong += ['  · %s — %s' % (nv.name, kn.name)
                         for nv, kn, _h in thieu]
            if dong:
                dong.append(_('Soi hiệu lực tại ngày làm: %s.')
                            % o._ngay_kiem())
            o.crew_gap = '\n'.join(dong) or False

    # ------------------------------------------------------------------
    def _muc_siet(self):
        return self.env['ir.config_parameter'].sudo().get_param(
            'eam_competency.enforce', 'warn')

    def _kiem_nang_luc(self):
        """Cổng trước khi bắt đầu."""
        muc = self._muc_siet()
        if muc == 'off':
            return True
        for o in self:
            if o.crew_ok:
                continue
            if not o.crew_ids and o.skill_ids:
                tin = _(
                    'Lệnh "%(ten)s" yêu cầu năng lực (%(kn)s) nhưng chưa '
                    'khai tổ được phân công — nên không kiểm được ai sẽ '
                    'làm.', ten=o.name,
                    kn=', '.join(o.skill_ids.mapped('name')))
            else:
                tin = _(
                    'Tổ của lệnh "%(ten)s" chưa đủ năng lực:\n\n%(gap)s',
                    ten=o.name, gap=o.crew_gap or '')
            if muc == 'block':
                raise UserError(tin)
            # `message_post` ESCAPE chuỗi thường, nên `<br/>` viết thẳng
            # sẽ hiện ra nguyên văn `&lt;br/&gt;` trong nhật ký. Dùng
            # `Markup.join` để thẻ là thẻ thật mà nội dung từng dòng vẫn
            # được escape.
            o.message_post(body=Markup('<br/>').join(tin.split('\n')))
        return True

    def action_bat_dau(self):
        self._kiem_nang_luc()
        return super().action_bat_dau()

    def action_xong(self):
        res = super().action_xong()
        # Sau khi làm thì CHỈ GHI NHẬN. Chặn ở đây chỉ khiến người ta sửa
        # dòng giờ công cho khớp, và mất luôn bản ghi thật về ai đã ở
        # trên trụ.
        self._ghi_nhan_nguoi_thuc_lam()
        return res

    def _ghi_nhan_nguoi_thuc_lam(self):
        E = self.env['hr.employee'].sudo()
        for o in self:
            if not o.skill_ids:
                continue
            uids = o.labour_line_ids.mapped('user_id')
            if not uids:
                continue
            nv = E.search([('user_id', 'in', uids.ids)])
            ngoai_to = nv - o.crew_ids
            thieu, het = o._thieu_nang_luc(nv)
            phan = []
            if ngoai_to:
                phan.append(_(
                    'Có người ghi giờ công mà không nằm trong tổ được phân '
                    'công: %s.', ', '.join(ngoai_to.mapped('name'))))
            for nguoi, kn, han in het:
                phan.append(_(
                    '%(nv)s đã làm việc này nhưng chứng chỉ %(kn)s hết hạn '
                    '%(d)s.', nv=nguoi.name, kn=kn.name, d=han or '?'))
            for nguoi, kn, _h in thieu:
                phan.append(_(
                    '%(nv)s đã làm việc này nhưng không có %(kn)s.',
                    nv=nguoi.name, kn=kn.name))
            if phan:
                o.message_post(body=Markup('<b>%s</b><br/>%s') % (
                    _('Ghi nhận sau khi làm (không chặn đóng lệnh):'),
                    Markup('<br/>').join('· ' + p for p in phan)))
        return True

    # ------------------------------------------------------------------
    def action_goi_y_nguoi(self):
        """Những người đủ năng lực vào ngày làm của lệnh này."""
        self.ensure_one()
        if not self.skill_ids:
            raise UserError(_(
                'Lệnh này chưa khai năng lực yêu cầu, nên chưa có gì để '
                'lọc người.'))
        ngay = self._ngay_kiem()
        ES = self.env['hr.employee.skill'].sudo()
        E = self.env['hr.employee']
        du = None
        for kn in self.skill_ids:
            co = ES.search([('skill_id', '=', kn.id)])
            hop_le = co.filtered(lambda s: s._hieu_luc_ngay(ngay))
            nguoi = set(hop_le.mapped('employee_id').ids)
            du = nguoi if du is None else (du & nguoi)
            if not du:
                break
        return {
            'type': 'ir.actions.act_window',
            'name': _('Đủ năng lực ngày %s', ngay),
            'res_model': 'hr.employee',
            'view_mode': 'list,form',
            'domain': [('id', 'in', list(du or []))],
            'context': {'create': False},
            'help': '<p class="o_view_nocontent_smiling_face">%s</p>' % _(
                'Không ai đủ cả %s vào ngày này',
                ', '.join(self.skill_ids.mapped('name'))),
        }

    def action_mo_nang_luc_to(self):
        """Hồ sơ chứng chỉ của tổ — để xem cái nào hết hạn ngày nào."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Chứng chỉ của tổ — %s', self.name),
            'res_model': 'hr.employee.skill',
            'view_mode': 'list,form',
            'domain': [('employee_id', 'in', self.crew_ids.ids),
                       ('skill_id', 'in', self.skill_ids.ids)],
        }
