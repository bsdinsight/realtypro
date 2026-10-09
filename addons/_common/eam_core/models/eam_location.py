# -*- coding: utf-8 -*-
from odoo import api, fields, models


class EamLocation(models.Model):
    """Vị trí chức năng — CHỖ, không phải VẬT.

    `WTG-07 / vị trí hộp số` là một chỗ. Con hộp số lắp ở đó là một vật,
    và nó sẽ đổi vài lần trong 25 năm. **Mã vị trí không bao giờ đổi khi
    thay thiết bị** — đó là toàn bộ lý do bảng này tồn tại tách khỏi
    bảng tài sản.

    Nhờ tách ra mới trả lời được câu *"vị trí 7 hỏng hộp số mấy lần"* —
    câu chỉ ra lỗi nền móng, lỗi dòng gió hay lỗi lắp đặt, khác hẳn câu
    *"con hộp số này hỏng ở mấy vị trí"* vốn chỉ ra lỗi lô hàng.
    """
    _name = 'eam.location'
    _description = 'Vị trí chức năng'
    _inherit = ['mail.thread']
    _parent_name = 'parent_id'
    _parent_store = True
    _order = 'complete_code'

    name = fields.Char(string='Tên vị trí', required=True, tracking=True)
    code = fields.Char(string='Mã vị trí', required=True, index=True,
                       tracking=True)
    complete_code = fields.Char(
        string='Mã đầy đủ', compute='_compute_complete', store=True,
        recursive=True, index=True)
    complete_name = fields.Char(
        string='Đường dẫn', compute='_compute_complete', store=True,
        recursive=True)
    parent_id = fields.Many2one(
        'eam.location', string='Vị trí cha', ondelete='restrict', index=True,
        tracking=True)
    child_ids = fields.One2many(
        'eam.location', 'parent_id', string='Vị trí con')
    parent_path = fields.Char(index=True)
    level = fields.Integer(
        string='Cấp', compute='_compute_complete', store=True, recursive=True)

    location_type = fields.Selection(
        [('plant', 'Nhà máy'),
         ('system', 'Hệ thống'),
         ('position', 'Vị trí thiết bị'),
         ('component', 'Vị trí cấu phần')],
        string='Loại vị trí', required=True, default='position',
        tracking=True)
    category_id = fields.Many2one(
        'eam.asset.category', string='Loại cấu phần chấp nhận',
        help='Để trống nghĩa là nhận mọi loại. Khai vào thì hệ thống '
             'cảnh báo khi lắp nhầm loại thiết bị vào vị trí này.')

    # Quy tắc một-chỗ-một-vật. Mặc định BẬT cho vị trí thiết bị và vị
    # trí cấu phần: hai con hộp số không thể cùng nằm ở một chỗ. Nhà máy
    # và hệ thống thì chứa nhiều, nên phải tắt.
    allow_multiple = fields.Boolean(
        string='Cho phép nhiều tài sản cùng lúc',
        compute='_compute_allow_multiple', store=True, readonly=False,
        help='Vị trí thiết bị và vị trí cấu phần chỉ được chứa MỘT tài '
             'sản tại một thời điểm. Nhà máy và hệ thống thì chứa nhiều.')

    installation_ids = fields.One2many(
        'eam.installation', 'location_id', string='Lịch sử lắp đặt')
    asset_ids = fields.Many2many(
        'eam.asset', string='Tài sản đang lắp',
        compute='_compute_asset_ids')
    # LƯU: cần lọc "vị trí chưa lắp tài sản nào" ngay trên danh sách,
    # mà trường tính không lưu thì không đưa vào domain được.
    #
    # Hàm tính RIÊNG, không dùng chung với asset_ids: Odoo cảnh báo khi
    # một hàm tính vừa nuôi trường lưu vừa nuôi trường không lưu, vì khi
    # đó chỉ ĐỌC asset_ids cũng kéo theo ghi lại asset_count.
    asset_count = fields.Integer(
        string='Số tài sản đang lắp', compute='_compute_asset_count',
        store=True)

    # Nhà máy của vị trí này — leo ngược cây tới nút gốc. LƯU lại vì
    # pane lọc và mọi báo cáo theo nhà máy đều cần lọc được bằng domain,
    # mà trường tính không lưu thì không đưa vào domain được.
    plant_id = fields.Many2one(
        'eam.location', string='Thuộc nhà máy', compute='_compute_plant',
        store=True, recursive=True, index=True)
    company_id = fields.Many2one(
        'res.company', string='Công ty', required=True,
        default=lambda self: self.env.company, index=True)
    note = fields.Text(string='Ghi chú')
    active = fields.Boolean(default=True)

    # Định danh thật là ĐƯỜNG DẪN ĐẦY ĐỦ, không phải mã lẻ: mã "GBX"
    # (vị trí hộp số) phải lặp lại ở cả 30 tua-bin, nhưng
    # SAVA1/WTG/T07/GBX thì chỉ có một. Ràng buộc trên complete_code
    # đồng thời chặn luôn hai vị trí con trùng mã dưới cùng một cha.
    _uniq_path = models.Constraint(
        'UNIQUE(company_id, complete_code)',
        'Đường dẫn vị trí này đã tồn tại — hai vị trí con cùng một cha '
        'không được trùng mã.')

    @api.depends('name', 'code', 'parent_id.complete_code',
                 'parent_id.complete_name', 'parent_id.level')
    def _compute_complete(self):
        for l in self:
            if l.parent_id:
                l.complete_code = '%s/%s' % (l.parent_id.complete_code,
                                             l.code or '')
                l.complete_name = '%s / %s' % (l.parent_id.complete_name,
                                               l.name or '')
                l.level = (l.parent_id.level or 0) + 1
            else:
                l.complete_code = l.code or ''
                l.complete_name = l.name or ''
                l.level = 1

    @api.depends('location_type', 'parent_id.plant_id')
    def _compute_plant(self):
        for l in self:
            l.plant_id = (l if l.location_type == 'plant'
                          else l.parent_id.plant_id)

    @api.depends('location_type')
    def _compute_allow_multiple(self):
        for l in self:
            l.allow_multiple = l.location_type in ('plant', 'system')

    @api.depends('installation_ids.is_current',
                 'installation_ids.asset_id')
    def _compute_asset_ids(self):
        for l in self:
            l.asset_ids = l.installation_ids.filtered('is_current')\
                .mapped('asset_id')

    @api.depends('installation_ids.is_current',
                 'installation_ids.asset_id')
    def _compute_asset_count(self):
        for l in self:
            l.asset_count = len(
                l.installation_ids.filtered('is_current').mapped('asset_id'))

    @api.depends('complete_code', 'name')
    def _compute_display_name(self):
        for l in self:
            l.display_name = '[%s] %s' % (l.complete_code or '', l.name or '')

    def action_mo_lich_su(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Lịch sử lắp đặt — %s' % self.display_name,
            'res_model': 'eam.installation',
            'view_mode': 'list,form',
            'domain': [('location_id', 'child_of', self.id)],
            'context': {'default_location_id': self.id},
        }
