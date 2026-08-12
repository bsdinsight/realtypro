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
    project_id = fields.Many2one(
        related='ipc_id.project_id', string='Dự án',
        help='IPC của dự án nào chỉ thế chấp cho khoản vay của CHÍNH dự '
             'án đó — danh sách HĐTD/facility bên dưới đã lọc theo các '
             'HĐTD có khai phân bổ hạn mức cho dự án này.')

    pledge_target = fields.Selection(
        [('contract', 'HĐTD (toàn hợp đồng)'),
         ('facility', 'Facility (1 hạn mức)')],
        string='Cấp bảo đảm', required=True, default='contract')
    credit_contract_id = fields.Many2one(
        're.loan.credit.contract', string='Hợp đồng tín dụng')
    facility_id = fields.Many2one(
        're.loan.facility', string='Facility (hạn mức)')

    def _project_allocations(self):
        """Các dòng phân bổ hạn mức thuộc dự án của IPC."""
        self.ensure_one()
        if not self.project_id:
            return self.env['re.loan.facility.project.allocation']
        return self.env['re.loan.facility.project.allocation'].search(
            [('project_id', '=', self.project_id.id)])

    @api.onchange('ipc_id', 'pledge_target')
    def _onchange_project_domain(self):
        """Ràng buộc nghiệp vụ: chỉ cho chọn HĐTD/facility CỦA dự án IPC."""
        allocs = self._project_allocations()
        return {'domain': {
            'credit_contract_id':
                [('id', 'in', allocs.mapped('credit_contract_id').ids)],
            'facility_id':
                [('id', 'in', allocs.mapped('facility_id').ids)],
        }}

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

    # --- Phân bổ base vào từng facility (khi bảo đảm cấp HĐTD) ---
    line_ids = fields.One2many(
        'rp.owner.ipc.pledge.line', 'wizard_id',
        string='Phân bổ vào facility',
        help='Chia phần "cộng thêm từ IPC này" cho từng facility của HĐTD '
             'có phân bổ hạn mức cho dự án của IPC. Để TRỐNG hết = giữ '
             'nguyên kiểu cũ: toàn bộ vào bể chung của HĐTD (umbrella).')
    line_allocated = fields.Monetary(
        string='Đã phân bổ vào facility', compute='_compute_line_stats')
    line_unallocated = fields.Monetary(
        string='Còn ở bể chung HĐTD', compute='_compute_line_stats',
        help='Phần base không phân bổ riêng facility nào — vẫn nằm ở '
             'umbrella HĐTD, mọi facility dùng chung.')

    @api.depends('line_ids.base_amount', 'preview_base_add')
    def _compute_line_stats(self):
        for w in self:
            alloc = sum(w.line_ids.mapped('base_amount'))
            w.line_allocated = alloc
            w.line_unallocated = max(0.0, (w.preview_base_add or 0.0) - alloc)

    @api.onchange('credit_contract_id', 'pledge_target')
    def _onchange_build_lines(self):
        """Sinh danh sách facility của HĐTD CÓ phân bổ cho dự án IPC."""
        self.line_ids = [(5, 0, 0)]
        if self.pledge_target != 'contract' or not self.credit_contract_id:
            return
        allocs = self._project_allocations().filtered(
            lambda a: a.credit_contract_id == self.credit_contract_id)
        self.line_ids = [(0, 0, {
            'facility_id': a.facility_id.id,
            'base_amount': 0.0,
        }) for a in allocs]

    @api.constrains('line_ids')
    def _check_line_total(self):
        for w in self:
            alloc = sum(w.line_ids.mapped('base_amount'))
            if alloc > (w.preview_base_add or 0.0) + 0.01:
                raise ValidationError(_(
                    'Tổng phân bổ vào các facility (%(a)s) vượt phần base '
                    'cộng thêm từ IPC này (%(t)s).',
                    a='{:,.0f}'.format(alloc),
                    t='{:,.0f}'.format(w.preview_base_add or 0.0)))

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

        # Ràng buộc nghiệp vụ: IPC dự án X chỉ thế chấp cho khoản vay dự án X.
        # HĐTD/facility được chọn PHẢI có phân bổ hạn mức cho dự án đó
        # (onchange đã lọc UI, đây là chặn server-side).
        allocs = self._project_allocations()
        if self.project_id:
            if not allocs:
                raise UserError(_(
                    'Chưa có HĐTD nào khai PHÂN BỔ HẠN MỨC cho dự án '
                    '%(p)s.\nVào HĐTD → Facility → tab "Phân bổ dự án" '
                    'khai trước, rồi mới đưa IPC vào làm TSBĐ — quyền '
                    'đòi nợ của dự án nào chỉ bảo đảm cho khoản vay của '
                    'chính dự án đó.', p=self.project_id.display_name))
            if (self.pledge_target == 'contract'
                    and self.credit_contract_id
                    not in allocs.mapped('credit_contract_id')):
                raise UserError(_(
                    'HĐTD %(c)s không có phân bổ hạn mức cho dự án '
                    '%(p)s — không nhận IPC của dự án này làm TSBĐ.',
                    c=self.credit_contract_id.display_name,
                    p=self.project_id.display_name))
            if (self.pledge_target == 'facility'
                    and self.facility_id
                    not in allocs.mapped('facility_id')):
                raise UserError(_(
                    'Facility %(f)s không có phân bổ cho dự án %(p)s — '
                    'không nhận IPC của dự án này làm TSBĐ.',
                    f=self.facility_id.display_name,
                    p=self.project_id.display_name))
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

        Pledge = self.env['re.loan.collateral.pledge']
        rate = self.advance_rate or (self.type_id.advance_rate or 0.0)

        def _mk(vals, secured):
            v = {
                'name': self.pledge_ref or False,
                'collateral_id': collateral.id,
                'secured_amount': secured,
                'date_pledge': self.date_pledge,
                'state': 'active',
            }
            v.update(vals)
            p = Pledge.create(v)
            if rate:
                p.advance_rate = rate
            return p

        pledges = Pledge.browse()
        if self.pledge_target == 'contract' and any(
                l.base_amount for l in self.line_ids):
            # Chia base cho từng facility → tạo pledge RIÊNG facility
            # (ring-fence). Quy ngược: secured = base / tỷ lệ cho vay.
            if not rate:
                raise UserError(_(
                    'Chưa khai Tỷ lệ cho vay — không quy đổi được phần '
                    'base phân bổ sang giá trị bảo đảm.'))
            used = 0.0
            for line in self.line_ids.filtered('base_amount'):
                secured = line.base_amount / (rate / 100.0)
                used += secured
                pledges |= _mk({'pledge_target': 'facility',
                                'facility_id': line.facility_id.id}, secured)
            rest = self.secured_amount - used
            if rest > 0.01:
                pledges |= _mk(
                    {'pledge_target': 'contract',
                     'credit_contract_id': self.credit_contract_id.id}, rest)
        elif self.pledge_target == 'contract':
            pledges = _mk({'pledge_target': 'contract',
                           'credit_contract_id': self.credit_contract_id.id},
                          self.secured_amount)
        else:
            pledges = _mk({'pledge_target': 'facility',
                           'facility_id': self.facility_id.id},
                          self.secured_amount)
        pledge = pledges[:1]

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
