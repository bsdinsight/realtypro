# -*- coding: utf-8 -*-
"""
Thế chấp (pledge) — gắn 1 tài sản vào khoản vay ở 3 cấp:
  - contract: bảo đảm cho TOÀN HĐTD (mặc định + phổ biến nhất)
  - facility: bảo đảm cho 1 facility cụ thể
  - note:     bảo đảm cho 1 KW cụ thể (hiếm — vay từng lần)

KW kế thừa pledge từ facility + contract của nó (computed read-only trên
KW form). Giải chấp ghi nhận trên bản ghi pledge.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class ReLoanCollateralPledge(models.Model):
    _name = 're.loan.collateral.pledge'
    _description = 'Thế chấp tài sản'
    _inherit = ['mail.thread']
    _order = 'date_pledge desc, id desc'

    name = fields.Char(string='Số văn bản thế chấp', copy=False)
    collateral_id = fields.Many2one(
        're.loan.collateral', string='Tài sản', required=True,
        ondelete='cascade',
        domain="[('state', 'in', ['available', 'partial_pledged'])]",
        help='Hiện TS:\n'
             '• Sẵn sàng (chưa thế chấp lần nào), hoặc\n'
             '• Thế chấp 1 phần (còn dư giá trị có thể đem TC thêm).\n'
             'KHÔNG hiện: đã thế chấp hết / quá thế chấp / đã thanh lý.')

    pledge_target = fields.Selection(
        [('contract', 'HĐTD (toàn HĐ)'),
         ('facility', 'Facility (1 hạn mức)'),
         ('note',     'KW (1 khế ước)')],
        string='Cấp bảo đảm', required=True, default='contract', tracking=True,
        help='Cấp pháp lý mà TSBĐ này bảo đảm:\n'
             '• HĐTD: tất cả facility + KW dưới HĐTD được bảo đảm (chuẩn VN)\n'
             '• Facility: chỉ KW thuộc facility được bảo đảm\n'
             '• KW: chỉ KW đó được bảo đảm (hiếm — vay từng lần riêng)')

    credit_contract_id = fields.Many2one(
        're.loan.credit.contract', string='HĐTD',
        compute='_compute_credit_contract_id', store=True, readonly=False,
        help='Tự fill từ facility/note. Required với mọi cấp.')
    facility_id = fields.Many2one(
        're.loan.facility', string='Facility',
        compute='_compute_facility_id', store=True, readonly=False,
        domain="[('credit_contract_id', '=', credit_contract_id)]",
        help='Required khi pledge_target=facility hoặc note.')
    note_id = fields.Many2one(
        're.loan.note', string='Khế ước',
        domain="[('facility_id', '=', facility_id)]",
        help='Required khi pledge_target=note.')

    partner_id = fields.Many2one(
        'res.partner', string='Ngân hàng', compute='_compute_partner',
        store=True)
    date_pledge = fields.Date(
        string='Ngày thế chấp', required=True,
        default=fields.Date.context_today)
    secured_amount = fields.Monetary(
        string='Giá trị đảm bảo',
        help='Giá trị tài sản dùng đảm bảo cho khoản vay này.')

    state = fields.Selection(
        [('active', 'Đang thế chấp'),
         ('released', 'Đã giải chấp')],
        string='Trạng thái', default='active', required=True, tracking=True)
    release_date = fields.Date(string='Ngày giải chấp', readonly=True)
    release_reason = fields.Char(string='Lý do giải chấp')

    currency_id = fields.Many2one(
        related='collateral_id.currency_id', store=True, readonly=True)
    company_id = fields.Many2one(
        related='collateral_id.company_id', store=True, readonly=True)

    # ------------------------------------------------------------------
    # Computes: auto-fill cấp cao hơn từ cấp thấp hơn
    # ------------------------------------------------------------------
    @api.depends('facility_id', 'note_id', 'pledge_target')
    def _compute_credit_contract_id(self):
        for rec in self:
            if rec.note_id:
                rec.credit_contract_id = (
                    rec.note_id.facility_id.credit_contract_id)
            elif rec.facility_id:
                rec.credit_contract_id = rec.facility_id.credit_contract_id
            elif not rec.credit_contract_id:
                rec.credit_contract_id = False

    @api.depends('note_id', 'pledge_target')
    def _compute_facility_id(self):
        for rec in self:
            if rec.note_id:
                rec.facility_id = rec.note_id.facility_id
            elif rec.pledge_target == 'contract':
                # Cấp HĐTD: clear facility/note
                rec.facility_id = False

    @api.depends('credit_contract_id', 'note_id', 'facility_id')
    def _compute_partner(self):
        for rec in self:
            rec.partner_id = (
                rec.note_id.partner_id
                or rec.credit_contract_id.partner_id)

    @api.onchange('pledge_target')
    def _onchange_target_clear(self):
        # Khi đổi target xuống cấp thấp hơn, KHÔNG clear; lên cấp cao
        # hơn thì clear facility/note để user chọn lại.
        if self.pledge_target == 'contract':
            self.facility_id = False
            self.note_id = False
        elif self.pledge_target == 'facility':
            self.note_id = False

    @api.onchange('collateral_id')
    def _onchange_collateral_suggest_amount(self):
        """Khi pick TS, gợi ý secured_amount = giá trị còn lại của TS.
        User vẫn có thể sửa nhỏ hơn (constraint sẽ chặn nếu vượt).
        """
        if self.collateral_id and not self.secured_amount:
            self.secured_amount = self.collateral_id.value_available

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    @api.constrains('secured_amount', 'collateral_id', 'state')
    def _check_secured_within_value(self):
        """secured_amount của pledge này KHÔNG được vượt giá trị còn
        lại của TS sau khi trừ các pledge ACTIVE KHÁC.

        Vd: TS 10 tỷ, pledge khác active đang giữ 6 tỷ → pledge này
        max = 10 − 6 = 4 tỷ.
        """
        for rec in self:
            if not rec.collateral_id or rec.state != 'active':
                continue
            others_secured = sum(
                p.secured_amount for p in rec.collateral_id.pledge_ids
                if p.id != rec.id and p.state == 'active'
            )
            max_allowed = rec.collateral_id.value_current - others_secured
            if rec.secured_amount > max_allowed + 1:  # tolerance 1đ
                raise ValidationError(_(
                    "Giá trị đảm bảo (%(s)s) vượt giá trị còn lại của "
                    "tài sản '%(t)s' sau khi trừ các thế chấp khác. "
                    "Tối đa cho pledge này: %(m)s.",
                    s=rec.secured_amount,
                    t=rec.collateral_id.name,
                    m=max_allowed))

    @api.constrains('pledge_target', 'credit_contract_id',
                    'facility_id', 'note_id')
    def _check_target_consistency(self):
        for rec in self:
            if rec.pledge_target == 'contract':
                if not rec.credit_contract_id:
                    raise ValidationError(_(
                        "Pledge cấp HĐTD cần chọn HĐTD."))
            elif rec.pledge_target == 'facility':
                if not rec.facility_id:
                    raise ValidationError(_(
                        "Pledge cấp Facility cần chọn Facility."))
                if (rec.credit_contract_id
                        and rec.facility_id.credit_contract_id
                        != rec.credit_contract_id):
                    raise ValidationError(_(
                        "Facility '%(f)s' không thuộc HĐTD '%(c)s'.",
                        f=rec.facility_id.name,
                        c=rec.credit_contract_id.name))
            elif rec.pledge_target == 'note':
                if not rec.note_id:
                    raise ValidationError(_(
                        "Pledge cấp KW cần chọn Khế ước."))
                if (rec.facility_id
                        and rec.note_id.facility_id != rec.facility_id):
                    raise ValidationError(_(
                        "KW '%(n)s' không thuộc Facility '%(f)s'.",
                        n=rec.note_id.name, f=rec.facility_id.name))

    # ------------------------------------------------------------------
    # State machine
    # ------------------------------------------------------------------
    def action_release(self):
        for rec in self:
            if rec.state != 'active':
                raise UserError(_("Thế chấp này đã được giải chấp."))
            rec.state = 'released'
            rec.release_date = fields.Date.context_today(rec)
            # Cảnh báo (ghi chatter) nếu còn KW thuộc HĐTD có dư nợ.
            contract = rec.credit_contract_id
            if contract:
                outstanding_notes = self.env['re.loan.note'].search([
                    ('facility_id.credit_contract_id', '=', contract.id),
                    ('principal_outstanding', '>', 0),
                ])
                if outstanding_notes:
                    rec.collateral_id.message_post(body=_(
                        "Giải chấp '%(c)s' khi HĐTD '%(ct)s' còn %(n)s KW "
                        "có dư nợ gốc.",
                        c=rec.collateral_id.name,
                        ct=contract.name,
                        n=len(outstanding_notes)))
        return True

    def action_set_active(self):
        for rec in self:
            rec.state = 'active'
            rec.release_date = False
