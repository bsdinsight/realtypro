# -*- coding: utf-8 -*-
"""Wizard Định giá lại TSBĐ — mở từ dòng pledge trên form HĐTD.

Một màn hình làm trọn chu trình định giá lại của ngân hàng:
  1. Ghi bản định giá mới cho tài sản (re.loan.collateral.valuation)
  2. Khai lại **giá trị đảm bảo** của pledge (secured_amount) — thường
     điều chỉnh theo giá trị mới × tỷ lệ trong HĐ thế chấp
  3. Khả dụng của HĐTD / facility tự tính lại (compute cascade)

Log đầy đủ vào chatter HĐTD: giá cũ → mới, đảm bảo cũ → mới.
"""
from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ReLoanCollateralRevalueWizard(models.TransientModel):
    _name = 're.loan.collateral.revalue.wizard'
    _description = 'Định giá lại TSBĐ'

    pledge_id = fields.Many2one(
        're.loan.collateral.pledge', string='Bản ghi thế chấp',
        required=True, readonly=True, ondelete='cascade')
    collateral_id = fields.Many2one(
        related='pledge_id.collateral_id', string='Tài sản')
    currency_id = fields.Many2one(
        related='pledge_id.currency_id')
    value_current = fields.Monetary(
        related='pledge_id.collateral_id.value_current',
        string='Giá trị hiện hành')
    secured_amount_old = fields.Monetary(
        related='pledge_id.secured_amount',
        string='Giá trị đảm bảo hiện tại')

    date = fields.Date(
        string='Ngày định giá', required=True,
        default=fields.Date.context_today)
    amount_new = fields.Monetary(
        string='Giá trị định giá mới', required=True)
    method = fields.Selection(
        [('market', 'So sánh thị trường'),
         ('cost', 'Chi phí'),
         ('income', 'Thu nhập'),
         ('appraisal', 'Tổ chức thẩm định giá')],
        string='Phương pháp', default='appraisal', required=True)
    appraiser_id = fields.Many2one(
        'res.partner', string='Tổ chức thẩm định giá',
        domain="[('is_appraiser', '=', True)]",
        context={'default_is_appraiser': True, 'default_is_company': True},
        help='Gõ tên mới rồi Create để thêm nhanh tổ chức TĐG vào '
             'danh mục.')
    date_valid_until = fields.Date(
        string='Hiệu lực đến',
        help='Ngày hết hiệu lực chứng thư định giá (nếu có).')
    secured_amount_new = fields.Monetary(
        string='Giá trị đảm bảo mới', required=True,
        help='Giá trị đảm bảo khai lại theo kết quả định giá — thường '
             '≤ giá trị định giá mới. Đây là số chảy vào cơ sở bảo đảm '
             '(borrowing base) nếu dùng.')
    note = fields.Char(string='Ghi chú')

    # ---- Phân bổ lại hạn mức facility (tùy chọn, cùng dialog) -------
    contract_amount_total = fields.Monetary(
        string='Tổng hạn mức HĐTD', readonly=True)
    facility_line_ids = fields.One2many(
        're.loan.collateral.revalue.facility.line', 'wizard_id',
        string='Phân bổ hạn mức facility')
    facility_allocated = fields.Monetary(
        string='Σ đã phân bổ', compute='_compute_facility_totals')
    facility_remaining = fields.Monetary(
        string='Hạn mức HĐTD còn lại', compute='_compute_facility_totals',
        help='= Tổng hạn mức HĐTD − Σ hạn mức các facility. Âm = vượt.')

    @api.depends('contract_amount_total',
                 'facility_line_ids.amount_limit_new')
    def _compute_facility_totals(self):
        for rec in self:
            allocated = sum(rec.facility_line_ids.mapped('amount_limit_new'))
            rec.facility_allocated = allocated
            rec.facility_remaining = rec.contract_amount_total - allocated

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        pledge_id = vals.get('pledge_id') or self.env.context.get(
            'default_pledge_id')
        if pledge_id:
            pledge = self.env['re.loan.collateral.pledge'].browse(pledge_id)
            vals.setdefault(
                'amount_new', pledge.collateral_id.value_current)
            vals.setdefault('secured_amount_new', pledge.secured_amount)
            contract = pledge.credit_contract_id
            if contract:
                vals['contract_amount_total'] = contract.amount_total
                vals['facility_line_ids'] = [(0, 0, {
                    'facility_id': f.id,
                    'amount_limit_new': f.amount_limit,
                }) for f in contract.facility_ids]
        return vals

    def _apply_facility_reallocation(self, contract):
        """Ghi lại amount_limit các facility nếu user có sửa. Trả về list
        mô tả thay đổi cho chatter. Ghi GIẢM trước, TĂNG sau để luôn
        thỏa Σ facility ≤ tổng HĐTD ở mọi bước."""
        cur = contract.currency_id
        lines = self.facility_line_ids
        # validate: mỗi facility ≥ đã dùng; Σ ≤ tổng
        bad = lines.filtered(
            lambda l: l.amount_limit_new < l.amount_used)
        if bad:
            raise UserError(_(
                "Hạn mức mới facility '%(f)s' (%(new)s) nhỏ hơn phần đã "
                "dùng (%(used)s).",
                f=bad[0].facility_id.name,
                new='{:,.0f}'.format(bad[0].amount_limit_new),
                used='{:,.0f}'.format(bad[0].amount_used)))
        if cur.compare_amounts(
                self.facility_allocated, self.contract_amount_total) > 0:
            raise UserError(_(
                "Σ hạn mức các facility (%(a)s) vượt tổng hạn mức HĐTD "
                "(%(t)s).",
                a='{:,.0f}'.format(self.facility_allocated),
                t='{:,.0f}'.format(self.contract_amount_total)))
        changed = lines.filtered(
            lambda l: cur.compare_amounts(
                l.amount_limit_new, l.facility_id.amount_limit) != 0)
        # giảm trước, tăng sau
        decreases = changed.filtered(
            lambda l: l.amount_limit_new < l.facility_id.amount_limit)
        increases = changed - decreases
        notes = []
        for line in list(decreases) + list(increases):
            notes.append(Markup(_(
                "• %(f)s: %(o)s → <b>%(n)s</b>")) % {
                'f': line.facility_id.name,
                'o': '{:,.0f}'.format(line.facility_id.amount_limit),
                'n': '{:,.0f}'.format(line.amount_limit_new)})
            line.facility_id.amount_limit = line.amount_limit_new
        return notes

    @api.onchange('amount_new')
    def _onchange_amount_new(self):
        """Đảm bảo không vượt giá trị định giá — tự co về trần mới."""
        if (self.amount_new
                and self.secured_amount_new > self.amount_new):
            self.secured_amount_new = self.amount_new
            return {'warning': {
                'title': _("Giá trị đảm bảo đã điều chỉnh"),
                'message': _(
                    "Giá trị đảm bảo đang lớn hơn giá trị định giá mới "
                    "— hệ thống tự co về bằng giá trị định giá. Sửa lại "
                    "nếu HĐ thế chấp quy định khác."),
            }}

    def action_confirm(self):
        self.ensure_one()
        pledge = self.pledge_id
        if self.amount_new <= 0:
            raise UserError(_("Giá trị định giá mới phải > 0."))
        if self.secured_amount_new < 0:
            raise UserError(_("Giá trị đảm bảo không được âm."))

        old_value = pledge.collateral_id.value_current
        old_secured = pledge.secured_amount

        self.env['re.loan.collateral.valuation'].create({
            'collateral_id': pledge.collateral_id.id,
            'date': self.date,
            'amount': self.amount_new,
            'method': self.method,
            'appraiser_id': self.appraiser_id.id or False,
            'date_valid_until': self.date_valid_until or False,
            'note': self.note or _('Định giá lại từ HĐTD %s')
                % (pledge.credit_contract_id.name or ''),
        })
        if (pledge.currency_id.compare_amounts(
                self.secured_amount_new, old_secured) != 0):
            pledge.secured_amount = self.secured_amount_new

        contract = pledge.credit_contract_id

        # Phân bổ lại hạn mức facility (nếu user có sửa trong lưới)
        facility_notes = []
        if contract and self.facility_line_ids:
            facility_notes = self._apply_facility_reallocation(contract)

        if contract:
            body = Markup(_(
                "<b>Định giá lại TSBĐ:</b> %(asset)s<br/>"
                "• Giá trị tài sản: %(ov)s → <b>%(nv)s</b><br/>"
                "• Giá trị đảm bảo: %(os)s → <b>%(ns)s</b><br/>"
                "• Phương pháp: %(m)s%(ap)s")) % {
                'asset': pledge.collateral_id.display_name,
                'ov': f"{old_value:,.0f}",
                'nv': f"{self.amount_new:,.0f}",
                'os': f"{old_secured:,.0f}",
                'ns': f"{self.secured_amount_new:,.0f}",
                'm': dict(self._fields['method'].selection).get(self.method),
                'ap': (" — %s" % self.appraiser_id.name)
                if self.appraiser_id else ''}
            if facility_notes:
                body += (Markup(_("<br/><b>Phân bổ lại hạn mức "
                                  "facility:</b><br/>"))
                         + Markup('<br/>').join(facility_notes))
            contract.message_post(body=body)

        # Reload để form HĐTD hiện ngay khả dụng mới
        return {'type': 'ir.actions.client', 'tag': 'reload'}


class ReLoanCollateralRevalueFacilityLine(models.TransientModel):
    _name = 're.loan.collateral.revalue.facility.line'
    _description = 'Dòng phân bổ hạn mức trong định giá lại'
    _order = 'id'

    wizard_id = fields.Many2one(
        're.loan.collateral.revalue.wizard', ondelete='cascade',
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
    currency_id = fields.Many2one(related='facility_id.currency_id')
