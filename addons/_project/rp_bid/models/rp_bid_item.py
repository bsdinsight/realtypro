# -*- coding: utf-8 -*-
"""rp.bid.item — Dòng chào giá theo ĐÚNG khuôn bên mời thầu gửi.

VÌ SAO PHẢI CÓ TẦNG NÀY, KHÔNG CHÀO THẲNG TỪ HẠNG MỤC CỦA TA:

Bên mời thầu chia việc theo cách của họ, ta chia theo cách thi công —
hai cách gần như không bao giờ trùng. Bộ dữ liệu thật minh hoạ rõ:

    Phiếu mời gửi sang           Ta tự chia
    ─────────────────            ──────────────
    A. Huy động/giải thể     ┐
    B.1 Tường dẫn    192 md  ┼──→  Tường dẫn
    B.2 Tường vây  4761,6 m³ ┼──→  Tường vây
    C.1–4 Cọc thí nghiệm     ┼──→  Cọc TN D1200 + D1500
    D.1–4 Cọc đại trà        ┼──→  Cọc đại trà D1200 + D1500
    (không có dòng nào)      └──→  3 hạng mục thí nghiệm — 2,83 tỷ

Dòng ở đây là **bất biến**: nội dung, đơn vị và khối lượng phải giữ y
như file khách gửi, vì hồ sơ nộp lại sai khuôn là bị loại. Hạng mục của
ta thì tự do.

QUAN HỆ MỘT–NHIỀU, KHÔNG PHẢI NHIỀU–NHIỀU: mỗi hạng mục của ta cuộn vào
ĐÚNG MỘT dòng chào giá (`rp.bid.structure.item_id`). Cho phép nhiều–
nhiều thì một hạng mục có thể bị đếm ở hai dòng, và tổng chào sẽ vượt
giá thành mà không ai thấy. Chiều một–nhiều làm việc đếm trùng thành
điều KHÔNG THỂ xảy ra, thay vì thành điều phải đi kiểm.

CÁCH PHÂN BỔ GIÁ: markup nằm ở cấp hồ sơ (chi phí chung, nhà tạm, TNCTT,
VAT tính trên tổng), nên không thể gán thẳng cho từng dòng. Ở đây phân
bổ **theo tỷ trọng chi phí trực tiếp**: dòng nào ngốn nhiều chi phí trực
tiếp thì gánh nhiều markup. Đây là cách phân bổ thông dụng và giải thích
được với bên mời thầu; nếu khách yêu cầu cách khác thì sửa ở một chỗ.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class RpBidItem(models.Model):
    _name = 'rp.bid.item'
    _description = 'Dòng chào giá (theo khuôn bên mời thầu)'
    _order = 'bid_id, sequence, id'

    bid_id = fields.Many2one(
        'rp.bid', string='Hồ sơ dự thầu', required=True,
        ondelete='cascade', index=True)
    currency_id = fields.Many2one(
        related='bid_id.currency_id', string='Đồng tiền')

    sequence = fields.Integer(string='STT', default=10)
    code = fields.Char(
        string='Mã', help='Ký hiệu đúng như file mời thầu: A, B.1, C.2…')
    name = fields.Char(
        string='Nội dung', required=True, translate=True,
        help='Chép nguyên văn từ file mời thầu — nộp lại sai chữ là rủi ro.')
    is_section = fields.Boolean(
        string='Dòng tiêu đề',
        help='Dòng nhóm (A, B, C…) không có khối lượng, chỉ để gom.')

    uom_text = fields.Char(
        string='ĐVT (theo mời thầu)',
        help='Giữ nguyên chuỗi khách ghi ("md", "m3", "Trọn gói"). Cố ý là '
             'CHỮ chứ không phải danh mục: đơn vị của khách không phải lúc '
             'nào cũng có trong danh mục của mình, và ép map sẽ làm sai '
             'khuôn hồ sơ nộp.')
    quantity_client = fields.Float(
        string='KL mời thầu', digits=(16, 5),
        help='Khối lượng bên mời thầu đưa ra. KHÔNG sửa theo bóc tách của '
             'mình — lệch thì để lệch và hỏi lại, vì đây là số trong hồ sơ.')

    structure_ids = fields.One2many(
        'rp.bid.structure', 'item_id', string='Hạng mục cuộn vào dòng này')
    structure_count = fields.Integer(compute='_compute_amounts', store=True)

    cost_direct = fields.Monetary(
        string='Chi phí trực tiếp', currency_field='currency_id',
        compute='_compute_amounts', store=True,
        help='Chi phí của các hạng mục gắn thẳng vào dòng này.')
    cost_spread = fields.Monetary(
        string='Chi phí rải vào', currency_field='currency_id',
        compute='_compute_amounts', store=True,
        help='Phần chia về từ các hạng mục chọn "Rải đều" — thí nghiệm, '
             'vận chuyển, huy động… những thứ không thuộc riêng dòng nào.')
    cost_total = fields.Monetary(
        string='Chi phí gánh', currency_field='currency_id',
        compute='_compute_amounts', store=True)
    cost_share = fields.Float(
        string='Tỷ trọng %', digits=(5, 2),
        compute='_compute_amounts', store=True)
    amount_offer = fields.Monetary(
        string='Thành tiền chào', currency_field='currency_id',
        compute='_compute_amounts', store=True,
        help='Giá dự thầu của hồ sơ phân bổ về dòng này theo tỷ trọng chi '
             'phí trực tiếp.')
    unit_price_offer = fields.Monetary(
        string='ĐƠN GIÁ CHÀO', currency_field='currency_id',
        compute='_compute_amounts', store=True,
        help='Thành tiền chào chia cho khối lượng mời thầu. Đây chính là ô '
             'phải điền vào file gửi lại khách.')
    client_supplied_cost = fields.Monetary(
        string='Vật tư bên mời cấp', currency_field='currency_id',
        compute='_compute_amounts', store=True)

    takeoff_quantity = fields.Float(
        string='KL ta bóc được', digits=(16, 5),
        compute='_compute_amounts', store=True,
        help='Tổng khối lượng của các hạng mục cuộn vào dòng này, chỉ tính '
             'các dòng BoQ CÙNG đơn vị với đơn vị mời thầu.')

    note = fields.Text(string='Ghi chú')

    # ==================================================================
    @api.depends('structure_ids.direct_cost',
                 'structure_ids.client_supplied_cost',
                 'bid_id.direct_cost', 'bid_id.bid_total',
                 'bid_id.spread_cost', 'bid_id.outside_cost',
                 'quantity_client')
    def _compute_amounts(self):
        """Rót giá dự thầu về từng dòng chào.

        Ba bước, và bước giữa là bước mới:

          ① chi phí gắn thẳng      Σ hạng mục có item_id = dòng này
          ② cộng phần rải đều      pool "spread" chia theo tỷ trọng ①
          ③ nhân lên thành giá     theo tỷ trọng trên TỔNG PHẢI CHÀO

        Mẫu số ở bước ③ là `direct_cost − outside_cost`, KHÔNG phải tổng
        của ① + ②. Cố ý: phần chưa gắn dòng nào vẫn nằm trong mẫu số, nên
        Σ dòng chào sẽ NHỎ HƠN tổng phải chào đúng bằng phần còn treo.
        Nếu lấy mẫu số là ①+② thì phần treo bị chia ngầm vào các dòng và
        bảng chào tự khớp — che mất đúng cái cần nhìn thấy.
        """
        for item in self:
            bid = item.bid_id
            structs = item.structure_ids
            item.structure_count = len(structs)
            item.cost_direct = sum(structs.mapped('direct_cost'))
            item.client_supplied_cost = sum(
                structs.mapped('client_supplied_cost'))

            # ② Pool rải đều, chia theo tỷ trọng chi phí gắn thẳng.
            anchored = sum(bid.item_ids.mapped('cost_direct')) or 0.0
            item.cost_spread = (
                (bid.spread_cost or 0.0) * item.cost_direct / anchored
                if anchored else 0.0)
            item.cost_total = item.cost_direct + item.cost_spread

            # ③ Mẫu số giữ nguyên phần còn treo — xem docstring.
            total = (bid.direct_cost or 0.0) - (bid.outside_cost or 0.0)
            share = (item.cost_total / total) if total else 0.0
            item.cost_share = share * 100.0
            item.amount_offer = (bid.offer_total or 0.0) * share
            item.unit_price_offer = (
                item.amount_offer / item.quantity_client
                if item.quantity_client else 0.0)

            # Khối lượng ta bóc được, chỉ cộng dòng BoQ cùng đơn vị với
            # đơn vị mời thầu — cộng lẫn m³ với tấn ra một số vô nghĩa.
            unit = (item.uom_text or '').strip().lower()
            qty = 0.0
            if unit:
                for line in structs.mapped('line_ids'):
                    if (line.uom_id.code or '').strip().lower() == unit:
                        qty += line.quantity
            item.takeoff_quantity = qty


class RpBidStructureItem(models.Model):
    _inherit = 'rp.bid.structure'

    allocation_mode = fields.Selection(
        [('item', 'Gắn vào dòng chào'),
         ('spread', 'Rải đều theo tỷ trọng'),
         ('outside', 'Ngoài giá chào (claim riêng)')],
        string='Cách đưa vào bảng chào', default='item', required=True,
        index=True,
        help='Bên mời thầu không phải lúc nào cũng có dòng cho mọi việc ta '
             'phải làm. Ba đường ra:\n'
             '· Gắn vào dòng chào — thường gặp nhất.\n'
             '· Rải đều — thí nghiệm, vận chuyển, huy động: việc phục vụ '
             'cả gói, không thuộc riêng dòng nào.\n'
             '· Ngoài giá chào — không nộp trong bảng, để claim riêng '
             'hoặc thương lượng thêm.')
    item_id = fields.Many2one(
        'rp.bid.item', string='Dòng chào giá',
        ondelete='set null', index=True,
        domain="[('bid_id', '=', bid_id), ('is_section', '=', False)]",
        help='Dòng trong file mời thầu mà hạng mục này cuộn vào. Bỏ trống '
             'khi cách đưa vào là Rải đều hoặc Ngoài giá chào.')
    allocation_done = fields.Boolean(
        string='Đã xử lý phân bổ', compute='_compute_allocation_done',
        store=True)

    @api.depends('allocation_mode', 'item_id')
    def _compute_allocation_done(self):
        for rec in self:
            rec.allocation_done = bool(
                rec.allocation_mode != 'item' or rec.item_id)

    @api.onchange('allocation_mode')
    def _onchange_allocation_mode(self):
        """Đổi sang Rải đều / Ngoài giá chào thì bỏ dòng chào đang gắn —
        để lại sẽ thành hai nguồn sự thật cho cùng một hạng mục."""
        if self.allocation_mode != 'item':
            self.item_id = False

    @api.constrains('allocation_mode', 'item_id')
    def _check_allocation(self):
        for rec in self:
            if rec.allocation_mode != 'item' and rec.item_id:
                raise ValidationError(_(
                    'Hạng mục "%(s)s" đang để cách đưa vào là "%(m)s" nhưng '
                    'vẫn gắn dòng chào. Bỏ dòng chào, hoặc đổi lại thành '
                    '"Gắn vào dòng chào".',
                    s=rec.display_name,
                    m=dict(rec._fields['allocation_mode'].selection)[
                        rec.allocation_mode]))

