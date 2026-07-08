# -*- coding: utf-8 -*-
"""Wizard phân bổ lại hạn mức xuống các facility.

Khi HĐTD có hạn mức mới (NH tăng/giảm, ký phụ lục) → mở 1 màn hình để
khai lại tổng hạn mức HĐTD và phân bổ lại số tiền hạn mức cho từng
facility hiện có, trong một lần. Chặn:
  • hạn mức mới từng facility KHÔNG được nhỏ hơn phần ĐÃ DÙNG
  • Σ hạn mức các facility ≤ tổng hạn mức HĐTD mới

Áp xong: ghi lại amount_total của HĐTD + amount_limit từng facility,
log chatter cũ→mới.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ReLoanFacilityReallocateWizard(models.TransientModel):
    _name = 're.loan.facility.reallocate.wizard'
    _description = 'Phân bổ lại hạn mức facility'

    contract_id = fields.Many2one(
        're.loan.credit.contract', string='HĐTD', required=True,
        readonly=True, ondelete='cascade')
    currency_id = fields.Many2one(
        related='contract_id.currency_id')
    amount_total_old = fields.Monetary(
        string='Tổng hạn mức hiện tại', readonly=True)
    amount_total_new = fields.Monetary(
        string='Tổng hạn mức mới', required=True,
        help='Hạn mức HĐTD sau điều chỉnh (NH cấp mới / ký phụ lục). '
             'Mặc định = hạn mức hiện tại; sửa lại nếu có thay đổi.')
    line_ids = fields.One2many(
        're.loan.facility.reallocate.line', 'wizard_id',
        string='Phân bổ theo facility')

    total_allocated = fields.Monetary(
        string='Σ đã phân bổ', compute='_compute_totals')
    amount_remaining = fields.Monetary(
        string='Chưa phân bổ', compute='_compute_totals',
        help='= Tổng hạn mức mới − Σ hạn mức các facility. Âm = vượt.')

    @api.depends('amount_total_new', 'line_ids.amount_limit_new')
    def _compute_totals(self):
        for rec in self:
            allocated = sum(rec.line_ids.mapped('amount_limit_new'))
            rec.total_allocated = allocated
            rec.amount_remaining = rec.amount_total_new - allocated

    # ------------------------------------------------------------------
    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        contract_id = (vals.get('contract_id')
                       or self.env.context.get('default_contract_id'))
        if not contract_id:
            return vals
        contract = self.env['re.loan.credit.contract'].browse(contract_id)
        vals['amount_total_old'] = contract.amount_total
        vals.setdefault('amount_total_new', contract.amount_total)
        vals['line_ids'] = [(0, 0, {
            'facility_id': f.id,
            'amount_limit_new': f.amount_limit,
        }) for f in contract.facility_ids]
        return vals

    # ------------------------------------------------------------------
    def action_distribute_proportional(self):
        """Chia tổng hạn mức mới theo TỶ LỆ hạn mức hiện tại của từng
        facility (facility nào đang lớn hơn nhận nhiều hơn). Kỳ cuối vét
        cho tròn tổng. Sàn = phần đã dùng."""
        self.ensure_one()
        lines = self.line_ids
        if not lines:
            return self._reopen()
        base_total = sum(lines.mapped('amount_limit_old'))
        target = self.amount_total_new
        remaining = target
        n = len(lines)
        for idx, line in enumerate(lines):
            if idx == n - 1:
                share = remaining  # kỳ cuối vét phần còn lại
            elif base_total:
                share = self.currency_id.round(
                    target * line.amount_limit_old / base_total)
            else:
                share = self.currency_id.round(target / n)
            share = max(share, line.amount_used)  # không dưới đã dùng
            line.amount_limit_new = share
            remaining -= share
        return self._reopen()

    def action_confirm(self):
        self.ensure_one()
        contract = self.contract_id
        if self.amount_total_new <= 0:
            raise UserError(_("Tổng hạn mức mới phải > 0."))

        # Validate từng facility ≥ đã dùng
        bad = self.line_ids.filtered(
            lambda l: l.amount_limit_new < l.amount_used)
        if bad:
            raise UserError(_(
                "Hạn mức mới của facility '%(f)s' (%(new)s) nhỏ hơn phần "
                "đã dùng (%(used)s) — không thể cấp thấp hơn dư nợ/cam "
                "kết hiện hữu.",
                f=bad[0].facility_id.name,
                new='{:,.0f}'.format(bad[0].amount_limit_new),
                used='{:,.0f}'.format(bad[0].amount_used)))

        # Validate Σ ≤ tổng mới
        if self.currency_id.compare_amounts(
                self.total_allocated, self.amount_total_new) > 0:
            raise UserError(_(
                "Σ hạn mức các facility (%(a)s) vượt tổng hạn mức HĐTD "
                "mới (%(t)s). Giảm bớt phân bổ hoặc tăng tổng hạn mức.",
                a='{:,.0f}'.format(self.total_allocated),
                t='{:,.0f}'.format(self.amount_total_new)))

        # Thứ tự ghi an toàn với constraint Σ facility ≤ tổng HĐTD:
        # đặt tổng = max(cũ, mới) TRƯỚC (đủ chỗ cho mọi phân bổ), ghi
        # facility, rồi hạ tổng về số mới. Ở mọi bước Σ ≤ tổng.
        total_changed = self.currency_id.compare_amounts(
            self.amount_total_new, self.amount_total_old) != 0
        headroom = max(self.amount_total_old, self.amount_total_new)
        if self.currency_id.compare_amounts(
                headroom, self.amount_total_old) != 0:
            contract.amount_total = headroom

        changes = []
        for line in self.line_ids:
            if self.currency_id.compare_amounts(
                    line.amount_limit_new, line.amount_limit_old) != 0:
                changes.append(_(
                    "• %(f)s: %(o)s → <b>%(n)s</b>",
                    f=line.facility_id.name,
                    o='{:,.0f}'.format(line.amount_limit_old),
                    n='{:,.0f}'.format(line.amount_limit_new)))
                line.facility_id.amount_limit = line.amount_limit_new

        if self.currency_id.compare_amounts(
                contract.amount_total, self.amount_total_new) != 0:
            contract.amount_total = self.amount_total_new

        if changes or total_changed:
            head = ''
            if total_changed:
                head = _(
                    "<b>Điều chỉnh tổng hạn mức HĐTD:</b> %(o)s → "
                    "<b>%(n)s</b><br/>",
                    o='{:,.0f}'.format(self.amount_total_old),
                    n='{:,.0f}'.format(self.amount_total_new))
            contract.message_post(body=_(
                "%(head)s<b>Phân bổ lại hạn mức facility:</b><br/>%(body)s",
                head=head, body='<br/>'.join(changes) or _('(không đổi)')))

        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def _reopen(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }


class ReLoanFacilityReallocateLine(models.TransientModel):
    _name = 're.loan.facility.reallocate.line'
    _description = 'Dòng phân bổ lại hạn mức'
    _order = 'id'

    wizard_id = fields.Many2one(
        're.loan.facility.reallocate.wizard', ondelete='cascade',
        required=True)
    facility_id = fields.Many2one(
        're.loan.facility', string='Facility', required=True,
        readonly=True)
    purpose = fields.Selection(
        related='facility_id.purpose', string='Mục đích')
    amount_limit_old = fields.Monetary(
        string='Hạn mức hiện tại', related='facility_id.amount_limit',
        readonly=True)
    amount_used = fields.Monetary(
        string='Đã dùng', related='facility_id.amount_used',
        readonly=True)
    amount_limit_new = fields.Monetary(string='Hạn mức mới')
    currency_id = fields.Many2one(
        related='facility_id.currency_id')
