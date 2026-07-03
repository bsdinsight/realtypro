# -*- coding: utf-8 -*-
"""
Wizard điều chỉnh lãi suất HÀNG LOẠT cho nhiều KW active.

Nghiệp vụ: NH gửi 1 thông báo điều chỉnh LS (kỳ điều chỉnh 3/6 tháng
theo HĐTD) áp cho nhiều KW cùng lúc. Thay vì tạo phụ lục từng KW,
wizard này:
  1. Lọc KW theo NH / HĐTD / hạn mức → user CHỌN LẠI (xoá dòng
     không điều chỉnh — không phải mọi KW active đều đổi)
  2. Set LS mới đồng loạt HOẶC delta ±% — preview per-KW editable
     (biên độ mỗi KW khác nhau → số cuối có thể khác nhau)
  3. Confirm → mỗi KW sinh 1 Phụ lục đổi LS riêng (audit per-KW như
     làm tay) + apply → kỳ CHƯA trả regen theo LS mới

Kỳ ĐÃ trả sau ngày hiệu lực KHÔNG bị đụng — cảnh báo user chờ NH
phát hành Thông báo Nợ/Có (re.loan.adjustment.note) ghi nhận riêng.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ReLoanRateMassWizard(models.TransientModel):
    _name = 're.loan.rate.mass.wizard'
    _description = 'Điều chỉnh lãi suất hàng loạt'

    partner_id = fields.Many2one(
        'res.partner', string='Ngân hàng',
        domain="[('is_bank', '=', True)]",
        help='Lọc KW theo NH. Để trống = mọi NH.')
    credit_contract_id = fields.Many2one(
        're.loan.credit.contract', string='HĐTD',
        domain="[('partner_id', '=?', partner_id)]",
        help='Lọc KW theo HĐTD. Để trống = mọi HĐTD.')
    facility_id = fields.Many2one(
        're.loan.facility', string='Hạn mức',
        domain="[('credit_contract_id', '=?', credit_contract_id)]",
        help='Lọc KW theo hạn mức. Để trống = mọi hạn mức.')

    adjust_mode = fields.Selection(
        [('set',   'Đặt LS mới đồng loạt'),
         ('delta', 'Cộng/trừ delta (%)')],
        string='Cách điều chỉnh', default='delta', required=True,
        help='Delta khuyến nghị khi NH tăng/giảm lãi suất THAM CHIẾU '
             '— mỗi KW có biên độ riêng nên LS mới ra khác nhau.')
    new_rate = fields.Float(
        string='LS mới (%/năm)', digits=(5, 2),
        help='Mode "Đặt đồng loạt": mọi KW nhận LS này.')
    delta_rate = fields.Float(
        string='Delta (±%)', digits=(5, 2),
        help='Mode "Delta": LS mới = LS hiện tại + delta. Âm = giảm.')
    date_effective = fields.Date(
        string='Ngày hiệu lực', required=True,
        default=fields.Date.context_today)
    bank_document = fields.Char(
        string='Số văn bản NH',
        help='Số thông báo điều chỉnh LS của NH — ghi vào số phụ lục '
             'từng KW để trace ngược.')
    description = fields.Text(string='Diễn giải')

    line_ids = fields.One2many(
        're.loan.rate.mass.wizard.line', 'wizard_id', string='Các KW')

    # ------------------------------------------------------------------
    def action_load_notes(self):
        """Tải KW theo filter → tạo lines. User xoá dòng không muốn."""
        self.ensure_one()
        domain = [('state', 'in', ('active', 'partial_paid'))]
        if self.facility_id:
            domain.append(('facility_id', '=', self.facility_id.id))
        elif self.credit_contract_id:
            domain.append(
                ('credit_contract_id', '=', self.credit_contract_id.id))
        elif self.partner_id:
            domain.append(('partner_id', '=', self.partner_id.id))
        notes = self.env['re.loan.note'].search(domain)
        if not notes:
            raise UserError(_(
                "Không tìm thấy KW active/trả một phần nào theo bộ lọc."))
        self.line_ids.unlink()
        vals_list = []
        for note in notes:
            current = note._effective_rate_at(self.date_effective)
            vals_list.append((0, 0, {
                'note_id': note.id,
                'current_rate': current,
                'new_rate': self._compute_new_rate_for(current),
            }))
        self.line_ids = vals_list
        return self._reopen()

    def _compute_new_rate_for(self, current):
        if self.adjust_mode == 'set':
            return self.new_rate
        return current + self.delta_rate

    @api.onchange('adjust_mode', 'new_rate', 'delta_rate')
    def _onchange_recompute_lines(self):
        """Đổi mode/rate → recompute LS mới TẤT CẢ lines.
        (Sửa tay từng dòng SAU khi đã chốt mode.)"""
        for line in self.line_ids:
            line.new_rate = self._compute_new_rate_for(line.current_rate)

    def _reopen(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    # ------------------------------------------------------------------
    def action_confirm(self):
        """Mỗi line → 1 Phụ lục đổi LS + apply."""
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_(
                "Chưa có KW nào — bấm 'Tải danh sách KW' trước."))
        Amendment = self.env['re.loan.note.amendment']
        amendments = Amendment.browse()
        warn_notes = []
        for line in self.line_ids:
            note = line.note_id
            if line.new_rate < 0:
                raise UserError(_(
                    "KW %s: LS mới âm (%.2f%%).", note.name, line.new_rate))
            pl_name = (
                '%s — %s' % (self.bank_document, note.name)
                if self.bank_document
                else 'PL-LS/%s/%s' % (
                    self.date_effective.strftime('%Y%m%d'), note.name))
            am = Amendment.create({
                'name': pl_name,
                'note_id': note.id,
                'amendment_type': 'rate',
                'date_effective': self.date_effective,
                'new_interest_rate': line.new_rate,
                'description': self.description or _(
                    'Điều chỉnh LS hàng loạt theo văn bản NH %s'
                ) % (self.bank_document or '-'),
            })
            am.action_apply()
            amendments |= am
            # Cảnh báo kỳ ĐÃ trả sau ngày hiệu lực → cần Thông báo Nợ/Có
            paid_after = note.interest_line_ids.filtered(
                lambda l: l.line_type == 'period'
                and l.state in ('paid', 'partial_paid')
                and l.date_to and l.date_to > self.date_effective)
            if paid_after:
                warn_notes.append(note.name)
                note.message_post(body=_(
                    "⚠ Phụ lục %(pl)s hiệu lực %(d)s nhưng %(n)s kỳ đã "
                    "thanh toán sau ngày này KHÔNG bị tính lại. Chờ NH "
                    "phát hành Thông báo Nợ/Có (truy thu/truy hoàn) rồi "
                    "ghi nhận tại menu Quản lý Vay → Thông báo Nợ/Có.",
                    pl=pl_name, d=self.date_effective, n=len(paid_after)))
        action = {
            'type': 'ir.actions.act_window',
            'name': _('Phụ lục đã tạo (%s)') % len(amendments),
            'res_model': 're.loan.note.amendment',
            'view_mode': 'list,form',
            'domain': [('id', 'in', amendments.ids)],
        }
        if warn_notes:
            action['context'] = {'mass_rate_warn': ', '.join(warn_notes)}
        return action


class ReLoanRateMassWizardLine(models.TransientModel):
    _name = 're.loan.rate.mass.wizard.line'
    _description = 'Dòng wizard điều chỉnh LS hàng loạt'

    wizard_id = fields.Many2one(
        're.loan.rate.mass.wizard', required=True, ondelete='cascade')
    note_id = fields.Many2one(
        're.loan.note', string='Khế ước', required=True)
    credit_contract_id = fields.Many2one(
        related='note_id.credit_contract_id', string='HĐTD')
    partner_id = fields.Many2one(
        related='note_id.partner_id', string='Ngân hàng')
    principal_outstanding = fields.Monetary(
        related='note_id.principal_outstanding', string='Dư nợ gốc')
    currency_id = fields.Many2one(related='note_id.currency_id')
    current_rate = fields.Float(
        string='LS hiện tại (%)', digits=(5, 2), readonly=True)
    new_rate = fields.Float(
        string='LS mới (%)', digits=(5, 2),
        help='Sửa tay được từng KW (biên độ khác nhau).')
    future_period_count = fields.Integer(
        string='Kỳ chưa trả', compute='_compute_impact')
    has_paid_after = fields.Boolean(
        string='⚠ Có kỳ đã trả sau hiệu lực', compute='_compute_impact',
        help='KW có kỳ đã thanh toán sau ngày hiệu lực — phần đó cần '
             'Thông báo Nợ/Có của NH, wizard không tính lại.')

    @api.depends('note_id', 'wizard_id.date_effective')
    def _compute_impact(self):
        for line in self:
            d = line.wizard_id.date_effective
            periods = line.note_id.interest_line_ids.filtered(
                lambda l: l.line_type == 'period')
            line.future_period_count = len(periods.filtered(
                lambda l: l.state == 'planned'
                and l.date_from and d and l.date_from >= d))
            line.has_paid_after = bool(periods.filtered(
                lambda l: l.state in ('paid', 'partial_paid')
                and l.date_to and d and l.date_to > d))
