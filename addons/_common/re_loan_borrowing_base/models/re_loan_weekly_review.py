# -*- coding: utf-8 -*-
"""Vòng vận hành hàng tuần — tài liệu nghiệp vụ §10.

Bảy bước tài liệu liệt kê, chia làm ba loại việc khác hẳn nhau:

  NGƯỜI LÀM (1-3) — cập nhật hợp đồng/tiến độ/chi phí, nghiệm thu → hồ sơ
    thanh toán trình CĐT ký, dư nợ/giải ngân/trả nợ/bảo lãnh.
    Máy KHÔNG làm thay được, nhưng ĐO ĐƯỢC tuần này có động hay không.
    Cột "đã cập nhật" ở đây là số chứng từ phát sinh trong tuần — tuần
    nào về 0 hết là dấu hiệu quên cập nhật, không phải lỗi hệ thống.

  MÁY LÀM (4-5) — định giá lại TSBĐ theo sản lượng mới, tính lại dòng
    tiền/khả dụng. Nút "Tính lại" và cron sáng thứ Hai.

  QUẢN LÝ QUYẾT (6-7) — rà ngoại lệ rồi ra quyết định trên từng ca.

Bốn loại ngoại lệ §10 nêu đích danh: âm dòng tiền · thiếu vốn tự có ·
nợ quá hạn · vượt hạn mức.

Bước 7 ở đây chỉ GHI NHẬN quyết định (ai, khi nào, làm gì) — luồng phê
duyệt 5 cấp của §11 anh Đại đã hoãn tới lúc triển khai, đừng dựng ở đây.
"""
from dateutil.relativedelta import relativedelta
from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError

EXC_KINDS = [
    ('cashflow', 'Âm dòng tiền'),
    ('equity', 'Thiếu vốn tự có'),
    ('overdue', 'Nợ quá hạn'),
    ('over_limit', 'Vượt hạn mức / thiếu bảo đảm'),
]

DECISIONS = [
    ('disburse', 'Vẫn giải ngân'),
    ('reallocate', 'Điều chuyển hạn mức'),
    ('more_collateral', 'Yêu cầu bổ sung tài sản bảo đảm'),
    ('stop', 'Dừng tài trợ'),
    ('watch', 'Theo dõi tiếp'),
]


class ReLoanWeeklyReview(models.Model):
    _name = 're.loan.weekly.review'
    _description = 'Phiên rà soát tuần (§10)'
    _inherit = ['mail.thread']
    _order = 'date_from desc'

    name = fields.Char(string='Kỳ rà soát', compute='_compute_name',
                       store=True)
    date_from = fields.Date(string='Từ ngày', required=True,
                            default=lambda s: s._default_monday())
    date_to = fields.Date(string='Đến ngày', required=True,
                          default=lambda s: s._default_monday()
                          + relativedelta(days=6))
    company_id = fields.Many2one(
        'res.company', string='Công ty', required=True,
        default=lambda s: s.env.company)
    state = fields.Selection(
        [('draft', 'Đang rà'), ('done', 'Đã chốt')],
        string='Trạng thái', default='draft', required=True, tracking=True)

    # ── bước 1-3: người cập nhật, máy chỉ ĐO ──
    upd_contract_count = fields.Integer(
        string='HĐ có cập nhật', compute='_compute_activity',
        help='Hợp đồng với CĐT + hợp đồng nhà thầu được sửa trong tuần.')
    upd_progress_count = fields.Integer(
        string='Nghiệm thu nội bộ', compute='_compute_activity',
        help='Biên bản nghiệm thu khối lượng lập trong tuần.')
    upd_ipc_count = fields.Integer(
        string='Hồ sơ thanh toán (IPC)', compute='_compute_activity',
        help='IPC trình CĐT lập trong tuần.')
    upd_disbursement_count = fields.Integer(
        string='Đợt giải ngân', compute='_compute_activity')
    upd_repayment_count = fields.Integer(
        string='Đợt trả nợ', compute='_compute_activity')
    upd_guarantee_count = fields.Integer(
        string='Bảo lãnh', compute='_compute_activity')
    activity_warning = fields.Char(
        string='Nhắc cập nhật', compute='_compute_activity')

    # ── bước 4-5: máy tính lại ──
    date_recomputed = fields.Datetime(string='Tính lại lúc', readonly=True)
    recompute_log = fields.Text(string='Kết quả tính lại', readonly=True)

    # ── bước 6-7 ──
    exception_ids = fields.One2many(
        're.loan.weekly.exception', 'review_id', string='Ngoại lệ')
    exception_count = fields.Integer(
        string='Số ngoại lệ', compute='_compute_exception_stats',
        store=True)
    exception_open = fields.Integer(
        string='Chưa quyết', compute='_compute_exception_stats', store=True)
    note = fields.Text(string='Kết luận phiên rà soát')

    _uniq_week = models.Constraint(
        'unique(company_id, date_from)',
        'Mỗi công ty chỉ có một phiên rà soát cho một tuần.')

    @api.model
    def _default_monday(self):
        today = fields.Date.context_today(self)
        return today - relativedelta(days=today.weekday())

    @api.depends('date_from', 'date_to')
    def _compute_name(self):
        for rec in self:
            if rec.date_from:
                iso = rec.date_from.isocalendar()
                rec.name = _('Tuần %(w)s/%(y)s (%(a)s → %(b)s)',
                             w=iso[1], y=iso[0],
                             a=rec.date_from.strftime('%d/%m'),
                             b=(rec.date_to or rec.date_from).strftime(
                                 '%d/%m'))
            else:
                rec.name = _('Phiên rà soát')

    @api.depends('exception_ids.decision')
    def _compute_exception_stats(self):
        for rec in self:
            rec.exception_count = len(rec.exception_ids)
            rec.exception_open = len(
                rec.exception_ids.filtered(lambda e: not e.decision))

    def _count_between(self, model, date_field='create_date'):
        """Đếm bản ghi phát sinh trong tuần; model chưa cài thì trả 0."""
        self.ensure_one()
        if model not in self.env:
            return 0
        start = fields.Datetime.to_datetime(self.date_from)
        end = fields.Datetime.to_datetime(
            self.date_to + relativedelta(days=1))
        return self.env[model].search_count([
            (date_field, '>=', start), (date_field, '<', end)])

    @api.depends('date_from', 'date_to')
    def _compute_activity(self):
        for rec in self:
            rec.upd_contract_count = (
                rec._count_between('rp.owner.contract', 'write_date')
                + rec._count_between('rp.contract', 'write_date'))
            rec.upd_progress_count = rec._count_between(
                'rp.progress.acceptance')
            rec.upd_ipc_count = rec._count_between('rp.owner.ipc')
            rec.upd_disbursement_count = rec._count_between(
                're.loan.note.disbursement')
            rec.upd_repayment_count = rec._count_between(
                're.loan.note.repayment')
            rec.upd_guarantee_count = rec._count_between('re.bank.guarantee')
            silent = []
            if not rec.upd_contract_count:
                silent.append(_('hợp đồng/tiến độ/chi phí'))
            if not (rec.upd_progress_count or rec.upd_ipc_count):
                silent.append(_('nghiệm thu & hồ sơ thanh toán'))
            if not (rec.upd_disbursement_count or rec.upd_repayment_count
                    or rec.upd_guarantee_count):
                silent.append(_('dư nợ/giải ngân/trả nợ/bảo lãnh'))
            rec.activity_warning = (
                _('Tuần này KHÔNG có cập nhật: %s — số liệu rà soát bên '
                  'dưới đang dựa trên dữ liệu tuần trước.',
                  ', '.join(silent)) if silent else False)

    # ------------------------------------------------------------------
    def action_recompute(self):
        """Bước 4-5: định giá lại TSBĐ rồi tính lại dòng tiền dự án."""
        Col = self.env['re.loan.collateral']
        Cashflow = self.env['re.loan.project.cashflow']
        for rec in self:
            cols = Col.search(['|', ('owner_ipc_id', '!=', False),
                               ('owner_contract_id', '!=', False)])
            cols._sync_receivable_valuation(
                reason=_('Rà soát tuần %s') % rec.name)
            flows = Cashflow.search([])
            flows.action_generate()
            self.env.invalidate_all()
            rec.date_recomputed = fields.Datetime.now()
            rec.recompute_log = _(
                'Định giá lại %(c)s tài sản quyền đòi nợ.\n'
                'Tính lại %(f)s bảng dòng tiền dự án.\n'
                'Khả dụng theo dự án/facility/HĐTD tính động khi mở — '
                'không cần lưu.',
                c=len(cols), f=len(flows))
        return True

    def action_scan_exceptions(self):
        """Bước 6: rà bốn loại ngoại lệ §10."""
        Exc = self.env['re.loan.weekly.exception']
        Funding = self.env['re.loan.project.funding']
        Note = self.env['re.loan.note']
        Fac = self.env['re.loan.facility']
        Cc = self.env['re.loan.credit.contract']
        Cashflow = self.env['re.loan.project.cashflow']
        for rec in self:
            # giữ lại các ca ĐÃ có quyết định, chỉ quét lại phần chưa quyết
            rec.exception_ids.filtered(lambda e: not e.decision).unlink()
            decided = {(e.kind, e.res_model, e.res_id)
                       for e in rec.exception_ids}
            vals = []

            def add(kind, model, rid, label, amount, detail):
                if (kind, model, rid) in decided:
                    return
                vals.append({
                    'review_id': rec.id, 'kind': kind,
                    'res_model': model, 'res_id': rid,
                    'name': label, 'amount': amount, 'detail': detail})

            # ① âm dòng tiền
            for cf in Cashflow.search([]):
                if cf.month_cash_short:
                    add('cashflow', 're.loan.project.cashflow', cf.id,
                        cf.project_id.display_name, abs(cf.cash_min),
                        _('%(n)s tháng số dư tiền luỹ kế âm, đáy %(b)s; '
                          'DSCR toàn kỳ %(d).2f.',
                          n=cf.month_cash_short,
                          b='{:,.0f}'.format(cf.cash_min),
                          d=cf.dscr_overall))
            # ② thiếu vốn tự có
            for f in Funding.search([]):
                if f.equity_shortfall > 0.01:
                    add('equity', 're.loan.project.funding', f.id,
                        f.project_id.display_name, f.equity_shortfall,
                        _('Phải góp %(r)s, đã góp %(c)s.',
                          r='{:,.0f}'.format(f.equity_required),
                          c='{:,.0f}'.format(f.equity_contributed_total)))
            # ③ nợ quá hạn
            for n in Note.search([('state', '=', 'overdue')]):
                add('overdue', 're.loan.note', n.id, n.name,
                    n.principal_outstanding,
                    _('KW quá hạn, dư nợ gốc %(o)s%(p)s.',
                      o='{:,.0f}'.format(n.principal_outstanding),
                      p=(_(' — dự án %s') % n.project_id.display_name)
                      if n.project_id else ''))
            # ④ vượt hạn mức / thiếu bảo đảm
            # `margin_call` là field TÍNH ĐỘNG không lưu → không lọc được
            # bằng domain, phải duyệt trong Python.
            for fac in Fac.search([]):
                if fac.margin_call:
                    add('over_limit', 're.loan.facility', fac.id,
                        fac.display_name, fac.amount_used,
                        _('Dư nợ vượt cơ sở bảo đảm riêng của facility.'))
            for cc in Cc.search([]):
                if cc.margin_call:
                    add('over_limit', 're.loan.credit.contract', cc.id,
                        cc.display_name, cc.amount_used_total,
                        _('Dư nợ toàn HĐTD vượt cơ sở bảo đảm tổng.'))

            Exc.create(vals)
            rec.message_post(body=_(
                'Rà soát: %(n)s ngoại lệ mới, %(k)s ca đã có quyết định '
                'giữ nguyên.', n=len(vals), k=len(decided)))
        return True

    def action_run_week(self):
        """Chạy trọn bước 4-5-6 trong một nút."""
        self.action_recompute()
        self.action_scan_exceptions()
        return True

    def action_done(self):
        for rec in self:
            if rec.exception_open:
                raise UserError(_(
                    'Còn %(n)s ngoại lệ chưa có quyết định của cấp quản '
                    'lý (§10 bước 7). Chọn quyết định cho từng ca rồi '
                    'chốt phiên.', n=rec.exception_open))
            rec.state = 'done'
        return True

    def action_reopen(self):
        self.write({'state': 'draft'})
        return True

    @api.model
    def _cron_weekly_review(self):
        """Sáng thứ Hai: mở phiên tuần mới, tính lại và rà ngoại lệ sẵn."""
        for company in self.env['res.company'].search([]):
            monday = self.with_company(company)._default_monday()
            rec = self.search([('company_id', '=', company.id),
                               ('date_from', '=', monday)], limit=1)
            if not rec:
                rec = self.create({
                    'company_id': company.id, 'date_from': monday,
                    'date_to': monday + relativedelta(days=6)})
            rec.action_run_week()
        return True


class ReLoanWeeklyException(models.Model):
    _name = 're.loan.weekly.exception'
    _description = 'Ngoại lệ cần xử trong tuần (§10)'
    _order = 'kind, amount desc'

    review_id = fields.Many2one(
        're.loan.weekly.review', required=True, ondelete='cascade',
        index=True)
    company_id = fields.Many2one(
        related='review_id.company_id', store=True, readonly=True)
    currency_id = fields.Many2one(
        related='company_id.currency_id', readonly=True)
    kind = fields.Selection(EXC_KINDS, string='Loại', required=True)
    name = fields.Char(string='Đối tượng', required=True)
    amount = fields.Monetary(string='Số tiền liên quan')
    detail = fields.Char(string='Diễn giải')
    res_model = fields.Char(string='Model', required=True)
    res_id = fields.Integer(string='ID bản ghi', required=True)

    decision = fields.Selection(
        DECISIONS, string='Quyết định',
        help='Bước 7 §10 — cấp quản lý quyết. Bỏ trống = chưa xử; phiên '
             'rà soát không chốt được khi còn ca chưa quyết.')
    decision_note = fields.Char(string='Lý do / chỉ đạo')
    decision_uid = fields.Many2one(
        'res.users', string='Người quyết', readonly=True)
    decision_date = fields.Datetime(string='Ngày quyết', readonly=True)

    def write(self, vals):
        if vals.get('decision'):
            vals.setdefault('decision_uid', self.env.uid)
            vals.setdefault('decision_date', fields.Datetime.now())
        res = super().write(vals)
        if vals.get('decision'):
            # Ghi vết vào chatter của PHIÊN RÀ SOÁT: model dòng này không
            # kế thừa mail.thread nên `tracking=True` sẽ bị Odoo bỏ qua
            # âm thầm — tưởng có vết audit mà không có.
            labels = dict(DECISIONS)
            for ln in self:
                # Markup: thiếu thì message_post escape thẻ HTML, chatter
                # hiện ra chữ &lt;b&gt; thay vì in đậm.
                ln.review_id.message_post(body=Markup(_(
                    'Quyết định <b>%(d)s</b> cho ngoại lệ [%(k)s] '
                    '%(n)s%(note)s',
                    d=labels.get(ln.decision, ln.decision),
                    k=dict(EXC_KINDS).get(ln.kind, ln.kind),
                    n=ln.name,
                    note=(' — %s' % ln.decision_note)
                    if ln.decision_note else '')))
        return res

    def action_open_record(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': self.res_model,
            'res_id': self.res_id,
            'view_mode': 'form',
            'target': 'current',
        }
