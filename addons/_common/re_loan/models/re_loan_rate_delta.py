# -*- coding: utf-8 -*-
"""Chênh lệch lãi (Δ) khi phụ lục lãi suất có hiệu lực HỒI TỐ.

BÀI TOÁN: ngân hàng ký phụ lục đổi lãi suất với ngày hiệu lực nằm ở
QUÁ KHỨ, trong khi các kỳ lãi từ ngày đó tới nay đã ghi nhận và có kỳ
đã thanh toán. Số lãi đã trả không còn đúng nữa. Phải trả lời được:
mỗi kỳ lệch bao nhiêu, tính từ lãi suất nào sang lãi suất nào, ai chốt
con số đó và chốt lúc nào.

FILE NÀY CHỈ TÍNH VÀ GHI VẾT — KHÔNG SỬA GÌ.

Không đụng vào dòng lịch lãi, không sinh bút toán, không cấn trừ. Cố ý:
kỳ đã thanh toán thường đã khoá sổ, và việc quyết định đưa phần lệch
vào đâu (kỳ mở kế tiếp hay quyết toán riêng) là chính sách của doanh
nghiệp chứ không phải hệ quả kỹ thuật của phép trừ. Tách bạch như vậy
thì bảng Δ này còn dùng được cho mọi cách xử lý về sau, và quan trọng
hơn: bấm nút tính Δ là một thao tác AN TOÀN, không ai phải sợ.

CÔNG THỨC PHẢI TRÙNG VỚI CHỖ TÍNH LÃI GỐC, không được viết lại theo
trí nhớ. Lãi một kỳ = dư nợ gốc × lãi suất/năm × hệ số ngày, hệ số
ngày theo đúng quy ước day_count của khế ước (act/365, act/360, 30/360)
— xem `re_loan_note_interest_line._day_factor`. Lệch quy ước ngày giữa
hai chỗ tính thì Δ sai ngay ở những kỳ không hề bị ảnh hưởng.

KỲ VẮT NGANG NGÀY HIỆU LỰC được chẻ làm hai đoạn: phần trước ngày hiệu
lực giữ lãi suất cũ, phần từ ngày hiệu lực trở đi tính lãi suất mới.
Gán nguyên kỳ theo một lãi suất là sai vài ngày lãi — số nhỏ nhưng
đúng vào kỳ mà kiểm toán soi kỹ nhất, vì đó là kỳ giao thời.

KỲ ĐÃ SỬA TAY (`is_overridden`) THÌ KHÔNG TỰ TÍNH LẠI. Số lãi ở đó là
con số người dùng cố ý ghi đè theo giấy báo ngân hàng; tính lại bằng
công thức rồi báo Δ nghĩa là đòi bỏ cái đã biết chắc để lấy cái suy ra.
Các kỳ này vẫn được liệt kê nhưng đánh dấu riêng, Δ để 0, và người
dùng tự nhập nếu ngân hàng có báo số.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ReLoanNoteAmendmentDelta(models.Model):
    _inherit = 're.loan.note.amendment'

    is_retroactive = fields.Boolean(
        string='Hiệu lực hồi tố',
        help='Đánh dấu khi ngày hiệu lực rơi vào giai đoạn ĐÃ ghi nhận '
             'hoặc ĐÃ thanh toán lãi. Bật cờ này rồi bấm "Tính chênh '
             'lệch" để ra bảng Δ từng kỳ.')
    delta_line_ids = fields.One2many(
        're.loan.rate.delta.line', 'amendment_id', string='Chênh lệch lãi')
    delta_count = fields.Integer(
        string='Số kỳ ảnh hưởng', compute='_compute_delta', store=True)
    delta_total = fields.Monetary(
        string='Tổng chênh lệch', currency_field='currency_id',
        compute='_compute_delta', store=True,
        help='Dương = phải THU THÊM của bên vay (lãi suất mới cao hơn). '
             'Âm = phải HOÀN LẠI.')
    delta_skipped = fields.Integer(
        string='Kỳ không tự tính được', compute='_compute_delta', store=True,
        help='Kỳ có số lãi sửa tay — không tính lại tự động.')
    delta_state = fields.Selection(
        [('none', 'Chưa tính'),
         ('computed', 'Đã tính'),
         ('approved', 'Đã duyệt')],
        string='Trạng thái Δ', default='none', required=True, tracking=True)
    delta_computed_uid = fields.Many2one(
        'res.users', string='Người tính', readonly=True, copy=False)
    delta_computed_on = fields.Datetime(
        string='Thời điểm tính', readonly=True, copy=False)
    delta_approved_uid = fields.Many2one(
        'res.users', string='Người duyệt Δ', readonly=True, copy=False,
        tracking=True)
    delta_approved_on = fields.Datetime(
        string='Thời điểm duyệt', readonly=True, copy=False, tracking=True)

    @api.depends('delta_line_ids.delta_amount', 'delta_line_ids.skipped')
    def _compute_delta(self):
        for am in self:
            am.delta_count = len(am.delta_line_ids)
            am.delta_total = sum(am.delta_line_ids.mapped('delta_amount'))
            am.delta_skipped = len(
                am.delta_line_ids.filtered('skipped'))

    # ------------------------------------------------------------------
    def action_compute_delta(self):
        """Dựng bảng Δ cho các kỳ đã ghi nhận từ ngày hiệu lực trở đi."""
        self.ensure_one()
        if self.amendment_type != 'rate':
            raise UserError(_(
                'Chỉ phụ lục đổi lãi suất mới có chênh lệch hồi tố.'))
        if not self.is_retroactive:
            raise UserError(_(
                'Phụ lục chưa đánh dấu "Hiệu lực hồi tố". Nếu ngày hiệu '
                'lực nằm ở tương lai thì không có kỳ nào phải tính lại.'))
        if self.delta_state == 'approved':
            raise UserError(_(
                'Bảng chênh lệch đã được duyệt. Muốn tính lại thì phải '
                'huỷ duyệt trước — số đã duyệt là căn cứ để xử lý tiếp.'))
        note = self.note_id
        eff = self.date_effective
        # Chỉ những kỳ ĐÃ ghi nhận mới cần tính lại. Kỳ còn 'planned' đã
        # được `action_apply` ghi thẳng lãi suất mới, không phải hồi tố.
        affected = note.interest_line_ids.filtered(
            lambda l: l.date_to and l.date_to > eff
            and l.state in ('accrued', 'partial_paid', 'paid'))
        if not affected:
            # KHÔNG phải lỗi, nên không dựng hộp thoại đỏ (backlog 737):
            # "không có gì để tính" là một kết quả hợp lệ của phép tính,
            # người dùng chỉ cần biết vì sao. Hộp đỏ khiến họ tưởng phần
            # mềm hỏng và đi báo lỗi.
            planned = len(note.interest_line_ids.filtered(
                lambda l: l.date_to and l.date_to > eff
                and l.state == 'planned'))
            msg = _(
                'Không có chênh lệch hồi tố để tính.\n'
                'Từ ngày hiệu lực %(d)s trở đi, khế ước chưa có kỳ lãi '
                'nào ở trạng thái đã ghi nhận / đã thanh toán — mà chỉ '
                'những kỳ đó mới phải tính lại.', d=eff)
            if planned:
                msg += _(
                    '\n%(n)s kỳ còn Dự kiến đã được ghi thẳng lãi suất '
                    'mới khi áp dụng phụ lục, nên không có gì hồi tố.',
                    n=planned)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Không phát sinh chênh lệch'),
                    'message': msg,
                    'type': 'info',
                    'sticky': True,
                },
            }
        self.delta_line_ids.unlink()
        vals = []
        for line in affected.sorted('period_no'):
            vals.append((0, 0, {
                'interest_line_id': line.id,
                'rate_old': line.interest_rate,
                'rate_new': self.new_interest_rate,
            }))
        self.write({
            'delta_line_ids': vals,
            'delta_state': 'computed',
            'delta_computed_uid': self.env.uid,
            'delta_computed_on': fields.Datetime.now(),
            'delta_approved_uid': False,
            'delta_approved_on': False,
        })
        self.message_post(body=_(
            'Tính chênh lệch hồi tố: %(n)s kỳ ảnh hưởng, tổng Δ = '
            '%(d)s. Bảng này chỉ ghi nhận, chưa sửa lịch lãi.',
            n=len(affected),
            d='{:,.0f}'.format(self.delta_total)))
        return True

    def action_approve_delta(self):
        self.ensure_one()
        if self.delta_state != 'computed':
            raise UserError(_('Chưa có bảng chênh lệch để duyệt.'))
        self.write({
            'delta_state': 'approved',
            'delta_approved_uid': self.env.uid,
            'delta_approved_on': fields.Datetime.now(),
        })
        self.message_post(body=_(
            'Duyệt bảng chênh lệch hồi tố — tổng Δ = %s.',
            '{:,.0f}'.format(self.delta_total)))
        return True

    def action_reset_delta(self):
        """Huỷ duyệt để tính lại. Giữ nguyên dòng, chỉ mở khoá."""
        self.ensure_one()
        if self.delta_state != 'approved':
            raise UserError(_('Bảng chênh lệch chưa được duyệt.'))
        self.write({
            'delta_state': 'computed',
            'delta_approved_uid': False,
            'delta_approved_on': False,
        })
        self.message_post(body=_('Huỷ duyệt bảng chênh lệch hồi tố.'))
        return True


class ReLoanRateDeltaLine(models.Model):
    _name = 're.loan.rate.delta.line'
    _description = 'Chênh lệch lãi theo kỳ do phụ lục hồi tố'
    _order = 'amendment_id, period_no, id'

    amendment_id = fields.Many2one(
        're.loan.note.amendment', string='Phụ lục', required=True,
        ondelete='cascade', index=True)
    note_id = fields.Many2one(
        related='amendment_id.note_id', string='Khế ước', store=True,
        index=True)
    currency_id = fields.Many2one(
        related='amendment_id.currency_id', string='Đồng tiền')
    company_id = fields.Many2one(
        related='amendment_id.company_id', store=True)
    date_effective = fields.Date(
        related='amendment_id.date_effective', string='Ngày hiệu lực')

    interest_line_id = fields.Many2one(
        're.loan.note.interest.line', string='Kỳ lãi', required=True,
        ondelete='cascade', index=True)
    period_no = fields.Integer(
        related='interest_line_id.period_no', string='Kỳ', store=True)
    date_from = fields.Date(
        related='interest_line_id.date_from', string='Từ ngày')
    date_to = fields.Date(
        related='interest_line_id.date_to', string='Đến ngày')
    days = fields.Integer(
        related='interest_line_id.days', string='Số ngày')
    principal_base = fields.Monetary(
        related='interest_line_id.principal_base', string='Dư nợ gốc',
        currency_field='currency_id')
    period_state = fields.Selection(
        related='interest_line_id.state', string='Trạng thái kỳ', store=True)

    days_old_rate = fields.Integer(
        string='Số ngày lãi cũ', compute='_compute_delta', store=True,
        help='Phần của kỳ nằm TRƯỚC ngày hiệu lực — vẫn tính lãi suất cũ.')
    days_new_rate = fields.Integer(
        string='Số ngày lãi mới', compute='_compute_delta', store=True)

    rate_old = fields.Float(
        string='Lãi suất trước', digits=(5, 2), readonly=True,
        aggregator=None)
    rate_new = fields.Float(
        string='Lãi suất sau', digits=(5, 2), readonly=True,
        aggregator=None)
    interest_old = fields.Monetary(
        string='Lãi đã ghi nhận', currency_field='currency_id',
        compute='_compute_delta', store=True)
    interest_new = fields.Monetary(
        string='Lãi tính lại', currency_field='currency_id',
        compute='_compute_delta', store=True)
    delta_amount = fields.Monetary(
        string='Chênh lệch Δ', currency_field='currency_id',
        compute='_compute_delta', store=True,
        help='= Lãi tính lại − Lãi đã ghi nhận. Dương là phải thu thêm.')
    skipped = fields.Boolean(
        string='Không tự tính', compute='_compute_delta', store=True,
        help='Kỳ có số lãi sửa tay — giữ nguyên, Δ để 0.')
    note = fields.Char(string='Ghi chú')

    # ==================================================================
    def _interest_for(self, line, rate, days):
        """Lãi của một đoạn `days` ngày trong kỳ, theo quy ước của KW.

        Dùng lại đúng ba quy ước ở `_day_factor`. Riêng 30/360 hệ số là
        cố định cho cả kỳ nên đoạn con được chia theo tỷ lệ ngày —
        không có cách nào khác giữ được tổng hai đoạn bằng cả kỳ.
        """
        dc = line.note_id.day_count
        if dc == 'act_360':
            factor = days / 360.0
        elif dc == '30_360':
            factor = (30.0 / 360.0) * (days / line.days if line.days else 0.0)
        else:
            factor = days / 365.0
        return (line.principal_base or 0.0) * (rate / 100.0) * factor

    @api.depends('interest_line_id', 'rate_old', 'rate_new',
                 'date_effective',
                 'interest_line_id.interest_amount',
                 'interest_line_id.principal_base',
                 'interest_line_id.days')
    def _compute_delta(self):
        for rec in self:
            line = rec.interest_line_id
            eff = rec.date_effective
            rec.interest_old = line.interest_amount
            if not (line and eff and line.date_from and line.date_to):
                rec.days_old_rate = rec.days_new_rate = 0
                rec.interest_new = line.interest_amount
                rec.delta_amount = 0.0
                rec.skipped = True
                continue
            if line.is_overridden:
                # Số lãi ghi đè theo giấy báo NH — không suy diễn lại.
                rec.days_old_rate = 0
                rec.days_new_rate = line.days
                rec.interest_new = line.interest_amount
                rec.delta_amount = 0.0
                rec.skipped = True
                continue
            # Chẻ kỳ tại ngày hiệu lực.
            if eff <= line.date_from:
                d_old, d_new = 0, line.days
            elif eff >= line.date_to:
                d_old, d_new = line.days, 0
            else:
                d_old = (eff - line.date_from).days
                d_new = line.days - d_old
            rec.days_old_rate = d_old
            rec.days_new_rate = d_new
            new_amount = (rec._interest_for(line, rec.rate_old, d_old)
                          + rec._interest_for(line, rec.rate_new, d_new))
            cur = rec.currency_id
            rec.interest_new = cur.round(new_amount) if cur else new_amount
            rec.delta_amount = rec.interest_new - (line.interest_amount or 0.0)
            rec.skipped = False
