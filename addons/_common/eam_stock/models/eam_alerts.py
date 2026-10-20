# -*- coding: utf-8 -*-
"""Phụ tùng tương đương (KHO-06) và bảng cảnh báo kho (KHO-43).

Tương đương phải CÓ NGƯỜI DUYỆT
---------------------------------
"Hai con này thay nhau được" là một kết luận kỹ thuật, không phải một
ghi chú. Cho khai tự do rồi dùng luôn là mở đường để ai đó lắp một con
"trông giống" vào máy đang trong bảo hành — và mất bảo hành cả cụm.

Nên bản ghi tương đương có trạng thái: khai xong là **chờ duyệt**, chỉ
khi kỹ thuật duyệt mới được phép dùng thay. Và luôn ghi **điều kiện áp
dụng**, vì rất ít cặp thay thế được vô điều kiện.

Cảnh báo: gom về MỘT chỗ, nhưng nói rõ từng loại
--------------------------------------------------
Năm nguồn lo khác nhau, cùng một câu hỏi "có gì sắp vỡ không". Tách
thành năm màn hình thì không ai mở đủ; gộp thành một con số thì không ai
biết phải làm gì. Nên: một bảng, mỗi dòng nói rõ loại và việc cần làm.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class EamPartEquivalent(models.Model):
    _name = 'eam.part.equivalent'
    _description = 'Phụ tùng tương đương'
    _inherit = ['mail.thread']
    _order = 'product_id, id'

    product_id = fields.Many2one(
        'product.template', string='Phụ tùng gốc', required=True,
        ondelete='cascade', index=True)
    equivalent_id = fields.Many2one(
        'product.template', string='Thay được bằng', required=True,
        ondelete='cascade', index=True)
    two_way = fields.Boolean(
        string='Thay được cả hai chiều', default=True,
        help='Không phải cặp nào cũng đối xứng: con đời mới thay được con '
             'đời cũ, nhưng ngược lại thì không.')
    condition = fields.Text(
        string='Điều kiện áp dụng', required=True,
        help='Rất ít cặp thay thế được vô điều kiện. Ghi rõ: chỉ cho '
             'model nào, chỉ khi nào, phải làm gì thêm.')
    affects_warranty = fields.Boolean(
        string='Ảnh hưởng bảo hành',
        help='Lắp đồ không chính hãng vào máy còn bảo hành thường làm '
             'mất bảo hành CẢ CỤM, không riêng con đó.')
    state = fields.Selection(
        [('draft', 'Chờ duyệt kỹ thuật'),
         ('approved', 'Đã duyệt — dùng được'),
         ('rejected', 'Không chấp nhận')],
        string='Trạng thái', default='draft', required=True, tracking=True)
    approver_id = fields.Many2one('res.users', string='Kỹ thuật duyệt',
                                  readonly=True, tracking=True)
    date_approved = fields.Date(string='Duyệt ngày', readonly=True)
    note = fields.Text(string='Căn cứ kỹ thuật')
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda s: s.env.company)

    @api.constrains('product_id', 'equivalent_id')
    def _check_khac_nhau(self):
        for r in self:
            if r.product_id == r.equivalent_id:
                raise UserError(_(
                    'Một phụ tùng không thể tương đương với chính nó.'))

    def action_duyet(self):
        for r in self:
            r.write({'state': 'approved', 'approver_id': self.env.user.id,
                     'date_approved': fields.Date.context_today(r)})
            if r.affects_warranty:
                r.message_post(body=_(
                    'Đã duyệt NHƯNG có ảnh hưởng bảo hành — kiểm tra máy '
                    'còn bảo hành hay không trước khi lắp.'))
        return True

    def action_tu_choi(self):
        self.write({'state': 'rejected', 'approver_id': self.env.user.id,
                    'date_approved': fields.Date.context_today(self)})
        return True


class ProductTemplateEquiv(models.Model):
    _inherit = 'product.template'

    eam_equivalent_ids = fields.One2many(
        'eam.part.equivalent', 'product_id', string='Phụ tùng tương đương')
    eam_equivalent_ok = fields.Integer(
        string='Số tương đương đã duyệt', compute='_compute_equiv')

    @api.depends('eam_equivalent_ids.state')
    def _compute_equiv(self):
        for t in self:
            t.eam_equivalent_ok = len(
                t.eam_equivalent_ids.filtered(lambda e: e.state == 'approved'))


class EamStockAlert(models.TransientModel):
    _name = 'eam.stock.alert'
    _description = 'Bảng cảnh báo kho'

    ket_qua = fields.Html(string='Cảnh báo', readonly=True)

    def _gom_canh_bao(self):
        """Năm nguồn lo, trả về danh sách phẳng để dựng bảng."""
        hn = fields.Date.context_today(self)
        env = self.env
        ds = []

        # ① Phụ tùng TRỌNG YẾU dưới định mức — xếp trước vì hậu quả nặng
        #    nhất và thời gian cung ứng dài nhất.
        for o in env['stock.warehouse.orderpoint'].search([]):
            t = o.product_id.product_tmpl_id
            if t.eam_criticality not in ('critical', 'high'):
                continue
            con = o.product_id.with_context(
                location=o.location_id.id).qty_available
            if con >= o.product_min_qty:
                continue
            ds.append(('Thiếu phụ tùng trọng yếu', 'danger',
                       o.product_id.display_name,
                       _('còn %(c)g / tối thiểu %(m)g · cung ứng %(l)d ngày',
                         c=con, m=o.product_min_qty, l=t.eam_lead_days),
                       _('Đặt mua ngay — thiếu thì %s') % dict(
                           t._fields['eam_shortage_impact'].selection or []
                       ).get(t.eam_shortage_impact, _('ảnh hưởng vận hành'))))

        # ② Lô sắp hết hạn / đã hết hạn
        han = fields.Date.add(hn, days=60)
        for l in env['stock.lot'].search(
                [('expiration_date', '!=', False),
                 ('expiration_date', '<=', han)], order='expiration_date'):
            if not env['stock.quant'].search_count(
                    [('lot_id', '=', l.id),
                     ('location_id.usage', '=', 'internal'),
                     ('quantity', '>', 0)]):
                continue
            het = l.expiration_date.date() < hn
            ds.append((
                'Hết hạn sử dụng' if het else 'Sắp hết hạn',
                'danger' if het else 'warning',
                '%s — %s' % (l.product_id.display_name, l.name),
                _('hạn %s', l.expiration_date.date()),
                _('Lập phiếu thanh lý') if het
                else _('Ưu tiên dùng lô này trước')))

        # ③ Đơn mua giao trễ
        for po in env['purchase.order'].search(
                [('state', '=', 'purchase')]):
            if not po.date_planned or po.date_planned.date() >= hn:
                continue
            cho = [p for p in po.picking_ids
                   if p.state not in ('done', 'cancel')]
            if not cho:
                continue
            ds.append(('Đơn mua giao trễ', 'warning', po.name,
                       _('hẹn %(d)s, trễ %(n)d ngày',
                         d=po.date_planned.date(),
                         n=(hn - po.date_planned.date()).days),
                       _('Giục nhà cung cấp %s', po.partner_id.name)))

        # ④ Lệnh công việc giữ chỗ KHÔNG ĐỦ — biết trước khi tổ thợ lên trụ
        for l in env['eam.work.order.part'].search(
                [('trang_thai_kho', '=', 'thieu')]):
            ds.append(('Công việc thiếu vật tư', 'danger',
                       l.order_id.name,
                       _('%(sp)s: giữ được %(g)g / cần %(c)g',
                         sp=l.product_id.display_name,
                         g=l.move_id.quantity if l.move_id else 0, c=l.qty),
                       _('Bổ sung hàng hoặc dời lịch')))

        # ⑤ Hàng KÝ GỬI đang bị đếm vào tồn khả dụng — chỗ sai IM LẶNG:
        #    hệ thống báo đủ hàng trong khi hàng đó của người khác.
        for q in env['stock.quant'].search(
                [('owner_id', '!=', False),
                 ('location_id.usage', '=', 'internal'),
                 ('quantity', '>', 0)]):
            ds.append(('Hàng ký gửi tính nhầm vào tồn', 'warning',
                       q.product_id.display_name,
                       _('%(n)g đơn vị ở %(vt)s, chủ sở hữu %(ch)s',
                         n=q.quantity, vt=q.location_id.name,
                         ch=q.owner_id.name),
                       _('Định mức tối thiểu KHÔNG phân biệt chủ sở hữu '
                         '— trừ ra khi tính mua')))
        return ds

    def action_xem(self):
        self.ensure_one()
        ds = self._gom_canh_bao()
        if not ds:
            self.ket_qua = ('<p class="text-success"><b>Không có cảnh báo '
                            'nào.</b></p>')
        else:
            gom = {}
            for loai, mau, doi_tuong, chi_tiet, viec in ds:
                gom.setdefault((loai, mau), []).append(
                    (doi_tuong, chi_tiet, viec))
            h = ['<p>Tổng <b>%d</b> cảnh báo, %d nhóm.</p>'
                 % (len(ds), len(gom))]
            for (loai, mau), rows in sorted(
                    gom.items(), key=lambda x: -len(x[1])):
                h.append('<h4 class="text-%s">%s <span class="badge '
                         'text-bg-%s">%d</span></h4>'
                         % (mau, loai, mau, len(rows)))
                h.append('<table class="table table-sm"><tbody>')
                for a, b, c in rows[:25]:
                    h.append('<tr><td><b>%s</b></td><td>%s</td>'
                             '<td class="text-muted">%s</td></tr>'
                             % (a, b, c))
                h.append('</tbody></table>')
            self.ket_qua = ''.join(h)
        return {'type': 'ir.actions.act_window', 'res_model': self._name,
                'res_id': self.id, 'view_mode': 'form', 'target': 'new'}
