# -*- coding: utf-8 -*-
"""Sổ phát sinh (Variation) — thay đổi phạm vi và tác động tới ngân sách.

Câu hỏi của chủ đầu tư luôn là: "nhà thầu phát sinh khối lượng so với
hợp đồng thì ngân sách dự án ra sao". Trả lời được câu đó cần bốn thứ
đi cùng nhau, mà bảng tính thì rời rạc:

* **Nguồn gốc**: ai khởi xướng — chủ đầu tư chỉ thị, hay yêu cầu nhà
  thầu báo giá, hay nhà thầu tự đề xuất (value engineering), hay do
  thay đổi pháp luật. Mỗi nguồn gốc kéo theo quyền và nghĩa vụ khác
  nhau.
* **Đồng hồ 14 ngày** của điều 13: nhà thầu phải báo giá trong 14 ngày
  kể từ khi được yêu cầu, và chỉ có 14 ngày để phản đối một chỉ thị
  (vì bốn lý do hợp đồng cho phép). Quá hạn là mất quyền.
* **Căn cứ giá**: điều 13.3 buộc dùng ĐƠN GIÁ TRONG HỢP ĐỒNG (Schedule
  of Rates) khi có; không có mới tính theo chi phí + lợi nhuận hợp lý.
  Ghi rõ căn cứ từng dòng thì lúc đàm phán mới cãi được.
* **Đi tới đâu**: phát sinh được duyệt phải ra phụ lục điều chỉnh giá
  hợp đồng, và phải cộng vào dự báo chi phí cuối kỳ của dự án — không
  thì sổ phát sinh chỉ là danh sách cho vui.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

APPROVED = ('approved', 'instructed', 'applied')
OPEN = ('draft', 'requested', 'quoted', 'review')


class RpVariation(models.Model):
    _name = 'rp.variation'
    _description = 'Phát sinh / thay đổi hợp đồng (Variation)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_event desc, id desc'

    name = fields.Char(string='Nội dung phát sinh', required=True,
                       tracking=True)
    code = fields.Char(string='Mã', copy=False, readonly=True, index=True)
    contract_id = fields.Many2one(
        'rp.contract', string='Hợp đồng', required=True, index=True,
        ondelete='cascade', tracking=True)
    project_id = fields.Many2one(
        're.project', string='Dự án', related='contract_id.project_id',
        store=True, index=True)
    partner_id = fields.Many2one(
        'res.partner', string='Nhà thầu',
        related='contract_id.contractor_id', store=True)
    currency_id = fields.Many2one(
        'res.currency', related='contract_id.currency_id', store=True)

    origin = fields.Selection(
        [('instruction', 'Chủ đầu tư chỉ thị thực hiện'),
         ('proposal_request', 'Chủ đầu tư yêu cầu nhà thầu báo giá'),
         ('value_engineering', 'Nhà thầu đề xuất (value engineering)'),
         ('law_change', 'Thay đổi pháp luật'),
         ('daywork', 'Làm theo ngày công (daywork)')],
        string='Nguồn gốc', required=True, default='proposal_request',
        tracking=True)
    cause = fields.Selection(
        [('design_change', 'Thay đổi thiết kế'),
         ('scope_add', 'Bổ sung phạm vi'),
         ('quantity', 'Sai lệch khối lượng so với hợp đồng'),
         ('site_condition', 'Điều kiện hiện trường khác dự kiến'),
         ('employer_request', 'Yêu cầu của chủ đầu tư'),
         ('error', 'Sai sót hồ sơ'),
         ('statutory', 'Yêu cầu của cơ quan quản lý'),
         ('other', 'Khác')],
        string='Nguyên nhân', default='quantity', tracking=True)
    description = fields.Html(string='Mô tả & căn cứ')
    task_ids = fields.Many2many('project.task', string='Công việc liên quan')

    # --- Đồng hồ điều 13 ---------------------------------------------
    date_event = fields.Date(
        string='Ngày phát sinh', required=True, tracking=True,
        default=fields.Date.context_today)
    date_request = fields.Date(
        string='Ngày yêu cầu báo giá', tracking=True,
        help='Ngày chủ đầu tư/Engineer yêu cầu nhà thầu nộp đề xuất.')
    quote_days = fields.Integer(
        string='Hạn báo giá (ngày)', default=14,
        help='Điều 13.3: nhà thầu phải trả lời trong 14 ngày.')
    quote_due_date = fields.Date(
        string='Hạn chót báo giá', compute='_compute_clocks', store=True)
    date_quote = fields.Date(string='Ngày nhận báo giá', tracking=True)
    quote_late_days = fields.Integer(
        string='Báo giá trễ (ngày)', compute='_compute_clocks', store=True)
    quote_on_time = fields.Boolean(
        string='Báo giá đúng hạn', compute='_compute_clocks', store=True)

    date_instruction = fields.Date(string='Ngày chỉ thị', tracking=True)
    objection_due_date = fields.Date(
        string='Hạn phản đối chỉ thị', compute='_compute_clocks', store=True,
        help='Điều 13.1: nhà thầu có 14 ngày để phản đối, chỉ với bốn lý '
             'do hợp đồng cho phép.')
    objection_date = fields.Date(string='Ngày nhà thầu phản đối',
                                 tracking=True)
    objection_ground = fields.Selection(
        [('goods', 'Không mua được vật tư/thiết bị cần thiết'),
         ('safety', 'Giảm an toàn hoặc tính phù hợp của công trình'),
         ('guarantee', 'Ảnh hưởng cam kết hiệu suất'),
         ('technical', 'Không khả thi về kỹ thuật')],
        string='Lý do phản đối', tracking=True)

    # --- Tiền và thời gian --------------------------------------------
    pricing_basis = fields.Selection(
        [('schedule_rates', 'Đơn giá trong hợp đồng (Schedule of Rates)'),
         ('cost_plus', 'Chi phí + lợi nhuận hợp lý'),
         ('lumpsum', 'Khoán gọn thoả thuận'),
         ('daywork', 'Theo ngày công')],
        string='Căn cứ giá', default='schedule_rates', required=True,
        tracking=True,
        help='Điều 13.3: có đơn giá trong hợp đồng thì PHẢI dùng; không '
             'có mới tính theo chi phí cộng lợi nhuận hợp lý.')
    line_ids = fields.One2many('rp.variation.line', 'variation_id',
                               string='Chi tiết khối lượng')
    amount_lines = fields.Monetary(
        string='Giá trị theo chi tiết', compute='_compute_amounts',
        store=True)
    amount_quoted = fields.Monetary(string='Giá nhà thầu đề xuất',
                                    tracking=True)
    amount_approved = fields.Monetary(string='Giá được duyệt', tracking=True)
    eot_days_claimed = fields.Integer(string='Số ngày xin gia hạn')
    eot_days_granted = fields.Integer(string='Số ngày được gia hạn',
                                      tracking=True)

    state = fields.Selection(
        [('draft', 'Nháp'),
         ('requested', 'Đã yêu cầu báo giá'),
         ('quoted', 'Nhà thầu đã báo giá'),
         ('review', 'Đang thẩm định'),
         ('approved', 'Đã duyệt giá'),
         ('instructed', 'Đã chỉ thị thực hiện'),
         ('applied', 'Đã vào giá hợp đồng'),
         ('rejected', 'Từ chối'),
         ('cancelled', 'Huỷ')],
        string='Trạng thái', default='draft', required=True, tracking=True,
        index=True)
    amendment_id = fields.Many2one(
        'rp.contract.amendment', string='Phụ lục điều chỉnh giá',
        readonly=True, copy=False)
    claim_id = fields.Many2one(
        'rp.claim', string='Khiếu nại gia hạn kèm theo', readonly=True,
        copy=False)

    # ------------------------------------------------------------------
    @api.depends('date_request', 'quote_days', 'date_quote',
                 'date_instruction')
    def _compute_clocks(self):
        for rec in self:
            rec.quote_due_date = (
                fields.Date.add(rec.date_request, days=rec.quote_days)
                if rec.date_request and rec.quote_days else False)
            if rec.date_quote and rec.quote_due_date:
                late = (rec.date_quote - rec.quote_due_date).days
                rec.quote_late_days = max(late, 0)
                rec.quote_on_time = late <= 0
            else:
                rec.quote_late_days = 0
                rec.quote_on_time = False
            rec.objection_due_date = (
                fields.Date.add(rec.date_instruction, days=14)
                if rec.date_instruction else False)

    @api.depends('line_ids.amount')
    def _compute_amounts(self):
        for rec in self:
            rec.amount_lines = sum(rec.line_ids.mapped('amount'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code'):
                vals['code'] = self.env['ir.sequence'].next_by_code(
                    'rp.variation') or '/'
        return super().create(vals_list)

    @api.depends('name', 'code')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = (f'[{rec.code}] {rec.name}'
                                if rec.code else rec.name or '')

    @api.onchange('line_ids')
    def _onchange_lines_fill_quote(self):
        if self.amount_lines and not self.amount_quoted:
            self.amount_quoted = self.amount_lines

    # ------------------------------------------------------------------
    # Quy trình
    # ------------------------------------------------------------------
    def action_request_quote(self):
        for rec in self:
            rec.write({'state': 'requested',
                       'date_request': rec.date_request
                       or fields.Date.context_today(rec)})

    def action_receive_quote(self):
        for rec in self:
            rec.write({'state': 'quoted',
                       'date_quote': rec.date_quote
                       or fields.Date.context_today(rec),
                       'amount_quoted': rec.amount_quoted or rec.amount_lines})
            if not rec.quote_on_time:
                rec.message_post(body=_(
                    'Báo giá nhận ngày %(d)s, quá hạn %(n)s ngày so với hạn '
                    'chót %(h)s theo điều 13.3.',
                    d=rec.date_quote, n=rec.quote_late_days,
                    h=rec.quote_due_date))

    def action_review(self):
        self.write({'state': 'review'})

    def action_approve(self):
        for rec in self:
            if not rec.amount_approved:
                rec.amount_approved = rec.amount_quoted or rec.amount_lines
            rec.state = 'approved'

    def action_instruct(self):
        for rec in self:
            rec.write({'state': 'instructed',
                       'date_instruction': rec.date_instruction
                       or fields.Date.context_today(rec)})

    def action_reject(self):
        self.write({'state': 'rejected', 'amount_approved': 0,
                    'eot_days_granted': 0})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_reset(self):
        self.write({'state': 'draft'})

    def action_apply_to_contract(self):
        """Ra phụ lục điều chỉnh giá — phát sinh chỉ có giá trị khi vào HĐ."""
        self.ensure_one()
        if self.state not in ('approved', 'instructed'):
            raise UserError(_('Chỉ đưa vào hợp đồng khi phát sinh đã được '
                              'duyệt giá.'))
        if self.amendment_id:
            raise UserError(_('Phát sinh này đã có phụ lục %s.',
                              self.amendment_id.name))
        if not self.amount_approved:
            raise UserError(_('Chưa có giá được duyệt.'))
        contract = self.contract_id
        new_value = contract.contract_value_pretax + self.amount_approved
        am = self.env['rp.contract.amendment'].create({
            'name': _('Điều chỉnh giá theo phát sinh %s', self.code),
            'contract_id': contract.id,
            'amendment_type': 'value',
            'description': self.name,
            'new_contract_value_pretax': new_value,
        })
        old_value = contract.contract_value_pretax
        # Áp luôn phụ lục: nút này mang nghĩa "đưa vào giá hợp đồng", mà
        # để phụ lục ở trạng thái nháp thì giá hợp đồng chưa đổi — con số
        # "đã cam kết" của dự án sẽ thiếu đúng bằng khoản phát sinh.
        am.action_apply()
        self.write({'amendment_id': am.id, 'state': 'applied'})
        self.message_post(body=_(
            'Đã lập và áp phụ lục điều chỉnh giá: %(o)s → %(n)s.',
            o='{:,.0f}'.format(old_value),
            n='{:,.0f}'.format(new_value)))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'rp.contract.amendment',
            'res_id': am.id,
            'views': [[False, 'form']],
            'target': 'new',
        }

    def action_create_eot_claim(self):
        """Phát sinh có kéo dài thời gian thì mở hồ sơ khiếu nại gia hạn."""
        self.ensure_one()
        if not self.eot_days_claimed:
            raise UserError(_('Phát sinh này không xin gia hạn ngày nào.'))
        if self.claim_id:
            raise UserError(_('Đã có khiếu nại %s.', self.claim_id.code))
        claim = self.env['rp.claim'].create({
            'name': _('Gia hạn do phát sinh %(c)s — %(n)s',
                      c=self.code, n=self.name),
            'contract_id': self.contract_id.id,
            'direction': 'from_contractor',
            'claim_type': 'eot',
            'cause': 'design_change',
            'date_event': self.date_event,
            'eot_days_claimed': self.eot_days_claimed,
            'task_ids': [(6, 0, self.task_ids.ids)],
        })
        self.claim_id = claim
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'rp.claim',
            'res_id': claim.id,
            'views': [[False, 'form']],
        }


class RpVariationLine(models.Model):
    _name = 'rp.variation.line'
    _description = 'Chi tiết khối lượng phát sinh'
    _order = 'sequence, id'

    variation_id = fields.Many2one(
        'rp.variation', string='Phát sinh', required=True,
        ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    name = fields.Char(string='Hạng mục công việc', required=True)
    cost_category_id = fields.Many2one(
        'rp.cost.category', string='Khoản mục chi phí',
        help='Để biết phát sinh đội vào khoản mục nào của dự toán.')
    uom_name = fields.Char(string='Đơn vị')
    quantity = fields.Float(string='Khối lượng', default=1.0)
    unit_price = fields.Monetary(string='Đơn giá')
    amount = fields.Monetary(string='Thành tiền', compute='_compute_amount',
                             store=True)
    from_rates = fields.Boolean(
        string='Lấy từ đơn giá hợp đồng', default=True,
        help='Đơn giá này có trong Schedule of Rates của hợp đồng hay '
             'không. Không có thì phải chứng minh chi phí + lợi nhuận.')
    currency_id = fields.Many2one(
        'res.currency', related='variation_id.currency_id', store=True)

    @api.depends('quantity', 'unit_price')
    def _compute_amount(self):
        for rec in self:
            rec.amount = rec.quantity * rec.unit_price
