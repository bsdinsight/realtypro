# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class EamOutage(models.Model):
    """Sổ dừng máy — một quãng thời gian một vị trí ở một trạng thái.

    Ba quyết định thiết kế, cả ba đều ngược trực giác
    -------------------------------------------------

    **① Khoảng dừng ĐƯỢC PHÉP chồng nhau.** Khác hẳn lịch sử lắp đặt,
    nơi chồng nhau là vô lý vật lý. Một máy có thể vừa hỏng vừa bị cắt
    giảm lưới cùng một lúc — và đó chính là lý do chuẩn có cơ chế ưu
    tiên loại. Nên ở đây **không chặn** chồng nhau; thay vào đó đánh dấu
    và đưa ra màn hình để người có thẩm quyền phân xử.

    Chặn chồng nhau sẽ ép người nhập bịa số liệu cho khớp.

    **② Sự cố một chỗ làm dừng nhiều máy thì phải LIÊN KẾT, không nhân
    bản.** Trạm nâng áp hỏng làm cả 30 tua-bin dừng: ghi một khoảng dừng
    "cha" ở trạm, và 30 khoảng "con" ở từng tua-bin trỏ về nó. Báo cáo
    cộng khoảng CON (giờ-máy thật); khoảng cha chỉ là nguyên nhân.

    Cộng cả cha lẫn con là đếm đúp — và đây là lỗi im lặng, không màn
    hình nào báo.

    **③ Khoảng ĐANG MỞ phải hỗ trợ.** Máy còn đang dừng thì chưa có ngày
    kết thúc. Ép điền thì người ta bịa một ngày, và mọi chỉ số sai theo.

    Quan hệ với hỏng hóc và lệnh công việc
    --------------------------------------
    **Dừng máy ≠ hỏng.** Nhiều lần dừng chỉ cần khởi động lại từ xa,
    không có hành động bảo trì nào — các cơ sở dữ liệu ghi mọi lần dừng
    cho ra tỷ lệ cao hơn hẳn các cơ sở ghi hỏng. Đây là ba thực thể liên
    kết nhưng độc lập; gộp lại là MTBF sai hoàn toàn.
    """
    _name = 'eam.outage'
    _description = 'Khoảng dừng máy'
    _inherit = ['mail.thread']
    _order = 'date_start desc, id desc'
    _rec_name = 'display_name'

    name = fields.Char(string='Số hiệu', copy=False, index=True,
                       default=lambda s: _('Mới'))
    location_id = fields.Many2one(
        'eam.location', string='Vị trí', required=True, ondelete='restrict',
        index=True, tracking=True,
        help='Dừng máy xảy ra ở một CHỖ. Thiết bị đang nằm ở đó suy ra '
             'từ lịch sử lắp đặt.')
    asset_id = fields.Many2one(
        'eam.asset', string='Thiết bị liên quan',
        compute='_compute_asset', store=True, readonly=False,
        help='Tự suy từ vị trí và thời điểm bắt đầu. Sửa được khi cần '
             'chỉ đích danh một cấu phần khác.')
    category_id = fields.Many2one(
        'eam.time.category', string='Loại thời gian', required=True,
        ondelete='restrict', index=True, tracking=True)
    counts_as_downtime = fields.Boolean(
        related='category_id.counts_as_downtime', store=True,
        string='Tính là dừng')

    date_start = fields.Datetime(
        string='Bắt đầu', required=True, index=True, tracking=True,
        default=fields.Datetime.now)
    date_end = fields.Datetime(
        string='Kết thúc', index=True, tracking=True,
        help='Để trống nghĩa là ĐANG DỪNG. Không bịa ngày kết thúc cho '
             'sự cố chưa xử lý xong.')
    is_open = fields.Boolean(
        string='Đang mở', compute='_compute_thoi_luong', store=True,
        index=True)
    duration_hours = fields.Float(
        string='Số giờ', compute='_compute_thoi_luong', store=True,
        digits=(16, 2),
        help='Khoảng đang mở tính tới thời điểm này.')

    # Sự cố một chỗ làm dừng nhiều máy — liên kết, không nhân bản.
    parent_id = fields.Many2one(
        'eam.outage', string='Thuộc sự cố', ondelete='set null', index=True,
        help='Trạm nâng áp hỏng làm cả đội máy dừng: ghi một khoảng ở '
             'trạm rồi trỏ các khoảng của từng tua-bin về nó. Báo cáo '
             'cộng khoảng CON, không cộng cha — cộng cả hai là đếm đúp.')
    child_ids = fields.One2many(
        'eam.outage', 'parent_id', string='Khoảng dừng kéo theo')
    child_count = fields.Integer(
        string='Số máy bị kéo theo', compute='_compute_child_count',
        store=True)
    is_root_cause = fields.Boolean(
        string='Là sự cố gốc', compute='_compute_child_count', store=True,
        help='Có khoảng con trỏ về. Báo cáo giờ-máy phải LOẠI dòng này '
             'ra để khỏi đếm đúp.')

    liability = fields.Selection(
        [('undetermined', 'Chưa quy'),
         ('warranty', 'Bảo hành thiết bị'),
         ('om_contract', 'Nghĩa vụ hợp đồng O&M'),
         ('owner', 'Chủ đầu tư tự chịu'),
         ('grid', 'Lưới điện'),
         ('force_majeure', 'Bất khả kháng')],
        string='Quy trách nhiệm', default='undetermined', required=True,
        tracking=True,
        help='Ô làm ra tiền. Không có nó thì mỗi lần dừng chỉ là một '
             'dòng nhật ký; có nó thì là một khoản đòi được.')
    lost_mwh = fields.Float(
        string='Sản lượng mất (MWh)', digits=(16, 3), tracking=True,
        help='Theo mô hình ĐÃ DUYỆT — điều kiện gió và đường cong công '
             'suất, hoặc máy đối chứng. KHÔNG lấy công suất định mức '
             'nhân số giờ dừng: đó là cách nói sai phổ biến nhất trong '
             'báo cáo điện gió.')
    lost_revenue = fields.Monetary(
        string='Doanh thu tổn thất', tracking=True,
        help='Ước tính. Trình bày RIÊNG, không trộn vào kế toán hay dòng '
             'tiền. Và số ĐÒI ĐƯỢC thường không bằng số này — chế tài '
             'hợp đồng O&M thường là phạt theo khả dụng, không phải bồi '
             'thường doanh thu thực mất.')
    currency_id = fields.Many2one(
        'res.currency', string='Tiền tệ',
        default=lambda s: s.env.company.currency_id)

    source = fields.Selection(
        [('scada', 'Hệ giám sát'),
         ('manual', 'Nhập tay'),
         ('contractor', 'Báo cáo nhà thầu'),
         ('migration', 'Nhập dữ liệu lịch sử')],
        string='Nguồn', default='manual', required=True)
    source_ref = fields.Char(string='Mã tham chiếu nguồn', index=True,
                             copy=False,
                             help='Mã alarm hoặc mã bản ghi ở hệ nguồn. '
                                  'Dùng để nhập lại không tạo trùng.')
    state = fields.Selection(
        [('draft', 'Nháp'), ('confirmed', 'Đã xác nhận')],
        string='Trạng thái', default='draft', required=True, tracking=True)

    has_overlap = fields.Boolean(
        string='Chồng khoảng khác', compute='_compute_overlap', store=True,
        help='Cùng vị trí, cùng lúc, hai loại thời gian khác nhau. KHÔNG '
             'phải lỗi — chuẩn có cơ chế ưu tiên loại. Nhưng phải có '
             'người phân xử, không để máy tự chọn.')
    description = fields.Text(string='Diễn giải')
    company_id = fields.Many2one(
        'res.company', string='Công ty', required=True,
        default=lambda self: self.env.company, index=True)

    _uniq_source = models.Constraint(
        'UNIQUE(company_id, source, source_ref)',
        'Bản ghi nguồn này đã nhập rồi — nhập lại không được tạo trùng.')
    _ck_ngay = models.Constraint(
        'CHECK(date_end IS NULL OR date_end >= date_start)',
        'Thời điểm kết thúc không được trước thời điểm bắt đầu.')

    # ------------------------------------------------------------------
    @api.depends('date_start', 'date_end')
    def _compute_thoi_luong(self):
        bg = fields.Datetime.now()
        for o in self:
            o.is_open = bool(o.date_start and not o.date_end)
            # Chặn số âm: khoảng ĐANG MỞ tính tới bây giờ, nên một khoảng
            # bắt đầu ở tương lai (nhập trước, hoặc dữ liệu dựng sẵn) sẽ
            # ra thời lượng âm — và số âm đó cộng vào báo cáo làm KHẢ
            # DỤNG VỌT LÊN TRÊN 100%, con số vô lý mà không chỗ nào chặn.
            o.duration_hours = max(
                ((o.date_end or bg) - o.date_start).total_seconds() / 3600.0
                if o.date_start else 0.0, 0.0)

    @api.depends('child_ids')
    def _compute_child_count(self):
        for o in self:
            o.child_count = len(o.child_ids)
            o.is_root_cause = bool(o.child_ids)

    @api.depends('location_id', 'date_start')
    def _compute_asset(self):
        I = self.env['eam.installation']
        for o in self:
            if not (o.location_id and o.date_start):
                continue
            d = o.date_start.date()
            lap = I.search([
                ('location_id', '=', o.location_id.id),
                ('date_install', '<=', d),
            ])
            hop = lap.filtered(lambda x: not x.date_remove
                               or x.date_remove >= d)
            o.asset_id = hop[:1].asset_id

    @api.depends('location_id', 'date_start', 'date_end')
    def _compute_overlap(self):
        for o in self:
            o.has_overlap = bool(o._tim_chong())

    def _tim_chong(self):
        """Các khoảng khác cùng vị trí có giao thời gian với khoảng này."""
        self.ensure_one()
        if not (self.location_id and self.date_start):
            return self.browse()
        anh_em = self.search([
            ('location_id', '=', self.location_id.id),
            ('id', '!=', self.id or 0),
        ])
        return anh_em.filtered(
            lambda k: (not self.date_end or k.date_start < self.date_end)
            and (not k.date_end or self.date_start < k.date_end))

    @api.depends('name', 'location_id', 'category_id', 'date_start')
    def _compute_display_name(self):
        for o in self:
            o.display_name = '%s · %s · %s' % (
                o.location_id.complete_code or '?',
                o.category_id.name or '?',
                o.date_start and o.date_start.strftime('%d/%m/%Y %H:%M') or '')

    # ------------------------------------------------------------------
    def _lan_toa_chong(self):
        """Tính lại cờ chồng cho MỌI khoảng cùng vị trí.

        ``has_overlap`` phụ thuộc vào các bản ghi KHÁC, mà @api.depends
        chỉ theo dõi trường của chính bản ghi. Nên thêm một khoảng mới
        thì khoảng CŨ không tự biết mình vừa bị chồng — và màn hình "cần
        phân xử" sẽ thiếu đúng một nửa số dòng, im lặng.
        """
        loc = self.mapped('location_id')
        if not loc:
            return
        anh_em = self.search([('location_id', 'in', loc.ids)])
        anh_em._compute_overlap()
        anh_em.flush_recordset(['has_overlap'])

    @api.model_create_multi
    def create(self, vals_list):
        for v in vals_list:
            if not v.get('name') or v['name'] == _('Mới'):
                v['name'] = self.env['ir.sequence'].next_by_code(
                    'eam.outage') or '/'
        r = super().create(vals_list)
        r._lan_toa_chong()
        return r

    def write(self, vals):
        cu = self.mapped('location_id')
        r = super().write(vals)
        if {'location_id', 'date_start', 'date_end'} & set(vals):
            (self | self.search([('location_id', 'in', cu.ids)]))\
                ._lan_toa_chong()
        return r

    def unlink(self):
        loc = self.mapped('location_id')
        r = super().unlink()
        if loc:
            anh_em = self.search([('location_id', 'in', loc.ids)])
            anh_em._compute_overlap()
            anh_em.flush_recordset(['has_overlap'])
        return r

    def action_dong(self):
        """Đóng khoảng đang mở tại thời điểm này."""
        for o in self:
            if o.date_end:
                raise UserError(_('Khoảng này đã đóng lúc %s.', o.date_end))
            o.date_end = fields.Datetime.now()
        return True

    def action_xac_nhan(self):
        for o in self:
            if o.liability == 'undetermined':
                raise UserError(_(
                    'Khoảng dừng "%s" chưa quy trách nhiệm. Xác nhận mà '
                    'bỏ trống ô này thì nó sẽ nằm mãi ở đó — và đây đúng '
                    'là ô làm ra tiền.', o.display_name))
        self.state = 'confirmed'
        return True

    def action_xem_chong(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Khoảng chồng — %s', self.display_name),
            'res_model': 'eam.outage',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self._tim_chong().ids)],
        }
