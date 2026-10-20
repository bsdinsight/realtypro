# -*- coding: utf-8 -*-
"""Nhu cầu phụ tùng từ kế hoạch bảo trì (KHO-34), tối ưu tồn (KHO-36),
định giá và chi phí theo chiều (KHO-37).

Vì sao KHO-34 không chỉ là một báo cáo
----------------------------------------
Kế hoạch bảo trì ở ``eam.pm.plan`` **không khai vật tư nào cả**. Nên
"tổng hợp nhu cầu phụ tùng từ kế hoạch bảo trì" không phải viết một báo
cáo trên dữ liệu có sẵn — mà là **thiếu cả dữ liệu gốc**. Phải khai
trước: mỗi lần làm việc này tiêu thụ những gì.

Khai xong thì nhu cầu suy ra được: lịch nào sắp tới hạn × vật tư mỗi
lần × số lượng, trừ đi tồn khả dụng, ra phần thiếu. Đó mới là con số
dùng để đặt hàng — khác hẳn với định mức tối thiểu, vốn chỉ nhìn quá
khứ.

Chậm luân chuyển ≠ dư thừa ≠ ngừng sản xuất
---------------------------------------------
Ba thứ hay bị gộp làm một, nhưng cách xử khác hẳn:

* **Chậm luân chuyển** — lâu không động tới. Có thể vẫn đúng: phụ tùng
  cho sự cố hiếm thì nằm im là bình thường. Nhìn một mình con số này mà
  cắt kho là tự chặt tay mình.
* **Dư thừa** — nhiều hơn mức tối đa đã khai. Đây mới là tiền chết.
* **Ngừng sản xuất** — hãng không bán nữa. Loại này thì ngược lại: phải
  mua THÊM trước khi hết, không phải cắt.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class EamPmPlanMaterial(models.Model):
    _name = 'eam.pm.plan.material'
    _description = 'Vật tư cho một lần bảo trì'
    _order = 'plan_id, id'

    plan_id = fields.Many2one(
        'eam.pm.plan', string='Kế hoạch bảo trì', required=True,
        ondelete='cascade', index=True)
    product_id = fields.Many2one(
        'product.product', string='Vật tư', required=True,
        domain="[('is_storable', '=', True)]")
    qty = fields.Float(string='Số lượng mỗi lần', required=True,
                       default=1.0, digits='Product Unit of Measure')
    uom_id = fields.Many2one('uom.uom', string='Đơn vị')
    is_optional = fields.Boolean(
        string='Chỉ thay khi cần',
        help='Có thứ lần nào cũng thay (lọc, dầu); có thứ chỉ thay khi '
             'kiểm thấy hỏng. Gộp cả hai vào dự trù thì mua thừa đều đặn.')
    note = fields.Char(string='Ghi chú')

    @api.onchange('product_id')
    def _onchange_product(self):
        for l in self:
            if l.product_id:
                l.uom_id = l.product_id.uom_id


class EamPmPlan(models.Model):
    _inherit = 'eam.pm.plan'

    material_ids = fields.One2many(
        'eam.pm.plan.material', 'plan_id', string='Vật tư mỗi lần')
    material_count = fields.Integer(compute='_compute_material_count')

    @api.depends('material_ids')
    def _compute_material_count(self):
        for p in self:
            p.material_count = len(p.material_ids)


class EamPartDemand(models.TransientModel):
    _name = 'eam.part.demand'
    _description = 'Tổng hợp nhu cầu phụ tùng'

    date_to = fields.Date(
        string='Tổng hợp tới ngày', required=True,
        default=lambda s: fields.Date.add(
            fields.Date.context_today(s), days=90),
        help='Chân trời dự trù. Nên đặt ít nhất bằng thời gian cung ứng '
             'dài nhất, nếu không thì biết thiếu lúc đã không mua kịp.')
    warehouse_id = fields.Many2one(
        'stock.warehouse', string='Lấy từ kho', required=True)
    gom_tuy_chon = fields.Boolean(
        string='Tính cả vật tư "chỉ thay khi cần"',
        help='Bật thì ra con số an toàn nhưng mua thừa; tắt thì sát thực '
             'tế hơn nhưng có lúc phải mua gấp.')
    ket_qua = fields.Html(string='Kết quả', readonly=True)

    def action_tong_hop(self):
        self.ensure_one()
        S = self.env['eam.pm.schedule']
        hn = fields.Date.context_today(self)
        lich = S.search([('date_next', '!=', False),
                         ('date_next', '<=', self.date_to),
                         ('state', 'not in', ('done', 'cancelled'))])
        if not lich:
            raise UserError(_(
                'Không có lịch bảo trì nào tới hạn trước %s.', self.date_to))
        gom = {}
        for s in lich:
            for m in s.plan_id.material_ids:
                if m.is_optional and not self.gom_tuy_chon:
                    continue
                gom.setdefault(m.product_id, 0.0)
                gom[m.product_id] += m.qty
        if not gom:
            raise UserError(_(
                '%(n)d lịch bảo trì tới hạn nhưng KHÔNG kế hoạch nào khai '
                'vật tư.\n\nKhai vật tư cho kế hoạch bảo trì trước — '
                'không có dữ liệu gốc thì không tổng hợp được nhu cầu.',
                n=len(lich)))
        kho = self.warehouse_id.lot_stock_id
        rows = []
        for p, can in sorted(gom.items(), key=lambda x: -x[1]):
            co = p.with_context(location=kho.id).free_qty
            thieu = max(0.0, can - co)
            rows.append((p, can, co, thieu))
        tong_thieu = sum(1 for r in rows if r[3] > 0)
        html = [
            '<p>Tổng hợp từ <b>%d lịch bảo trì</b> tới hạn trước '
            '<b>%s</b>. Có <b>%d/%d</b> mặt hàng không đủ.</p>'
            % (len(lich), self.date_to, tong_thieu, len(rows)),
            '<table class="table table-sm"><thead><tr>'
            '<th>Mã</th><th>Vật tư</th><th class="text-end">Cần</th>'
            '<th class="text-end">Khả dụng</th><th class="text-end">Thiếu</th>'
            '<th class="text-end">Cung ứng</th></tr></thead><tbody>']
        for p, can, co, thieu in rows:
            mau = ' class="table-danger"' if thieu > 0 else ''
            html.append(
                '<tr%s><td>%s</td><td>%s</td><td class="text-end">%g</td>'
                '<td class="text-end">%g</td><td class="text-end">%g</td>'
                '<td class="text-end">%s</td></tr>' % (
                    mau, p.default_code or '', p.name, can, co, thieu,
                    '%d ngày' % p.eam_lead_days if p.eam_lead_days else '—'))
        html.append('</tbody></table>')
        html.append(
            '<p class="text-muted">Con số này khác định mức tối thiểu: '
            'định mức nhìn <b>quá khứ</b> (đã tiêu bao nhiêu), còn đây '
            'nhìn <b>lịch đã lên</b> (sắp phải làm gì).</p>')
        self.ket_qua = ''.join(html)
        return {'type': 'ir.actions.act_window', 'res_model': self._name,
                'res_id': self.id, 'view_mode': 'form', 'target': 'new'}


class ProductTemplateStockOpt(models.Model):
    _inherit = 'product.template'

    eam_last_move = fields.Date(
        string='Lần động gần nhất', compute='_compute_toi_uu', store=False)
    eam_months_idle = fields.Integer(
        string='Nằm im (tháng)', compute='_compute_toi_uu', store=False)
    eam_slow_moving = fields.Boolean(
        string='Chậm luân chuyển', compute='_compute_toi_uu', store=False,
        help='Không có phát sinh nào trong 12 tháng. CHƯA chắc là thừa — '
             'phụ tùng cho sự cố hiếm thì nằm im là đúng.')
    eam_excess_qty = fields.Float(
        string='Vượt mức tối đa', compute='_compute_toi_uu', store=False,
        digits='Product Unit of Measure',
        help='Tồn trừ đi mức tối đa đã khai. Đây mới là tiền chết.')
    eam_excess_value = fields.Monetary(
        string='Giá trị dư thừa', compute='_compute_toi_uu', store=False,
        currency_field='currency_id')
    eam_discontinued = fields.Boolean(
        string='Hãng ngừng sản xuất',
        help='Loại này xử NGƯỢC với dư thừa: phải mua thêm trước khi hết, '
             'không phải cắt.')

    def _compute_toi_uu(self):
        Move = self.env['stock.move']
        OP = self.env['stock.warehouse.orderpoint']
        hn = fields.Date.context_today(self)
        for t in self:
            p = t.product_variant_id
            if not p or not t.is_storable:
                t.eam_last_move = False
                t.eam_months_idle = 0
                t.eam_slow_moving = False
                t.eam_excess_qty = 0.0
                t.eam_excess_value = 0.0
                continue
            mv = Move.search([('product_id', '=', p.id),
                              ('state', '=', 'done')],
                             order='date desc', limit=1)
            t.eam_last_move = mv.date.date() if mv else False
            if t.eam_last_move:
                t.eam_months_idle = max(
                    0, (hn - t.eam_last_move).days // 30)
            else:
                t.eam_months_idle = 999
            t.eam_slow_moving = t.eam_months_idle >= 12
            ops = OP.search([('product_id', '=', p.id)])
            tran = sum(ops.mapped('product_max_qty')) if ops else 0.0
            ton = p.qty_available
            t.eam_excess_qty = max(0.0, ton - tran) if tran else 0.0
            t.eam_excess_value = t.eam_excess_qty * (t.standard_price or 0.0)
