# -*- coding: utf-8 -*-
"""Bảng chỉ tiêu XANH / VÀNG / ĐỎ — tài liệu nghiệp vụ §11.

Bảy chỉ tiêu theo dõi mà tài liệu liệt kê:
  1. Tỷ lệ sử dụng hạn mức
  2. Tỷ lệ dư nợ trên tài sản bảo đảm
  3. Tỷ lệ nợ quá hạn
  4. Tỷ lệ vốn tự có thực góp
  5. Hệ số trả nợ dự báo (DSCR)      ← chờ §8, hiện trả "chưa có dữ liệu"
  6. Mức độ chậm tiến độ (SPI)
  7. Biên lợi nhuận dự báo

Ngưỡng KHÔNG hardcode: mỗi công ty một bản ghi `re.loan.kpi.policy`, sửa
được trong Cấu hình — ngân hàng khác nhau đòi mức khác nhau.

Chiều của chỉ tiêu khác nhau: 1,2,3 CÀNG CAO CÀNG XẤU; 4,5,6,7 CÀNG THẤP
CÀNG XẤU. Vì vậy so ngưỡng phải theo chiều, không so máy móc.
"""
from odoo import _, api, fields, models

GREEN, YELLOW, RED, NA = 'green', 'yellow', 'red', 'na'
STATUS_SEL = [(GREEN, 'Xanh'), (YELLOW, 'Vàng'), (RED, 'Đỏ'),
              (NA, 'Chưa đủ dữ liệu')]


class ReLoanKpiPolicy(models.Model):
    _name = 're.loan.kpi.policy'
    _description = 'Ngưỡng cảnh báo chỉ tiêu (xanh/vàng/đỏ)'

    name = fields.Char(string='Tên bộ ngưỡng', required=True,
                       default='Ngưỡng mặc định')
    company_id = fields.Many2one(
        'res.company', string='Công ty', required=True,
        default=lambda s: s.env.company)
    active = fields.Boolean(default=True)

    # ── nhóm CÀNG CAO CÀNG XẤU: vượt vàng → vàng, vượt đỏ → đỏ ──
    limit_usage_yellow = fields.Float('Sử dụng hạn mức — vàng (%)', default=80.0)
    limit_usage_red = fields.Float('Sử dụng hạn mức — đỏ (%)', default=95.0)
    debt_collateral_yellow = fields.Float('Dư nợ/TSBĐ — vàng (%)', default=80.0)
    debt_collateral_red = fields.Float('Dư nợ/TSBĐ — đỏ (%)', default=100.0)
    overdue_yellow = fields.Float('Nợ quá hạn — vàng (%)', default=0.01)
    overdue_red = fields.Float('Nợ quá hạn — đỏ (%)', default=5.0)

    # ── nhóm CÀNG THẤP CÀNG XẤU: dưới vàng → vàng, dưới đỏ → đỏ ──
    equity_yellow = fields.Float('Vốn tự có thực góp — vàng (%)', default=90.0)
    equity_red = fields.Float('Vốn tự có thực góp — đỏ (%)', default=70.0)
    dscr_yellow = fields.Float('DSCR — vàng (lần)', default=1.2)
    dscr_red = fields.Float('DSCR — đỏ (lần)', default=1.0)
    spi_yellow = fields.Float('Tiến độ (SPI) — vàng (%)', default=95.0)
    spi_red = fields.Float('Tiến độ (SPI) — đỏ (%)', default=85.0)
    margin_yellow = fields.Float('Biên lợi nhuận — vàng (%)', default=5.0)
    margin_red = fields.Float('Biên lợi nhuận — đỏ (%)', default=0.0)

    @api.model
    def _get_policy(self):
        """Bộ ngưỡng của công ty hiện tại; chưa có thì tạo mặc định."""
        pol = self.search([('company_id', '=', self.env.company.id)], limit=1)
        if not pol:
            pol = self.sudo().create(
                {'name': _('Ngưỡng mặc định'),
                 'company_id': self.env.company.id})
        return pol


class ReLoanProjectFundingKpi(models.Model):
    _inherit = 're.loan.project.funding'

    kpi_limit_usage = fields.Float(
        string='① Sử dụng hạn mức (%)', compute='_compute_kpi',
        help='Dư nợ dự án / Hạn mức phân bổ cho dự án. Càng cao càng xấu.')
    kpi_debt_collateral = fields.Float(
        string='② Dư nợ / TSBĐ (%)', compute='_compute_kpi',
        help='Dư nợ dự án / Borrowing base riêng của dự án. Vượt 100% là '
             'margin call — TSBĐ không còn gánh nổi dư nợ.')
    kpi_overdue = fields.Float(
        string='③ Nợ quá hạn (%)', compute='_compute_kpi',
        help='Dư nợ các khế ước QUÁ HẠN của dự án / tổng dư nợ dự án.')
    kpi_equity = fields.Float(
        string='④ Vốn tự có thực góp (%)', compute='_compute_kpi',
        help='Đã góp (tiền + hiện vật) / Phải góp. Càng thấp càng xấu.')
    kpi_dscr = fields.Float(
        string='⑤ Hệ số trả nợ (DSCR)', compute='_compute_kpi',
        digits=(12, 2),
        help='DSCR TOÀN KỲ trong bảng Dòng tiền dự án = Σ CFADS ÷ Σ '
             'nghĩa vụ trả nợ. Chưa lập bảng dòng tiền thì để trống thay '
             'vì tô xanh giả.')
    kpi_spi = fields.Float(
        string='⑥ Tiến độ SPI (%)', compute='_compute_kpi',
        help='Giá trị làm ra (EV) / Giá trị kế hoạch đến hôm nay (PV). '
             'Dưới 100% là chậm tiến độ.')
    kpi_margin = fields.Float(
        string='⑦ Biên lợi nhuận dự báo (%)', compute='_compute_kpi',
        help='(Giá trị HĐ với CĐT − Dự báo chi phí cuối kỳ EAC) / Giá trị '
             'HĐ với CĐT.')

    kpi_limit_usage_state = fields.Selection(
        STATUS_SEL, compute='_compute_kpi', string='TT ①')
    kpi_debt_collateral_state = fields.Selection(
        STATUS_SEL, compute='_compute_kpi', string='TT ②')
    kpi_overdue_state = fields.Selection(
        STATUS_SEL, compute='_compute_kpi', string='TT ③')
    kpi_equity_state = fields.Selection(
        STATUS_SEL, compute='_compute_kpi', string='TT ④')
    kpi_dscr_state = fields.Selection(
        STATUS_SEL, compute='_compute_kpi', string='TT ⑤')
    kpi_spi_state = fields.Selection(
        STATUS_SEL, compute='_compute_kpi', string='TT ⑥')
    kpi_margin_state = fields.Selection(
        STATUS_SEL, compute='_compute_kpi', string='TT ⑦')
    # Hai field tổng hợp KHÔNG store, dù mất khả năng sắp xếp phía máy
    # chủ: 14 chỉ tiêu kia đều không lưu, trộn lưu/không lưu trong cùng
    # một compute làm Odoo cảnh báo "đọc field không lưu có thể GHI field
    # lưu" — chỉ MỞ bảng chỉ tiêu cũng sinh ghi DB, nhiều người mở cùng
    # lúc là đụng lỗi cập nhật đồng thời. Bảng này mỗi dự án một dòng nên
    # đổi lại bằng lọc/tô màu là đủ.
    kpi_overall_state = fields.Selection(
        STATUS_SEL, compute='_compute_kpi', string='Tổng thể',
        help='Xấu nhất trong các chỉ tiêu có dữ liệu — một chỉ tiêu đỏ là '
             'cả dự án đỏ.')
    kpi_red_count = fields.Integer(
        string='Số chỉ tiêu đỏ', compute='_compute_kpi')

    @staticmethod
    def _grade(value, yellow, red, higher_is_worse):
        if value is None:
            return NA
        if higher_is_worse:
            if value >= red:
                return RED
            return YELLOW if value >= yellow else GREEN
        if value <= red:
            return RED
        return YELLOW if value <= yellow else GREEN

    @api.depends('limit_used', 'limit_allocated', 'equity_required',
                 'equity_contributed_total', 'project_id')
    def _compute_kpi(self):
        pol = self.env['re.loan.kpi.policy']._get_policy()
        Note = self.env['re.loan.note']
        Alloc = self.env['re.loan.facility.project.allocation']
        for r in self:
            p = r.project_id
            # ① sử dụng hạn mức
            r.kpi_limit_usage = ((r.limit_used / r.limit_allocated * 100.0)
                                 if r.limit_allocated else 0.0)
            # ② dư nợ / TSBĐ riêng dự án
            bb = sum(Alloc.search([('project_id', '=', p.id)]).mapped(
                'borrowing_base_project')) if p else 0.0
            r.kpi_debt_collateral = ((r.limit_used / bb * 100.0)
                                     if bb else 0.0)
            # ③ nợ quá hạn
            od = 0.0
            if p:
                for n in Note.search([('state', 'not in',
                                       ('draft', 'cancelled', 'fully_paid'))]):
                    if n.is_overdue:
                        od += n._outstanding_by_project().get(p.id, 0.0)
            r.kpi_overdue = ((od / r.limit_used * 100.0)
                             if r.limit_used else 0.0)
            # ④ vốn tự có
            r.kpi_equity = ((r.equity_contributed_total / r.equity_required
                             * 100.0) if r.equity_required else 100.0)
            # ⑤ DSCR TOÀN KỲ từ bảng dòng tiền dự án (§8) — KHÔNG lấy
            # tháng thấp nhất: tiền xây lắp về theo đợt nghiệm thu nên
            # tháng không có đợt thu luôn âm, lấy min thì dự án nào cũng
            # đỏ. Rủi ro thanh khoản tháng đã có "số tháng thiếu tiền".
            cf = self.env['re.loan.project.cashflow'].search(
                [('project_id', '=', p.id)], limit=1) if p else None
            has_cf = bool(cf and cf.line_ids and cf.total_debt_service)
            r.kpi_dscr = cf.dscr_overall if has_cf else 0.0
            # ⑥ SPI
            pv = getattr(p, 'total_pv_today', 0.0) or 0.0
            r.kpi_spi = ((p.total_ev / pv * 100.0) if pv else 0.0)
            # ⑦ biên lợi nhuận dự báo
            rev = 0.0
            if p:
                rev = sum(self.env['rp.owner.contract'].search(
                    [('project_id', '=', p.id)]).mapped('contract_value_total'))
            eac = getattr(p, 'project_eac', 0.0) or 0.0
            r.kpi_margin = ((rev - eac) / rev * 100.0) if rev else 0.0

            g = self._grade
            r.kpi_limit_usage_state = g(
                r.kpi_limit_usage, pol.limit_usage_yellow,
                pol.limit_usage_red, True)
            r.kpi_debt_collateral_state = g(
                r.kpi_debt_collateral, pol.debt_collateral_yellow,
                pol.debt_collateral_red, True) if bb else NA
            r.kpi_overdue_state = g(
                r.kpi_overdue, pol.overdue_yellow, pol.overdue_red, True)
            r.kpi_equity_state = g(
                r.kpi_equity, pol.equity_yellow, pol.equity_red, False)
            r.kpi_dscr_state = g(
                r.kpi_dscr, pol.dscr_yellow, pol.dscr_red,
                False) if has_cf else NA
            r.kpi_spi_state = g(
                r.kpi_spi, pol.spi_yellow, pol.spi_red, False) if pv else NA
            r.kpi_margin_state = g(
                r.kpi_margin, pol.margin_yellow, pol.margin_red,
                False) if rev else NA

            states = [r.kpi_limit_usage_state, r.kpi_debt_collateral_state,
                      r.kpi_overdue_state, r.kpi_equity_state,
                      r.kpi_dscr_state, r.kpi_spi_state, r.kpi_margin_state]
            live = [s for s in states if s != NA]
            r.kpi_red_count = live.count(RED)
            r.kpi_overall_state = (
                RED if RED in live else
                YELLOW if YELLOW in live else
                GREEN if live else NA)
