# -*- coding: utf-8 -*-
"""Bridge: biến động sản lượng/thanh toán CĐT → định giá lại TSBĐ
quyền đòi nợ (tự động, có audit trail)."""
from odoo import _, api, fields, models


class RpOwnerAcceptance(models.Model):
    _inherit = 'rp.owner.acceptance'

    def action_approve(self):
        res = super().action_approve()
        self.mapped('contract_id')._sync_receivable_collaterals(
            reason=_('BBNT được CĐT duyệt'))
        return res


class RpOwnerPayment(models.Model):
    _inherit = 'rp.owner.payment'

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs.mapped('contract_id')._sync_receivable_collaterals(
            reason=_('CĐT thanh toán'))
        return recs

    def write(self, vals):
        res = super().write(vals)
        if 'amount' in vals or 'contract_id' in vals:
            self.mapped('contract_id')._sync_receivable_collaterals(
                reason=_('Sửa thanh toán CĐT'))
        return res

    def unlink(self):
        contracts = self.mapped('contract_id')
        res = super().unlink()
        contracts._sync_receivable_collaterals(
            reason=_('Xoá thanh toán CĐT'))
        return res


class RpOwnerContract(models.Model):
    _inherit = 'rp.owner.contract'

    def _sync_receivable_collaterals(self, reason=''):
        """Định giá lại CẢ HAI cấp: TSBĐ gắn HĐ và TSBĐ gắn từng IPC."""
        Col = self.env['re.loan.collateral']
        collaterals = Col.search([('owner_contract_id', 'in', self.ids)])
        ipcs = self.mapped('ipc_ids')
        if ipcs:
            collaterals |= Col.search([('owner_ipc_id', 'in', ipcs.ids)])
        collaterals._sync_receivable_valuation(reason=reason)


class ReLoanCreditContractIpc(models.Model):
    """Tab liệt kê IPC đang góp vào borrowing base của HĐTD này."""
    _inherit = 're.loan.credit.contract'

    ipc_ids = fields.Many2many(
        'rp.owner.ipc', string='IPC tham gia bảo đảm',
        compute='_compute_ipc_ids',
        help='Các IPC (CĐT đã ký) đang được thế chấp cho HĐTD này — kể '
             'cả thế chấp ở cấp facility con.')
    ipc_count = fields.Integer(compute='_compute_ipc_ids')
    ipc_base_contribution = fields.Monetary(
        string='Base từ quyền đòi nợ (IPC)', compute='_compute_ipc_ids',
        help='Phần Cơ sở bảo đảm đến từ IPC = Σ(giá trị bảo đảm × tỷ lệ '
             'cho vay). Phần còn lại đến từ TSBĐ khác (BĐS, tiền gửi…).')

    @api.depends('pledge_ids.state', 'pledge_ids.base_contribution',
                 'facility_ids.pledge_ids.state',
                 'facility_ids.pledge_ids.base_contribution')
    def _compute_ipc_ids(self):
        Pledge = self.env['re.loan.collateral.pledge']
        for rec in self:
            # `pledge_ids` có domain lọc cấp HĐ → bỏ sót pledge cấp
            # facility. Tìm thẳng cho đủ cả hai cấp.
            pledges = Pledge.search([
                ('state', '=', 'active'),
                ('collateral_id.owner_ipc_id', '!=', False),
                '|',
                ('credit_contract_id', '=', rec.id),
                ('facility_id.credit_contract_id', '=', rec.id),
            ]) if rec.id else Pledge
            rec.ipc_ids = pledges.mapped('collateral_id.owner_ipc_id')
            rec.ipc_count = len(rec.ipc_ids)
            rec.ipc_base_contribution = sum(
                pledges.mapped('base_contribution'))


class RpOwnerIpc(models.Model):
    """Bơm phần TSBĐ vào IPC — chỉ có khi cài phân hệ vay."""
    _inherit = 'rp.owner.ipc'

    collateral_ids = fields.One2many(
        're.loan.collateral', 'owner_ipc_id', string='TSBĐ từ IPC này')
    collateral_count = fields.Integer(compute='_compute_is_pledged')

    @api.depends('collateral_ids', 'collateral_ids.active',
                 'collateral_ids.pledge_ids.secured_amount',
                 'collateral_ids.pledge_ids.state')
    def _compute_is_pledged(self):
        for rec in self:
            rec.collateral_count = len(rec.collateral_ids)
            rec.is_pledged = bool(rec.collateral_ids)
            # NH có thể chỉ nhận MỘT PHẦN giá trị IPC → lấy đúng phần
            # đã đem bảo đảm, không lấy tổng quyền đòi nợ.
            rec.amount_pledged = sum(
                p.secured_amount
                for c in rec.collateral_ids
                for p in c.pledge_ids if p.state == 'active')

    def action_apply_to_credit(self):
        """Mở wizard đưa IPC (CĐT đã ký) vào HĐ tín dụng làm TSBĐ."""
        self.ensure_one()
        self._check_can_pledge()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Đưa IPC vào Hợp đồng tín dụng'),
            'res_model': 'rp.owner.ipc.pledge.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_ipc_id': self.id},
        }

    def action_open_collaterals(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('TSBĐ từ IPC %s') % self.name,
            'res_model': 're.loan.collateral',
            'view_mode': 'list,form',
            'domain': [('owner_ipc_id', '=', self.id)],
        }

    def write(self, vals):
        res = super().write(vals)
        # CĐT ký / huỷ ký → giá trị TSBĐ của IPC đổi theo.
        #
        # KHÔNG bắt `amount_received` ở đây: nó là field compute STORE,
        # Odoo ghi lại khi tính lại mà KHÔNG đi qua write() của model —
        # đã thử và test đỏ. Biến động tiền về bắt ở chính giao dịch
        # ngân hàng, xem ReBankTransactionCollateral bên dưới.
        if {'state', 'acceptance_ids'} & set(vals):
            cols = self.env['re.loan.collateral'].search(
                [('owner_ipc_id', 'in', self.ids)])
            cols._sync_receivable_valuation(
                reason=_('Biến động IPC'))
            # phần cầm cố theo IPC đổi → TSBĐ cấp HĐ phải tính lại
            self.mapped('contract_id')._sync_receivable_collaterals(
                reason=_('Biến động IPC'))
        return res


class ReBankTransactionCollateral(models.Model):
    """Tiền CĐT về IPC → định giá lại TSBĐ quyền đòi nợ NGAY.

    Không đợi ai nhập tay: khoản phải thu đã thu thì không còn đem thế
    chấp được, giữ nguyên giá trị là báo dư địa vay cao hơn thực tế.

    Bắt ở ĐÂY chứ không ở `rp.owner.ipc.write` vì `amount_received` là
    field compute STORE — Odoo tính lại và ghi thẳng, không qua write()
    của model, nên hook bên đó không bao giờ nổ.
    """
    _inherit = 're.bank.transaction'

    def _sync_ipc_collateral(self, reason, extra_ipcs=None):
        ipcs = self.mapped('ipc_id')
        if extra_ipcs:
            ipcs |= extra_ipcs
        if not ipcs:
            return
        self.env.flush_all()      # để amount_received kịp tính lại
        cols = self.env['re.loan.collateral'].search(
            [('owner_ipc_id', 'in', ipcs.ids)])
        cols._sync_receivable_valuation(reason=reason)
        ipcs.mapped('contract_id')._sync_receivable_collaterals(reason=reason)

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs._sync_ipc_collateral(_('CĐT trả tiền (đối soát ngân hàng)'))
        return recs

    def write(self, vals):
        # gỡ khớp / khớp sang IPC khác: IPC CŨ cũng phải định giá lại,
        # nếu không nó giữ mãi phần trừ của một giao dịch đã rời đi
        old = self.mapped('ipc_id') if 'ipc_id' in vals else None
        res = super().write(vals)
        if {'state', 'amount', 'ipc_id', 'direction'} & set(vals):
            self._sync_ipc_collateral(
                _('Đối soát ngân hàng thay đổi'), extra_ipcs=old)
        return res

    def unlink(self):
        ipcs = self.mapped('ipc_id')
        res = super().unlink()
        if ipcs:
            cols = self.env['re.loan.collateral'].search(
                [('owner_ipc_id', 'in', ipcs.ids)])
            cols._sync_receivable_valuation(reason=_('Xoá giao dịch NH'))
            ipcs.mapped('contract_id')._sync_receivable_collaterals(
                reason=_('Xoá giao dịch NH'))
        return res
