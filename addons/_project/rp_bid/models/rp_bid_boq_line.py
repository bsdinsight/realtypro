# -*- coding: utf-8 -*-
"""rp.bid.boq.line — Dòng BoQ của nhà thầu trong hồ sơ dự thầu.

Khác `rp.boq.line` (BoQ dự án) ở ba chỗ, và cả ba đều là lý do phải có
bảng riêng chứ không mở rộng bảng cũ:

1. **Ba đơn giá, không phải một.** Dự toán Việt Nam tách vật liệu / nhân
   công / máy thi công ngay từ đơn giá, vì ba thứ đó trượt giá khác nhau
   và thương lượng khác nhau. Gộp thành một ô "đơn giá" là mất khả năng
   trả lời "nhà thầu chào cao ở đâu" — biết họ cao 18% là báo động, biết
   ca máy của họ cao 47% mới là thông tin đàm phán được.

2. **Cờ ai cấp vật tư.** Bên mời thầu thường tự cấp vật tư chính. Phần
   đó vẫn phải bóc để biết tổng giá trị công việc, nhưng KHÔNG được cộng
   vào giá chào. Trong bộ dữ liệu thật, riêng một hạng mục cọc, phần vật
   tư bên mời cấp chiếm 56% chi phí trực tiếp — chào nhầm thành cao gấp
   2,3 lần.

3. **Khối lượng có xuất xứ.** `quantity` ở đây cộng từ các dòng bóc tách
   (`rp.bid.takeoff`) chứ không phải một con số gõ tay. Đây là thứ duy
   nhất chứng minh được khối lượng từ đâu ra khi bị hỏi.

`quantity` để 5 chữ số thập phân (BoQ dự án chỉ có 3). Dự toán thật dùng
tới 5 — khối lượng bê tông `4477.31570` mà lưu thành `4477.316` thì tổng
gói lệch vài chục nghìn đồng, không chết ai nhưng hồ sơ thầu không khớp
đến từng đồng là bị bắt bẻ.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

SUPPLIED_BY = [
    ('contractor', 'Nhà thầu (ta) cấp'),
    ('client', 'Bên mời thầu cấp'),
]


class RpBidBoqLine(models.Model):
    _name = 'rp.bid.boq.line'
    _description = 'Dòng BoQ nhà thầu'
    _order = 'bid_structure_id, sequence, id'

    bid_structure_id = fields.Many2one(
        'rp.bid.structure', string='Hạng mục nhà thầu',
        required=True, ondelete='cascade', index=True)
    bid_id = fields.Many2one(
        related='bid_structure_id.bid_id', string='Hồ sơ dự thầu',
        store=True, index=True)
    project_id = fields.Many2one(
        related='bid_structure_id.project_id', string='Dự án', store=True)
    currency_id = fields.Many2one(
        related='bid_structure_id.currency_id', string='Đồng tiền')
    bid_state = fields.Selection(
        related='bid_id.state', string='Trạng thái hồ sơ',
        store=True, index=True)
    package_id = fields.Many2one(
        related='bid_id.package_id', string='Gói thầu',
        store=True, index=True)

    sequence = fields.Integer(string='STT', default=10)
    norm_code = fields.Char(
        string='Mã định mức', index=True,
        help='Mã hiệu định mức (VD AC.32140). Để dạng chữ để nhập được cả '
             'khi chưa nạp bộ định mức vào thư viện.')
    description = fields.Char(
        string='Nội dung công việc', required=True, translate=True)
    uom_id = fields.Many2one(
        'rp.progress.uom', string='ĐVT', required=True)

    quantity = fields.Float(
        string='Khối lượng', digits=(16, 5), default=0.0,
        help='Nhập tay, hoặc bấm "Lấy từ bóc tách" để cộng từ các dòng '
             'bóc tách bên dưới.')
    takeoff_ids = fields.One2many(
        'rp.bid.takeoff', 'line_id', string='Bóc tách khối lượng')
    takeoff_quantity = fields.Float(
        string='KL theo bóc tách', digits=(16, 5),
        compute='_compute_takeoff', store=True)
    takeoff_count = fields.Integer(compute='_compute_takeoff', store=True)
    quantity_matches = fields.Boolean(
        string='Khớp bóc tách', compute='_compute_takeoff', store=True,
        help='Khối lượng đang dùng có khớp tổng các dòng bóc tách không. '
             'Lệch mà không ai thấy là cách sai đắt nhất trong dự toán.')

    supplied_by = fields.Selection(
        SUPPLIED_BY, string='Ai cấp vật tư', required=True,
        default='contractor', index=True,
        help='"Bên mời thầu cấp" thì phần VẬT LIỆU của dòng này KHÔNG vào '
             'giá chào — nhân công và máy vẫn tính, vì ta vẫn phải thi công.')

    material_price = fields.Monetary(
        string='ĐG vật liệu', currency_field='currency_id',
        compute='_compute_prices_from_resources', store=True, readonly=False)
    labor_price = fields.Monetary(
        string='ĐG nhân công', currency_field='currency_id',
        compute='_compute_prices_from_resources', store=True, readonly=False)
    machine_price = fields.Monetary(
        string='ĐG máy', currency_field='currency_id',
        compute='_compute_prices_from_resources', store=True, readonly=False)
    unit_price = fields.Monetary(
        string='ĐG tổng', currency_field='currency_id',
        compute='_compute_amounts', store=True)

    material_amount = fields.Monetary(
        string='TT vật liệu', currency_field='currency_id',
        compute='_compute_amounts', store=True)
    labor_amount = fields.Monetary(
        string='TT nhân công', currency_field='currency_id',
        compute='_compute_amounts', store=True)
    machine_amount = fields.Monetary(
        string='TT máy', currency_field='currency_id',
        compute='_compute_amounts', store=True)
    subtotal = fields.Monetary(
        string='Thành tiền (vào giá)', currency_field='currency_id',
        compute='_compute_amounts', store=True)
    client_supplied_amount = fields.Monetary(
        string='Vật tư bên mời cấp', currency_field='currency_id',
        compute='_compute_amounts', store=True,
        help='Giá trị vật liệu bên mời thầu cấp — theo dõi riêng, không '
             'cộng vào giá chào.')

    note = fields.Text(string='Ghi chú')

    # ==================================================================
    @api.depends('takeoff_ids.quantity', 'quantity')
    def _compute_takeoff(self):
        for rec in self:
            rec.takeoff_count = len(rec.takeoff_ids)
            total = sum(rec.takeoff_ids.mapped('quantity'))
            rec.takeoff_quantity = total
            # Không có dòng bóc tách thì coi như khớp — người dùng chủ động
            # nhập tay, không phải lỗi.
            rec.quantity_matches = (
                True if not rec.takeoff_ids
                else abs(total - (rec.quantity or 0.0)) < 0.00001)

    @api.depends('quantity', 'material_price', 'labor_price', 'machine_price',
                 'supplied_by')
    def _compute_amounts(self):
        for rec in self:
            qty = rec.quantity or 0.0
            mat = qty * (rec.material_price or 0.0)
            rec.labor_amount = qty * (rec.labor_price or 0.0)
            rec.machine_amount = qty * (rec.machine_price or 0.0)
            if rec.supplied_by == 'client':
                # Vật liệu bên mời cấp: bóc ra khỏi giá chào nhưng vẫn giữ
                # con số để biết tổng giá trị công việc.
                rec.material_amount = 0.0
                rec.client_supplied_amount = mat
            else:
                rec.material_amount = mat
                rec.client_supplied_amount = 0.0
            rec.subtotal = (rec.material_amount + rec.labor_amount
                            + rec.machine_amount)
            rec.unit_price = (rec.subtotal / qty) if qty else 0.0

    @api.constrains('quantity')
    def _check_quantity(self):
        for rec in self:
            if rec.quantity < 0:
                raise ValidationError(_(
                    'Khối lượng của dòng BoQ không được âm. Muốn trừ khối '
                    'lượng thì thêm một dòng BÓC TÁCH mang dấu âm.'))

    @api.depends('norm_code', 'description')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = ('[%s] %s' % (rec.norm_code, rec.description)
                                if rec.norm_code else (rec.description or ''))

    def action_pull_takeoff(self):
        """Lấy khối lượng từ tổng các dòng bóc tách."""
        for rec in self:
            if rec.takeoff_ids:
                rec.quantity = rec.takeoff_quantity
        return True
