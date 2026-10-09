# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class EamMeter(models.Model):
    """Đồng hồ của một vị trí — giờ máy chạy, sản lượng luỹ kế, số lần khởi động.

    Vì sao cần, và vì sao nó khó hơn vẻ ngoài
    ------------------------------------------
    Bảo trì theo *giờ chạy* là cách duy nhất đúng cho máy quay: một tua-bin
    ở vùng gió mạnh chạy 3.500 giờ một năm, một con ở vùng lặng chạy 2.000
    — cùng "6 tháng" nhưng hao mòn khác hẳn. Nhưng kích hoạt theo đồng hồ
    chỉ chạy được khi **có số đọc**, và số đọc luỹ kế có một cái bẫy:

    **Đồng hồ ĐI LÙI.** Thay bộ điều khiển là bộ đếm về 0. Nếu hệ thống cứ
    thế trừ, nó ra một khoảng âm khổng lồ và mọi kế hoạch bảo trì theo giờ
    **tự lùi hạn vô thời hạn** — im lặng, không báo gì. Vài năm sau mới lộ
    ra lúc hộp số hỏng trước kỳ thay dầu.

    Nên ở đây số đọc thô được giữ nguyên, và có một **giá trị liên tục**
    tính riêng bằng cách cộng bù mỗi lần đồng hồ bị thay. Lần lùi nào
    chưa được người có thẩm quyền xác nhận là thay đồng hồ thì **bị gắn
    cờ và không cộng bù** — vì nó nhiều khả năng là gõ nhầm.
    """
    _name = 'eam.meter'
    _description = 'Đồng hồ thiết bị'
    _order = 'location_code, meter_type'
    _rec_name = 'display_name'

    location_id = fields.Many2one(
        'eam.location', string='Vị trí', required=True, ondelete='cascade',
        index=True)
    location_code = fields.Char(
        related='location_id.complete_code', store=True, string='Mã vị trí')
    meter_type = fields.Selection(
        [('operating_hours', 'Giờ máy chạy'),
         ('production_mwh', 'Sản lượng luỹ kế (MWh)'),
         ('starts', 'Số lần khởi động'),
         ('other', 'Khác')],
        string='Loại đồng hồ', required=True, default='operating_hours')
    uom_label = fields.Char(
        string='Đơn vị', compute='_compute_uom', store=True)
    reading_ids = fields.One2many(
        'eam.meter.reading', 'meter_id', string='Số đọc')
    current_value = fields.Float(
        string='Giá trị liên tục', compute='_compute_current', store=True,
        digits=(16, 2),
        help='Đã cộng bù các lần thay đồng hồ. Đây là con số dùng để tính '
             'hạn bảo trì — KHÁC số đọc thô trên máy.')
    raw_value = fields.Float(
        string='Số đọc mới nhất (thô)', compute='_compute_current',
        store=True, digits=(16, 2))
    date_last_reading = fields.Date(
        string='Số đọc ngày', compute='_compute_current', store=True)
    suspect_count = fields.Integer(
        string='Số đọc nghi sai', compute='_compute_current', store=True,
        help='Số đọc THẤP HƠN lần trước mà chưa ai xác nhận là thay đồng '
             'hồ. Nhiều khả năng gõ nhầm — chưa xác nhận thì không cộng bù.')
    company_id = fields.Many2one(
        related='location_id.company_id', store=True, index=True)

    _uniq = models.Constraint(
        'UNIQUE(location_id, meter_type)',
        'Mỗi vị trí chỉ có một đồng hồ cho mỗi loại.')

    @api.depends('meter_type')
    def _compute_uom(self):
        nhan = {'operating_hours': 'giờ', 'production_mwh': 'MWh',
                'starts': 'lần', 'other': ''}
        for m in self:
            m.uom_label = nhan.get(m.meter_type, '')

    @api.depends('reading_ids.value', 'reading_ids.date',
                 'reading_ids.is_reset')
    def _compute_current(self):
        for m in self:
            ds = m.reading_ids.sorted(lambda r: (r.date, r.id))
            bu = 0.0          # cộng dồn các lần thay đồng hồ
            truoc = None
            nghi = 0
            for r in ds:
                lt = r.value + bu
                if truoc is not None and lt < truoc:
                    if r.is_reset:
                        # Thay đồng hồ: bù đúng bằng phần tụt xuống, để
                        # dãy số liên tục không gãy.
                        bu += truoc - r.value
                        lt = truoc
                    else:
                        nghi += 1
                r.effective_value = lt
                truoc = max(truoc or 0.0, lt)
            m.suspect_count = nghi
            cuoi = ds[-1] if ds else None
            m.current_value = cuoi.effective_value if cuoi else 0.0
            m.raw_value = cuoi.value if cuoi else 0.0
            m.date_last_reading = cuoi.date if cuoi else False

    @api.depends('location_code', 'meter_type')
    def _compute_display_name(self):
        nhan = dict(self._fields['meter_type'].selection)
        for m in self:
            m.display_name = '%s · %s' % (m.location_code or '?',
                                          nhan.get(m.meter_type, ''))

    @api.model
    def _lay_hoac_tao(self, location, meter_type):
        m = self.search([('location_id', '=', location.id),
                         ('meter_type', '=', meter_type)], limit=1)
        return m or self.create({'location_id': location.id,
                                 'meter_type': meter_type})


class EamMeterReading(models.Model):
    """Một lần đọc đồng hồ. Luỹ kế, không phải số gia."""
    _name = 'eam.meter.reading'
    _description = 'Số đọc đồng hồ'
    _order = 'date desc, id desc'

    meter_id = fields.Many2one(
        'eam.meter', string='Đồng hồ', required=True, ondelete='cascade',
        index=True)
    location_id = fields.Many2one(
        related='meter_id.location_id', store=True, string='Vị trí')
    date = fields.Date(
        string='Ngày đọc', required=True, index=True,
        default=lambda s: fields.Date.context_today(s))
    value = fields.Float(
        string='Số đọc (thô)', required=True, digits=(16, 2),
        help='Số LUỸ KẾ hiện trên máy, không phải số gia kể từ lần trước.')
    effective_value = fields.Float(
        string='Giá trị liên tục', compute='_compute_eff', store=True,
        digits=(16, 2))
    is_reset = fields.Boolean(
        string='Đã thay đồng hồ',
        help='Đánh dấu khi bộ đếm về 0 vì thay bộ điều khiển. Chỉ khi có '
             'dấu này hệ thống mới cộng bù — không thì một lần gõ nhầm sẽ '
             'làm mọi kế hoạch theo giờ tự lùi hạn.')
    source = fields.Selection(
        [('scada', 'Hệ giám sát'), ('manual', 'Nhập tay'),
         ('contractor', 'Báo cáo nhà thầu'), ('migration', 'Nhập lịch sử')],
        string='Nguồn', default='manual', required=True)
    note = fields.Char(string='Ghi chú')
    company_id = fields.Many2one(related='meter_id.company_id', store=True)

    _uniq = models.Constraint(
        'UNIQUE(meter_id, date)',
        'Mỗi đồng hồ chỉ có một số đọc cho mỗi ngày.')

    @api.depends('meter_id', 'value', 'date', 'is_reset')
    def _compute_eff(self):
        # Giá trị liên tục phụ thuộc TOÀN BỘ dãy số đọc của đồng hồ, không
        # chỉ bản ghi này — nên để chính đồng hồ tính và ghi xuống.
        for m in self.mapped('meter_id'):
            m._compute_current()
