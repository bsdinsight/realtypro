# -*- coding: utf-8 -*-
"""Dự án và Gói thầu — SỔ CỦA NHÀ THẦU, không phải của bên mời thầu.

VÌ SAO PHẢI CÓ BẢNG RIÊNG THAY VÌ DÙNG `re.project` / `rp.tender.package`
=========================================================================

Hai bảng kia là sổ của **chủ đầu tư / tổng thầu**: dự án họ làm chủ, gói
thầu họ đứng ra mời. Cụm Dự thầu lại là ứng dụng cho **nhà thầu đi dự** —
và nhà thầu không sở hữu dự án nào trong đó cả. Bắt họ chọn dự án từ danh
sách của bên mời thầu là sai ở ba mức:

* **Sai dữ liệu.** Nhà thầu dự thầu cho hàng chục chủ đầu tư khác nhau.
  Dự án của khách A chỉ tồn tại trong hệ thống nếu chính khách A cũng
  đang dùng RealtyPro — điều gần như không bao giờ đúng.
* **Sai quyền.** `re.project` mở ra toàn bộ ngân sách, hợp đồng, dòng
  tiền của bên mời thầu. Nhà thầu không được thấy những thứ đó.
* **Sai vòng đời.** Dự án bên mời thầu sống từ lúc lập chủ trương tới
  lúc bàn giao. Với nhà thầu, "dự án" chỉ là **một cơ hội**: biết tên,
  biết chủ đầu tư, biết địa điểm, và biết mình đang theo mấy gói.

Nên hai bảng này ghi đúng thứ nhà thầu tự nhập và tự quản:

    rp.bid.project   Dự án đang theo   (khách nào, ở đâu, theo mấy gói)
     └─ rp.bid.package  Gói thầu được mời (mã gói, hạn nộp, giá trần nếu công bố)
          └─ rp.bid       Hồ sơ dự thầu

CÒN KHI NHÀ THẦU TRÚNG VÀ BẮT ĐẦU THI CÔNG thì mới cần một dự án thật để
chạy tiến độ, nghiệm thu, thanh toán. Đó là `exec_project_id` — để trống
cho tới lúc đó, và chỉ điền khi bấm "Chuyển sang dự án thi công".
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class RpBidProject(models.Model):
    _name = 'rp.bid.project'
    _description = 'Dự án đang theo (nhà thầu)'
    _inherit = ['mail.thread']
    _order = 'sequence, code, id'

    name = fields.Char(string='Tên dự án', required=True, tracking=True)
    code = fields.Char(string='Mã dự án', tracking=True, copy=False)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    owner_id = fields.Many2one(
        'res.partner', string='Chủ đầu tư / Tổng thầu', tracking=True,
        help='Bên làm chủ dự án này. Nhà thầu tự nhập — đây là khách hàng '
             'của mình, không phải một bản ghi dự án trong hệ thống họ.')
    location = fields.Char(string='Địa điểm')
    scale = fields.Char(
        string='Quy mô',
        help='Ghi ngắn để nhận ra dự án: số tầng, diện tích sàn, số cọc…')
    note = fields.Text(string='Ghi chú')

    # Dự án thi công thật, chỉ có sau khi trúng thầu.
    exec_project_id = fields.Many2one(
        're.project', string='Dự án thi công', ondelete='set null',
        copy=False,
        help='Để trống tới khi trúng thầu. Nút "Chuyển sang dự án thi '
             'công" trên hồ sơ sẽ tạo/điền vào đây, rồi đổ hạng mục và '
             'BoQ sang để chạy tiến độ — nghiệm thu — thanh toán.')

    package_ids = fields.One2many(
        'rp.bid.package', 'project_id', string='Gói thầu được mời')
    bid_ids = fields.One2many('rp.bid', 'project_id', string='Hồ sơ dự thầu')

    package_count = fields.Integer(compute='_compute_counts')
    bid_count = fields.Integer(compute='_compute_counts')
    won_count = fields.Integer(compute='_compute_counts')
    currency_id = fields.Many2one(
        'res.currency', default=lambda s: s.env.company.currency_id)
    bid_total = fields.Monetary(
        string='Tổng giá đã chào', currency_field='currency_id',
        compute='_compute_counts',
        help='Cộng giá dự thầu của mọi hồ sơ trong dự án. Để ước lượng '
             'mình đang đặt bao nhiêu tiền chào vào một khách.')

    _uniq_code = models.Constraint(
        'unique(code)', 'Mã dự án đã tồn tại.')

    @api.depends('package_ids', 'bid_ids.state', 'bid_ids.bid_total')
    def _compute_counts(self):
        for rec in self:
            rec.package_count = len(rec.package_ids)
            rec.bid_count = len(rec.bid_ids)
            rec.won_count = len(rec.bid_ids.filtered(
                lambda b: b.state == 'won'))
            rec.bid_total = sum(rec.bid_ids.mapped('bid_total'))

    @api.depends('name', 'code')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = (
                '[%s] %s' % (rec.code, rec.name) if rec.code else rec.name)

    def action_open_packages(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Gói thầu — %s', self.name),
            'res_model': 'rp.bid.package',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }

    def action_open_bids(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Hồ sơ dự thầu — %s', self.name),
            'res_model': 'rp.bid',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }


class RpBidPackage(models.Model):
    _name = 'rp.bid.package'
    _description = 'Gói thầu được mời (nhà thầu)'
    _inherit = ['mail.thread']
    _order = 'project_id, sequence, code, id'

    name = fields.Char(string='Tên gói thầu', required=True, tracking=True)
    code = fields.Char(string='Mã gói', tracking=True, copy=False)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    project_id = fields.Many2one(
        'rp.bid.project', string='Dự án', required=True,
        ondelete='restrict', index=True, tracking=True)
    owner_id = fields.Many2one(
        related='project_id.owner_id', string='Chủ đầu tư / Tổng thầu',
        store=True)
    invited_by_id = fields.Many2one(
        'res.partner', string='Bên mời thầu', tracking=True,
        help='Ai gửi thư mời. Thường là chủ đầu tư, nhưng khi đi thầu phụ '
             'thì là tổng thầu — nên để riêng chứ không ăn theo dự án.')

    scope = fields.Text(
        string='Phạm vi công việc',
        help='Chép nguyên phần mô tả phạm vi trong thư mời / HSMT. Đây là '
             'căn cứ để sau này cãi việc nào trong giá, việc nào ngoài.')
    date_received = fields.Date(string='Ngày nhận HSMT')
    date_due = fields.Date(string='Hạn nộp', tracking=True)

    currency_id = fields.Many2one(
        'res.currency', string='Đồng tiền', required=True,
        default=lambda s: s.env.company.currency_id)
    max_approved_price = fields.Monetary(
        string='Giá trần', currency_field='currency_id', tracking=True,
        help='Chỉ điền khi bên mời thầu có công bố. Nhiều gói không công '
             'bố — để 0 thì hệ thống không cảnh báo vượt trần.')

    state = fields.Selection(
        [('invited', 'Được mời'),
         ('bidding', 'Đang làm hồ sơ'),
         ('submitted', 'Đã nộp'),
         ('won', 'Trúng thầu'),
         ('lost', 'Trượt'),
         ('dropped', 'Bỏ không theo')],
        string='Trạng thái', default='invited', required=True, tracking=True,
        help='Trạng thái theo đuổi gói. Khác trạng thái hồ sơ: bỏ không '
             'theo là quyết định trước khi có hồ sơ nào.')
    note = fields.Text(string='Ghi chú')

    bid_ids = fields.One2many('rp.bid', 'package_id', string='Hồ sơ dự thầu')
    bid_count = fields.Integer(compute='_compute_bid_count')

    _uniq_code = models.Constraint(
        'unique(project_id, code)',
        'Mã gói thầu đã tồn tại trong dự án này.')

    @api.depends('bid_ids')
    def _compute_bid_count(self):
        for rec in self:
            rec.bid_count = len(rec.bid_ids)

    @api.depends('name', 'code')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = (
                '[%s] %s' % (rec.code, rec.name) if rec.code else rec.name)

    def action_create_bid(self):
        """Lập hồ sơ dự thầu cho gói này.

        Tạo rỗng chứ không chia sẵn hạng mục: gói thầu ở đây KHÔNG có
        bảng khối lượng — bảng mời thầu về dưới dạng file Excel và được
        nạp vào Bảng giá chào của hồ sơ. Chia hạng mục là bước sau, từ
        bảng đó.
        """
        self.ensure_one()
        if self.bid_ids:
            return self.action_open_bids()
        bid = self.env['rp.bid'].create({
            'name': _('Chào giá %s', self.name),
            'project_id': self.project_id.id,
            'package_id': self.id,
            'invited_by_id': self.invited_by_id.id,
            'date_received': self.date_received,
            'date_due': self.date_due,
        })
        self.state = 'bidding'
        return {
            'type': 'ir.actions.act_window',
            'name': _('Hồ sơ dự thầu'),
            'res_model': 'rp.bid',
            'res_id': bid.id,
            'view_mode': 'form',
        }

    def action_open_bids(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Hồ sơ dự thầu — %s', self.name),
            'res_model': 'rp.bid',
            'view_mode': 'list,form',
            'domain': [('package_id', '=', self.id)],
            'context': {'default_package_id': self.id,
                        'default_project_id': self.project_id.id},
        }

    @api.constrains('date_received', 'date_due')
    def _check_dates(self):
        for rec in self:
            if rec.date_received and rec.date_due \
                    and rec.date_due < rec.date_received:
                raise UserError(_(
                    'Hạn nộp sớm hơn ngày nhận HSMT — kiểm tra lại ngày.'))
