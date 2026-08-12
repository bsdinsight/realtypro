# -*- coding: utf-8 -*-
"""Dòng tiền dự án theo THÁNG và hệ số trả nợ DSCR — tài liệu nghiệp vụ §8.

    CFADS (dòng tiền khả dụng trả nợ)
        = Thu từ chủ đầu tư
        − Chi trả thầu phụ/NCC
        − Chi phí cấp dự án (rải đều theo tiến độ)
    DSCR(kỳ) = CFADS ÷ (gốc + lãi đến hạn trong kỳ)

KHÔNG tính giải ngân vay vào phần thu: tiền vay là TÀI TRỢ, không phải
nguồn trả nợ — cộng vào thì DSCR luôn đẹp và mất hết ý nghĩa.

Anh Đại chốt 2026-08-11: kỳ tính theo THÁNG (ngân hàng xét theo quý
nhưng người dùng ước lượng theo tháng); cổng chặn là **cảnh báo mềm**,
không khoá thao tác — DSCR là dự báo, chặn cứng dễ kẹt vận hành.

Chỉ tiêu ⑤ của bảng xanh/vàng/đỏ lấy **DSCR THẤP NHẤT**, không lấy bình
quân: vỡ nợ xảy ra ở kỳ xấu nhất.
"""
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models


class ReLoanProjectCashflow(models.Model):
    _name = 're.loan.project.cashflow'
    _description = 'Dòng tiền dự án & DSCR'
    _inherit = ['mail.thread']
    _order = 'project_id'

    project_id = fields.Many2one(
        're.project', string='Dự án', required=True, index=True,
        ondelete='cascade')
    currency_id = fields.Many2one(
        related='project_id.currency_id', readonly=True)
    horizon_months = fields.Integer(
        string='Số tháng dự báo', default=24, required=True,
        help='Tính từ tháng hiện tại trở đi.')
    date_generated = fields.Datetime(string='Tính lúc', readonly=True)
    line_ids = fields.One2many(
        're.loan.project.cashflow.line', 'cashflow_id', string='Theo tháng')

    dscr_overall = fields.Float(
        string='DSCR toàn kỳ', compute='_compute_summary', store=True,
        digits=(12, 2),
        help='Σ CFADS ÷ Σ nghĩa vụ trả nợ trên cả kỳ dự báo. ĐÂY là số '
             'nuôi chỉ tiêu ⑤ — không lấy DSCR tháng thấp nhất.\n\n'
             'Vì sao: dòng tiền xây lắp về theo ĐỢT nghiệm thu (2-3 lần '
             '/năm) trong khi gốc + lãi đến hạn HÀNG THÁNG. DSCR tháng vì '
             'thế nhảy từ âm tới vài trăm lần; lấy tháng thấp nhất thì dự '
             'án nào cũng đỏ, mất hết khả năng phân biệt.')
    dscr_min = fields.Float(
        string='DSCR tháng thấp nhất', compute='_compute_summary',
        store=True, digits=(12, 2),
        help='Tham khảo thôi — tháng không có đợt thu nào là tự động âm, '
             'không có nghĩa là dự án mất khả năng trả nợ (tiền đợt trước '
             'còn giữ lại). Xem "Số tháng thiếu tiền" mới đúng là rủi ro '
             'thanh khoản.')
    dscr_avg = fields.Float(
        string='DSCR bình quân tháng', compute='_compute_summary',
        store=True, digits=(12, 2))
    month_below_count = fields.Integer(
        string='Số tháng DSCR < 1', compute='_compute_summary', store=True,
        help='Tháng mà riêng dòng tiền tháng đó không đủ trả gốc + lãi.')
    month_cash_short = fields.Integer(
        string='Số tháng thiếu tiền', compute='_compute_summary',
        store=True,
        help='Tháng mà SỐ DƯ TIỀN LUỸ KẾ âm — tức là gom cả tiền các đợt '
             'thu trước vẫn không đủ trả nợ. Đây mới là rủi ro thanh '
             'khoản thật; DSCR tháng âm thì không.')
    cash_min = fields.Monetary(
        string='Số dư tiền thấp nhất', compute='_compute_summary',
        store=True,
        help='Đáy của đường số dư tiền luỹ kế. Âm = phải xoay thêm vốn '
             'đúng vào tháng đó.')
    total_cfads = fields.Monetary(
        string='Σ CFADS', compute='_compute_summary')
    total_debt_service = fields.Monetary(
        string='Σ nghĩa vụ trả nợ', compute='_compute_summary')

    _uniq_project = models.Constraint(
        'unique(project_id)', 'Mỗi dự án chỉ có một bảng dòng tiền.')

    @api.depends('line_ids.dscr', 'line_ids.debt_service',
                 'line_ids.cfads', 'line_ids.cash_balance')
    def _compute_summary(self):
        for rec in self:
            live = rec.line_ids.filtered(lambda l: l.debt_service > 0)
            vals = live.mapped('dscr')
            rec.dscr_min = min(vals) if vals else 0.0
            rec.dscr_avg = (sum(vals) / len(vals)) if vals else 0.0
            rec.month_below_count = len([v for v in vals if v < 1.0])
            rec.total_cfads = sum(rec.line_ids.mapped('cfads'))
            rec.total_debt_service = sum(
                rec.line_ids.mapped('debt_service'))
            rec.dscr_overall = (rec.total_cfads / rec.total_debt_service
                                if rec.total_debt_service else 0.0)
            bals = rec.line_ids.mapped('cash_balance')
            rec.cash_min = min(bals) if bals else 0.0
            rec.month_cash_short = len([b for b in bals if b < 0])

    @api.depends('project_id')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = _('Dòng tiền — %s') % (
                rec.project_id.display_name or '')

    # ------------------------------------------------------------------
    def action_generate(self):
        """Sinh lại các dòng theo tháng từ dữ liệu hiện có."""
        Line = self.env['re.loan.project.cashflow.line']
        Note = self.env['re.loan.note']
        OwnerMs = self.env['rp.owner.payment.milestone']
        ContractMs = self.env['rp.contract.payment.milestone']
        IntLine = self.env['re.loan.note.interest.line']
        CostLine = self.env['rp.project.cost.line']
        for rec in self:
            rec.line_ids.unlink()
            today = fields.Date.context_today(rec)
            first = today.replace(day=1)
            n = max(1, rec.horizon_months)
            # chi phí cấp dự án: chưa có ngày đến hạn → RẢI ĐỀU
            direct_total = sum(CostLine.search(
                [('project_id', '=', rec.project_id.id)]).mapped('amount'))
            direct_per_month = direct_total / n if n else 0.0
            # KW liên quan dự án + tỷ trọng — một KW có thể rót cho nhiều
            # dự án nên phải chia, không lọc cứng note_id.project_id
            shares = {}
            for note in Note.search([('state', 'not in',
                                      ('draft', 'cancelled', 'fully_paid'))]):
                sh = note._project_share(rec.project_id)
                if sh:
                    shares[note.id] = sh
            vals = []
            for i in range(n):
                d0 = first + relativedelta(months=i)
                d1 = d0 + relativedelta(months=1, days=-1)
                # THU: mốc thu từ CĐT còn phải thu
                ins = OwnerMs.search([
                    ('project_id', '=', rec.project_id.id),
                    ('state', 'not in', ('cancelled', 'received')),
                    ('due_date', '>=', d0), ('due_date', '<=', d1)])
                amount_in = sum(
                    max(0.0, (m.amount or 0.0) - (m.amount_received or 0.0))
                    for m in ins)
                # CHI: mốc trả thầu phụ
                outs = ContractMs.search([
                    ('contract_id.project_id', '=', rec.project_id.id),
                    ('state', '!=', 'paid'),
                    ('due_date', '>=', d0), ('due_date', '<=', d1)])
                out_contract = sum(outs.mapped('amount'))
                # NỢ: gốc + lãi đến hạn, nhân tỷ trọng dự án của KW
                principal = interest = 0.0
                if shares:
                    debts = IntLine.search([
                        ('note_id', 'in', list(shares)),
                        ('state', '!=', 'paid'),
                        ('date_to', '>=', d0), ('date_to', '<=', d1)])
                    for dl in debts:
                        sh = shares.get(dl.note_id.id, 0.0)
                        principal += (dl.principal_due or 0.0) * sh
                        interest += (dl.interest_amount or 0.0) * sh
                vals.append({
                    'cashflow_id': rec.id,
                    'date_start': d0, 'date_end': d1,
                    'amount_in': amount_in,
                    'amount_out_contract': out_contract,
                    'amount_out_direct': direct_per_month,
                    'debt_principal': principal,
                    'debt_interest': interest,
                })
            Line.create(vals)
            # số dư tiền LUỸ KẾ: tiền đợt thu trước được giữ lại để trả
            # nợ các tháng sau — không có bước này thì tháng nào không có
            # đợt nghiệm thu cũng bị chấm là "không trả nổi nợ"
            running = 0.0
            for ln in rec.line_ids:
                running += (ln.cfads or 0.0) - (ln.debt_service or 0.0)
                ln.cash_balance = running
            rec.date_generated = fields.Datetime.now()
            rec.message_post(body=_(
                'Tính lại dòng tiền %(n)s tháng: DSCR toàn kỳ %(o)s, '
                'số tháng thiếu tiền %(s)s, đáy số dư %(b)s.',
                n=n, o=round(rec.dscr_overall, 2), s=rec.month_cash_short,
                b='{:,.0f}'.format(rec.cash_min)))
        return True

    @api.model
    def _get_or_create(self, project):
        rec = self.search([('project_id', '=', project.id)], limit=1)
        if not rec:
            rec = self.create({'project_id': project.id})
        return rec


class ReLoanProjectCashflowLine(models.Model):
    _name = 're.loan.project.cashflow.line'
    _description = 'Dòng tiền dự án theo tháng'
    _order = 'date_start'

    cashflow_id = fields.Many2one(
        're.loan.project.cashflow', required=True, ondelete='cascade',
        index=True)
    project_id = fields.Many2one(
        related='cashflow_id.project_id', store=True, readonly=True)
    currency_id = fields.Many2one(
        related='cashflow_id.currency_id', readonly=True)
    date_start = fields.Date(string='Từ ngày', required=True)
    date_end = fields.Date(string='Đến ngày', required=True)
    period_label = fields.Char(
        string='Tháng', compute='_compute_label', store=True)

    amount_in = fields.Monetary(string='Thu từ CĐT')
    amount_out_contract = fields.Monetary(string='Chi trả thầu phụ/NCC')
    amount_out_direct = fields.Monetary(
        string='Chi phí cấp dự án',
        help='Chưa có ngày đến hạn nên rải ĐỀU trên số tháng dự báo.')
    cfads = fields.Monetary(
        string='CFADS', compute='_compute_dscr', store=True,
        help='Dòng tiền khả dụng để trả nợ = Thu − Chi. KHÔNG gồm tiền '
             'giải ngân vay.')
    debt_principal = fields.Monetary(string='Gốc đến hạn')
    debt_interest = fields.Monetary(string='Lãi đến hạn')
    debt_service = fields.Monetary(
        string='Nghĩa vụ trả nợ', compute='_compute_dscr', store=True)
    dscr = fields.Float(
        string='DSCR tháng', compute='_compute_dscr', store=True,
        digits=(12, 2),
        help='CFADS ÷ nghĩa vụ trả nợ RIÊNG tháng này. Kỳ không có nợ '
             'đến hạn thì để 0 và không tính vào thống kê.')
    cash_balance = fields.Monetary(
        string='Số dư tiền luỹ kế', readonly=True,
        help='= Số dư cuối tháng trước + CFADS tháng này − nợ trả tháng '
             'này. Phản ánh việc tiền thu đợt trước được GIỮ LẠI để trả '
             'nợ các tháng sau. Âm = tháng đó thật sự thiếu tiền.')

    @api.depends('date_start')
    def _compute_label(self):
        for l in self:
            l.period_label = l.date_start.strftime('%m/%Y') if l.date_start \
                else ''

    @api.depends('amount_in', 'amount_out_contract', 'amount_out_direct',
                 'debt_principal', 'debt_interest')
    def _compute_dscr(self):
        for l in self:
            l.cfads = ((l.amount_in or 0.0) - (l.amount_out_contract or 0.0)
                       - (l.amount_out_direct or 0.0))
            l.debt_service = ((l.debt_principal or 0.0)
                              + (l.debt_interest or 0.0))
            l.dscr = (l.cfads / l.debt_service) if l.debt_service else 0.0
