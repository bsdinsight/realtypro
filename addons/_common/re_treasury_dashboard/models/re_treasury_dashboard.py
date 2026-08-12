# -*- coding: utf-8 -*-
"""Dashboard Vốn & Ngân quỹ — 3 màn theo 3 vai người dùng.

Hiện thực bản thiết kế "RealtyPro Dashboard Von Ngan Quy". Chia màn theo
AI MỞ NÓ MỖI SÁNG chứ không theo module:

  ① Bức tranh vốn      — giám đốc tài chính
  ② Việc hôm nay       — cán bộ vay / kế toán
  ③ Vốn theo dự án     — chỉ huy trưởng / ban TGĐ

Vì sao dựng HTML từ máy chủ thay vì làm component: Odoo Community không
có tầng dashboard dựng sẵn, và cả bộ RealtyPro đang theo lối sinh
HTML/SVG từ Python rồi nhúng vào form (re_loan_dashboard, re_cashflow).
Bám theo lối đó thì không cần thêm asset bundle, không phụ thuộc thư
viện ngoài, và in ra PDF được ngay bằng chức năng in của trình duyệt.

Hai chỗ tương tác được giữ mà không cần JavaScript:
  • đổi tab — nút thật trên header của form, Odoo tự nạp lại;
  • mở rộng thẻ dự án — thẻ <details> của HTML thuần.
"""
from dateutil.relativedelta import relativedelta
from markupsafe import Markup, escape

from odoo import _, api, fields, models

from . import dc_render as R


class ReTreasuryDashboard(models.TransientModel):
    _name = 're.treasury.dashboard'
    _description = 'Dashboard Vốn & Ngân quỹ'
    # TransientModel + act_window: menu KHÔNG dùng được ir.actions.server
    # — router /odoo/action-<id> của Odoo 19 không mở nổi action kiểu
    # server, bấm menu ra trang trắng. act_window mở form rỗng, bản ghi
    # tạm tự sinh và compute tự điền.

    name = fields.Char(default='Vốn & Ngân quỹ', readonly=True)
    tab = fields.Selection(
        [('1', '① Bức tranh vốn'),
         ('2', '② Việc hôm nay'),
         ('3', '③ Vốn theo dự án')],
        string='Màn hình', default='1', required=True)
    company_id = fields.Many2one(
        'res.company', string='Công ty', required=True,
        default=lambda s: s.env.company)
    currency_id = fields.Many2one(
        related='company_id.currency_id', readonly=True)
    body_html = fields.Html(
        string='Nội dung', sanitize=False, compute='_compute_body')

    # ------------------------------------------------------------------
    # Điều hướng
    # ------------------------------------------------------------------
    def action_tab_1(self):
        self.tab = '1'
        return True

    def action_tab_2(self):
        self.tab = '2'
        return True

    def action_tab_3(self):
        self.tab = '3'
        return True

    @api.model
    def action_open(self):
        rec = self.search([('company_id', '=', self.env.company.id)],
                          limit=1)
        if not rec:
            rec = self.create({'company_id': self.env.company.id})
        return {
            'type': 'ir.actions.act_window',
            'name': _('Vốn & Ngân quỹ'),
            'res_model': self._name,
            'res_id': rec.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # ------------------------------------------------------------------
    # Tiện ích chung
    # ------------------------------------------------------------------
    def _url(self, xmlid):
        """Đường dẫn tới một action đã khai bằng xmlid; không có thì
        trả None để thẻ số hiện dạng tĩnh, không phải link chết."""
        act = self.env.ref(xmlid, raise_if_not_found=False)
        return '/odoo/action-%s' % act.id if act else None

    @staticmethod
    def _a(url, inner, style=''):
        """Bọc link nếu có action; không có thì trả nguyên khối."""
        if not url:
            return Markup('<div style="%s">%s</div>') % (Markup(style),
                                                         inner)
        return Markup(
            '<a href="%s" style="text-decoration:none;color:inherit;'
            'display:block;%s">%s</a>') % (url, Markup(style), inner)

    # ------------------------------------------------------------------
    @api.depends('tab', 'company_id')
    def _compute_body(self):
        for rec in self:
            if rec.tab == '2':
                rec.body_html = rec._render_tab2()
            elif rec.tab == '3':
                rec.body_html = rec._render_tab3()
            else:
                rec.body_html = rec._render_tab1()

    def _head(self, title, subtitle, right=''):
        return Markup(
            '<div style="display:flex;align-items:baseline;'
            'justify-content:space-between;margin-bottom:12px">'
            '<div style="display:flex;align-items:baseline;gap:10px">'
            '<h1 style="margin:0;font-size:17px;font-weight:700">%s</h1>'
            '<span style="font-size:12px;color:%s">%s</span></div>'
            '<span style="font-size:11px;color:%s">%s</span></div>'
        ) % (title, R.C['muted'], subtitle, R.C['faint'], right)

    @staticmethod
    def _wrap(inner):
        return Markup(
            '<div style="background:%s;color:%s;font-size:13px;'
            'line-height:1.35;padding:16px 4px 24px">%s</div>'
        ) % (R.C['bg'], R.C['navy'], inner)

    # ==================================================================
    # ① BỨC TRANH VỐN
    # ==================================================================
    def _kpi_card(self, label, value_text, value_full, foot, top_color,
                  value_color=None, url=None, bar_pct=None):
        inner = Markup(
            '<div style="font-size:11.5px;font-weight:600;color:%s;'
            'text-transform:uppercase;letter-spacing:.04em">%s</div>'
            '<div title="%s" style="margin-top:8px;font-size:30px;'
            'font-weight:700;color:%s;font-variant-numeric:tabular-nums">'
            '%s</div>'
        ) % (R.C['muted'], label, value_full,
             value_color or R.C['navy'], value_text)
        if bar_pct is not None:
            inner += Markup(
                '<div style="margin-top:9px;height:7px;background:#E4EAED;'
                'border-radius:4px;overflow:hidden"><div style="width:%s%%;'
                'height:100%%;background:%s"></div></div>'
            ) % (min(100.0, max(0.0, bar_pct)), R.C['teal'])
        elif foot:
            inner += Markup(
                '<div style="margin-top:6px;font-size:11.5px;color:%s">'
                '%s</div>') % (R.C['faint'], foot)
        card = Markup(
            '<div style="background:#fff;border:1px solid %s;'
            'border-top:3px solid %s;border-radius:4px;padding:14px 16px">'
            '%s</div>') % (R.C['line'], top_color, inner)
        return self._a(url, card) if url else card

    def _collect_tab1(self):
        env = self.env
        CC = env['re.loan.credit.contract']
        Fac = env['re.loan.facility']
        Note = env['re.loan.note']
        contracts = CC.search([('state', '=', 'active')])
        facs = Fac.search([('credit_contract_id', 'in', contracts.ids)])
        notes = Note.search([('state', 'not in',
                              ('draft', 'cancelled', 'fully_paid'))])
        total_limit = sum(contracts.mapped('amount_total'))
        used = sum(notes.mapped('principal_outstanding'))
        # KHÔNG cộng thẳng khả dụng từng facility: các facility dưới cùng
        # một HĐTD dùng CHUNG bể umbrella, cộng lại là đếm trùng phần
        # dùng chung — trên dữ liệu thật cách cộng sai cho ra khả dụng
        # lớn hơn cả hạn mức còn lại của HĐTD. Với mỗi HĐTD phải kẹp
        # tổng facility bằng trần umbrella của chính HĐTD đó.
        avail = 0.0
        blocked_by_umbrella = 0.0
        for cc in contracts:
            fac_sum = sum(cc.facility_ids.mapped(
                'amount_available_effective'))
            cap = cc.amount_available_effective
            avail += min(fac_sum, cap)
            if fac_sum > cap:
                blocked_by_umbrella += fac_sum - cap
        banks = contracts.mapped('partner_id')
        return {
            'contracts': contracts, 'facs': facs, 'notes': notes,
            'total_limit': total_limit, 'used': used, 'avail': avail,
            'banks': banks, 'umbrella_gap': blocked_by_umbrella,
            'used_pct': (used / total_limit * 100.0) if total_limit else 0.0,
        }

    def _weekly_closings(self, n_weeks=13):
        """Số dư cuối tuần 13 tuần tới — dùng lại đúng nguồn của Dự báo
        dòng tiền để hai màn không bao giờ lệch nhau."""
        Fc = self.env['re.cashflow.forecast']
        today = fields.Date.context_today(self)
        week0 = today - relativedelta(days=today.weekday())
        try:
            flows = Fc._collect_flows()
            opening = Fc._opening_cash()
        except Exception:            # noqa: BLE001 - module chưa cài
            return [], []
        net = [0.0] * (n_weeks + 1)

        def bucket(d):
            if not d or d < week0:
                return -1 if (not d or d < today) else 0
            idx = (d - week0).days // 7
            return idx if idx < n_weeks else None

        for d, amt, _cat, sign in flows:
            b = bucket(d)
            if b is None:
                continue
            net[b + 1] += amt if sign > 0 else -amt
        closing, closings = opening, []
        for i in range(n_weeks + 1):
            closing += net[i]
            if i >= 1:
                closings.append(closing)
        labels = ['T%d' % (i + 1) for i in range(n_weeks)]
        return closings, labels

    def _render_tab1(self):
        d = self._collect_tab1()
        blocked_txt, unlock = self._umbrella_block(d)

        cards = Markup('').join([
            self._kpi_card(
                'Tổng hạn mức được cấp', R.fmt(d['total_limit']),
                R.full(d['total_limit']),
                '%d HĐTD · %d facility · %d ngân hàng →'
                % (len(d['contracts']), len(d['facs']), len(d['banks'])),
                R.C['navy'],
                url=self._url('re_loan.action_re_loan_credit_contract')),
            self._kpi_card(
                'Dư nợ hiện tại', R.fmt(d['used']), R.full(d['used']),
                '%d KW còn dư nợ →' % len(d['notes'].filtered(
                    lambda n: n.principal_outstanding > 0)),
                R.C['teal'], value_color=R.C['teal'],
                url=self._url('re_loan.action_re_loan_note')),
            self._kpi_card(
                'Khả dụng thực tế', R.fmt(d['avail']), R.full(d['avail']),
                blocked_txt, R.C['amber'],
                url=self._url('re_loan.action_re_loan_facility')),
            self._kpi_card(
                'Tỷ lệ sử dụng hạn mức', R.pct(d['used_pct']), '',
                '', R.C['teal'], bar_pct=d['used_pct']),
        ])

        closings, labels = self._weekly_closings()
        if closings:
            chart = R.line_chart(closings, labels, 744, 254, 52, 8, 14, 30,
                                 'cf', annotate_first_negative=True)
        else:
            chart = self._empty(
                'Chưa lập dự báo dòng tiền',
                'Mở Báo cáo → Dự báo dòng tiền để hệ thống gom nghĩa vụ '
                'thu/chi 13 tuần tới.')

        body = Markup(
            '%s<div style="display:grid;grid-template-columns:repeat(4,1fr);'
            'gap:12px">%s</div>'
            '<div style="display:grid;grid-template-columns:1fr 336px;'
            'gap:12px;margin-top:12px">'
            '<div style="background:#fff;border:1px solid %s;'
            'border-radius:4px;padding:14px 16px">'
            '<div style="display:flex;align-items:baseline;'
            'justify-content:space-between">'
            '<div style="font-size:13px;font-weight:700">Dòng tiền 13 tuần '
            '· số dư cuối kỳ</div>%s</div>%s</div>'
            '<div style="display:flex;flex-direction:column;gap:12px">'
            '%s%s</div></div>%s'
        ) % (
            self._head(
                'Bức tranh vốn',
                'Đang nợ bao nhiêu · còn rút được bao nhiêu · tháng tới có '
                'kẹt tiền không · chỗ nào đỏ',
                'Nguồn: HĐTD · khế ước · TSBĐ · dự báo dòng tiền'),
            cards, R.C['line'], self._legend_pos_neg(), chart,
            self._bg_block(), self._alert_block(), self._project_lamps())
        return self._wrap(body)

    def _umbrella_block(self, d):
        """Cái gì đang chặn khả dụng, và mở ra thì được thêm bao nhiêu.

        Hai nút thắt khác nhau, phải nói rõ cái nào:
        • umbrella — tổng khả dụng các facility vượt trần HĐTD, phần dôi
          ra không rút được dù facility còn chỗ;
        • TSBĐ — hạn mức còn nhưng cơ sở bảo đảm không gánh nổi.
        """
        if d['umbrella_gap'] > 0.01:
            return (Markup(
                '<span style="background:#FDF1DD;color:#9A6412;'
                'border:1px solid %s;border-radius:2px;padding:1px 6px;'
                'font-weight:600">Nhánh chặn: trần HĐTD</span> '
                '<span title="%s">facility còn chỗ nhưng trần HĐTD chặn '
                '%s</span>'
            ) % (R.C['amber'], R.full(d['umbrella_gap']),
                 R.fmt(d['umbrella_gap'])), d['umbrella_gap'])
        gap = d['total_limit'] - d['used'] - d['avail']
        if gap > 0.01:
            return (Markup(
                '<span style="background:#FDF1DD;color:#9A6412;'
                'border:1px solid %s;border-radius:2px;padding:1px 6px;'
                'font-weight:600">Nhánh chặn: TSBĐ</span> '
                '<span title="%s">thiếu %s cơ sở bảo đảm để mở khoá</span>'
            ) % (R.C['amber'], R.full(gap), R.fmt(gap)), gap)
        return Markup('Không nhánh nào đang chặn'), 0.0

    @staticmethod
    def _legend_pos_neg():
        return Markup(
            '<div style="display:flex;gap:14px;font-size:11px;color:%s">'
            '<span><span style="display:inline-block;width:10px;height:10px;'
            'background:%s;opacity:.35"></span> Dương</span>'
            '<span><span style="display:inline-block;width:10px;height:10px;'
            'background:%s;opacity:.45"></span> Âm</span></div>'
        ) % (R.C['muted'], R.C['teal'], R.C['red'])

    def _empty(self, title, hint):
        """Trạng thái rỗng phải nói VIỆC CẦN LÀM TIẾP, không viết
        'Không có dữ liệu'."""
        return Markup(
            '<div style="padding:34px 16px;text-align:center;color:%s">'
            '<div style="font-size:13px;font-weight:600;color:%s">%s</div>'
            '<div style="font-size:11.5px;margin-top:5px">%s</div></div>'
        ) % (R.C['faint'], R.C['muted'], title, hint)

    def _bg_block(self):
        G = self.env['re.bank.guarantee'] if \
            're.bank.guarantee' in self.env else None
        if G is None:
            return Markup('')
        live = G.search([('state', 'in', ('issued', 'extended'))])
        soon = live.filtered(lambda g: g.is_expiring_soon)
        return Markup(
            '<div style="background:#fff;border:1px solid %s;'
            'border-radius:4px;padding:12px 14px">'
            '<div style="font-size:13px;font-weight:700;margin-bottom:10px">'
            'Nghĩa vụ ngoài bảng · bảo lãnh</div>'
            '<div style="display:grid;grid-template-columns:1fr 1fr;'
            'gap:10px">'
            '<div style="border:1px solid #DCE3E6;border-left:3px solid %s;'
            'border-radius:3px;padding:10px">'
            '<div style="font-size:11px;color:%s;font-weight:600">Đang hiệu '
            'lực</div><div title="%s" style="margin-top:5px;font-size:21px;'
            'font-weight:700;color:%s;font-variant-numeric:tabular-nums">%s'
            '</div><div style="font-size:11px;color:%s;margin-top:3px">%d '
            'thư bảo lãnh</div></div>'
            '<div style="border:1px solid #DCE3E6;border-left:3px solid %s;'
            'border-radius:3px;padding:10px">'
            '<div style="font-size:11px;color:%s;font-weight:600">Hết hạn ≤ '
            '30 ngày</div><div style="margin-top:5px;font-size:21px;'
            'font-weight:700;color:#9A6412;'
            'font-variant-numeric:tabular-nums">%d thư</div>'
            '<div title="%s" style="font-size:11px;color:%s;margin-top:3px">'
            '%s · cần gia hạn</div></div></div></div>'
        ) % (R.C['line'], R.C['teal'], R.C['muted'],
             R.full(sum(live.mapped('amount'))), R.C['teal'],
             R.fmt(sum(live.mapped('amount'))), R.C['faint'], len(live),
             R.C['amber'], R.C['muted'], len(soon),
             R.full(sum(soon.mapped('amount'))), R.C['faint'],
             R.fmt(sum(soon.mapped('amount'))))

    def _alert_block(self):
        Note = self.env['re.loan.note']
        overdue = Note.search([('state', '=', 'overdue')])
        principal = sum(overdue.mapped('principal_outstanding'))
        IL = self.env['re.loan.note.interest.line']
        today = fields.Date.context_today(self)
        int_over = IL.search([('state', '!=', 'paid'),
                              ('date_to', '<', today)])
        interest = sum(int_over.mapped('amount_interest_remaining')) \
            if int_over else 0.0
        rows = [('Nợ gốc quá hạn', R.fmt(principal), R.full(principal)),
                ('Lãi quá hạn', R.fmt(interest), R.full(interest))]
        if 're.bank.guarantee' in self.env:
            # `is_expired` là compute KHÔNG store → không lọc được bằng
            # domain, phải duyệt Python (bẫy đã gặp với margin_call).
            live_bg = self.env['re.bank.guarantee'].search(
                [('state', 'in', ('issued', 'extended'))])
            expired = len(live_bg.filtered(lambda g: g.is_expired))
            rows.append(('Bảo lãnh đã hết hạn chưa xử',
                         '%d thư' % expired, ''))
        if not principal and not interest:
            body = self._empty('Không có cảnh báo đỏ',
                               'Không có nợ gốc hay lãi nào quá hạn.')
            return Markup(
                '<div style="background:#fff;border:1px solid %s;'
                'border-radius:4px">%s</div>') % (R.C['line'], body)
        items = Markup('').join([Markup(
            '<div style="display:flex;align-items:center;'
            'justify-content:space-between;background:#fff;'
            'border:1px solid #EFC9C9;border-radius:3px;padding:8px 10px">'
            '<span style="font-size:12px">%s</span>'
            '<span title="%s" style="font-size:16px;font-weight:700;'
            'color:%s;font-variant-numeric:tabular-nums">%s</span></div>'
        ) % (lbl, ttl, R.C['red'], val) for lbl, val, ttl in rows])
        return Markup(
            '<div style="background:#FCEDED;border:1px solid %s;'
            'border-radius:4px;padding:12px 14px">'
            '<div style="display:flex;align-items:center;gap:7px;'
            'font-size:13px;font-weight:700;color:#A62F2F;'
            'margin-bottom:10px"><span style="width:8px;height:8px;'
            'border-radius:50%%;background:%s;display:inline-block"></span>'
            'Cảnh báo đỏ · cần xử lý ngay</div>'
            '<div style="display:flex;flex-direction:column;gap:8px">%s'
            '</div></div>') % (R.C['red'], R.C['red'], items)

    def _project_lamps(self):
        sheets = self.env['re.loan.project.funding'].search([])
        if not sheets:
            return Markup('')
        cells = []
        for s in sheets:
            state = s.kpi_overall_state or 'na'
            color = {'green': R.C['green'], 'yellow': R.C['amber'],
                     'red': R.C['red']}.get(state, R.C['gray'])
            red_txt = str(s.kpi_red_count) if state != 'na' else '—'
            cells.append(Markup(
                '<div style="border:1px solid #DCE3E6;border-radius:3px;'
                'padding:10px 12px;background:#FBFCFC">'
                '<div style="display:flex;align-items:center;gap:7px">'
                '<span style="width:10px;height:10px;border-radius:50%%;'
                'flex:0 0 auto;background:%s"></span>'
                '<span style="font-size:12.5px;font-weight:600;'
                'white-space:nowrap;overflow:hidden;text-overflow:ellipsis">'
                '%s</span></div>'
                '<div style="display:flex;align-items:baseline;'
                'justify-content:space-between;margin-top:8px">'
                '<span style="font-size:11px;color:%s">Chỉ tiêu đỏ</span>'
                '<span style="font-size:18px;font-weight:700;'
                'font-variant-numeric:tabular-nums;color:%s">%s</span>'
                '</div></div>'
            ) % (color, escape(s.project_id.display_name or ''),
                 R.C['faint'], color, red_txt))
        return Markup(
            '<div style="background:#fff;border:1px solid %s;'
            'border-radius:4px;padding:12px 16px 14px;margin-top:12px">'
            '<div style="display:flex;align-items:baseline;'
            'justify-content:space-between;margin-bottom:10px">'
            '<div style="font-size:13px;font-weight:700">Đèn dự án</div>'
            '%s</div>'
            '<div style="display:grid;grid-template-columns:repeat(5,1fr);'
            'gap:10px">%s</div></div>'
        ) % (R.C['line'], self._legend_states(),
             Markup('').join(cells))

    @staticmethod
    def _legend_states():
        bits = [('Tốt', R.C['green']), ('Cảnh báo', R.C['amber']),
                ('Nguy hiểm', R.C['red']), ('Chưa đủ dữ liệu', R.C['gray'])]
        return Markup(
            '<div style="display:flex;gap:14px;font-size:11px;color:%s">%s'
            '</div>') % (R.C['muted'], Markup('').join([Markup(
                '<span><span style="display:inline-block;width:9px;'
                'height:9px;border-radius:50%%;background:%s"></span> %s'
                '</span>') % (c, t) for t, c in bits]))

    # ==================================================================
    # ② VIỆC HÔM NAY
    # ==================================================================
    def _tile(self, label, value, kind, hint='', amount=None, url=None,
              stacked=False):
        """Một ô việc. Giá trị 0 thì LÀM MỜ chứ không ẩn — người dùng cần
        thấy 'đã sạch', khác hẳn với 'mục này không tồn tại'."""
        color = R.tone(kind) if value else R.C['gray']
        opacity = '1' if value else '.45'
        amt_txt = R.fmt(amount) if amount else ''
        amt_full = R.full(amount) if amount else ''
        if stacked:
            inner = Markup(
                '<div style="font-size:12px;font-weight:500;'
                'min-height:32px">%s</div>'
                '<div style="display:flex;align-items:baseline;'
                'justify-content:space-between;gap:8px;margin-top:2px">'
                '<span style="font-size:22px;font-weight:700;'
                'font-variant-numeric:tabular-nums;color:%s">%s</span>'
                '<span title="%s" style="font-size:12px;font-weight:600;'
                'color:%s;font-variant-numeric:tabular-nums">%s</span></div>'
                '<div style="font-size:11px;color:%s;margin-top:3px">%s'
                '</div>'
            ) % (label, color, value, amt_full, R.C['muted'], amt_txt,
                 R.C['faint'], hint)
        else:
            inner = Markup(
                '<div style="display:flex;align-items:center;'
                'justify-content:space-between;gap:10px">'
                '<span style="font-size:12px;font-weight:500">%s</span>'
                '<span style="font-size:22px;font-weight:700;'
                'font-variant-numeric:tabular-nums;color:%s">%s</span></div>'
                '<div style="display:flex;align-items:baseline;'
                'justify-content:space-between;gap:10px;margin-top:3px">'
                '<span style="font-size:11px;color:%s">%s</span>'
                '<span title="%s" style="font-size:12px;font-weight:600;'
                'color:%s;font-variant-numeric:tabular-nums;'
                'min-width:100px;text-align:right">%s</span></div>'
            ) % (label, color, value, R.C['faint'], hint, amt_full,
                 R.C['muted'], amt_txt)
        card = Markup(
            '<div style="border:1px solid #DCE3E6;border-left:3px solid %s;'
            'border-radius:3px;padding:9px 11px;background:#fff;'
            'opacity:%s">%s</div>') % (color, opacity, inner)
        return self._a(url, card) if url else card

    def _group(self, title, color, tiles, grid=False):
        layout = ('display:grid;grid-template-columns:repeat(3,1fr);gap:8px'
                  if grid else
                  'display:flex;flex-direction:column;gap:8px')
        return Markup(
            '<div style="flex:1 1 0;background:#fff;border:1px solid %s;'
            'border-radius:4px;padding:12px 14px 14px">'
            '<div style="display:flex;align-items:center;gap:8px;'
            'padding-bottom:9px;border-bottom:1px solid %s">'
            '<span style="width:4px;height:15px;border-radius:2px;'
            'background:%s"></span>'
            '<span style="font-size:12.5px;font-weight:700;'
            'text-transform:uppercase;letter-spacing:.04em">%s</span></div>'
            '<div style="%s;margin-top:10px">%s</div></div>'
        ) % (R.C['line'], R.C['line2'], color, title, Markup(layout),
             Markup('').join(tiles))

    def _collect_tab2(self):
        env = self.env
        today = fields.Date.context_today(self)
        Note = env['re.loan.note']
        IL = env['re.loan.note.interest.line']
        live = [('state', 'not in', ('draft', 'cancelled', 'fully_paid'))]

        m30 = Note.search(live + [
            ('date_maturity', '>=', today),
            ('date_maturity', '<=', today + relativedelta(days=30))])
        m90 = Note.search(live + [
            ('date_maturity', '>=', today),
            ('date_maturity', '<=', today + relativedelta(days=90))])
        week_end = today + relativedelta(days=6 - today.weekday())
        due = IL.search([('state', '!=', 'paid'),
                         ('date_to', '>=', today),
                         ('date_to', '<=', week_end)])
        due_amt = sum(due.mapped('principal_due')) + \
            sum(due.mapped('interest_amount'))

        Disb = env['re.loan.note.disbursement']
        pending_disb = Disb.search([('state', 'in',
                                     ('draft', 'submitted'))])
        advice = env['re.loan.bank.advice'].search(
            [('state', '=', 'draft')]) \
            if 're.loan.bank.advice' in env else Disb.browse()
        bg_req = env['re.guarantee.request'].search(
            [('state', '=', 'draft')]) \
            if 're.guarantee.request' in env else Disb.browse()

        txn_unmatched = env['re.bank.transaction'].search(
            [('state', '!=', 'reconciled')]) \
            if 're.bank.transaction' in env else Disb.browse()

        Move = env['account.move']
        inv_missing = Move.search([('rp_project_missing', '=', True),
                                   ('state', '!=', 'cancel')]) \
            if 'rp_project_missing' in Move._fields else Move.browse()
        kw_no_project = Note.search(live + [('project_id', '=', False)]) \
            if 'project_id' in Note._fields else Note.browse()

        buckets = {}
        for n in Note.search(live + [('state', '=', 'overdue')]):
            buckets.setdefault(n.aging_bucket or 'b0', []).append(n)
        return {
            'm30': m30, 'm90': m90, 'due': due, 'due_amt': due_amt,
            'pending_disb': pending_disb, 'advice': advice,
            'bg_req': bg_req, 'txn': txn_unmatched,
            'inv_missing': inv_missing, 'kw_no_project': kw_no_project,
            'buckets': buckets,
        }

    def _render_tab2(self):
        d = self._collect_tab2()
        u_note = self._url('re_loan.action_re_loan_note')
        total = (len(d['m30']) + len(d['due']) + len(d['pending_disb'])
                 + len(d['advice']) + len(d['bg_req']) + len(d['txn'])
                 + len(d['inv_missing']) + len(d['kw_no_project']))

        g1 = self._group('Đến hạn', R.C['amber'], [
            self._tile('KW đáo hạn ≤ 30 ngày', len(d['m30']),
                       'warn' if d['m30'] else 'ok', 'cần chuẩn bị nguồn',
                       sum(d['m30'].mapped('principal_outstanding')),
                       u_note),
            self._tile('KW đáo hạn ≤ 90 ngày', len(d['m90']),
                       'warn' if d['m90'] else 'ok', 'nhìn xa hơn một quý',
                       sum(d['m90'].mapped('principal_outstanding')),
                       u_note),
            self._tile('Gốc + lãi đến hạn trong tuần', len(d['due']),
                       'warn' if d['due'] else 'ok', 'kỳ trả nợ tuần này',
                       d['due_amt']),
        ])
        g2 = self._group('Chờ xử lý', R.C['teal'], [
            self._tile('Hồ sơ giải ngân chờ trình NH',
                       len(d['pending_disb']),
                       'warn' if d['pending_disb'] else 'ok',
                       'nháp + đã gửi chờ duyệt',
                       sum(d['pending_disb'].mapped('amount'))
                       if d['pending_disb'] else 0),
            self._tile('Giấy báo ngân hàng chờ xử lý', len(d['advice']),
                       'warn' if d['advice'] else 'ok', 'còn ở trạng thái nháp'),
            self._tile('Đề nghị phát hành bảo lãnh', len(d['bg_req']),
                       'warn' if d['bg_req'] else 'ok', 'chờ gửi / chờ NH duyệt'),
        ])
        g3 = self._group('Đối soát', R.C['navy'], [
            self._tile('Giao dịch ngân hàng chưa khớp', len(d['txn']),
                       'warn' if d['txn'] else 'ok', 'chưa gắn chứng từ',
                       sum(d['txn'].mapped('amount')) if d['txn'] else 0),
        ])
        g4 = self._group('Vệ sinh dữ liệu', R.C['navy'], [
            self._tile('Hoá đơn chưa gắn dự án', len(d['inv_missing']),
                       'warn' if d['inv_missing'] else 'ok',
                       'rơi khỏi công nợ NCC và AC',
                       sum(d['inv_missing'].mapped('amount_total'))
                       if d['inv_missing'] else 0, stacked=True),
            self._tile('KW chưa gắn dự án', len(d['kw_no_project']),
                       'warn' if d['kw_no_project'] else 'ok',
                       'không vào khả dụng theo dự án',
                       sum(d['kw_no_project'].mapped(
                           'principal_outstanding'))
                       if d['kw_no_project'] else 0,
                       url=u_note, stacked=True),
        ], grid=True)

        labels = {'b1_30': 'Quá hạn 1 – 30 ngày',
                  'b31_60': 'Quá hạn 31 – 60 ngày',
                  'b61_90': 'Quá hạn 61 – 90 ngày',
                  'b91_180': 'Quá hạn 91 – 180 ngày',
                  'b181_365': 'Quá hạn 181 – 365 ngày',
                  'b365': 'Quá hạn > 365 ngày'}
        aging_tiles = []
        for key, lbl in labels.items():
            notes = d['buckets'].get(key, [])
            amt = sum(n.principal_outstanding for n in notes)
            aging_tiles.append(self._tile(
                lbl, len(notes), 'bad' if notes else 'ok', '', amt,
                url=u_note, stacked=True))
        g5 = self._group('Quá hạn theo tuổi nợ', R.C['red'], aging_tiles,
                         grid=True)

        return self._wrap(Markup(
            '%s<div style="display:flex;gap:12px">%s%s%s</div>'
            '<div style="display:flex;gap:12px;margin-top:12px">%s%s</div>'
        ) % (self._head(
            'Việc hôm nay',
            'Bấm vào mỗi con số để mở danh sách bản ghi cần xử lý. Ô bằng '
            '0 được làm mờ — nghĩa là đã sạch.',
            Markup('Tổng việc cần xử lý: <b style="color:%s;'
                   'font-size:13px">%d</b>') % (R.C['navy'], total)),
            g1, g2, g3, g4, g5))

    # ==================================================================
    # ③ VỐN THEO DỰ ÁN
    # ==================================================================
    BLOCKED_LABEL = {
        'limit': 'Hạn mức', 'collateral': 'TSBĐ',
        'facility': 'Facility', 'umbrella': 'Toàn HĐTD',
        'none': 'Không chặn',
    }

    def _project_rows(self):
        """Một dòng cho mỗi dự án có phiếu Nhu cầu vốn."""
        Alloc = self.env['re.loan.facility.project.allocation']
        Cashflow = self.env['re.loan.project.cashflow']
        Note = self.env['re.loan.note']
        rows = []
        for s in self.env['re.loan.project.funding'].search([]):
            p = s.project_id
            allocs = Alloc.search([('project_id', '=', p.id)])
            # nhánh chặn hay gặp nhất trong các phân bổ của dự án
            blocked = 'none'
            worst = None
            for a in allocs:
                if a.blocked_by and a.blocked_by != 'none':
                    if worst is None or a.amount_available_project < worst:
                        worst = a.amount_available_project
                        blocked = a.blocked_by
            cf = Cashflow.search([('project_id', '=', p.id)], limit=1)
            note = Note.search([('project_id', '=', p.id),
                                ('state', 'not in',
                                 ('draft', 'cancelled', 'fully_paid'))],
                               limit=1)
            rows.append({
                'sheet': s, 'project': p, 'allocs': allocs, 'cf': cf,
                'note': note, 'blocked': blocked,
                'state': s.kpi_overall_state or 'na',
            })
        return rows

    @staticmethod
    def _dot(state):
        return {'green': R.C['green'], 'yellow': R.C['amber'],
                'red': R.C['red']}.get(state, R.C['gray'])

    def _render_tab3(self):
        rows = self._project_rows()
        if not rows:
            return self._wrap(Markup('%s%s') % (
                self._head('Vốn theo dự án', '', ''),
                Markup('<div style="background:#fff;border:1px solid %s;'
                       'border-radius:4px">%s</div>')
                % (R.C['line'], self._empty(
                    'Chưa có dự án nào lập phiếu Nhu cầu vốn',
                    'Mở Quản lý Vay → Nhu cầu vốn dự án và tạo phiếu cho '
                    'dự án đầu tiên.'))))

        cols = ('236px 150px 150px 185px 118px 150px 92px 96px')
        header = Markup(
            '<div style="display:grid;grid-template-columns:%s;'
            'gap:0 10px;padding:0 14px 7px;font-size:10.5px;'
            'font-weight:700;color:%s;text-transform:uppercase;'
            'letter-spacing:.04em">'
            '<div>Dự án</div><div style="text-align:right">Hạn mức phân bổ'
            '</div><div style="text-align:right">Dư nợ</div>'
            '<div style="text-align:right">Khả dụng</div>'
            '<div>Nhánh chặn</div>'
            '<div style="text-align:right">Nhu cầu vay thêm</div>'
            '<div style="text-align:right">DSCR toàn kỳ</div>'
            '<div style="text-align:right">Tháng thiếu tiền</div></div>'
        ) % (Markup(cols), R.C['muted'])

        cards = []
        for r in rows:
            cards.append(self._project_card(r, cols))
        return self._wrap(Markup(
            '%s%s<div style="display:flex;flex-direction:column;gap:8px">'
            '%s</div>'
        ) % (self._head(
            'Vốn theo dự án',
            'Còn rút được bao nhiêu · thiếu vốn tự có không · trả nợ nổi '
            'không',
            'Bấm vào thẻ dự án để mở chi tiết chuỗi nhu cầu vốn'),
            header, Markup('').join(cards)))

    def _project_card(self, r, cols):
        s, cf = r['sheet'], r['cf']
        dot = self._dot(r['state'])
        avail = s.available_now
        dscr = cf.dscr_overall if cf and cf.total_debt_service else None
        short = cf.month_cash_short if cf and cf.line_ids else None
        blocked = self.BLOCKED_LABEL.get(r['blocked'], '—')
        bl_color = (R.C['amber'] if r['blocked'] in ('collateral',
                                                     'umbrella')
                    else R.C['gray'] if r['blocked'] == 'none'
                    else R.C['ink'])
        summary = Markup(
            '<div style="display:grid;grid-template-columns:%s;'
            'gap:0 10px;align-items:center;padding:12px 14px;'
            'cursor:pointer">'
            '<div style="display:flex;align-items:center;gap:8px">'
            '<span style="width:10px;height:10px;border-radius:50%%;'
            'flex:0 0 auto;background:%s"></span>'
            '<span style="font-size:13.5px;font-weight:600">%s</span></div>'
            '<div title="%s" style="text-align:right;font-size:14px;'
            'font-variant-numeric:tabular-nums;color:%s">%s</div>'
            '<div title="%s" style="text-align:right;font-size:14px;'
            'font-variant-numeric:tabular-nums;color:%s;font-weight:600">'
            '%s</div>'
            '<div title="%s" style="text-align:right;font-size:20px;'
            'font-weight:700;font-variant-numeric:tabular-nums;color:%s">'
            '%s</div>'
            '<div><span style="display:inline-block;font-size:11px;'
            'font-weight:600;border-radius:2px;padding:2px 7px;'
            'border:1px solid %s;color:%s">%s</span></div>'
            '<div title="%s" style="text-align:right;font-size:14px;'
            'font-variant-numeric:tabular-nums;color:%s">%s</div>'
            '<div style="text-align:right;font-size:15px;font-weight:700;'
            'font-variant-numeric:tabular-nums;color:%s">%s</div>'
            '<div style="text-align:right;font-size:15px;font-weight:700;'
            'font-variant-numeric:tabular-nums;color:%s">%s</div></div>'
        ) % (
            Markup(cols), dot, escape(r['project'].display_name or ''),
            R.full(s.limit_allocated), R.C['ink'],
            R.fmt(s.limit_allocated),
            R.full(s.limit_used), R.C['teal'], R.fmt(s.limit_used),
            R.full(avail),
            R.C['red'] if avail <= 0 else R.C['navy'], R.fmt(avail),
            bl_color, bl_color, blocked,
            R.full(s.funding_need), R.C['ink'], R.fmt(s.funding_need),
            (R.C['red'] if (dscr is not None and dscr < 1)
             else R.C['gray'] if dscr is None else R.C['green']),
            R.num(dscr) if dscr is not None else '—',
            (R.C['red'] if short else R.C['gray'] if short is None
             else R.C['green']),
            str(short) if short is not None else '—',
        )
        detail = self._project_detail(r)
        return Markup(
            '<details style="background:#fff;border:1px solid %s;'
            'border-left:3px solid %s;border-radius:4px">'
            '<summary style="list-style:none;cursor:pointer">%s</summary>'
            '%s</details>') % (R.C['line'], dot, summary, detail)

    def _project_detail(self, r):
        s, cf, p = r['sheet'], r['cf'], r['project']
        # --- chuỗi nhu cầu vốn ---
        steps = [
            {'kind': 'total', 'value': s.cost_to_complete,
             'n1': 'Chi phí còn', 'n2': 'phải chi'},
            {'kind': 'delta', 'value': s.equity_to_contribute,
             'n1': 'Vốn tự có', 'n2': ''},
            {'kind': 'delta', 'value': s.advance_available,
             'n1': 'Tạm ứng', 'n2': 'CĐT'},
            {'kind': 'delta', 'value': s.supplier_credit_total,
             'n1': 'Công nợ', 'n2': 'NCC'},
            {'kind': 'result', 'value': s.funding_need,
             'n1': 'Nhu cầu', 'n2': 'vay thêm'},
            {'kind': 'risk', 'value': s.unfunded_need,
             'n1': 'Chưa được', 'n2': 'tài trợ'},
        ]
        wf = R.waterfall(steps)

        # --- số dư tiền luỹ kế theo tháng ---
        if cf and cf.line_ids:
            lines = cf.line_ids.sorted('date_start')[:12]
            vals = [l.cash_balance for l in lines]
            labs = [l.period_label or '' for l in lines]
            mc = R.line_chart(vals, labs, 400, 190, 46, 6, 12, 24,
                              'mc%s' % p.id, tick_font=9, grid_font=9,
                              stroke=2)
            short_txt = Markup(
                '<div style="font-size:11px;color:#A62F2F;'
                'font-weight:600">%d tháng âm</div>') % cf.month_cash_short
        else:
            mc = self._empty(
                'Chưa lập bảng dòng tiền',
                'Mở Báo cáo → Dòng tiền dự án & DSCR rồi bấm "Tính lại '
                'dòng tiền".')
            short_txt = Markup('')

        # --- 5 tín hiệu §8 ---
        note = r['note']
        sig_defs = [('Dòng tiền', 'cap_cashflow'),
                    ('Nguồn thanh toán của CĐT', 'cap_owner_source'),
                    ('Tiến độ', 'cap_schedule'),
                    ('Lỗ', 'cap_profit'),
                    ('DSCR', 'cap_dscr')]
        sig_rows = []
        for label, fname in sig_defs:
            val = getattr(note, fname, 'na') if note else 'na'
            kind = {'ok': 'ok', 'warn': 'bad', 'na': 'na'}.get(val, 'na')
            color = R.tone(kind)
            txt = {'ok': 'Tốt', 'warn': 'Cảnh báo',
                   'na': 'Chưa đủ dữ liệu'}.get(val, '—')
            sig_rows.append(Markup(
                '<div style="display:flex;align-items:center;gap:8px">'
                '<span style="width:11px;height:11px;border-radius:50%%;'
                'flex:0 0 auto;background:%s"></span>'
                '<span style="font-size:12px;flex:1 1 auto">%s</span>'
                '<span style="font-size:11px;font-weight:600;color:%s">%s'
                '</span></div>') % (color, label, color, txt))

        # --- 7 chỉ tiêu ---
        kpi_defs = [
            ('Tỷ lệ sử dụng hạn mức', R.pct(s.kpi_limit_usage),
             s.kpi_limit_usage_state),
            ('Dư nợ / TSBĐ', R.pct(s.kpi_debt_collateral),
             s.kpi_debt_collateral_state),
            ('Nợ quá hạn', R.pct(s.kpi_overdue), s.kpi_overdue_state),
            ('Vốn tự có thực góp', R.pct(s.kpi_equity),
             s.kpi_equity_state),
            ('DSCR toàn kỳ', R.num(s.kpi_dscr), s.kpi_dscr_state),
            ('SPI (tiến độ)', R.pct(s.kpi_spi), s.kpi_spi_state),
            ('Biên lợi nhuận', R.pct(s.kpi_margin), s.kpi_margin_state),
        ]
        kpi_rows = []
        for label, value, state in kpi_defs:
            kind = {'green': 'ok', 'yellow': 'warn', 'red': 'bad'}.get(
                state, 'na')
            color = R.tone(kind)
            shown = value if kind != 'na' else '—'
            kpi_rows.append(Markup(
                '<div style="display:grid;grid-template-columns:1fr 62px '
                '8px;gap:8px;align-items:center;border-bottom:1px solid '
                '#F1F4F5;padding-bottom:4px">'
                '<span style="font-size:12px">%s</span>'
                '<span style="font-size:12px;font-weight:700;'
                'text-align:right;font-variant-numeric:tabular-nums;'
                'color:%s">%s</span>'
                '<span style="width:8px;height:8px;border-radius:2px;'
                'background:%s"></span></div>')
                % (label, color, shown, color))

        next_action = self._next_action(r)
        panel = Markup(
            '<div style="background:#fff;border:1px solid #DCE3E6;'
            'border-radius:3px;padding:11px 12px">'
            '<div style="font-size:12.5px;font-weight:700;margin-bottom:8px">'
            '5 tín hiệu năng lực trả nợ (§8)</div>'
            '<div style="display:flex;flex-direction:column;gap:6px">%s'
            '</div></div>'
            '<div style="background:#fff;border:1px solid #DCE3E6;'
            'border-radius:3px;padding:11px 12px">'
            '<div style="font-size:12.5px;font-weight:700;margin-bottom:8px">'
            '7 chỉ tiêu xanh / vàng / đỏ</div>'
            '<div style="display:flex;flex-direction:column;gap:5px">%s'
            '</div></div>%s'
        ) % (Markup('').join(sig_rows), Markup('').join(kpi_rows),
             next_action)

        return Markup(
            '<div style="border-top:1px solid %s;background:#FAFBFC;'
            'padding:14px;display:grid;grid-template-columns:1fr 1fr 330px;'
            'gap:14px">'
            '<div style="background:#fff;border:1px solid #DCE3E6;'
            'border-radius:3px;padding:11px 12px">'
            '<div style="font-size:12.5px;font-weight:700;margin-bottom:2px">'
            'Chuỗi nhu cầu vốn</div>'
            '<div style="font-size:11px;color:%s">Chi phí còn phải chi → '
            'vốn tự có → tạm ứng CĐT → công nợ NCC → nhu cầu vay thêm → '
            'chưa được tài trợ</div>%s</div>'
            '<div style="background:#fff;border:1px solid #DCE3E6;'
            'border-radius:3px;padding:11px 12px">'
            '<div style="display:flex;align-items:baseline;'
            'justify-content:space-between"><div>'
            '<div style="font-size:12.5px;font-weight:700">Số dư tiền luỹ '
            'kế theo tháng</div>'
            '<div style="font-size:11px;color:%s">Tô đỏ đoạn âm · không vẽ '
            'DSCR từng tháng</div></div>%s</div>%s</div>'
            '<div style="display:flex;flex-direction:column;gap:10px">%s'
            '</div></div>'
        ) % (R.C['line2'], R.C['faint'], wf, R.C['faint'], short_txt, mc,
             panel)

    def _next_action(self, r):
        """Việc cần làm tiếp — suy ra từ nút thắt đang chặn, không phải
        câu chữ chung chung."""
        s, cf = r['sheet'], r['cf']
        msgs = []
        if r['blocked'] == 'collateral':
            gap = sum(a.unlock_gap for a in r['allocs'])
            if gap > 0:
                msgs.append(_('Bổ sung TSBĐ (quyền đòi nợ từ IPC đã được '
                              'CĐT ký) để mở khoá thêm %s.') % R.fmt(gap))
        if s.equity_shortfall > 0.01:
            msgs.append(_('Góp thêm vốn tự có %s cho đủ cam kết.')
                        % R.fmt(s.equity_shortfall))
        if cf and cf.month_cash_short:
            msgs.append(_('Có %d tháng số dư tiền âm (đáy %s) — cần xoay '
                          'vốn đúng các tháng đó.')
                        % (cf.month_cash_short, R.fmt(cf.cash_min)))
        if s.unfunded_need > 0.01:
            msgs.append(_('Còn %s chưa được tài trợ — con số đi đàm phán '
                          'thêm hạn mức.') % R.fmt(s.unfunded_need))
        if not msgs:
            return Markup(
                '<div style="background:#EAF6EE;border:1px solid %s;'
                'border-radius:3px;padding:10px 12px">'
                '<div style="font-size:11.5px;font-weight:700;color:#1F6B3D">'
                'Không có nút thắt</div>'
                '<div style="font-size:11.5px;color:#2E5A41">Khả dụng, vốn '
                'tự có và dòng tiền của dự án đang ổn.</div></div>'
            ) % R.C['green']
        return Markup(
            '<div style="background:#FDF1DD;border:1px solid %s;'
            'border-radius:3px;padding:10px 12px">'
            '<div style="font-size:11.5px;font-weight:700;color:#9A6412;'
            'margin-bottom:3px">Việc cần làm tiếp</div>'
            '<div style="font-size:11.5px;color:#6B4A0F">%s</div></div>'
        ) % (R.C['amber'], Markup(' ').join(msgs))
