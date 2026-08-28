# -*- coding: utf-8 -*-
"""rp.bid — Hồ sơ dự thầu (ta ĐI dự thầu).

VỊ TRÍ TRONG CHUỖI DỮ LIỆU:

    Dự án
     └─ Hạng mục dự án (rp.structure) ─ BoQ dự án (rp.boq.line)   ← CĐT/tổng thầu lập
     └─ Gói thầu (rp.tender.package)
          └─ HỒ SƠ DỰ THẦU (model này)                            ← nhà thầu lập
               └─ Hạng mục nhà thầu (rp.bid.structure)   ← cấp thấp hơn hạng mục dự án
                    └─ BoQ nhà thầu (rp.bid.boq.line)    ← cấp thấp hơn BoQ dự án

VÌ SAO KHÔNG DÙNG LẠI `rp.tender.package` VỚI MỘT CỜ CHIỀU:

Hai chiều dùng cùng danh từ nhưng ngược nghĩa. Ở gói thầu, "giá" là giá
TRẦN được duyệt và việc chính là chấm nhà thầu; ở đây "giá" là giá TA
CHÀO và việc chính là bóc khối lượng rồi quyết biên lợi nhuận. Nhét cả
hai vào một model thì mọi view, domain và báo cáo đều phải rẽ nhánh, mà
hai nhánh không bao giờ hội tụ.

VÌ SAO HẠNG MỤC / BOQ NHÀ THẦU LÀ BẢNG RIÊNG, KHÔNG PHẢI CẤP THỨ BA CỦA
`rp.structure`:

`rp.structure.boq_total` → `estimate_value` → nuôi % tiến độ và BAC của
EVM. Nếu bóc tách của nhà thầu nằm chung bảng thì cùng một khối lượng
công việc bị tính hai lần: một lần ở BoQ dự án, một lần ở BoQ nhà thầu.
Ngân sách dự án sẽ phình gấp đôi mà báo cáo vẫn ra số, nên rất khó phát
hiện. Quan hệ "cấp thấp hơn" diễn đạt bằng khoá ngoại
(`rp.bid.package_id`) là đủ: phạm vi do gói thầu xác định.

MARKUP ĐỂ Ở ĐÂY, KHÔNG TRA THƯ VIỆN:

Markup là quyết định THƯƠNG MẠI của từng hồ sơ — cùng một loại công
việc, gói dễ thì chào 5,5% lãi, gói muốn lấy bằng được thì chào 2%. Tra
từ thư viện đơn giá sẽ biến quyết định kinh doanh thành hằng số kỹ
thuật. Năm tầng dưới đây theo đúng cấu trúc dự toán Việt Nam:

    T   = VL + NC + M                    chi phí trực tiếp
    C   = T × chi phí chung %
    LT  = T × nhà tạm %
    TT  = T × công việc không xác định KL %
    GT  = C + LT + TT                    chi phí gián tiếp
    TL  = (T + GT) × TNCTT %             thu nhập chịu thuế tính trước
    G   = T + GT + TL                    trước thuế
    GTGT= G × VAT %
    GXD = G + GTGT
    GDP = GXD × dự phòng %
    GIÁ DỰ THẦU = GXD + GDP
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

BID_STATES = [
    ('draft', 'Nháp'),
    ('pricing', 'Đang tính giá'),
    ('submitted', 'Đã nộp'),
    ('won', 'Trúng thầu'),
    ('lost', 'Trượt thầu'),
    ('cancelled', 'Huỷ'),
]


class RpBid(models.Model):
    _name = 'rp.bid'
    _description = 'Hồ sơ dự thầu'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_due desc, id desc'

    name = fields.Char(
        string='Tên hồ sơ', required=True, tracking=True,
        default=lambda s: _('Hồ sơ dự thầu mới'))
    code = fields.Char(string='Mã hồ sơ', tracking=True)

    # Dự án chọn TRƯỚC, rồi mới chọn gói thầu trong dự án đó.
    #
    # Bản đầu tôi để `project_id` là trường ăn theo gói thầu (related,
    # chỉ đọc). Chạy được nhưng ngược với cách nhà thầu làm việc: họ
    # nghĩ theo "dự án nào → gói nào của dự án đó", và danh sách gói thầu
    # của mọi dự án gộp lại thì dài không chọn nổi. Để `project_id` là
    # trường thật thì lọc được danh sách gói ngay tại chỗ.
    # SỔ CỦA NHÀ THẦU, không phải của bên mời thầu. Trước đây hai trường
    # này trỏ vào `re.project` / `rp.tender.package` — tức là bắt nhà thầu
    # chọn dự án và gói thầu từ danh sách của CHỦ ĐẦU TƯ. Sai: nhà thầu dự
    # thầu cho hàng chục chủ đầu tư, dự án của họ không nằm trong hệ thống
    # của mình; và `re.project` còn mở ra ngân sách, hợp đồng, dòng tiền
    # của bên kia. Xem `rp_bid_project.py`.
    project_id = fields.Many2one(
        'rp.bid.project', string='Dự án', required=True,
        ondelete='restrict', index=True, tracking=True)
    package_id = fields.Many2one(
        'rp.bid.package', string='Gói thầu', required=True,
        ondelete='restrict', index=True, tracking=True,
        domain="[('project_id', '=', project_id)]",
        help='Gói thầu ta được mời dự — do nhà thầu tự nhập khi nhận thư '
             'mời. Mọi hạng mục và BoQ bên dưới đều nằm trong phạm vi gói '
             'này.')
    invited_by_id = fields.Many2one(
        'res.partner', string='Bên mời thầu', tracking=True)

    date_received = fields.Date(string='Ngày nhận HSMT')
    date_due = fields.Date(string='Hạn nộp', tracking=True)
    date_submitted = fields.Date(string='Ngày nộp', readonly=True, copy=False)

    currency_id = fields.Many2one(
        'res.currency', string='Đồng tiền', required=True,
        default=lambda s: s.env.company.currency_id)
    company_id = fields.Many2one(
        'res.company', string='Công ty',
        default=lambda s: s.env.company, index=True)

    structure_ids = fields.One2many(
        'rp.bid.structure', 'bid_id', string='Hạng mục nhà thầu')
    structure_count = fields.Integer(compute='_compute_counts')
    line_count = fields.Integer(compute='_compute_counts')

    # BoQ của cả hồ sơ, không phải của riêng một hạng mục. Đi được vì
    # `rp.bid.boq.line.bid_id` là related STORE nên có cột thật để làm
    # khoá ngược. Nhờ vậy màn hình BoQ mở thẳng 163 dòng thay vì bắt mở
    # từng hạng mục một.
    line_ids = fields.One2many(
        'rp.bid.boq.line', 'bid_id', string='BoQ nhà thầu')

    item_ids = fields.One2many(
        'rp.bid.item', 'bid_id', string='Dòng chào giá')
    item_count = fields.Integer(compute='_compute_counts')

    unallocated_cost = fields.Monetary(
        string='Chi phí chưa có dòng chào', currency_field='currency_id',
        compute='_compute_unallocated', store=True,
        help='Chi phí trực tiếp của các hạng mục CHƯA gắn dòng chào giá '
             'nào. Tiền này vẫn nằm trong giá dự thầu nhưng không có ô '
             'nào trong file khách để ghi — nếu không xử lý thì hoặc mất '
             'trắng, hoặc phải nhét ẩn vào đơn giá dòng khác.')
    unallocated_pct = fields.Float(
        string='% chưa có dòng chào', digits=(5, 2),
        compute='_compute_unallocated', store=True)
    spread_cost = fields.Monetary(
        string='Chi phí rải đều', currency_field='currency_id',
        compute='_compute_unallocated', store=True,
        help='Chi phí của hạng mục chọn "Rải đều" — chia về mọi dòng chào '
             'theo tỷ trọng, thay vì dồn vào một dòng.')
    outside_cost = fields.Monetary(
        string='Chi phí ngoài giá chào', currency_field='currency_id',
        compute='_compute_unallocated', store=True,
        help='Hạng mục đánh dấu claim riêng. KHÔNG nằm trong bảng chào giá, '
             'nhưng vẫn nằm trong chi phí để biết giá thành thật.')
    offer_total = fields.Monetary(
        string='Tổng phải chào', currency_field='currency_id',
        compute='_compute_unallocated', store=True,
        help='Giá dự thầu trừ phần đánh dấu ngoài giá chào. Đây là con số '
             'mà tổng bảng chào giá phải khớp.')
    offer_gap = fields.Monetary(
        string='Chênh bảng chào', currency_field='currency_id',
        compute='_compute_unallocated', store=True,
        help='Tổng phải chào trừ tổng bảng chào giá. Khác 0 nghĩa là còn '
             'chi phí chưa có chỗ đứng trong hồ sơ nộp đi.')
    offer_balanced = fields.Boolean(
        string='Bảng chào đã khớp', compute='_compute_unallocated',
        store=True)

    # ------------------------------------------------------------------
    # Markup — 5 tầng theo dự toán Việt Nam
    # ------------------------------------------------------------------
    overhead_pct = fields.Float(
        string='Chi phí chung %', default=6.5, tracking=True)
    temp_facility_pct = fields.Float(
        string='Nhà tạm %', default=0.95, tracking=True,
        help='Chi phí nhà tạm để ở và điều hành thi công. Tầng này hay bị '
             'bỏ sót vì nhiều mẫu dự toán gộp vào chi phí chung.')
    undefined_work_pct = fields.Float(
        string='CV không xác định KL %', default=2.5, tracking=True,
        help='Chi phí một số công việc không xác định được khối lượng.')
    profit_pct = fields.Float(
        string='TNCTT %', default=5.5, tracking=True,
        help='Thu nhập chịu thuế tính trước — đây là chỗ quyết định biên '
             'lợi nhuận của gói thầu.')
    vat_pct = fields.Float(string='Thuế GTGT %', default=10.0, tracking=True)
    contingency_pct = fields.Float(
        string='Dự phòng %', default=0.0, tracking=True)

    # ------------------------------------------------------------------
    # Kết quả tính giá
    # ------------------------------------------------------------------
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
        string='Chi phí trực tiếp (T)', currency_field='currency_id',
        compute='_compute_amounts', store=True)

    overhead_amount = fields.Monetary(
        string='Chi phí chung (C)', currency_field='currency_id',
        compute='_compute_amounts', store=True)
    temp_facility_amount = fields.Monetary(
        string='Nhà tạm (LT)', currency_field='currency_id',
        compute='_compute_amounts', store=True)
    undefined_work_amount = fields.Monetary(
        string='CV không xác định KL (TT)', currency_field='currency_id',
        compute='_compute_amounts', store=True)
    indirect_cost = fields.Monetary(
        string='Chi phí gián tiếp (GT)', currency_field='currency_id',
        compute='_compute_amounts', store=True)

    profit_amount = fields.Monetary(
        string='TNCTT (TL)', currency_field='currency_id',
        compute='_compute_amounts', store=True)
    pre_tax_total = fields.Monetary(
        string='Trước thuế (G)', currency_field='currency_id',
        compute='_compute_amounts', store=True)
    vat_amount = fields.Monetary(
        string='Thuế GTGT', currency_field='currency_id',
        compute='_compute_amounts', store=True)
    contingency_amount = fields.Monetary(
        string='Dự phòng', currency_field='currency_id',
        compute='_compute_amounts', store=True)
    bid_total = fields.Monetary(
        string='GIÁ DỰ THẦU', currency_field='currency_id',
        compute='_compute_amounts', store=True, tracking=True)

    # Phần bên mời thầu tự cấp — theo dõi nhưng KHÔNG vào giá chào.
    client_supplied_cost = fields.Monetary(
        string='Vật tư bên mời cấp', currency_field='currency_id',
        compute='_compute_amounts', store=True,
        help='Giá trị vật tư do bên mời thầu cấp, KHÔNG tính vào giá chào. '
             'Bỏ sót việc loại phần này ra là cách phổ biến nhất để chào '
             'cao gấp nhiều lần mà không hiểu vì sao trượt.')

    max_approved_price = fields.Monetary(
        related='package_id.max_approved_price', string='Giá trần gói thầu',
        currency_field='currency_id',
        help='Lấy từ gói thầu. Gói không công bố giá trần thì để 0 và hệ '
             'thống không cảnh báo vượt trần.')
    price_gap = fields.Monetary(
        string='So với giá trần', currency_field='currency_id',
        compute='_compute_amounts', store=True,
        help='Giá trần trừ giá dự thầu. Âm là vượt trần.')

    state = fields.Selection(
        BID_STATES, string='Trạng thái', default='draft', required=True,
        tracking=True, copy=False)
    note = fields.Text(string='Ghi chú')
    active = fields.Boolean(default=True)

    _uniq_code = models.Constraint(
        'unique(code, company_id)', 'Mã hồ sơ dự thầu đã tồn tại.')

    # ==================================================================
    @api.depends('structure_ids.cost_material', 'structure_ids.cost_labor',
                 'structure_ids.cost_machine',
                 'structure_ids.client_supplied_cost',
                 'overhead_pct', 'temp_facility_pct', 'undefined_work_pct',
                 'profit_pct', 'vat_pct', 'contingency_pct',
                 'package_id.max_approved_price')
    def _compute_amounts(self):
        for bid in self:
            # Hạng mục phẳng một cấp nên cộng thẳng, không phải lọc gốc.
            structs = bid.structure_ids
            bid.cost_material = sum(structs.mapped('cost_material'))
            bid.cost_labor = sum(structs.mapped('cost_labor'))
            bid.cost_machine = sum(structs.mapped('cost_machine'))
            bid.client_supplied_cost = sum(
                structs.mapped('client_supplied_cost'))

            t = bid.cost_material + bid.cost_labor + bid.cost_machine
            bid.direct_cost = t
            bid.overhead_amount = t * (bid.overhead_pct or 0.0) / 100.0
            bid.temp_facility_amount = t * (bid.temp_facility_pct or 0.0) / 100.0
            bid.undefined_work_amount = (
                t * (bid.undefined_work_pct or 0.0) / 100.0)
            gt = (bid.overhead_amount + bid.temp_facility_amount
                  + bid.undefined_work_amount)
            bid.indirect_cost = gt
            bid.profit_amount = (t + gt) * (bid.profit_pct or 0.0) / 100.0
            g = t + gt + bid.profit_amount
            bid.pre_tax_total = g
            bid.vat_amount = g * (bid.vat_pct or 0.0) / 100.0
            gxd = g + bid.vat_amount
            bid.contingency_amount = gxd * (bid.contingency_pct or 0.0) / 100.0
            bid.bid_total = gxd + bid.contingency_amount
            bid.price_gap = (bid.max_approved_price or 0.0) - bid.bid_total

    @api.depends('structure_ids', 'structure_ids.line_ids', 'item_ids')
    def _compute_counts(self):
        for bid in self:
            bid.structure_count = len(bid.structure_ids)
            bid.line_count = len(bid.structure_ids.mapped('line_ids'))
            bid.item_count = len(bid.item_ids)

    @api.depends('structure_ids.direct_cost', 'structure_ids.item_id',
                 'structure_ids.allocation_mode',
                 'item_ids.amount_offer', 'direct_cost', 'bid_total')
    def _compute_unallocated(self):
        """Đối soát giữa GIÁ DỰ THẦU và BẢNG CHÀO GIÁ.

        Hai con số này phải bằng nhau, nhưng chúng đi hai đường khác nhau:
        giá dự thầu cộng lên từ hạng mục CỦA TA, bảng chào giá thì phải
        rót vào các dòng CỦA BÊN MỜI THẦU. Hạng mục nào không có dòng nào
        để rót vào thì tiền đó rơi ra ngoài — trong bộ dữ liệu thật là
        7,13%, tức 2,27 tỷ sau markup.

        Ba cách xử một hạng mục, khai ở `allocation_mode`:

          item     gắn vào một dòng chào (mặc định)
          spread   rải đều về mọi dòng theo tỷ trọng chi phí
          outside  ngoài giá chào — claim riêng, không nộp trong bảng

        CHỈ mode `item` mà bỏ trống dòng chào mới tính là CHƯA XỬ LÝ. Hai
        mode kia là quyết định đã ra, không phải việc còn tồn.
        """
        for bid in self:
            structs = bid.structure_ids
            orphan = structs.filtered(
                lambda s: s.allocation_mode == 'item' and not s.item_id)
            bid.unallocated_cost = sum(orphan.mapped('direct_cost'))
            bid.unallocated_pct = (
                bid.unallocated_cost / bid.direct_cost * 100.0
                if bid.direct_cost else 0.0)
            bid.spread_cost = sum(structs.filtered(
                lambda s: s.allocation_mode == 'spread').mapped('direct_cost'))
            bid.outside_cost = sum(structs.filtered(
                lambda s: s.allocation_mode == 'outside').mapped('direct_cost'))

            # Markup rót đều theo chi phí trực tiếp, nên phần "ngoài giá
            # chào" cũng rút ra theo đúng tỷ lệ đó.
            base = (bid.direct_cost or 0.0) - bid.outside_cost
            bid.offer_total = (
                (bid.bid_total or 0.0) * base / bid.direct_cost
                if bid.direct_cost else 0.0)
            bid.offer_gap = bid.offer_total - sum(
                bid.item_ids.mapped('amount_offer'))
            # Dung sai = số dòng chào. Mỗi dòng là Monetary nên làm tròn
            # tối đa 1 đồng; cộng 18 dòng lệch 18 đồng là chuyện làm tròn,
            # không phải chi phí bỏ quên. Để dung sai 0 thì cờ này không
            # bao giờ xanh và người dùng sẽ học cách phớt lờ nó.
            bid.offer_balanced = abs(bid.offer_gap) <= max(
                1.0, len(bid.item_ids))

    def action_open_unallocated(self):
        """Mở đúng các hạng mục còn treo, không bắt tự lọc."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Chi phí chưa có dòng chào — %s', self.name),
            'res_model': 'rp.bid.structure',
            'view_mode': 'list,form',
            'domain': [('bid_id', '=', self.id),
                       ('allocation_mode', '=', 'item'),
                       ('item_id', '=', False)],
            'context': {'default_bid_id': self.id},
        }

    def action_open_items(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Dòng chào giá — %s', self.name),
            'res_model': 'rp.bid.item',
            'view_mode': 'list,form',
            'domain': [('bid_id', '=', self.id)],
            'context': {'default_bid_id': self.id},
        }

    # ==================================================================
    @api.onchange('package_id')
    def _onchange_package_sets_project(self):
        """Chọn gói thầu thì kéo theo mọi thứ đã khai ở gói.

        Dự án, bên mời thầu, ngày nhận HSMT và hạn nộp đều là thuộc tính
        của LỜI MỜI, đã khai một lần ở gói thầu. Bắt người dùng gõ lại
        trên hồ sơ vừa thừa vừa dễ lệch — hai chỗ hai ngày hạn nộp thì
        không biết tin chỗ nào.

        Chỉ điền vào ô đang TRỐNG: hồ sơ có thể cố ý ghi ngày khác gói
        (ví dụ bên mời gia hạn riêng cho mình), sửa đè là mất.
        """
        if not self.package_id:
            return
        pkg = self.package_id
        if pkg.project_id != self.project_id:
            self.project_id = pkg.project_id
        if not self.invited_by_id:
            self.invited_by_id = pkg.invited_by_id
        if not self.date_received:
            self.date_received = pkg.date_received
        if not self.date_due:
            self.date_due = pkg.date_due

    @api.constrains('date_received', 'date_due')
    def _check_dates(self):
        """Hạn nộp không thể sớm hơn ngày nhận hồ sơ mời thầu.

        Ràng buộc này đã có ở gói thầu; hồ sơ dự thầu mang hai ngày
        tương tự mà lại không kiểm, nên gõ ngược vẫn lưu được.
        """
        for bid in self:
            if bid.date_received and bid.date_due \
                    and bid.date_due < bid.date_received:
                raise ValidationError(_(
                    'Hạn nộp (%(due)s) sớm hơn ngày nhận HSMT (%(rec)s) — '
                    'kiểm tra lại ngày.',
                    due=bid.date_due, rec=bid.date_received))

    @api.onchange('project_id')
    def _onchange_project_clears_package(self):
        if self.package_id and self.package_id.project_id != self.project_id:
            self.package_id = False

    @api.constrains('project_id', 'package_id')
    def _check_package_in_project(self):
        for bid in self:
            if bid.package_id.project_id != bid.project_id:
                raise UserError(_(
                    'Gói thầu "%(p)s" thuộc dự án khác. Hồ sơ dự thầu phải '
                    'nằm trong đúng dự án của gói thầu.',
                    p=bid.package_id.display_name))

    def action_open_package(self):
        """Mở gói thầu — thứ nhà thầu bám vào để làm giá."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Gói thầu'),
            'res_model': 'rp.bid.package',
            'res_id': self.package_id.id,
            'view_mode': 'form',
        }

    def action_pricing(self):
        self.write({'state': 'pricing'})

    def action_submit(self):
        for bid in self:
            if not bid.structure_ids:
                raise UserError(_(
                    'Chưa có hạng mục nào — không nộp được hồ sơ rỗng.'))
            if not bid.bid_total:
                raise UserError(_(
                    'Giá dự thầu đang bằng 0. Kiểm tra lại BoQ trước khi nộp.'))
            bid.write({'state': 'submitted',
                       'date_submitted': fields.Date.context_today(bid)})

    def action_won(self):
        self.write({'state': 'won'})

    def action_lost(self):
        self.write({'state': 'lost'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_reset_to_draft(self):
        self.write({'state': 'draft', 'date_submitted': False})

    # ==================================================================
    # Chia hạng mục
    # ==================================================================
    def action_split_from_items(self):
        """Chia hạng mục từ BẢNG CHÀO GIÁ (BoQ của CĐT / tổng thầu).

        Đây là cách chia đúng nhất với thực tế, vì nó bám vào TÀI LIỆU
        NHÀ THẦU THỰC SỰ NHẬN ĐƯỢC. Ba lý do:

        1. **Không phụ thuộc CĐT có khai dòng gói thầu hay không.**
           `rp.tender.package.line` là cách chủ đầu tư chia việc trong nội
           bộ họ — nhà thầu thường không có, và trong dữ liệu thật thì 4
           trên 14 gói thầu không có dòng nào.
        2. **File mời thầu đã tự chia nhóm sẵn.** Dòng tiêu đề A, B, C, D
           chính là cách bên mời thầu gom việc; lấy đúng bộ khung đó thì
           hồ sơ nộp lại khớp khuôn của họ.
        3. **Gắn luôn dòng chào giá.** Mỗi hạng mục sinh ra từ một dòng
           chào nên `item_id` được nối ngay — bỏ hẳn bước map tay vốn là
           chỗ tốn công và dễ sót nhất.

        Dòng KHÔNG có khối lượng thì bỏ qua: trong phiếu mời thật, đó là
        các dòng liệt kê vật tư bên mời thầu tự cấp (cốt thép, bê tông,
        ống siêu âm…) — không phải phần việc ta chào.
        """
        Struct = self.env['rp.bid.structure']
        created = skipped = 0
        for bid in self:
            if not bid.item_ids:
                raise UserError(_(
                    'Chưa có bảng chào giá. Bấm "Nhập BoQ mời thầu (Excel)" '
                    'để đọc file của bên mời thầu trước đã.'))
            taken_items = bid.structure_ids.mapped('item_id').ids
            taken_names = set(bid.structure_ids.mapped('name'))
            section, seq = '', 0
            for item in bid.item_ids.sorted('sequence'):
                if item.is_section:
                    # Dòng nhóm A/B/C/D KHÔNG thành hạng mục — nó chỉ là
                    # nhãn gom của bảng mời thầu, và bảng đó vẫn giữ
                    # nguyên. Lấy mã nhóm làm tiền tố để hạng mục vẫn sắp
                    # đúng thứ tự của khách.
                    section = item.code or ''
                    continue
                if item.id in taken_items:
                    continue
                if not item.quantity_client:
                    skipped += 1
                    continue
                seq += 10
                Struct.create({
                    'bid_id': bid.id,
                    'code': '%s%s' % (section, item.code or ''),
                    'name': item.name[:120],
                    'sequence': seq,
                    'item_id': item.id,
                })
                created += 1
        msg = _('Đã chia %s hạng mục từ bảng chào giá.', created)
        if skipped:
            msg += _(' Bỏ qua %s dòng không có khối lượng (thường là vật '
                     'tư bên mời thầu tự cấp).', skipped)
        return self._notify(msg)

    # KHÔNG CÓ `action_split_from_package`.
    #
    # Nó từng chia hạng mục từ các dòng của `rp.tender.package` — bảng
    # khối lượng nằm trong sổ của BÊN MỜI THẦU. Bỏ cùng lúc với việc
    # chuyển gói thầu về cho nhà thầu tự quản: gói thầu của nhà thầu chỉ
    # ghi thông tin lời mời, còn bảng khối lượng về dưới dạng file Excel
    # và được nạp vào Bảng giá chào. Chia hạng mục đi từ đó —
    # `action_split_from_items`.

    @api.model
    def _notify(self, message):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'message': message, 'type': 'success', 'sticky': False},
        }

    def action_open_structures(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Hạng mục nhà thầu — %s', self.name),
            'res_model': 'rp.bid.structure',
            'view_mode': 'list,form',
            'domain': [('bid_id', '=', self.id)],
            'context': {'default_bid_id': self.id},
        }

    def action_open_lines(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('BoQ nhà thầu — %s', self.name),
            'res_model': 'rp.bid.boq.line',
            'view_mode': 'list,form',
            'domain': [('bid_id', '=', self.id)],
            'context': {'default_bid_id': self.id,
                        'search_default_group_structure': 1},
        }
