# -*- coding: utf-8 -*-
"""Dashboard Doanh thu — nhìn cả hai chiều tiền của tổng thầu.

Doanh thu (thu CĐT) − Chi phí (trả nhà thầu) = Lãi gộp dự án. Đây là
màn trả lời câu hỏi lớn nhất của lãnh đạo tổng thầu: dự án đang lãi/lỗ
bao nhiêu, còn phải thu bao nhiêu, ba tháng tới thu được bao nhiêu.

Pattern giống rp_finance/rp_construction dashboard (TransientModel +
default_get, chỉ đọc). Chi phí đọc mềm từ rp.contract (phía đầu vào).
"""
from odoo import api, fields, models

FMT = '{:,.0f}'


def _f(v):
    return FMT.format(v or 0)


class RpOwnerDashboard(models.TransientModel):
    _name = 'rp.owner.dashboard'
    _description = 'Realty Project — Dashboard Doanh thu'

    @api.depends_context('lang')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = 'Doanh thu — Dashboard'

    # ─── 1. Doanh thu & phải thu (với CĐT) ─────────────────────────
    kpi_owner_contract = fields.Monetary(
        string='Giá trị HĐ với CĐT',
        help='Σ giá trị HĐ đầu ra đã ký với Chủ đầu tư (sau thuế).')
    kpi_accepted = fields.Monetary(
        string='Sản lượng nghiệm thu (gửi CĐT)',
        help='Σ BBNT gửi CĐT đã được duyệt = doanh thu ghi nhận.')
    kpi_revenue_invoiced = fields.Monetary(
        string='Doanh thu đã xuất HĐ',
        help='Σ giá trị trước thuế hoá đơn đã phát hành cho CĐT.')
    kpi_received = fields.Monetary(
        string='CĐT đã thanh toán')
    kpi_receivable = fields.Monetary(
        string='Còn phải thu (theo HĐ)')

    # ─── 2. Chi phí (với nhà thầu) ─────────────────────────────────
    kpi_cost_contract = fields.Monetary(
        string='Giá trị HĐ nhà thầu đã ký')
    kpi_cost_accepted = fields.Monetary(
        string='Chi phí nghiệm thu (từ nhà thầu)',
        help='Σ nghiệm thu khối lượng đã duyệt của nhà thầu phụ.')
    kpi_cost_paid = fields.Monetary(
        string='Đã trả nhà thầu')

    # ─── 3. Lãi gộp & dòng tiền ────────────────────────────────────
    kpi_gross_margin = fields.Monetary(
        string='Lãi gộp thi công',
        help='= Sản lượng nghiệm thu gửi CĐT − Chi phí nghiệm thu nhà thầu.')
    kpi_margin_pct = fields.Float(
        string='Tỷ suất lãi gộp (%)')
    kpi_net_cash = fields.Monetary(
        string='Dòng tiền ròng',
        help='= CĐT đã thanh toán − Đã trả nhà thầu.')
    kpi_inflow_90d = fields.Monetary(
        string='Kế hoạch thu 90 ngày tới',
        help='Σ đợt thanh toán của CĐT dự kiến thu trong 90 ngày tới '
             '(chưa thu xong).')

    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id)
    project_id = fields.Many2one(
        're.project', string='Lọc theo dự án',
        help='Bỏ trống = tổng hợp tất cả dự án.')

    # ------------------------------------------------------------------
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        res.update(self._compute_kpis())
        return res

    @api.onchange('project_id')
    def _onchange_project_id(self):
        self.update(self._compute_kpis(self.project_id.id))

    def _compute_kpis(self, project_id=False):
        pid = project_id
        pf = [('project_id', '=', pid)] if pid else []
        OC = self.env['rp.owner.contract']
        owner = OC.search(
            [('state', 'in', ('signed', 'executing', 'completed'))] + pf)
        accepted = sum(owner.mapped('accepted_to_date'))

        # Chi phí — đọc mềm từ rp.contract (phía đầu vào)
        cost_contract = cost_accepted = cost_paid = 0.0
        if 'rp.contract' in self.env:
            Contract = self.env['rp.contract']
            signed = Contract.search(
                [('state', 'in', ('signed', 'executing', 'completed'))] + pf)
            cost_contract = sum(signed.mapped('contract_value_total'))
            cost_accepted = sum(
                signed.mapped('acceptance_value_to_date')) \
                if 'acceptance_value_to_date' in Contract._fields else 0.0
            cost_paid = sum(signed.mapped('amount_paid')) \
                if 'amount_paid' in Contract._fields else 0.0

        received = sum(owner.mapped('received_to_date'))
        gross = accepted - cost_accepted

        today = fields.Date.context_today(self)
        horizon = fields.Date.add(today, days=90)
        due = self.env['rp.owner.payment.milestone'].search([
            ('state', 'in', ('planned', 'invoiced')),
            ('due_date', '!=', False),
            ('due_date', '<=', horizon)] + pf)
        inflow = sum(m.amount - m.amount_received for m in due)

        return {
            'kpi_owner_contract': sum(owner.mapped('contract_value_total')),
            'kpi_accepted': accepted,
            'kpi_revenue_invoiced': sum(owner.mapped('revenue_invoiced')),
            'kpi_received': received,
            'kpi_receivable': sum(owner.mapped('receivable_invoiced')),
            'kpi_cost_contract': cost_contract,
            'kpi_cost_accepted': cost_accepted,
            'kpi_cost_paid': cost_paid,
            'kpi_gross_margin': gross,
            'kpi_margin_pct': (gross / accepted * 100.0) if accepted else 0.0,
            'kpi_net_cash': received - cost_paid,
            'kpi_inflow_90d': inflow,
        }

    def action_refresh(self):
        self.write(self._compute_kpis(self.project_id.id))
        return True

    def _open(self, name, model, domain, views='list,form', context=None):
        return {
            'type': 'ir.actions.act_window', 'name': name,
            'res_model': model, 'view_mode': views,
            'domain': domain or [], 'context': context or {},
            'target': 'current',
        }

    def action_open_owner_contracts(self):
        pf = [('project_id', '=', self.project_id.id)] if self.project_id else []
        return self._open('HĐ với CĐT', 'rp.owner.contract',
                          [('state', 'in', ('signed', 'executing', 'completed'))] + pf)

    def action_open_receivable(self):
        pid = self.project_id.id
        dom = [('move_type', '=', 'out_invoice'),
               ('owner_contract_id', '!=', False),
               ('payment_state', 'in', ('not_paid', 'partial'))]
        if pid:
            dom.append(('owner_project_id', '=', pid))
        return self._open('Hoá đơn còn phải thu', 'account.move', dom)

    def action_open_inflow(self):
        today = fields.Date.context_today(self)
        pf = [('project_id', '=', self.project_id.id)] if self.project_id else []
        return self._open(
            'Kế hoạch thu 90 ngày', 'rp.owner.payment.milestone',
            [('state', 'in', ('planned', 'invoiced')),
             ('due_date', '<=', fields.Date.add(today, days=90))] + pf,
            views='list,pivot')
