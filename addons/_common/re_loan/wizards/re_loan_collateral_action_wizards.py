# -*- coding: utf-8 -*-
"""Hai thao tác trên tài sản bảo đảm cần NGƯỜI DÙNG KHAI THÊM, nên
không làm bằng một nút bấm là xong: giải chấp và thanh lý.

Cả hai đều là sự kiện có thật ngoài đời, xảy ra vào một NGÀY CỤ THỂ và
vì một LÝ DO cụ thể. Trước đây giải chấp lấy luôn ngày bấm nút — đúng
khi thao tác ngay trong ngày, sai khi kế toán nhập bù hồ sơ của tuần
trước, mà nhập bù là chuyện thường xuyên hơn.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ReLoanPledgeReleaseWizard(models.TransientModel):
    _name = 're.loan.pledge.release.wizard'
    _description = 'Giải chấp tài sản bảo đảm'

    pledge_ids = fields.Many2many(
        're.loan.collateral.pledge', string='Văn bản thế chấp',
        required=True)
    release_date = fields.Date(
        string='Ngày giải chấp', required=True,
        default=fields.Date.context_today,
        help='Ngày ngân hàng giải chấp trên hồ sơ. Bỏ trống thì lấy '
             'ngày hôm nay.')
    release_reason = fields.Char(
        string='Lý do giải chấp',
        help='VD: đã tất toán khoản vay, thay bằng tài sản khác, '
             'ngân hàng chấp thuận giảm bảo đảm.')
    warn_outstanding = fields.Char(
        string='Cảnh báo', compute='_compute_warn')

    @api.depends('pledge_ids')
    def _compute_warn(self):
        Note = self.env['re.loan.note']
        for wiz in self:
            contracts = wiz.pledge_ids.mapped('credit_contract_id')
            n = Note.search_count([
                ('facility_id.credit_contract_id', 'in', contracts.ids),
                ('principal_outstanding', '>', 0),
            ]) if contracts else 0
            wiz.warn_outstanding = _(
                'HĐTD liên quan còn %s khế ước có dư nợ gốc. Giải chấp '
                'sẽ làm hạn mức khả dụng giảm theo.', n) if n else ''

    @api.constrains('release_date')
    def _check_date(self):
        today = fields.Date.context_today(self)
        for wiz in self:
            if wiz.release_date and wiz.release_date > today:
                raise UserError(_(
                    'Ngày giải chấp không được ở tương lai.'))

    def action_confirm(self):
        self.ensure_one()
        self.pledge_ids._do_release(self.release_date, self.release_reason)
        return {'type': 'ir.actions.act_window_close'}


class ReLoanCollateralDisposeWizard(models.TransientModel):
    _name = 're.loan.collateral.dispose.wizard'
    _description = 'Thanh lý tài sản bảo đảm'

    collateral_ids = fields.Many2many(
        're.loan.collateral', string='Tài sản', required=True)
    disposal_date = fields.Date(
        string='Ngày thanh lý', required=True,
        default=fields.Date.context_today)
    disposal_reason = fields.Char(
        string='Lý do thanh lý', required=True,
        help='VD: đã bán, chuyển nhượng, hết giá trị sử dụng.')

    @api.constrains('disposal_date')
    def _check_date(self):
        today = fields.Date.context_today(self)
        for wiz in self:
            if wiz.disposal_date and wiz.disposal_date > today:
                raise UserError(_(
                    'Ngày thanh lý không được ở tương lai.'))

    def action_confirm(self):
        self.ensure_one()
        for col in self.collateral_ids:
            if col.active_pledge_count:
                raise UserError(_(
                    'Tài sản "%(n)s" còn %(c)s văn bản thế chấp hiệu '
                    'lực — giải chấp trước khi thanh lý.',
                    n=col.name, c=col.active_pledge_count))
        self.collateral_ids.write({
            'disposed': True,
            'disposal_date': self.disposal_date,
            'disposal_reason': self.disposal_reason,
        })
        for col in self.collateral_ids:
            col.message_post(body=_(
                'Thanh lý tài sản ngày %(d)s — %(r)s',
                d=self.disposal_date, r=self.disposal_reason))
        return {'type': 'ir.actions.act_window_close'}
