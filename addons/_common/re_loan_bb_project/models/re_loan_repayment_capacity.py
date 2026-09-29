# -*- coding: utf-8 -*-
"""Năng lực trả nợ — 5 tín hiệu chặn giải ngân của tài liệu nghiệp vụ §8.

Nguyên văn: "Không giải ngân mới nếu:
  ① Dòng tiền dự báo không đủ trả nợ.
  ② Chủ đầu tư không có nguồn thanh toán rõ ràng.
  ③ Công trình chậm tiến độ nghiêm trọng.
  ④ Dự án đang lỗ mà chưa có phương án bù đắp.
  ⑤ Hệ số trả nợ dưới ngưỡng cho phép."

Anh Đại chốt 2026-08-11: **cảnh báo mềm, KHÔNG chặn** — cả 5 tín hiệu đều
là số DỰ BÁO, chặn cứng theo dự báo dễ kẹt vận hành. Người duyệt tự cân.
Vì vậy không tín hiệu nào vào `_checklist_failures()` (nơi chặn thật của
§7); chúng chỉ tô đỏ và giải thích.

Vì sao ① và ⑤ KHÔNG trùng nhau — chúng bắt hai kiểu hỏng khác nhau:
  ① LỆCH PHA thanh khoản: có tháng số dư tiền luỹ kế ÂM, dù cả kỳ vẫn
     thừa tiền trả nợ. Đây là "đến hạn mà trong két không có tiền".
  ⑤ Cả kỳ KHÔNG ĐỦ: DSCR toàn kỳ dưới ngưỡng chính sách NH. Đây là
     "làm xong dự án vẫn không trả nổi".
Một dự án có thể dính ① mà không dính ⑤ (BVABC là ca đó) và ngược lại.

Tín hiệu ② cần cả KHAI BÁO lẫn BẰNG CHỨNG:
  - khai báo: nguồn vốn của CĐT trên HĐ (vốn tự có / vay NH có cam kết
    cấp vốn / ngân sách / hỗn hợp / chưa rõ);
  - bằng chứng: mốc thu đã quá hạn bao lâu mà CĐT chưa trả.
Chỉ khai báo thì thành hình thức; chỉ đo chậm trả thì bắt hụt CĐT mới
chưa phát sinh đợt thu nào.
"""
from odoo import _, api, fields, models

CAP_SEL = [('ok', 'Đạt'), ('warn', 'CẢNH BÁO'),
           ('na', 'Chưa đủ dữ liệu')]

OWNER_FUNDING_SOURCES = [
    ('own', 'Vốn tự có của CĐT'),
    ('bank', 'Vốn vay NH — đã có cam kết cấp vốn'),
    ('budget', 'Vốn ngân sách / đầu tư công'),
    ('mixed', 'Hỗn hợp'),
    ('unclear', 'CHƯA RÕ'),
]


class ReLoanKpiPolicyCapacity(models.Model):
    _inherit = 're.loan.kpi.policy'

    owner_overdue_days = fields.Integer(
        string='CĐT chậm trả — số ngày báo động', default=60,
        help='Mốc thu từ CĐT quá hạn quá số ngày này thì coi là "nguồn '
             'thanh toán của CĐT không rõ ràng" (§8 ②).')


class RpOwnerContractFundingSource(models.Model):
    """Nguồn tiền mà CĐT lấy ra để trả cho mình (§8 ②)."""
    _inherit = 'rp.owner.contract'

    owner_funding_source = fields.Selection(
        OWNER_FUNDING_SOURCES, string='Nguồn thanh toán của CĐT',
        tracking=True,
        help='CĐT lấy tiền ở đâu ra để trả cho mình. Bỏ trống hoặc '
             '"CHƯA RÕ" sẽ bật cảnh báo §8 ② khi đề xuất giải ngân.')
    owner_funding_note = fields.Char(
        string='Diễn giải nguồn thanh toán',
        help='Ví dụ: số thư cam kết cấp tín dụng của NH tài trợ CĐT, '
             'quyết định giao vốn, nghị quyết HĐQT bố trí vốn.')
    owner_overdue_amount = fields.Monetary(
        string='Mốc thu quá hạn', compute='_compute_owner_overdue',
        help='Tổng tiền các mốc thu đã tới hạn mà CĐT chưa thanh toán.')
    owner_overdue_days_max = fields.Integer(
        string='Quá hạn lâu nhất (ngày)', compute='_compute_owner_overdue')

    @api.depends('milestone_ids.due_date', 'milestone_ids.state',
                 'milestone_ids.amount', 'milestone_ids.amount_received')
    def _compute_owner_overdue(self):
        today = fields.Date.context_today(self)
        for rec in self:
            amt = 0.0
            days = 0
            for ms in rec.milestone_ids:
                if not ms.due_date or ms.due_date >= today:
                    continue
                if ms.state in ('received', 'cancelled'):
                    continue
                left = (ms.amount or 0.0) - (ms.amount_received or 0.0)
                if left <= 0:
                    continue
                amt += left
                days = max(days, (today - ms.due_date).days)
            rec.owner_overdue_amount = amt
            rec.owner_overdue_days_max = days


class ReLoanProjectFundingLossPlan(models.Model):
    """Phương án bù đắp khi dự án dự báo LỖ (§8 ④)."""
    _inherit = 're.loan.project.funding'

    loss_plan_confirmed = fields.Boolean(
        string='Đã có phương án bù đắp lỗ', tracking=True,
        help='Tick khi dự án dự báo lỗ NHƯNG đã có phương án xử lý được '
             'duyệt (đàm phán phụ lục tăng giá, cắt giảm phạm vi, bù từ '
             'dự án khác, CĐT hỗ trợ...). Chưa tick mà biên lợi nhuận âm '
             'thì bật cảnh báo §8 ④.')
    loss_plan = fields.Text(
        string='Nội dung phương án bù đắp',
        help='Ghi rõ làm gì, ai duyệt, khi nào có hiệu lực.')


class ReLoanNoteRepaymentCapacity(models.Model):
    _inherit = 're.loan.note'

    cap_cashflow = fields.Selection(
        CAP_SEL, string='① Dòng tiền đủ trả nợ',
        compute='_compute_capacity',
        help='Bảng Dòng tiền dự án có tháng nào SỐ DƯ TIỀN LUỸ KẾ ÂM '
             'không — tức đến hạn mà trong két không có tiền, dù cả kỳ '
             'vẫn thừa.')
    cap_owner_source = fields.Selection(
        CAP_SEL, string='② CĐT có nguồn thanh toán rõ ràng',
        compute='_compute_capacity',
        help='Đỏ khi HĐ với CĐT chưa khai nguồn thanh toán (hoặc khai '
             '"CHƯA RÕ"), hoặc CĐT đang để mốc thu quá hạn lâu hơn ngưỡng '
             'trong Ngưỡng cảnh báo chỉ tiêu.')
    cap_schedule = fields.Selection(
        CAP_SEL, string='③ Tiến độ không chậm nghiêm trọng',
        compute='_compute_capacity',
        help='SPI = giá trị làm ra (EV) / giá trị kế hoạch đến hôm nay '
             '(PV), so với ngưỡng ĐỎ của chỉ tiêu ⑥.')
    cap_profit = fields.Selection(
        CAP_SEL, string='④ Không lỗ (hoặc lỗ đã có phương án)',
        compute='_compute_capacity',
        help='Biên lợi nhuận dự báo = (giá trị HĐ với CĐT − dự báo chi '
             'phí cuối kỳ EAC). Âm mà phiếu Nhu cầu vốn chưa tick '
             '"đã có phương án bù đắp lỗ" thì đỏ.')
    cap_dscr = fields.Selection(
        CAP_SEL, string='⑤ DSCR đạt ngưỡng',
        compute='_compute_capacity',
        help='DSCR TOÀN KỲ so với ngưỡng đỏ trong Ngưỡng cảnh báo chỉ '
             'tiêu (mặc định 1,0 lần).')

    cap_dscr_value = fields.Float(
        string='DSCR toàn kỳ', compute='_compute_capacity', digits=(12, 2))
    cap_warning_count = fields.Integer(
        string='Số tín hiệu đỏ (§8)', compute='_compute_capacity')
    cap_state = fields.Selection(
        CAP_SEL, string='Năng lực trả nợ', compute='_compute_capacity')
    cap_message = fields.Text(
        string='Diễn giải cảnh báo', compute='_compute_capacity')

    @api.depends('project_id', 'facility_id', 'state')
    def _compute_capacity(self):
        pol = self.env['re.loan.kpi.policy']._get_policy()
        Cashflow = self.env['re.loan.project.cashflow']
        Funding = self.env['re.loan.project.funding']
        Owner = self.env['rp.owner.contract']
        for rec in self:
            p = rec.project_id
            if not p:
                rec.update({
                    'cap_cashflow': 'na', 'cap_owner_source': 'na',
                    'cap_schedule': 'na', 'cap_profit': 'na',
                    'cap_dscr': 'na', 'cap_dscr_value': 0.0,
                    'cap_warning_count': 0, 'cap_state': 'na',
                    'cap_message': False})
                continue
            msgs = []

            # ① lệch pha thanh khoản
            cf = Cashflow.search([('project_id', '=', p.id)], limit=1)
            has_cf = bool(cf and cf.line_ids and cf.total_debt_service)
            if not has_cf:
                rec.cap_cashflow = 'na'
            elif cf.month_cash_short:
                rec.cap_cashflow = 'warn'
                msgs.append(_(
                    '① %(n)s tháng số dư tiền luỹ kế ÂM (đáy %(b)s) — đến '
                    'hạn trả nợ mà chưa có tiền về.',
                    n=cf.month_cash_short,
                    b='{:,.0f}'.format(cf.cash_min)))
            else:
                rec.cap_cashflow = 'ok'

            # ② nguồn thanh toán của CĐT
            contracts = Owner.search(
                [('project_id', '=', p.id),
                 ('state', 'in', ('signed', 'executing'))])
            if not contracts:
                rec.cap_owner_source = 'na'
            else:
                blank = contracts.filtered(
                    lambda c: c.owner_funding_source in (False, 'unclear'))
                late = contracts.filtered(
                    lambda c: c.owner_overdue_days_max
                    > (pol.owner_overdue_days or 0)
                    and c.owner_overdue_amount > 0)
                if blank or late:
                    rec.cap_owner_source = 'warn'
                    if blank:
                        msgs.append(_(
                            '② %(n)s hợp đồng với CĐT chưa khai nguồn '
                            'thanh toán (hoặc khai CHƯA RÕ).',
                            n=len(blank)))
                    if late:
                        msgs.append(_(
                            '② CĐT đang nợ quá hạn %(a)s, chậm nhất '
                            '%(d)s ngày (ngưỡng %(t)s).',
                            a='{:,.0f}'.format(
                                sum(late.mapped('owner_overdue_amount'))),
                            d=max(late.mapped('owner_overdue_days_max')),
                            t=pol.owner_overdue_days))
                else:
                    rec.cap_owner_source = 'ok'

            # ③ tiến độ
            pv = p.total_pv_today or 0.0
            if not pv:
                rec.cap_schedule = 'na'
            else:
                spi = (p.total_ev or 0.0) / pv * 100.0
                if spi < (pol.spi_red or 0.0):
                    rec.cap_schedule = 'warn'
                    msgs.append(_(
                        '③ Tiến độ SPI %(s).1f%% dưới ngưỡng đỏ %(r).1f%% '
                        '— chậm tiến độ nghiêm trọng.',
                        s=spi, r=pol.spi_red))
                else:
                    rec.cap_schedule = 'ok'

            # ④ lỗ chưa có phương án
            rev = sum(Owner.search(
                [('project_id', '=', p.id)]).mapped('contract_value_total'))
            eac = p.project_eac or 0.0
            sheet = Funding.search([('project_id', '=', p.id)], limit=1)
            if not rev:
                rec.cap_profit = 'na'
            elif (rev - eac) < 0 and not (sheet and sheet.loss_plan_confirmed):
                rec.cap_profit = 'warn'
                msgs.append(_(
                    '④ Dự báo LỖ %(l)s (HĐ CĐT %(r)s − EAC %(e)s) mà '
                    'phiếu Nhu cầu vốn chưa xác nhận phương án bù đắp.',
                    l='{:,.0f}'.format(eac - rev),
                    r='{:,.0f}'.format(rev), e='{:,.0f}'.format(eac)))
            else:
                rec.cap_profit = 'ok'

            # ⑤ DSCR toàn kỳ so ngưỡng chính sách
            rec.cap_dscr_value = cf.dscr_overall if has_cf else 0.0
            if not has_cf:
                rec.cap_dscr = 'na'
            elif cf.dscr_overall < (pol.dscr_red or 0.0):
                rec.cap_dscr = 'warn'
                msgs.append(_(
                    '⑤ DSCR toàn kỳ %(v).2f dưới ngưỡng cho phép %(r).2f.',
                    v=cf.dscr_overall, r=pol.dscr_red))
            else:
                rec.cap_dscr = 'ok'

            signals = [rec.cap_cashflow, rec.cap_owner_source,
                       rec.cap_schedule, rec.cap_profit, rec.cap_dscr]
            rec.cap_warning_count = signals.count('warn')
            live = [s for s in signals if s != 'na']
            rec.cap_state = ('warn' if 'warn' in live
                             else 'ok' if live else 'na')
            rec.cap_message = '\n'.join(msgs) or False
