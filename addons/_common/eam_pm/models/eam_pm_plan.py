# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class EamPmPlan(models.Model):
    """Kế hoạch bảo trì phòng ngừa — việc gì, làm ở đâu, bao lâu một lần.

    Bốn quyết định, cả bốn đều là chỗ các hệ CMMS hay làm sai
    ---------------------------------------------------------

    **① Chu kỳ đếm từ lần LÀM XONG THẬT, không từ một lưới ngày cố định.**
    Bảo dưỡng 6 tháng bị trễ 3 tuần thì lần sau cách lần vừa làm 6 tháng,
    chứ không phải vẫn rơi vào ngày đã định. Giữ lưới cố định thì khoảng
    cách thật co lại còn 5 tháng, rồi có tháng phải làm hai lần.

    Nhưng **kiểm định bắt buộc thì ngược lại**: hạn do pháp luật đặt,
    làm sớm hay muộn thì hạn sau vẫn là ngày đó. Nên có hai chế độ neo,
    và chọn sai chế độ là sai cả chuỗi về sau.

    **② Hai điều kiện thì cái nào ĐẾN TRƯỚC thắng.** Thay dầu hộp số:
    *12 tháng hoặc 8.000 giờ chạy, tuỳ cái nào tới trước*. Hệ nào chỉ cho
    chọn một trong hai là buộc người dùng bỏ đi một nửa điều kiện — và
    họ sẽ bỏ cái khó đo, tức cái theo giờ, tức cái đúng hơn.

    **③ Sinh lệnh TRƯỚC hạn một khoảng.** Sinh đúng ngày đến hạn là quá
    muộn: chưa kịp đặt phụ tùng, chưa xếp được người, chưa thuê được cẩu.
    Khoảng báo trước phải khai theo từng kế hoạch — thay dầu báo trước 2
    tuần, đại tu báo trước 3 tháng.

    **④ Một kế hoạch × một vị trí chỉ có MỘT lệnh đang mở.** Cron chạy
    hằng ngày, mà kế hoạch quá hạn thì ngày nào cũng thoả điều kiện —
    không chặn thì sau một tháng có 30 lệnh y hệt nhau cho cùng một máy.
    """
    _name = 'eam.pm.plan'
    _description = 'Kế hoạch bảo trì phòng ngừa'
    _inherit = ['mail.thread']
    _order = 'sequence, code'

    name = fields.Char(string='Tên kế hoạch', required=True, tracking=True)
    code = fields.Char(string='Mã', required=True, index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True, tracking=True)
    note = fields.Text(string='Mô tả')

    work_type = fields.Selection(
        [('preventive', 'Bảo trì phòng ngừa'),
         ('predictive', 'Bảo trì theo trạng thái'),
         ('inspection', 'Kiểm tra, xem xét'),
         ('statutory', 'Kiểm định bắt buộc')],
        string='Loại công việc', default='preventive', required=True,
        tracking=True)
    priority = fields.Selection(
        [('0', 'Thấp'), ('1', 'Bình thường'),
         ('2', 'Cao'), ('3', 'Khẩn cấp')],
        string='Mức ưu tiên', default='1', required=True)

    # ------------------------------------------------------------------
    # Áp cho đâu
    # ------------------------------------------------------------------
    plant_id = fields.Many2one(
        'eam.location', string='Giới hạn trong nhà máy',
        domain="[('location_type', '=', 'plant')]", index=True,
        help='Để trống thì áp cho MỌI nhà máy. Khoanh lại vì mỗi nhà máy '
             'một chế độ dịch vụ của hãng, một tuổi máy, một hợp đồng '
             'O&M — dùng chung một kế hoạch là vơ cả nhà máy đang xây vào '
             'lịch bảo trì của nhà máy đang chạy.')
    category_id = fields.Many2one(
        'eam.asset.category', string='Áp cho loại cấu phần',
        ondelete='restrict', index=True,
        help='Áp cho mọi vị trí đang lắp tài sản thuộc loại này (và loại '
             'con của nó). Để trống thì chỉ áp cho các vị trí khai đích '
             'danh bên dưới.')
    location_ids = fields.Many2many(
        'eam.location', string='Vị trí khai đích danh',
        domain="[('location_type', 'in', ('position', 'plant'))]")

    # ------------------------------------------------------------------
    # Khi nào tới hạn
    # ------------------------------------------------------------------
    use_calendar = fields.Boolean(string='Theo lịch', default=True)
    calendar_months = fields.Integer(string='Mỗi … tháng', default=6)
    calendar_days = fields.Integer(
        string='… cộng thêm … ngày', default=0,
        help='Dùng cho chu kỳ không tròn tháng, ví dụ 90 ngày.')
    anchor = fields.Selection(
        [('from_last_done', 'Từ lần làm xong gần nhất'),
         ('fixed_calendar', 'Theo mốc cố định (không trôi)')],
        string='Neo chu kỳ', default='from_last_done', required=True,
        help='"Từ lần làm xong" là mặc định đúng cho bảo dưỡng: trễ thì '
             'lần sau dời theo. "Mốc cố định" dành cho kiểm định bắt '
             'buộc — hạn do pháp luật đặt, làm sớm hay muộn thì hạn sau '
             'vẫn là ngày đó.')

    use_meter = fields.Boolean(string='Theo đồng hồ')
    meter_type = fields.Selection(
        [('operating_hours', 'Giờ máy chạy'),
         ('production_mwh', 'Sản lượng luỹ kế (MWh)'),
         ('starts', 'Số lần khởi động')],
        string='Loại đồng hồ', default='operating_hours')
    meter_interval = fields.Float(
        string='Mỗi … (đơn vị đồng hồ)', digits=(16, 2), default=8000.0)

    lead_days = fields.Integer(
        string='Sinh lệnh trước hạn (ngày)', default=14, required=True,
        help='Sinh đúng ngày đến hạn là quá muộn: chưa kịp đặt phụ tùng, '
             'chưa xếp được người, chưa thuê được cẩu.')
    grace_days = fields.Integer(
        string='Dung sai quá hạn (ngày)', default=0,
        help='Quá hạn bao nhiêu ngày thì còn coi là chấp nhận được. Chỉ '
             'đổi màu cảnh báo, không dời hạn.')

    # ------------------------------------------------------------------
    # Nội dung công việc
    # ------------------------------------------------------------------
    task_ids = fields.One2many(
        'eam.pm.task', 'plan_id', string='Các bước công việc')
    est_hours = fields.Float(string='Giờ công dự kiến', digits=(16, 2))
    trade = fields.Selection(
        [('mechanical', 'Cơ khí'), ('electrical', 'Điện'),
         ('control', 'Điều khiển, tự động'), ('blade', 'Cánh quạt'),
         ('hv', 'Điện cao áp'), ('rope', 'Tiếp cận bằng dây'),
         ('other', 'Khác')],
        string='Nghề chính')
    requires_permit = fields.Boolean(string='Cần phiếu, lệnh công tác')
    requires_isolation = fields.Boolean(string='Phải cắt điện, cô lập')
    work_at_height = fields.Boolean(string='Làm việc trên cao')

    schedule_ids = fields.One2many(
        'eam.pm.schedule', 'plan_id', string='Lịch theo vị trí')
    schedule_count = fields.Integer(
        string='Số vị trí áp dụng', compute='_compute_counts')
    due_count = fields.Integer(
        string='Sắp tới hạn / quá hạn', compute='_compute_counts')
    company_id = fields.Many2one(
        'res.company', string='Công ty', required=True,
        default=lambda self: self.env.company, index=True)

    _uniq_code = models.Constraint(
        'UNIQUE(company_id, code)', 'Mã kế hoạch không được trùng.')

    @api.depends('schedule_ids.state')
    def _compute_counts(self):
        for p in self:
            p.schedule_count = len(p.schedule_ids)
            p.due_count = len(p.schedule_ids.filtered(
                lambda s: s.state in ('due_soon', 'overdue')))

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for p in self:
            p.display_name = '[%s] %s' % (p.code or '', p.name or '')

    @api.constrains('use_calendar', 'use_meter', 'calendar_months',
                    'calendar_days', 'meter_interval')
    def _check_dieu_kien(self):
        for p in self:
            if not p.use_calendar and not p.use_meter:
                raise ValidationError(_(
                    'Kế hoạch "%s" không có điều kiện tới hạn nào — nó sẽ '
                    'không bao giờ sinh ra lệnh công việc.', p.name))
            if p.use_calendar and not (p.calendar_months or p.calendar_days):
                raise ValidationError(_(
                    'Kế hoạch "%s" bật chu kỳ theo lịch nhưng để trống số '
                    'tháng và số ngày.', p.name))
            if p.use_meter and p.meter_interval <= 0:
                raise ValidationError(_(
                    'Kế hoạch "%s" bật chu kỳ theo đồng hồ nhưng khoảng '
                    'cách không dương.', p.name))

    # ------------------------------------------------------------------
    def _vi_tri_ap_dung(self):
        """Các vị trí kế hoạch này áp vào."""
        self.ensure_one()
        L = self.env['eam.location']
        vt = self.location_ids
        if self.category_id:
            loai = self.env['eam.asset.category'].search(
                [('id', 'child_of', self.category_id.id)])
            # Vị trí đang lắp tài sản thuộc loại đó — lấy theo vị trí CHA
            # cấp thiết bị, vì hộp số nằm ở vị trí con bên trong tua-bin
            # mà lệnh công việc thì làm ở cấp tua-bin.
            ts = self.env['eam.asset'].search(
                [('category_id', 'in', loai.ids), ('is_installed', '=', True)])
            for a in ts:
                l = a.current_location_id
                while l and l.location_type not in ('position', 'plant'):
                    l = l.parent_id
                if l:
                    vt |= l
        if self.plant_id:
            trong = self.env['eam.location'].search(
                [('id', 'child_of', self.plant_id.id)])
            vt = vt & trong
        return vt

    def action_ap_dung(self):
        """Dựng lịch cho mọi vị trí kế hoạch này áp vào.

        Chạy lại được: chỉ thêm vị trí mới, không đụng lịch đã có — nếu
        không thì mỗi lần bấm là xoá sạch lịch sử lần làm gần nhất và
        mọi kế hoạch bị đẩy về như chưa từng bảo trì.
        """
        S = self.env['eam.pm.schedule']
        for p in self:
            vt = p._vi_tri_ap_dung()
            da_co = S.search([('plan_id', '=', p.id)]).mapped('location_id')
            moi = vt - da_co
            S.create([{'plan_id': p.id, 'location_id': l.id} for l in moi])
            # Vị trí không còn thuộc phạm vi thì NGHỈ chứ không xoá — xoá
            # là mất ngày làm gần nhất, thứ không dựng lại được.
            thua = S.search([('plan_id', '=', p.id),
                             ('location_id', 'not in', vt.ids)])
            thua.active = False
        return True

    def action_mo_lich(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Lịch bảo trì — %s', self.name),
            'res_model': 'eam.pm.schedule',
            'view_mode': 'list,form',
            'domain': [('plan_id', '=', self.id)],
            'context': {'default_plan_id': self.id},
        }


class EamPmTask(models.Model):
    """Một bước trong kế hoạch — chép sang lệnh công việc khi sinh lệnh."""
    _name = 'eam.pm.task'
    _description = 'Bước công việc trong kế hoạch bảo trì'
    _order = 'plan_id, sequence, id'

    plan_id = fields.Many2one(
        'eam.pm.plan', string='Kế hoạch', required=True, ondelete='cascade',
        index=True)
    sequence = fields.Integer(default=10)
    name = fields.Char(string='Bước công việc', required=True)
    spec = fields.Char(
        string='Tiêu chuẩn / trị số',
        help='Lực siết, khe hở, ngưỡng rung… Ghi ra thì người làm không '
             'phải tra sổ tay, và người kiểm tra biết lấy gì để đối chiếu.')
    is_critical = fields.Boolean(
        string='Bước chịu lực',
        help='Bỏ bước này là hỏng cả lần bảo trì. Dùng để siết khâu kiểm.')
