# -*- coding: utf-8 -*-
"""Vật tư quay vòng: nối sổ kho với sổ lắp đặt (KHO-23), RMA & hoàn lõi
(KHO-25), bảo hành phụ tùng (KHO-26).

Một con hộp số có HAI danh tính
--------------------------------
* Nằm trong kho, nó là một **lô/sê-ri** (``stock.lot``) — đếm được, có
  giá, nhập xuất được.
* Lắp lên trụ, nó là một **tài sản** (``eam.asset``) — có lịch sử lắp
  đặt, có hỏng hóc, có bảo hành.

Cùng một vật. Để hai sổ tự sống riêng là chuyện xảy ra ở hầu hết nơi
dùng hai phần mềm rời: kho báo đã xuất, sổ tài sản không biết con nào
đang nằm ở trụ nào, và tới lúc đòi bảo hành thì không ai chứng minh
được.

Nên: mỗi sê-ri của vật tư quay vòng có **đúng một** bản ghi tài sản,
tạo ngay lúc NHẬP KHO chứ không đợi lúc lắp. Lý do: đồng hồ bảo hành
chạy từ ngày nhận hàng, và con hàng nằm kho hai năm thì hết bảo hành
trước khi kịp lắp.

Ranh giới hai sổ
-----------------
* **Sổ kho** trả lời: còn mấy con, đang ở kho nào, giá bao nhiêu.
* **Sổ lắp đặt** trả lời: con nào đang nằm ở trụ nào, từ bao giờ.

Không ghi chéo. Lúc xuất kho để lắp, hàng rời sổ kho và MỞ một quãng
lắp đặt — một sự kiện, hai sổ ghi hai mặt khác nhau của nó.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

LOAI_RMA = [
    ('warranty', 'Đòi bảo hành'),
    ('repair', 'Gửi sửa / đại tu'),
    ('core', 'Trả lõi cũ theo cam kết'),
    ('return', 'Trả hàng sai / hỏng khi nhận'),
]


class StockLot(models.Model):
    _inherit = 'stock.lot'

    eam_asset_id = fields.Many2one(
        'eam.asset', string='Tài sản tương ứng', ondelete='set null',
        copy=False, index=True,
        help='Vật tư quay vòng: mỗi sê-ri là một tài sản có lịch sử lắp '
             'đặt và bảo hành riêng. Cùng một vật, hai sổ ghi hai mặt.')
    eam_warranty_end = fields.Date(
        string='Bảo hành đến ngày',
        help='Tính từ ngày NHẬN HÀNG, không phải ngày lắp. Hàng nằm kho '
             'hai năm thì hết bảo hành trước khi kịp dùng.')
    eam_warranty_note = fields.Text(string='Điều kiện bảo hành')
    eam_core_due = fields.Date(
        string='Hạn trả lõi cũ',
        help='Nhiều hãng bán phụ tùng quay vòng theo cơ chế đổi lõi: giá '
             'rẻ hơn, kèm cam kết trả con cũ trong một hạn nhất định. Quá '
             'hạn là bị tính thêm tiền.')

    def _eam_tao_tai_san(self, warranty_months=24):
        """Dựng bản ghi tài sản cho sê-ri này nếu chưa có."""
        A = self.env['eam.asset']
        tao = A
        for l in self:
            if l.eam_asset_id or l.product_id.tracking != 'serial':
                continue
            if not l.product_id.eam_is_rotable:
                continue
            v = {
                'name': '%s — %s' % (l.product_id.name, l.name),
                # Tên sê-ri đã mang sẵn mã sản phẩm nên dùng luôn làm mã
                # tài sản: duy nhất toàn hệ thống, và tra ngược được từ
                # con số dập trên vỏ.
                'code': l.name,
                'serial_no': l.name,
                'category_id': l.product_id.eam_category_id.id or False,
                'manufacturer_id': (
                    l.product_id.eam_oem_partner_id.id or False),
                'model_ref': ', '.join(
                    l.product_id.eam_model_ids.mapped('name')) or False,
                'is_rotable': True,
                'date_manufacture': l.eam_mfg_date or False,
                'warranty_end': l.eam_warranty_end or False,
                'warranty_note': l.eam_warranty_note or False,
            }
            # Con máy này đến từ kho, tức qua đường mua sắm — hệ BIẾT
            # điều đó, nên đừng để sổ ghi "chưa rõ". Có eam_warranty thì
            # ghi; không có thì bỏ qua, vì eam_stock không được phụ thuộc
            # vào nó.
            if 'nguon_goc' in A._fields:
                v['nguon_goc'] = 'mua_sam'
                if l.ref:
                    v['nguon_tham_chieu'] = l.ref
            a = A.create(v)
            l.eam_asset_id = a.id
            tao |= a
        return tao


class EamAsset(models.Model):
    _inherit = 'eam.asset'

    lot_id = fields.One2many(
        'stock.lot', 'eam_asset_id', string='Lô/sê-ri trong kho')
    eam_in_stock = fields.Boolean(
        string='Đang trong kho', compute='_compute_in_stock',
        help='Có tồn ở vị trí nội bộ nào không. Khác với "đang lắp" — '
             'một con vừa tháo ra, chưa về kho, thì không ở đâu cả, và '
             'đó chính là lúc dễ mất dấu nhất.')

    def _compute_in_stock(self):
        Q = self.env['stock.quant']
        for a in self:
            lot = a.lot_id[:1]
            a.eam_in_stock = bool(lot) and bool(Q.search_count([
                ('lot_id', '=', lot.id),
                ('location_id.usage', '=', 'internal'),
                ('quantity', '>', 0)]))


class EamRma(models.Model):
    _name = 'eam.rma'
    _description = 'Trả hàng / đòi bảo hành / hoàn lõi'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(string='Số phiếu', required=True, copy=False,
                       readonly=True, default=lambda s: _('Mới'))
    rma_type = fields.Selection(
        LOAI_RMA, string='Loại', required=True, default='warranty',
        tracking=True)
    date = fields.Date(string='Ngày lập', required=True, tracking=True,
                       default=fields.Date.context_today)
    partner_id = fields.Many2one(
        'res.partner', string='Gửi cho bên nào', required=True,
        tracking=True)
    product_id = fields.Many2one(
        'product.product', string='Vật tư', required=True)
    lot_id = fields.Many2one(
        'stock.lot', string='Sê-ri / lô',
        domain="[('product_id', '=', product_id)]", tracking=True)
    asset_id = fields.Many2one(
        'eam.asset', string='Tài sản tương ứng',
        compute='_compute_asset', store=True, readonly=True)
    qty = fields.Float(string='Số lượng', default=1.0, required=True,
                       digits='Product Unit of Measure')
    location_id = fields.Many2one(
        'stock.location', string='Hàng đang ở',
        domain="[('usage', '=', 'internal')]")
    date_due = fields.Date(
        string='Hạn phải trả / phải xong', tracking=True,
        help='Trả lõi quá hạn thì bị tính thêm tiền; đòi bảo hành quá hạn '
             'thì mất quyền. Hạn này là thứ duy nhất ngăn phiếu nằm quên.')
    qua_han = fields.Boolean(string='Quá hạn', compute='_compute_qua_han',
                             search='_search_qua_han')
    reason = fields.Text(string='Lý do / mô tả hỏng hóc')
    ref_supplier = fields.Char(string='Số RMA của nhà cung cấp')
    state = fields.Selection(
        [('draft', 'Nháp'),
         ('sent', 'Đã gửi đi'),
         ('accepted', 'Bên kia chấp nhận'),
         ('returned', 'Đã nhận lại'),
         ('closed', 'Đã đóng'),
         ('rejected', 'Bên kia từ chối')],
        string='Trạng thái', default='draft', required=True, tracking=True,
        copy=False)
    work_order_id = fields.Many2one(
        'eam.work.order', string='Phát sinh từ lệnh')
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda s: s.env.company)

    @api.depends('lot_id')
    def _compute_asset(self):
        for r in self:
            r.asset_id = r.lot_id.eam_asset_id.id if r.lot_id else False

    def _compute_qua_han(self):
        hn = fields.Date.context_today(self)
        for r in self:
            r.qua_han = bool(
                r.date_due and r.date_due < hn
                and r.state not in ('returned', 'closed', 'rejected'))

    def _search_qua_han(self, operator, value):
        hn = fields.Date.context_today(self)
        dom = [('date_due', '<', hn),
               ('state', 'not in', ('returned', 'closed', 'rejected'))]
        if (operator == '=' and not value) or (operator == '!=' and value):
            return ['!'] + dom
        return dom

    @api.model_create_multi
    def create(self, vals_list):
        for v in vals_list:
            if v.get('name', _('Mới')) == _('Mới'):
                v['name'] = self.env['ir.sequence'].next_by_code(
                    'eam.rma') or _('Mới')
        return super().create(vals_list)

    def action_gui(self):
        for r in self:
            if not r.date_due:
                raise UserError(_(
                    'Phiếu "%s" chưa có hạn. Phiếu không hạn là phiếu nằm '
                    'quên — trả lõi quá hạn bị tính thêm tiền, đòi bảo '
                    'hành quá hạn thì mất quyền.', r.name))
            r.state = 'sent'
        return True

    def action_chap_nhan(self):
        self.write({'state': 'accepted'})
        return True

    def action_nhan_lai(self):
        """Nhận lại hàng — vào CHỜ KIỂM TRA, không vào thẳng kho.

        Hàng hãng sửa xong gửi về vẫn phải kiểm. Tin thẳng là cách để một
        con chưa sửa xong quay lại dây chuyền.
        """
        for r in self:
            r.state = 'returned'
            r.message_post(body=_(
                'Đã nhận lại. Hàng vào "Chờ kiểm tra" — lập phiếu kiểm '
                'tra đầu vào trước khi đưa về tồn khả dụng.'))
        return True

    def action_tu_choi(self):
        self.write({'state': 'rejected'})
        return True

    def action_dong(self):
        self.write({'state': 'closed'})
        return True
