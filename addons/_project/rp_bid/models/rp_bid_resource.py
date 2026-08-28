# -*- coding: utf-8 -*-
"""Tầng chi phí: một dòng BoQ tiêu thụ những tài nguyên nào.

DÙNG LẠI `rp.resource` CỦA THƯ VIỆN ĐƠN GIÁ, KHÔNG DỰNG MASTER RIÊNG.

Bản đầu tôi tự tạo `rp.bid.resource` — sai. `rp.resource` đã tồn tại
trong `rp_cost_library`, dùng đúng hệ mã của bộ đơn giá Việt Nam
(`NC2357`, `M103.1102`), đã có `categ_id` trỏ vào cây nhóm, và còn có
sẵn trường `gxd_code` dành riêng cho việc nhập từ GXD. Dựng thêm một
master nữa nghĩa là cùng một cần cẩu 25 tấn tồn tại ở hai bảng, và sớm
muộn hai bảng sẽ nói hai giá khác nhau.

TRỤC LỌC LÀ **NHÓM** TÀI NGUYÊN, KHÔNG PHẢI TỪNG TÀI NGUYÊN.

Bộ dữ liệu thật có 58 vật tư và 37 máy. Đưa nguyên danh mục lên panel
trái thì người dùng phải dò trong 58 dòng để tìm thứ mình cần — panel
lọc mà phải tìm kiếm bên trong nó thì đã hỏng mục đích. Trục phải là
danh mục CÓ BIÊN: "Cần cẩu", "Máy đào chuyên dùng", "Xi măng" — vài
chục nhóm, đọc lướt là thấy.
"""
from odoo import _, api, fields, models


class RpBidResourceLine(models.Model):
    _name = 'rp.bid.resource.line'
    _description = 'Chi phí của một dòng BoQ'
    _order = 'line_id, resource_type, sequence, id'

    line_id = fields.Many2one(
        'rp.bid.boq.line', string='Dòng BoQ',
        required=True, ondelete='cascade', index=True)
    bid_id = fields.Many2one(
        related='line_id.bid_id', string='Hồ sơ dự thầu', store=True,
        index=True)
    currency_id = fields.Many2one(related='line_id.currency_id')
    sequence = fields.Integer(default=10)

    # Ngữ cảnh của dòng BoQ mẹ, lưu lại để liệt kê theo dòng chi phí mà
    # vẫn biết nó thuộc hạng mục nào, đầu việc gì — và để lọc được.
    bid_structure_id = fields.Many2one(
        related='line_id.bid_structure_id', string='Hạng mục',
        store=True, index=True)
    project_id = fields.Many2one(
        related='line_id.project_id', string='Dự án', store=True, index=True)
    package_id = fields.Many2one(
        related='line_id.package_id', string='Gói thầu',
        store=True, index=True)
    norm_code = fields.Char(
        related='line_id.norm_code', string='Mã định mức', store=True)
    work_name = fields.Char(
        related='line_id.description', string='Đầu việc', store=True)
    work_qty = fields.Float(
        related='line_id.quantity', string='KL đầu việc')
    work_uom_id = fields.Many2one(
        related='line_id.uom_id', string='ĐVT đầu việc')

    resource_id = fields.Many2one(
        'rp.resource', string='Tài nguyên', required=True,
        ondelete='restrict', index=True)
    resource_type = fields.Selection(
        related='resource_id.resource_type', string='Loại',
        store=True, index=True)
    categ_id = fields.Many2one(
        related='resource_id.categ_id', string='Nhóm',
        store=True, index=True)
    uom_id = fields.Many2one(related='resource_id.uom_id', string='ĐVT')

    norm_qty = fields.Float(
        string='Định mức', digits=(16, 6),
        help='Chi phí cho MỘT đơn vị khối lượng của dòng BoQ.')
    is_percent = fields.Boolean(
        string='Tính theo %',
        help='Dòng "vật liệu khác", "máy khác" — định mức khai theo phần '
             'trăm chứ không theo lượng.')
    unit_price = fields.Monetary(
        string='Đơn giá', currency_field='currency_id')
    amount = fields.Monetary(
        string='Thành tiền', currency_field='currency_id',
        compute='_compute_amount', store=True)

    @api.depends('norm_qty', 'unit_price', 'is_percent', 'line_id.quantity')
    def _compute_amount(self):
        for rec in self:
            if rec.is_percent:
                # Dòng % tính trên tổng của nhóm cùng loại — để phần tính
                # đó cho bộ đơn giá gốc, ở đây không tự suy ra con số.
                rec.amount = 0.0
            else:
                rec.amount = ((rec.line_id.quantity or 0.0)
                              * (rec.norm_qty or 0.0)
                              * (rec.unit_price or 0.0))


class RpBidBoqLineResource(models.Model):
    _inherit = 'rp.bid.boq.line'

    resource_line_ids = fields.One2many(
        'rp.bid.resource.line', 'line_id', string='Chi phí')
    resource_count = fields.Integer(
        compute='_compute_resource_sets', store=True)

    # Ba trường m2m tới NHÓM tài nguyên, lưu lại để làm trục lọc. Panel
    # của Odoo chỉ nhận field có trong CSDL nên phải vật chất hoá.
    material_categ_ids = fields.Many2many(
        'rp.resource.category', 'rp_bid_line_mat_categ_rel',
        'line_id', 'categ_id', string='Nhóm vật tư',
        compute='_compute_resource_sets', store=True)
    labor_categ_ids = fields.Many2many(
        'rp.resource.category', 'rp_bid_line_lab_categ_rel',
        'line_id', 'categ_id', string='Nhóm nhân công',
        compute='_compute_resource_sets', store=True)
    machine_categ_ids = fields.Many2many(
        'rp.resource.category', 'rp_bid_line_mac_categ_rel',
        'line_id', 'categ_id', string='Nhóm thiết bị',
        compute='_compute_resource_sets', store=True)

    # Danh sách tài nguyên của dòng, để hiện thành thẻ ngay trên bảng
    # BoQ. Không dùng làm trục lọc (đó là việc của nhóm) — chỉ để nhìn
    # là biết dòng này ăn những gì, khỏi phải mở form từng dòng.
    resource_ids = fields.Many2many(
        'rp.resource', 'rp_bid_line_res_rel', 'line_id', 'res_id',
        string='Vật tư / NC / Máy',
        compute='_compute_resource_sets', store=True)

    price_from_resources = fields.Boolean(
        string='Đơn giá tính từ chi phí', compute='_compute_resource_sets',
        store=True,
        help='Dòng có chi phí thì ba đơn giá được TÍNH RA từ chi phí, không '
             'nhập tay. Sửa giá vật tư ở Bảng giá gói thầu là giá dự thầu '
             'đổi theo — đó là mục đích của tầng chi phí.')

    @api.depends('resource_line_ids.resource_id',
                 'resource_line_ids.resource_type',
                 'resource_line_ids.categ_id')
    def _compute_resource_sets(self):
        for rec in self:
            lines = rec.resource_line_ids
            rec.resource_count = len(lines)
            by_type = {'material': [], 'labor': [], 'machine': []}
            for rl in lines:
                if rl.resource_type in by_type and rl.categ_id:
                    # Lấy nhóm GỐC: cây nhóm 2 cấp (M103 > M103.1100),
                    # lọc theo cấp lá thì lại vụn ra hàng chục mục — đúng
                    # cái bệnh đang phải chữa.
                    root = rl.categ_id
                    while root.parent_id:
                        root = root.parent_id
                    by_type[rl.resource_type].append(root.id)
            rec.material_categ_ids = [(6, 0, list(set(by_type['material'])))]
            rec.labor_categ_ids = [(6, 0, list(set(by_type['labor'])))]
            rec.machine_categ_ids = [(6, 0, list(set(by_type['machine'])))]
            rec.resource_ids = [(6, 0, lines.mapped('resource_id').ids)]
            rec.price_from_resources = bool(lines)

    @api.depends('resource_line_ids.norm_qty', 'resource_line_ids.unit_price',
                 'resource_line_ids.is_percent',
                 'resource_line_ids.resource_type')
    def _compute_prices_from_resources(self):
        """Cộng chi phí thành ba đơn giá của dòng BoQ.

        Đây là chỗ KHÉP VÒNG. Trước đây tầng chi phí và ba đơn giá chạy
        song song: sửa giá vật tư trong chi phí thì giá dự thầu không
        nhúc nhích, nên cả tầng chi phí chỉ để xem.

        Công thức đúng theo cách dự toán Việt Nam lập đơn giá:

            đơn giá = Σ (chi phí × giá)  rồi nhân thêm phần khai theo %

        Dòng "vật liệu khác 2%", "máy khác 2%" tính trên tổng CÙNG LOẠI
        chứ không phải trên tổng cả dòng — bỏ qua chúng thì đơn giá hụt
        đúng 2%.

        Dòng KHÔNG có chi phí thì giữ nguyên giá đang nhập tay: hồ sơ
        nhập từ file dự toán vốn đã có giá, xoá trắng là mất dữ liệu.
        """
        for rec in self:
            lines = rec.resource_line_ids
            if not lines:
                rec.material_price = rec.material_price
                rec.labor_price = rec.labor_price
                rec.machine_price = rec.machine_price
                continue
            base = {'material': 0.0, 'labor': 0.0, 'machine': 0.0}
            pct = {'material': 0.0, 'labor': 0.0, 'machine': 0.0}
            for rl in lines:
                t = rl.resource_type
                if t not in base:
                    continue
                if rl.is_percent:
                    pct[t] += rl.norm_qty or 0.0
                else:
                    base[t] += (rl.norm_qty or 0.0) * (rl.unit_price or 0.0)
            rec.material_price = base['material'] * (1 + pct['material'] / 100.0)
            rec.labor_price = base['labor'] * (1 + pct['labor'] / 100.0)
            rec.machine_price = base['machine'] * (1 + pct['machine'] / 100.0)
