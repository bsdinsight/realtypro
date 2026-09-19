# -*- coding: utf-8 -*-
"""
Tài sản đảm bảo (collateral) — master.

Tài sản thuộc công ty thành viên (hoặc bên thứ ba) dùng đảm bảo cho khoản vay.
Có nhiều lần định giá; giá trị hiện hành lấy định giá mới nhất. Một tài sản có
thể thế chấp cho nhiều khoản (multi-pledge).
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ReLoanCollateral(models.Model):
    _name = 're.loan.collateral'
    _description = 'Tài sản đảm bảo'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(string='Tên tài sản', required=True, tracking=True)
    code = fields.Char(string='Mã', copy=False)
    type_id = fields.Many2one(
        're.loan.collateral.type', string='Loại tài sản', required=True,
        tracking=True)
    owner_company_id = fields.Many2one(
        'res.company', string='Công ty sở hữu',
        default=lambda self: self.env.company,
        help='Công ty thành viên sở hữu tài sản.')
    owner_partner_id = fields.Many2one(
        'res.partner', string='Chủ sở hữu (bên thứ ba)',
        help='Điền nếu tài sản thuộc bên thứ ba bảo lãnh.')
    legal_info = fields.Text(string='Thông tin pháp lý',
                             help='Sổ đỏ/sổ hồng, đăng ký, số seri...')
    description = fields.Text(string='Mô tả')

    company_id = fields.Many2one(
        'res.company', string='Công ty', required=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', string='Loại tiền', required=True,
        default=lambda self: self.env.company.currency_id)

    valuation_ids = fields.One2many(
        're.loan.collateral.valuation', 'collateral_id', string='Định giá')
    value_current = fields.Monetary(
        string='Giá trị hiện hành', compute='_compute_value_current',
        store=True, help='Lấy theo lần định giá mới nhất.')

    pledge_ids = fields.One2many(
        're.loan.collateral.pledge', 'collateral_id', string='Thế chấp')
    pledge_count = fields.Integer(
        string='Số lần thế chấp', compute='_compute_pledge_count')
    active_pledge_count = fields.Integer(
        string='Số thế chấp đang hiệu lực',
        compute='_compute_pledge_stats', store=True)
    total_secured = fields.Monetary(
        string='Giá trị đã đem thế chấp',
        compute='_compute_pledge_stats', store=True,
        help='Σ giá trị đảm bảo của các thế chấp đang hiệu lực '
             '(qua tất cả HĐTD, các NH).')
    value_available = fields.Monetary(
        string='Giá trị còn lại có thể thế chấp',
        compute='_compute_pledge_stats', store=True,
        help='= Giá trị hiện hành − Đã đem thế chấp. Số tiền tối đa '
             'có thể đem TS này thế chấp thêm cho HĐTD khác (cùng NH '
             'hoặc NH khác).')
    coverage_percent = fields.Float(
        string='% đã thế chấp',
        compute='_compute_pledge_stats', store=True,
        help='= Đã đem thế chấp / Giá trị hiện hành × 100.')

    state = fields.Selection(
        [('available', 'Sẵn sàng — chưa thế chấp'),
         ('partial_pledged', 'Thế chấp 1 phần — còn dư'),
         ('fully_pledged', 'Đã thế chấp hết'),
         ('over_pledged', 'Quá thế chấp (cảnh báo)'),
         ('disposed', 'Đã thanh lý')],
        string='Trạng thái',
        compute='_compute_state', store=True,
        help='Trạng thái phản ánh giá trị còn lại của TS:\n'
             '• Sẵn sàng: chưa thế chấp lần nào\n'
             '• Thế chấp 1 phần: đã có thế chấp, còn giá trị thể thế '
             'chấp thêm — vd BĐS 10 tỷ đã đem 6 tỷ thế chấp BIDV, '
             'còn 4 tỷ có thể thế chấp NH khác\n'
             '• Đã thế chấp hết: Σ đảm bảo ≈ giá trị TS\n'
             '• Quá thế chấp: Σ đảm bảo > giá trị (cảnh báo — sai sót)\n'
             '• Đã thanh lý: TS đã bán, không dùng nữa')

    active = fields.Boolean(default=True)

    # ── Thanh lý ──────────────────────────────────────────────────
    # KHÔNG dùng `active` làm cờ thanh lý. Trước đây trạng thái
    # 'disposed' suy ra từ `active = False`, nhưng `active = False`
    # trong Odoo nghĩa là LƯU TRỮ: bản ghi biến mất khỏi mọi danh sách.
    # Tài sản đã thanh lý thì ngược lại — phải còn nhìn thấy được, vì
    # nó từng bảo đảm cho những khoản vay còn dư nợ và kiểm toán sẽ
    # hỏi tới. Hai khái niệm khác nhau nên tách làm hai trường.
    disposed = fields.Boolean(
        string='Đã thanh lý', readonly=True, copy=False, index=True,
        help='Tài sản đã bán hoặc không còn dùng làm bảo đảm. Vẫn hiển '
             'thị trong danh sách để tra cứu lịch sử.')
    disposal_date = fields.Date(
        string='Ngày thanh lý', readonly=True, copy=False)
    disposal_reason = fields.Char(
        string='Lý do thanh lý', readonly=True, copy=False)

    # ── Hết hạn định giá (việc "Thông báo khi TSDB hết hạn định giá")
    valuation_expiry_date = fields.Date(
        string='Hạn hiệu lực định giá',
        compute='_compute_valuation_expiry', store=True,
        help='Ngày hết hạn của lần định giá MỚI NHẤT.')
    valuation_expired = fields.Boolean(
        string='Định giá hết hạn',
        compute='_compute_valuation_expiry', store=True,
        help='Định giá mới nhất đã quá hạn hiệu lực. Ngân hàng sẽ yêu '
             'cầu định giá lại trước khi cho rút thêm.')

    @api.depends('valuation_ids.date', 'valuation_ids.amount')
    def _compute_value_current(self):
        # Tie-break theo id khi 2 định giá cùng ngày (vd định giá tay +
        # auto theo phải thu cùng ngày) — lấy bản mới nhất. Trong
        # onchange, dòng vừa thêm chưa lưu mang NewId (không so được với
        # id int) và date có thể trống → key phải quy đổi: dòng chưa lưu
        # xếp mới nhất (inf), date trống xếp cũ nhất.
        date_min = fields.Date.to_date('1900-01-01')

        def _key(v):
            vid = v.id if isinstance(v.id, int) else float('inf')
            return (v.date or date_min, vid)

        for rec in self:
            latest = rec.valuation_ids.sorted(key=_key, reverse=True)[:1]
            rec.value_current = latest.amount if latest else 0.0

    @api.depends('pledge_ids')
    def _compute_pledge_count(self):
        for rec in self:
            rec.pledge_count = len(rec.pledge_ids)

    @api.depends('pledge_ids.state', 'pledge_ids.secured_amount',
                 'value_current')
    def _compute_pledge_stats(self):
        for rec in self:
            active = rec.pledge_ids.filtered(lambda p: p.state == 'active')
            rec.active_pledge_count = len(active)
            rec.total_secured = sum(active.mapped('secured_amount'))
            rec.value_available = rec.value_current - rec.total_secured
            # Trả về dạng fraction (0..1) để widget="percentage" trên view
            # tự nhân 100 + thêm dấu %. Vd 0.4762 → "47.62%".
            if rec.value_current:
                rec.coverage_percent = (
                    rec.total_secured / rec.value_current)
            else:
                rec.coverage_percent = 0.0

    @api.depends('total_secured', 'value_current', 'active_pledge_count',
                 'disposed')
    def _compute_state(self):
        for rec in self:
            if rec.disposed:
                rec.state = 'disposed'
                continue
            if rec.active_pledge_count == 0:
                rec.state = 'available'
            elif rec.total_secured > rec.value_current + 0.01:
                rec.state = 'over_pledged'
            elif rec.total_secured >= rec.value_current - 0.01:
                rec.state = 'fully_pledged'
            else:
                rec.state = 'partial_pledged'

    @api.depends('valuation_ids.date', 'valuation_ids.date_valid_until')
    def _compute_valuation_expiry(self):
        """Hạn hiệu lực lấy theo lần định giá MỚI NHẤT, không phải lần
        có hạn xa nhất — một chứng thư cũ còn hạn dài không cứu được
        việc chứng thư mới nhất đã hết hiệu lực."""
        today = fields.Date.context_today(self)
        date_min = fields.Date.to_date('1900-01-01')

        def _key(v):
            vid = v.id if isinstance(v.id, int) else float('inf')
            return (v.date or date_min, vid)

        for rec in self:
            latest = rec.valuation_ids.sorted(key=_key, reverse=True)[:1]
            exp = latest.date_valid_until if latest else False
            rec.valuation_expiry_date = exp
            rec.valuation_expired = bool(exp and exp < today)

    # ------------------------------------------------------------------
    def action_dispose(self):
        """Thanh lý tài sản — chỉ khi chưa đem thế chấp gì.

        Tài sản đang bảo đảm cho một khoản vay mà bị đánh dấu thanh lý
        thì hạn mức khả dụng của khoản vay đó tụt xuống mà không ai
        biết vì sao. Muốn thanh lý thì giải chấp trước.
        """
        for rec in self:
            if rec.disposed:
                raise UserError(_('Tài sản "%s" đã thanh lý rồi.', rec.name))
            if rec.active_pledge_count:
                raise UserError(_(
                    'Tài sản "%(n)s" đang có %(c)s văn bản thế chấp còn '
                    'hiệu lực. Giải chấp hết rồi mới thanh lý được.',
                    n=rec.name, c=rec.active_pledge_count))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Thanh lý tài sản bảo đảm'),
            'res_model': 're.loan.collateral.dispose.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_collateral_ids': self.ids},
        }

    def unlink(self):
        """Chỉ xoá được tài sản chưa từng thế chấp và chưa thanh lý.

        Tài sản đã từng đem thế chấp là một mắt xích của hồ sơ tín
        dụng: xoá đi thì văn bản thế chấp mất tài sản, và không ai trả
        lời được HĐTD ngày đó được bảo đảm bằng gì.
        """
        for rec in self:
            if rec.pledge_ids:
                raise UserError(_(
                    'Không xoá được tài sản "%(n)s": đã có %(c)s văn bản '
                    'thế chấp gắn vào (kể cả đã giải chấp). Chỉ xoá được '
                    'tài sản ở trạng thái "Sẵn sàng — chưa thế chấp".',
                    n=rec.name, c=len(rec.pledge_ids)))
            if rec.disposed:
                raise UserError(_(
                    'Không xoá được tài sản "%s" đã thanh lý — giữ lại '
                    'để tra cứu lịch sử.', rec.name))
        return super().unlink()

    # ------------------------------------------------------------------
    @api.model
    def _cron_valuation_expiry_reminder(self):
        """Nhắc mỗi ngày các tài sản có định giá đã hết hạn.

        Chỉ nhắc tài sản ĐANG THẾ CHẤP: tài sản chưa đem thế chấp mà
        chứng thư hết hạn thì không ai thiệt gì, đến lúc dùng sẽ định
        giá lại. Nhắc cả hai loại là mỗi sáng gửi một danh sách dài
        không ai đọc.

        Không nhắc lại tài sản đã nhắc và chưa ai xử — hoạt động cũ vẫn
        còn treo, thêm cái nữa chỉ làm nhiễu.
        """
        today = fields.Date.context_today(self)
        stale = self.search([
            ('disposed', '=', False),
            ('valuation_expired', '=', True),
            ('active_pledge_count', '>', 0),
        ])
        if not stale:
            return True
        act_type = self.env.ref('mail.mail_activity_data_todo',
                                raise_if_not_found=False)
        managers = self.env.ref('re_loan.group_loan_manager',
                                raise_if_not_found=False)
        users = self.env['res.users']
        if managers:
            users = (managers.all_user_ids
                     if 'all_user_ids' in managers._fields
                     else managers.user_ids)
        Activity = self.env['mail.activity']
        model_id = self.env['ir.model']._get_id(self._name)
        made = 0
        for rec in stale:
            existing = Activity.search_count([
                ('res_model_id', '=', model_id),
                ('res_id', '=', rec.id),
                ('activity_type_id', '=', act_type.id if act_type else False),
            ])
            if existing:
                continue
            for user in users:
                Activity.create({
                    'res_model_id': model_id,
                    'res_id': rec.id,
                    'activity_type_id': act_type.id if act_type else False,
                    'user_id': user.id,
                    'date_deadline': today,
                    'summary': _('Định giá hết hạn — cần định giá lại'),
                    'note': _(
                        'Chứng thư định giá của "%(n)s" hết hiệu lực ngày '
                        '%(d)s. Tài sản đang bảo đảm cho %(c)s văn bản thế '
                        'chấp, ngân hàng sẽ yêu cầu định giá lại trước khi '
                        'cho rút thêm.',
                        n=rec.name, d=rec.valuation_expiry_date,
                        c=rec.active_pledge_count),
                })
                made += 1
        return made
