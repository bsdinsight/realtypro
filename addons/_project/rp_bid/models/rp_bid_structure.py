# -*- coding: utf-8 -*-
"""rp.bid.structure — Hạng mục do NHÀ THẦU chia trong một hồ sơ dự thầu.

CHỈ MỘT CẤP — KHÔNG CÓ CHA CON.

Bản trước có cây hai cấp để chứa nhóm A/B/C/D của bảng mời thầu. Gỡ đi
vì cái giá quá đắt so với thứ nhận được: hạng mục cha không có BoQ
riêng nên bày ra toàn số cộng dồn cạnh một bảng trống, dòng tổng của
danh sách đếm cả cha lẫn con (lệch 13 tỷ trên 26 tỷ), và mỗi chỗ tính
tiền đều phải phân biệt "của riêng" với "cộng dồn".

Mà cách gom nhóm VẪN CÒN — nó nằm ở Bảng giá chào, nơi dòng tiêu đề
A/B/C/D được giữ nguyên theo file khách gửi. Hạng mục chỉ cần phẳng và
mỗi cái gắn vào một dòng chào giá.

KHÔNG CÓ LIÊN KẾT NGƯỢC LÊN HẠNG MỤC DỰ ÁN — CÓ CHỦ Ý.

Bản đầu tôi cho mỗi hạng mục nhà thầu trỏ lên một hạng mục của dự án.
Sai về vai: nhà thầu chỉ nhận GÓI THẦU, họ không có và không cần biết
chủ đầu tư chia dự án thành hạng mục thế nào. Trong tình huống thật,
nhà thầu còn chẳng có cây hạng mục của chủ đầu tư trong hệ thống của
mình.

Phạm vi của hồ sơ đã được xác định bởi gói thầu (`rp.bid.package_id`).
Từ đó xuống, cách chia hạng mục là quyền của nhà thầu, không phải bản
sao cây của ai khác.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class RpBidStructure(models.Model):
    _name = 'rp.bid.structure'
    _description = 'Hạng mục nhà thầu (hồ sơ dự thầu)'
    _order = 'bid_id, sequence, code, id'

    name = fields.Char(string='Tên hạng mục', required=True, translate=True)
    code = fields.Char(string='Mã')
    sequence = fields.Integer(default=10)

    bid_id = fields.Many2one(
        'rp.bid', string='Hồ sơ dự thầu', required=True,
        ondelete='cascade', index=True)
    project_id = fields.Many2one(
        related='bid_id.project_id', string='Dự án', store=True, index=True)
    package_id = fields.Many2one(
        related='bid_id.package_id', string='Gói thầu',
        store=True, index=True)
    currency_id = fields.Many2one(
        related='bid_id.currency_id', string='Đồng tiền')
    # Trạng thái hồ sơ, lưu lại để dùng làm trục lọc. Selection nên số
    # giá trị có biên — hợp làm panel trái; lấy chính hồ sơ làm trục thì
    # panel sẽ dài thêm mãi theo số hồ sơ đã lập.
    bid_state = fields.Selection(
        related='bid_id.state', string='Trạng thái hồ sơ',
        store=True, index=True)




    line_ids = fields.One2many(
        'rp.bid.boq.line', 'bid_structure_id', string='BoQ nhà thầu')
    line_count = fields.Integer(compute='_compute_amounts', store=True)

    cost_material = fields.Monetary(
        string='Vật liệu', currency_field='currency_id',
        compute='_compute_amounts', store=True)
    cost_labor = fields.Monetary(
        string='Nhân công', currency_field='currency_id',
        compute='_compute_amounts', store=True)
    cost_machine = fields.Monetary(
        string='Máy thi công', currency_field='currency_id',
        compute='_compute_amounts', store=True)
    direct_cost = fields.Monetary(
        string='Chi phí trực tiếp', currency_field='currency_id',
        compute='_compute_amounts', store=True)
    client_supplied_cost = fields.Monetary(
        string='Vật tư bên mời cấp', currency_field='currency_id',
        compute='_compute_amounts', store=True)

    note = fields.Text(string='Ghi chú')

    # ==================================================================
    @api.depends('line_ids.material_amount', 'line_ids.labor_amount',
                 'line_ids.machine_amount', 'line_ids.client_supplied_amount')
    def _compute_amounts(self):
        for rec in self:
            lines = rec.line_ids
            rec.line_count = len(lines)
            rec.cost_material = sum(lines.mapped('material_amount'))
            rec.cost_labor = sum(lines.mapped('labor_amount'))
            rec.cost_machine = sum(lines.mapped('machine_amount'))
            rec.direct_cost = (rec.cost_material + rec.cost_labor
                               + rec.cost_machine)
            rec.client_supplied_cost = sum(
                lines.mapped('client_supplied_amount'))







    @api.depends('code', 'name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = ('[%s] %s' % (rec.code, rec.name)
                                if rec.code else rec.name)
