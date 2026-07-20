# -*- coding: utf-8 -*-
"""Wizard: đưa IPC (CĐT đã ký nhận) vào Hợp đồng tín dụng làm TSBĐ.

Một thao tác, ba bản ghi:
  1. `re.loan.collateral` — tài sản "Quyền đòi nợ theo IPC ..." (giá trị
     tự cập nhật = quyền đòi nợ trên IPC);
  2. `re.loan.collateral.valuation` — định giá đầu tiên (auto, có audit);
  3. `re.loan.collateral.pledge` — thế chấp tài sản đó cho HĐTD/facility.

Sau đó `borrowing_base_total` cộng thêm `giá trị × advance rate`, và
`amount_available_effective` (hạn mức khả dụng) tăng theo — trừ khi
đã chạm trần hạn mức tổng.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class RpOwnerIpcPledgeWizard(models.TransientModel):
    _name = 'rp.owner.ipc.pledge.wizard'
    _description = 'Đưa IPC vào Hợp đồng tín dụng'

    ipc_id = fields.Many2one(
        'rp.owner.ipc', string='IPC', required=True, readonly=True)
    currency_id = fields.Many2one(
        related='ipc_id.currency_id', string='Loại tiền')
    amount_certified = fields.Monetary(
        related='ipc_id.amount_certified', string='Quyền đòi nợ trên IPC')
    owner_id = fields.Many2one(
        related='ipc_id.owner_id', string='Chủ đầu tư (con nợ)')

    pledge_target = fields.Selection(
        [('contract', 'HĐTD (toàn hợp đồng)'),
         ('facility', 'Facility (1 hạn mức)')],
        string='Cấp bảo đảm', required=True, default='contract')
    credit_contract_id = fields.Many2one(
        're.loan.credit.contract', string='Hợp đồng tín dụng')
    facility_id = fields.Many2one(
        're.loan.facility', string='Facility (hạn mức)')

    type_id = fields.Many2one(
        're.loan.collateral.type', string='Loại TSBĐ', required=True,
        help='Loại tài sản "quyền đòi nợ" — advance rate mặc định lấy '
             'từ đây.')
    advance_rate = fields.Float(
        string='Tỷ lệ cho vay (%)',
        help='NH cho vay bao nhiêu %% trên giá trị quyền đòi nợ. Bỏ '
             'trống = lấy theo Loại TSBĐ. 0 = KHÔNG tính vào borrowing '
             'base.')
    # --- NH thường KHÔNG nhận hết giá trị IPC ---
    apply_mode = fields.Selection(
        [('percent', 'Theo % quyền đòi nợ'),
         ('amount', 'Nhập số tiền trực tiếp')],
        string='Cách nhận bảo đảm', required=True, default='percent',
        help='Ngân hàng thường chỉ nhận một phần giá trị IPC. Chọn nhập '
             'theo tỷ lệ %% hoặc gõ thẳng số tiền.')
    apply_percent = fields.Float(
        string='% quyền đòi nợ nhận bảo đảm', default=100.0,
        help='Phần trăm trên quyền đòi nợ của IPC mà NH đồng ý nhận. '
             'Tối đa 100%%.')
    secured_amount = fields.Monetary(
        string='Giá trị bảo đảm', required=True,
        compute='_compute_secured_amount', store=False, readonly=False,
        help='Phần giá trị IPC đem bảo đảm. KHÔNG vượt quyền đòi nợ của '
             'IPC.')
    remaining_amount = fields.Monetary(
        string='Phần IPC không đưa vào', compute='_compute_secured_amount',
        help='Phần quyền đòi nợ còn lại của IPC — vẫn là công nợ phải '
             'thu bình thường, chỉ không đem thế chấp.')
    date_pledge = fields.Date(
        string='Ngày thế chấp', required=True,
        default=fields.Date.context_today)
    pledge_ref = fields.Char(
        string='Số HĐ thế chấp',
        help='Số văn bản thế chấp quyền đòi nợ ký với ngân hàng.')

    # --- Xem trước tác động lên hạn mức ---
    preview_base_before = fields.Monetary(
        string='Borrowing base hiện tại', compute='_compute_preview')
    preview_base_add = fields.Monetary(
        string='Cộng thêm từ IPC này', compute='_compute_preview')
    preview_available_before = fields.Monetary(
        string='Hạn mức khả dụng hiện tại', compute='_compute_preview')
    preview_note = fields.Char(compute='_compute_preview')

    @api.depends('apply_mode', 'apply_percent', 'ipc_id.amount_certified')
    def _compute_secured_amount(self):
        for w in self:
            cert = w.ipc_id.amount_certified or 0.0
            if w.apply_mode == 'percent':
                w.secured_amount = cert * (w.apply_percent or 0.0) / 100.0
            # mode 'amount': giữ nguyên số user gõ (readonly=False)
            w.remaining_amount = max(0.0, cert - (w.secured_amount or 0.0))

    @api.onchange('apply_mode')
    def _onchange_apply_mode(self):
        """Đổi sang nhập tay thì mồi bằng số đang hiện, khỏi gõ lại."""
        if self.apply_mode == 'amount' and not self.secured_amount:
            self.secured_amount = self.ipc_id.amount_certified

    @api.constrains('apply_percent')
    def _check_percent(self):
        for w in self:
            if w.apply_mode == 'percent' and not (0 < w.apply_percent <= 100):
                raise ValidationError(_(
                    'Tỷ lệ nhận bảo đảm phải trong khoảng 0–100%%.'))

    @api.onchange('type_id')
    def _onchange_type(self):
        if self.type_id and not self.advance_rate:
            self.advance_rate = self.type_id.advance_rate

    @api.onchange('pledge_target')
    def _onchange_target(self):
        if self.pledge_target == 'contract':
            self.facility_id = False
        else:
            self.credit_contract_id = False

    @api.depends('credit_contract_id', 'facility_id', 'pledge_target',
                 'secured_amount', 'advance_rate', 'apply_mode',
                 'apply_percent')
    def _compute_preview(self):
        for w in self:
            cc = w.credit_contract_id or w.facility_id.credit_contract_id
            w.preview_base_before = cc.borrowing_base_total if cc else 0.0
            w.preview_available_before = (
                cc.amount_available_effective if cc else 0.0)
            rate = (w.advance_rate or (w.type_id.advance_rate if w.type_id
                                       else 0.0)) / 100.0
            w.preview_base_add = (w.secured_amount or 0.0) * rate
            if not rate:
                w.preview_note = _(
                    '⚠ Tỷ lệ cho vay = 0 → IPC này KHÔNG làm tăng '
                    'borrowing base. Khai tỷ lệ trên Loại TSBĐ hoặc nhập '
                    'trực tiếp ở trên.')
            else:
                w.preview_note = _(
                    'Hạn mức khả dụng tăng tối đa %(a)s — thực tế còn bị '
                    'chặn bởi hạn mức tổng chưa dùng.',
                    a='{:,.0f}'.format(w.preview_base_add))

    # ------------------------------------------------------------------
    def action_confirm(self):
        self.ensure_one()
        ipc = self.ipc_id
        ipc._check_can_pledge()

        if self.pledge_target == 'contract' and not self.credit_contract_id:
            raise UserError(_('Chọn Hợp đồng tín dụng.'))
        if self.pledge_target == 'facility' and not self.facility_id:
            raise UserError(_('Chọn Facility (hạn mức).'))
        if self.secured_amount <= 0:
            raise UserError(_('Giá trị bảo đảm phải lớn hơn 0.'))
        if self.secured_amount > ipc.amount_certified + 0.01:
            raise UserError(_(
                'Giá trị bảo đảm (%(s)s) vượt quyền đòi nợ của IPC '
                '(%(q)s).',
                s='{:,.0f}'.format(self.secured_amount),
                q='{:,.0f}'.format(ipc.amount_certified)))
        if ipc.is_pledged:
            raise UserError(_(
                'IPC %s đã được đưa vào TSBĐ — không cầm cố lần hai '
                '(chống thế chấp trùng).', ipc.name))

        collateral = self.env['re.loan.collateral'].create({
            'name': _('Quyền đòi nợ theo IPC %(n)s — %(o)s',
                      n=ipc.name, o=ipc.owner_id.name or ''),
            'type_id': self.type_id.id,
            'owner_ipc_id': ipc.id,
            'company_id': ipc.company_id.id,
            'currency_id': ipc.currency_id.id,
            'legal_info': _(
                'IPC %(n)s — CĐT %(o)s ký nhận ngày %(d)s, văn bản '
                '%(r)s, người ký %(p)s. Quyền đòi nợ %(q)s.',
                n=ipc.name, o=ipc.owner_id.name or '',
                d=ipc.date_signed or '—', r=ipc.sign_ref or '—',
                p=ipc.signed_by_id.display_name or '—',
                q='{:,.0f}'.format(ipc.amount_certified)),
        })

        pledge_vals = {
            'name': self.pledge_ref or False,
            'collateral_id': collateral.id,
            'pledge_target': self.pledge_target,
            'secured_amount': self.secured_amount,
            'date_pledge': self.date_pledge,
            'state': 'active',
        }
        if self.pledge_target == 'contract':
            pledge_vals['credit_contract_id'] = self.credit_contract_id.id
        else:
            pledge_vals['facility_id'] = self.facility_id.id
        pledge = self.env['re.loan.collateral.pledge'].create(pledge_vals)
        if self.advance_rate:
            pledge.advance_rate = self.advance_rate

        cc = self.credit_contract_id or self.facility_id.credit_contract_id
        cc.invalidate_recordset()
        ipc.message_post(body=_(
            'Đưa vào TSBĐ của <b>%(c)s</b>: NH nhận %(pc)s trên quyền '
            'đòi nợ %(q)s → giá trị bảo đảm %(s)s × tỷ lệ cho vay %(r)s%% '
            '→ borrowing base +%(b)s. Hạn mức khả dụng hiện tại: '
            '<b>%(a)s</b>.',
            c=cc.display_name,
            pc=('{:.0f}%'.format(self.apply_percent)
                if self.apply_mode == 'percent' else _('số ấn định')),
            q='{:,.0f}'.format(ipc.amount_certified),
            s='{:,.0f}'.format(self.secured_amount),
            r='{:,.0f}'.format(pledge.advance_rate or 0.0),
            b='{:,.0f}'.format(pledge.base_contribution or 0.0),
            a='{:,.0f}'.format(cc.amount_available_effective or 0.0)))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Hợp đồng tín dụng'),
            'res_model': 're.loan.credit.contract',
            'res_id': cc.id,
            'view_mode': 'form',
        }
