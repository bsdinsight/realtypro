# -*- coding: utf-8 -*-
"""Đánh giá lại tỷ giá khoản vay ngoại tệ cuối kỳ — TT 200 Điều 69.

VÌ SAO PHẢI CÓ CHỨNG TỪ, KHÔNG PHẢI WIZARD:

Số dư nợ vay ngoại tệ cuối kỳ phải được đánh giá lại theo tỷ giá cuối
kỳ. Kiểm toán sẽ hỏi ba câu và cả ba đều phải trả lời được sau nhiều
tháng: đánh giá lại vào ngày nào, lấy tỷ giá bao nhiêu, và tỷ giá đó ở
đâu ra. Wizard chạy xong là mất dấu, nên đây là một chứng từ có trạng
thái, có dòng chi tiết từng khế ước, và lưu cả tỷ giá đã dùng lẫn nguồn
của nó.

CHIỀU BÚT TOÁN — chỗ dễ làm ngược nhất:

    Tỷ giá TĂNG → quy ra đồng ghi sổ, khoản NỢ PHẢI TRẢ tăng → LỖ
        Nợ 413 / Có 341
    Tỷ giá GIẢM → nghĩa vụ giảm → LÃI
        Nợ 341 / Có 413

Trực giác hay nhầm vì "tỷ giá tăng" nghe như có lợi. Với người đi vay
thì ngược lại: cùng một số ngoại tệ phải trả, nay tốn nhiều đồng nội tệ
hơn.

SỐ ĐANG GHI SỔ LẤY TỪ SỔ CÁI, KHÔNG PHẢI TỪ SỔ VAY:

Chênh lệch = (dư nợ nguyên tệ × tỷ giá mới) − (số VND ĐANG NẰM TRÊN SỔ
CÁI). Vế trừ phải đọc từ tài khoản vay trong `account.move.line`, vì đó
mới là con số kế toán đang mang. Lấy từ sổ vay quy đổi lại theo tỷ giá
gốc sẽ bỏ sót đúng phần chênh lệch của những lần đánh giá lại trước —
tức là đánh giá lại lần hai sẽ tính trùng lần một.

Hệ quả bắt buộc: mỗi khế ước một bút toán riêng, để dòng bút toán mang
`loan_note_id` và lần đánh giá lại sau còn đọc đúng số dư sổ cái của
từng khế ước.

MỘT KHOẢN VAY KHÔNG CÓ BÚT TOÁN NÀO TRÊN SỔ THÌ KHÔNG ĐÁNH GIÁ LẠI.
Số ghi sổ khi đó bằng 0, chênh lệch sẽ bằng toàn bộ dư nợ và sinh ra
một bút toán vô nghĩa. Các khế ước này bị đánh dấu và loại khỏi bút
toán, chứ không im lặng bỏ qua.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ReLoanFxRevaluation(models.Model):
    _name = 're.loan.fx.revaluation'
    _description = 'Đánh giá lại tỷ giá khoản vay ngoại tệ'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(
        string='Số phiếu', default='/', copy=False, readonly=True,
        tracking=True)
    date = fields.Date(
        string='Ngày đánh giá lại', required=True, tracking=True,
        default=fields.Date.context_today,
        help='Ngày cuối kỳ / cuối năm. Tỷ giá và số dư đều lấy tại ngày '
             'này, và bút toán cũng ghi vào ngày này.')
    company_id = fields.Many2one(
        'res.company', string='Công ty', required=True,
        default=lambda s: s.env.company, index=True)
    company_currency_id = fields.Many2one(
        related='company_id.currency_id', string='Đồng tiền hạch toán')
    journal_id = fields.Many2one(
        'account.journal', string='Sổ nhật ký', check_company=True,
        domain="[('type', 'in', ['general', 'bank'])]",
        help='Bỏ trống thì dùng Sổ Nhật ký Vay khai ở Cấu hình.')
    state = fields.Selection(
        [('draft', 'Nháp'),
         ('posted', 'Đã ghi sổ'),
         ('closed', 'Đã kết chuyển'),
         ('cancelled', 'Đã huỷ')],
        string='Trạng thái', default='draft', required=True, tracking=True)

    line_ids = fields.One2many(
        're.loan.fx.revaluation.line', 'reval_id', string='Chi tiết')
    line_count = fields.Integer(compute='_compute_line_count')
    move_ids = fields.One2many(
        'account.move', 'fx_revaluation_id', string='Bút toán')
    move_count = fields.Integer(compute='_compute_move_count')
    close_move_id = fields.Many2one(
        'account.move', string='Bút toán kết chuyển', readonly=True,
        copy=False)

    amount_loss = fields.Monetary(
        string='Tổng lỗ tỷ giá', currency_field='company_currency_id',
        compute='_compute_totals', store=True)
    amount_gain = fields.Monetary(
        string='Tổng lãi tỷ giá', currency_field='company_currency_id',
        compute='_compute_totals', store=True)
    amount_net = fields.Monetary(
        string='Thuần (lỗ − lãi)', currency_field='company_currency_id',
        compute='_compute_totals', store=True)
    warn_no_gl = fields.Integer(
        string='KW chưa có bút toán', compute='_compute_totals', store=True,
        help='Số khế ước chưa có bút toán nào trên sổ cái — bị loại khỏi '
             'bút toán đánh giá lại.')
    note = fields.Text(string='Ghi chú')

    # ==================================================================
    @api.depends('line_ids')
    def _compute_line_count(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)

    @api.depends('line_ids.diff_amount', 'line_ids.gl_missing')
    def _compute_totals(self):
        for rec in self:
            live = rec.line_ids.filtered(lambda l: not l.gl_missing)
            rec.amount_loss = sum(
                l.diff_amount for l in live if l.diff_amount > 0)
            rec.amount_gain = sum(
                -l.diff_amount for l in live if l.diff_amount < 0)
            rec.amount_net = rec.amount_loss - rec.amount_gain
            rec.warn_no_gl = len(rec.line_ids) - len(live)

    def _compute_move_count(self):
        for rec in self:
            rec.move_count = len(rec.move_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    're.loan.fx.revaluation') or '/'
        return super().create(vals_list)

    # ------------------------------------------------------------------
    def _get_journal(self):
        self.ensure_one()
        journal = self.journal_id or self.company_id.loan_journal_id
        if not journal:
            raise UserError(_(
                'Chưa khai Sổ Nhật ký Vay cho công ty "%s". Vào Cấu hình '
                '→ Tài khoản vay để khai.', self.company_id.name))
        return journal

    def _get_account(self, fname, label):
        self.ensure_one()
        acc = getattr(self.company_id, fname, False)
        if not acc:
            raise UserError(_(
                'Chưa khai "%(l)s" cho công ty "%(c)s". Vào Cấu hình → '
                'Tài khoản vay để khai.',
                l=label, c=self.company_id.name))
        return acc

    # ------------------------------------------------------------------
    def action_collect_notes(self):
        """Quét khế ước ngoại tệ còn dư nợ tại ngày đánh giá lại."""
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_('Chỉ nạp được khi phiếu đang ở trạng thái '
                              'Nháp.'))
        comp_cur = self.company_id.currency_id
        notes = self.env['re.loan.note'].search([
            ('company_id', '=', self.company_id.id),
            ('state', 'in', ('active', 'partial_paid', 'overdue',
                             'restructured')),
        ])
        notes = notes.filtered(
            lambda n: n.currency_id and n.currency_id != comp_cur
            and n.principal_outstanding > 0)
        if not notes:
            raise UserError(_(
                'Không có khế ước ngoại tệ nào còn dư nợ. Khế ước cùng '
                'đồng tiền với công ty (%s) không phải đánh giá lại.',
                comp_cur.name))
        self.line_ids.unlink()
        self.line_ids = [(0, 0, {'note_id': n.id}) for n in notes]
        return True

    def action_post(self):
        """Ghi sổ: mỗi khế ước một bút toán, để còn truy vết về sau."""
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_('Phiếu này đã ghi sổ hoặc đã huỷ.'))
        live = self.line_ids.filtered(
            lambda l: not l.gl_missing and l.diff_amount)
        if not live:
            raise UserError(_(
                'Không có dòng nào phát sinh chênh lệch để ghi sổ.'))
        journal = self._get_journal()
        fx_acc = self._get_account('loan_account_fx_diff_id',
                                   'TK Chênh lệch tỷ giá')
        Move = self.env['account.move']
        for line in live:
            note = line.note_id
            loan_acc = note._get_loan_account('loan_account_principal_id')
            diff = line.diff_amount
            if diff > 0:
                # Lỗ: nghĩa vụ trả nợ tăng.
                pairs = [(fx_acc, diff, 0.0), (loan_acc, 0.0, diff)]
                label = _('Lỗ tỷ giá %s', note.name)
            else:
                pairs = [(loan_acc, -diff, 0.0), (fx_acc, 0.0, -diff)]
                label = _('Lãi tỷ giá %s', note.name)
            vals_lines = []
            for acc, dr, cr in pairs:
                v = {
                    'account_id': acc.id,
                    'name': label,
                    'debit': dr,
                    'credit': cr,
                    'partner_id': note.partner_id.id or False,
                }
                if acc == loan_acc:
                    # Đánh giá lại KHÔNG làm đổi số nguyên tệ phải trả,
                    # chỉ đổi giá trị quy đổi — nên nguyên tệ ghi 0.
                    v['currency_id'] = note.currency_id.id
                    v['amount_currency'] = 0.0
                vals_lines.append((0, 0, v))
            move = Move.create({
                'journal_id': journal.id,
                'date': self.date,
                'partner_id': note.partner_id.id or False,
                'ref': _('Đánh giá lại tỷ giá %(d)s — %(kw)s',
                         d=self.date, kw=note.name),
                'company_id': self.company_id.id,
                'loan_note_id': note.id,
                'fx_revaluation_id': self.id,
                'line_ids': vals_lines,
            })
            move.action_post()
            line.move_id = move.id
        self.state = 'posted'
        return True

    def action_close_to_pl(self):
        """Kết chuyển TK chênh lệch tỷ giá sang 635 / 515.

        TT 200 Điều 69 khoản 3: chênh lệch tỷ giá đánh giá lại cuối kỳ
        được kết chuyển ngay vào chi phí tài chính (lỗ) hoặc doanh thu
        hoạt động tài chính (lãi). Để riêng một nút vì có đơn vị muốn
        kết chuyển theo lịch của kế toán chứ không ngay lúc đánh giá.
        """
        self.ensure_one()
        if self.state != 'posted':
            raise UserError(_('Phải ghi sổ đánh giá lại trước khi kết '
                              'chuyển.'))
        if self.close_move_id:
            raise UserError(_('Phiếu này đã kết chuyển bằng bút toán %s.',
                              self.close_move_id.name))
        if not (self.amount_loss or self.amount_gain):
            raise UserError(_('Không có chênh lệch nào để kết chuyển.'))
        journal = self._get_journal()
        fx_acc = self._get_account('loan_account_fx_diff_id',
                                   'TK Chênh lệch tỷ giá')
        lines = []
        if self.amount_loss:
            loss_acc = self._get_account('loan_account_fx_loss_id',
                                         'TK Lỗ tỷ giá (kết chuyển)')
            lines += [
                (0, 0, {'account_id': loss_acc.id,
                        'name': _('Kết chuyển lỗ tỷ giá %s', self.date),
                        'debit': self.amount_loss, 'credit': 0.0}),
                (0, 0, {'account_id': fx_acc.id,
                        'name': _('Kết chuyển lỗ tỷ giá %s', self.date),
                        'debit': 0.0, 'credit': self.amount_loss}),
            ]
        if self.amount_gain:
            gain_acc = self._get_account('loan_account_fx_gain_id',
                                         'TK Lãi tỷ giá (kết chuyển)')
            lines += [
                (0, 0, {'account_id': fx_acc.id,
                        'name': _('Kết chuyển lãi tỷ giá %s', self.date),
                        'debit': self.amount_gain, 'credit': 0.0}),
                (0, 0, {'account_id': gain_acc.id,
                        'name': _('Kết chuyển lãi tỷ giá %s', self.date),
                        'debit': 0.0, 'credit': self.amount_gain}),
            ]
        move = self.env['account.move'].create({
            'journal_id': journal.id,
            'date': self.date,
            'ref': _('Kết chuyển chênh lệch tỷ giá %s', self.date),
            'company_id': self.company_id.id,
            'fx_revaluation_id': self.id,
            'line_ids': lines,
        })
        move.action_post()
        self.write({'close_move_id': move.id, 'state': 'closed'})
        return True

    def action_cancel(self):
        """Huỷ: đảo mọi bút toán đã ghi, không xoá.

        Bút toán đã ghi sổ thì không được xoá — kỳ có thể đã khoá và
        dấu vết phải còn. Đảo bút toán giữ được cả hai chiều.
        """
        self.ensure_one()
        posted = self.move_ids.filtered(lambda m: m.state == 'posted')
        if posted:
            # PHẢI TỰ GÁN LẠI `loan_note_id`. Cả hai trường liên kết đều
            # để `copy=False` (đúng, vì nhân bản một bút toán sang khế
            # ước khác là sai), nhưng bút toán ĐẢO thì bắt buộc phải giữ
            # nguyên khế ước — nếu không, số dư kế toán của khế ước đọc
            # theo `loan_note_id` sẽ không thấy phần đảo và vẫn giữ giá
            # trị đã đánh giá lại. Lần đánh giá sau lấy đúng con số sai
            # đó làm nền.
            posted._reverse_moves(default_values_list=[
                {'date': self.date,
                 'ref': _('Đảo đánh giá lại tỷ giá %s', self.name),
                 'loan_note_id': m.loan_note_id.id,
                 'fx_revaluation_id': self.id}
                for m in posted], cancel=True)
        self.state = 'cancelled'
        return True

    def action_draft(self):
        self.ensure_one()
        if self.move_ids.filtered(lambda m: m.state == 'posted'):
            raise UserError(_(
                'Còn bút toán đang ở trạng thái đã ghi sổ. Bấm Huỷ để đảo '
                'bút toán trước.'))
        self.state = 'draft'

    def action_view_moves(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Bút toán — %s', self.name),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('fx_revaluation_id', '=', self.id)],
        }


class ReLoanFxRevaluationLine(models.Model):
    _name = 're.loan.fx.revaluation.line'
    _description = 'Dòng đánh giá lại tỷ giá'
    _order = 'reval_id, id'

    reval_id = fields.Many2one(
        're.loan.fx.revaluation', string='Phiếu đánh giá lại',
        required=True, ondelete='cascade', index=True)
    date = fields.Date(related='reval_id.date', string='Ngày')
    company_id = fields.Many2one(related='reval_id.company_id', store=True)
    company_currency_id = fields.Many2one(
        related='reval_id.company_currency_id')

    note_id = fields.Many2one(
        're.loan.note', string='Khế ước', required=True,
        ondelete='restrict', index=True)
    currency_id = fields.Many2one(
        related='note_id.currency_id', string='Nguyên tệ')
    partner_id = fields.Many2one(
        related='note_id.partner_id', string='Ngân hàng')
    date_maturity = fields.Date(
        related='note_id.date_maturity', string='Ngày đáo hạn')
    term_class = fields.Selection(
        [('short', 'Ngắn hạn'),
         ('long', 'Dài hạn'),
         ('unknown', 'Chưa xác định')],
        string='Kỳ hạn', compute='_compute_term_class', store=True,
        help='Phân loại theo thời gian còn lại tới ngày đáo hạn, tính từ '
             'ngày đánh giá lại: đến 12 tháng là ngắn hạn.')

    amount_fc = fields.Monetary(
        string='Dư nợ nguyên tệ', currency_field='currency_id',
        compute='_compute_amounts', store=True, readonly=False,
        help='Mặc định lấy dư nợ gốc của khế ước tại thời điểm nạp. Sửa '
             'tay được khi số dư ngân hàng xác nhận khác sổ.')
    amount_booked = fields.Monetary(
        string='Đang ghi sổ', currency_field='company_currency_id',
        compute='_compute_amounts', store=True,
        help='Số dư tài khoản vay của khế ước này trên SỔ CÁI (Σ Có − Σ '
             'Nợ). Đây là con số kế toán đang mang, không phải số quy '
             'đổi lại từ sổ vay.')
    gl_missing = fields.Boolean(
        string='Chưa có bút toán', compute='_compute_amounts', store=True,
        help='Khế ước chưa có bút toán nào trên tài khoản vay. Dòng này '
             'bị loại khỏi bút toán đánh giá lại.')

    rate = fields.Float(
        string='Tỷ giá đánh giá lại', digits=(16, 6),
        compute='_compute_rate', store=True, readonly=False,
        help='Số đồng tiền hạch toán cho 1 đơn vị nguyên tệ. Mặc định lấy '
             'từ bảng tỷ giá tại ngày đánh giá lại; sửa tay được khi dùng '
             'tỷ giá ngân hàng công bố.')
    rate_source = fields.Selection(
        [('table', 'Bảng tỷ giá'),
         ('manual', 'Nhập tay')],
        string='Nguồn tỷ giá', default='table', required=True,
        help='Ghi lại tỷ giá ở đâu ra — câu hỏi đầu tiên khi bị kiểm.')
    rate_booked = fields.Float(
        string='Tỷ giá đang ghi sổ', digits=(16, 6),
        compute='_compute_amounts', store=True,
        help='= Số đang ghi sổ ÷ dư nợ nguyên tệ. Chỉ để đối chiếu.')

    amount_revalued = fields.Monetary(
        string='Giá trị đánh giá lại', currency_field='company_currency_id',
        compute='_compute_diff', store=True)
    diff_amount = fields.Monetary(
        string='Chênh lệch', currency_field='company_currency_id',
        compute='_compute_diff', store=True,
        help='= Giá trị đánh giá lại − Số đang ghi sổ. Dương là nghĩa vụ '
             'trả nợ TĂNG, tức là LỖ tỷ giá.')
    direction = fields.Selection(
        [('loss', 'Lỗ tỷ giá'),
         ('gain', 'Lãi tỷ giá'),
         ('none', 'Không đổi')],
        string='Chiều', compute='_compute_diff', store=True)
    move_id = fields.Many2one(
        'account.move', string='Bút toán', readonly=True, copy=False)

    # ==================================================================
    @api.depends('date', 'note_id.date_maturity')
    def _compute_term_class(self):
        for rec in self:
            d, m = rec.date, rec.note_id.date_maturity
            if not (d and m):
                rec.term_class = 'unknown'
            else:
                rec.term_class = 'short' if (m - d).days <= 365 else 'long'

    @api.depends('note_id', 'note_id.principal_outstanding', 'date')
    def _compute_amounts(self):
        AML = self.env['account.move.line']
        for rec in self:
            note = rec.note_id
            rec.amount_fc = note.principal_outstanding
            loan_acc = (note.facility_id.loan_account_principal_id
                        or note.company_id.loan_account_principal_id)
            booked = 0.0
            found = False
            if loan_acc and rec.date:
                lines = AML.search([
                    ('loan_note_id', '=', note.id),
                    ('account_id', '=', loan_acc.id),
                    ('parent_state', '=', 'posted'),
                    ('date', '<=', rec.date),
                ])
                found = bool(lines)
                # Nợ vay là công nợ phải trả: Có làm tăng, Nợ làm giảm.
                booked = sum(lines.mapped('credit')) - sum(
                    lines.mapped('debit'))
            rec.amount_booked = booked
            rec.gl_missing = not found
            rec.rate_booked = (booked / rec.amount_fc) if rec.amount_fc else 0.0

    @api.depends('note_id', 'date', 'rate_source')
    def _compute_rate(self):
        for rec in self:
            if rec.rate_source == 'manual':
                continue
            cur = rec.note_id.currency_id
            comp = rec.company_id or rec.env.company
            if not (cur and rec.date) or cur == comp.currency_id:
                rec.rate = 0.0
            else:
                rec.rate = cur._convert(
                    1.0, comp.currency_id, comp, rec.date, round=False)

    @api.depends('amount_fc', 'rate', 'amount_booked', 'gl_missing')
    def _compute_diff(self):
        for rec in self:
            comp_cur = rec.company_currency_id
            revalued = (rec.amount_fc or 0.0) * (rec.rate or 0.0)
            rec.amount_revalued = comp_cur.round(revalued) if comp_cur \
                else revalued
            diff = rec.amount_revalued - (rec.amount_booked or 0.0)
            if rec.gl_missing:
                # Không có gì trên sổ để so — không tạo ra chênh lệch giả.
                diff = 0.0
            rec.diff_amount = diff
            rec.direction = ('loss' if diff > 0
                             else 'gain' if diff < 0 else 'none')

    @api.onchange('rate')
    def _onchange_rate_manual(self):
        """Sửa tay tỷ giá thì tự ghi nhận nguồn là nhập tay."""
        for rec in self:
            if rec.rate_source == 'table':
                rec.rate_source = 'manual'


class AccountMoveFxReval(models.Model):
    _inherit = 'account.move'

    fx_revaluation_id = fields.Many2one(
        're.loan.fx.revaluation', string='Phiếu đánh giá lại tỷ giá',
        index=True, copy=False, ondelete='set null')
