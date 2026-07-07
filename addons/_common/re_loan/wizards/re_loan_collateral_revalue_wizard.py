# -*- coding: utf-8 -*-
"""Wizard Định giá lại TSBĐ — mở từ dòng pledge trên form HĐTD.

Một màn hình làm trọn chu trình định giá lại của ngân hàng:
  1. Ghi bản định giá mới cho tài sản (re.loan.collateral.valuation)
  2. Khai lại **giá trị đảm bảo** của pledge (secured_amount) — thường
     điều chỉnh theo giá trị mới × tỷ lệ trong HĐ thế chấp
  3. Khả dụng của HĐTD / facility tự tính lại (compute cascade)

Log đầy đủ vào chatter HĐTD: giá cũ → mới, đảm bảo cũ → mới.
"""
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
    appraiser = fields.Char(string='Tổ chức / Người định giá')
    date_valid_until = fields.Date(
        string='Hiệu lực đến',
        help='Ngày hết hiệu lực chứng thư định giá (nếu có).')
    secured_amount_new = fields.Monetary(
        string='Giá trị đảm bảo mới', required=True,
        help='Giá trị đảm bảo khai lại theo kết quả định giá — thường '
             '≤ giá trị định giá mới. Đây là số chảy vào cơ sở bảo đảm '
             '(borrowing base) nếu dùng.')
    note = fields.Char(string='Ghi chú')

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
        return vals

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
            'appraiser': self.appraiser or '',
            'date_valid_until': self.date_valid_until or False,
            'note': self.note or _('Định giá lại từ HĐTD %s')
                % (pledge.credit_contract_id.name or ''),
        })
        if (pledge.currency_id.compare_amounts(
                self.secured_amount_new, old_secured) != 0):
            pledge.secured_amount = self.secured_amount_new

        contract = pledge.credit_contract_id
        if contract:
            contract.message_post(body=_(
                "<b>Định giá lại TSBĐ:</b> %(asset)s<br/>"
                "• Giá trị tài sản: %(ov)s → <b>%(nv)s</b><br/>"
                "• Giá trị đảm bảo: %(os)s → <b>%(ns)s</b><br/>"
                "• Phương pháp: %(m)s%(ap)s",
                asset=pledge.collateral_id.display_name,
                ov=f"{old_value:,.0f}",
                nv=f"{self.amount_new:,.0f}",
                os=f"{old_secured:,.0f}",
                ns=f"{self.secured_amount_new:,.0f}",
                m=dict(self._fields['method'].selection).get(self.method),
                ap=(" — %s" % self.appraiser) if self.appraiser else ''))

        # Reload để form HĐTD hiện ngay khả dụng mới
        return {'type': 'ir.actions.client', 'tag': 'reload'}
