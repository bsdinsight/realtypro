# -*- coding: utf-8 -*-
"""Dự báo dòng tiền theo tuần — tổng hợp mọi nghĩa vụ thu/chi tương lai.

Nguồn tự phát hiện theo module đã cài (check registry, không hard-
depend). Chống đếm trùng: đã thành hóa đơn → tính theo hóa đơn; lịch
chỉ tính phần CHƯA lên hóa đơn.
"""
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


def _fmt(v):
    v = float(v or 0)
    if abs(v) >= 1e9:
        return '%.1f tỷ' % (v / 1e9)
    if abs(v) >= 1e6:
        return '%.0f tr' % (v / 1e6)
    if abs(v) >= 1e3:
        return '%.0f k' % (v / 1e3)
    return '%.0f' % v


class ReCashflowForecast(models.TransientModel):
    _name = 're.cashflow.forecast'
    _description = 'Ngân quỹ — Dự báo dòng tiền'

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = 'Dự báo dòng tiền'

    horizon = fields.Selection(
        [('13', '13 tuần'), ('26', '26 tuần')],
        string='Tầm nhìn', default='13', required=True)
    currency_id = fields.Many2one(
        'res.currency', default=lambda self: self.env.company.currency_id)

    kpi_opening_cash = fields.Monetary(
        string='Số dư đầu kỳ (NH + tiền mặt)',
        help='Σ số dư các tài khoản gắn với sổ nhật ký Ngân hàng / '
             'Tiền mặt (bút toán đã vào sổ).')
    kpi_total_in = fields.Monetary(string='Tổng thu dự kiến')
    kpi_total_out = fields.Monetary(string='Tổng chi dự kiến')
    kpi_closing = fields.Monetary(string='Số dư cuối kỳ dự kiến')
    kpi_overdue_out = fields.Monetary(
        string='Chi quá hạn (chưa trả)',
        help='Nghĩa vụ chi có hạn TRƯỚC hôm nay còn chưa thanh toán.')
    kpi_overdue_in = fields.Monetary(string='Thu quá hạn (chưa thu)')
    kpi_receivable_undated = fields.Monetary(
        string='Phải thu CĐT (chưa có ngày)',
        help='Khoản phải thu từ HĐ với Chủ đầu tư — chưa có ngày thu '
             'dự kiến nên KHÔNG nằm trong bảng tuần.')
    first_negative_week = fields.Char(
        string='Tuần đầu tiên ÂM',
        help='Tuần đầu tiên số dư lũy kế dự kiến xuống dưới 0 — thời '
             'điểm cần thu xếp nguồn (rút KW, giãn thanh toán, đòi nợ).')

    table_html = fields.Html(sanitize=False)
    chart_html = fields.Html(sanitize=False)

    # ------------------------------------------------------------------
    # Thu thập dòng tiền: list of (date|None, amount, category, sign)
    # sign: +1 thu, -1 chi. date None → quá hạn/không ngày (bucket riêng)
    # ------------------------------------------------------------------
    def _collect_flows(self):
        env, flows = self.env, []

        # --- CHI: kỳ trả nợ KW chưa trả (re_loan) ---
        if 're.loan.note.interest.line' in env:
            lines = env['re.loan.note.interest.line'].search([
                ('state', '!=', 'paid'),
                ('note_id.state', 'in',
                 ('active', 'partial_paid', 'overdue', 'restructured')),
            ])
            for l in lines:
                amt = (l.amount_principal_remaining
                       + l.amount_interest_remaining
                       + l.amount_fee_remaining)
                if amt > 0:
                    flows.append((l.date_to, amt, 'Trả nợ vay (KW)', -1))

        # --- CHI: đợt phí bảo lãnh chưa trả (re_guarantee) ---
        if 're.bank.guarantee.payment.schedule' in env:
            scheds = env['re.bank.guarantee.payment.schedule'].search([])
            for s in scheds:
                remain = s.amount_due - s.amount_paid
                if remain > 0.01:
                    flows.append((s.due_date, remain, 'Phí bảo lãnh', -1))

        # --- Thuê tài sản: kỳ CHƯA lên hóa đơn (re_lease) ---
        if 're.lease.payment.line' in env:
            lease_lines = env['re.lease.payment.line'].search([
                ('state', '=', 'draft'),
                ('contract_id.state', '=', 'active')])
            for l in lease_lines:
                if l.amount_total <= 0:
                    continue
                if l.direction == 'in':
                    flows.append((l.date_due, l.amount_total,
                                  'Kỳ thuê phải trả', -1))
                else:
                    flows.append((l.date_due, l.amount_total,
                                  'Kỳ cho thuê lại (chưa HĐơn)', +1))

        # --- Hóa đơn NCC chưa trả / hóa đơn bán chưa thu ---
        moves = env['account.move'].search([
            ('state', '=', 'posted'),
            ('move_type', 'in', ('in_invoice', 'in_refund',
                                 'out_invoice', 'out_refund')),
            ('payment_state', 'in', ('not_paid', 'partial')),
        ])
        for m in moves:
            res = m.amount_residual
            if res <= 0.01:
                continue
            due = m.invoice_date_due or m.invoice_date
            if m.move_type == 'in_invoice':
                flows.append((due, res, 'Hóa đơn NCC', -1))
            elif m.move_type == 'in_refund':
                flows.append((due, res, 'Hóa đơn NCC', +1))
            elif m.move_type == 'out_invoice':
                flows.append((due, res, 'Hóa đơn bán chờ thu', +1))
            else:
                flows.append((due, res, 'Hóa đơn bán chờ thu', -1))

        # --- CHI: milestone HĐ nhà thầu KẾ HOẠCH (rp_contract) ---
        if 'rp.contract.payment.milestone' in env:
            miles = env['rp.contract.payment.milestone'].search([
                ('state', '=', 'planned'),
                ('contract_id.state', 'in', ('signed', 'executing'))])
            for ms in miles:
                if ms.amount > 0:
                    flows.append((ms.due_date, ms.amount,
                                  'Milestone HĐ nhà thầu (KH)', -1))
        return flows

    def _opening_cash(self):
        journals = self.env['account.journal'].search(
            [('type', 'in', ('bank', 'cash'))])
        accounts = journals.mapped('default_account_id')
        if not accounts:
            return 0.0
        groups = self.env['account.move.line']._read_group(
            [('account_id', 'in', accounts.ids),
             ('parent_state', '=', 'posted')],
            [], ['balance:sum'])
        return groups[0][0] or 0.0 if groups else 0.0

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        n_weeks = int(res.get('horizon') or 13)
        today = fields.Date.context_today(self)
        week0 = today - relativedelta(days=today.weekday())  # thứ 2
        flows = self._collect_flows()
        opening = self._opening_cash()

        # Bucket hoá: -1 = quá hạn, 0..n-1 = tuần, bỏ ngoài horizon
        cats_in, cats_out = {}, {}

        def bucket_of(d):
            if not d or d < week0:
                # không ngày hoặc trước tuần này: nếu đã quá hạn (< hôm
                # nay) → cột Quá hạn; trong tuần này nhưng chưa tới →
                # vẫn tuần 0
                if not d or d < today:
                    return -1
                return 0
            idx = (d - week0).days // 7
            return idx if idx < n_weeks else None

        total_in = total_out = over_in = over_out = 0.0
        for d, amt, cat, sign in flows:
            b = bucket_of(d)
            if b is None:
                continue
            target = cats_in if sign > 0 else cats_out
            row = target.setdefault(cat, [0.0] * (n_weeks + 1))
            row[b + 1] += amt
            if sign > 0:
                total_in += amt
                if b == -1:
                    over_in += amt
            else:
                total_out += amt
                if b == -1:
                    over_out += amt

        res['kpi_opening_cash'] = opening
        res['kpi_total_in'] = total_in
        res['kpi_total_out'] = total_out
        res['kpi_closing'] = opening + total_in - total_out
        res['kpi_overdue_in'] = over_in
        res['kpi_overdue_out'] = over_out
        if 'rp.owner.contract' in self.env:
            contracts = self.env['rp.owner.contract'].search(
                [('state', 'in', ('signed', 'executing'))])
            res['kpi_receivable_undated'] = sum(
                c.receivable for c in contracts if c.receivable > 0)
        else:
            res['kpi_receivable_undated'] = 0.0

        # Net + số dư lũy kế theo tuần (quá hạn tính vào tuần 0 khi
        # chiếu số dư — thận trọng: coi như phải trả/thu ngay)
        net = [0.0] * (n_weeks + 1)
        for row in cats_in.values():
            net = [a + b for a, b in zip(net, row)]
        for row in cats_out.values():
            net = [a - b for a, b in zip(net, row)]
        closing, closings = opening, []
        for i in range(n_weeks + 1):
            closing += net[i]
            if i >= 1:
                closings.append(closing)
            elif i == 0:
                pass  # cột quá hạn gộp vào trước tuần 1
        # closings[k] = số dư cuối tuần k+1 (đã trừ quá hạn từ đầu)
        first_neg = next(
            (k for k, v in enumerate(closings) if v < 0), None)
        res['first_negative_week'] = (
            'Tuần %d (%s)' % (
                first_neg + 1,
                (week0 + relativedelta(weeks=first_neg)
                 ).strftime('%d/%m'))
            if first_neg is not None else '')

        res['table_html'] = self._build_table(
            cats_in, cats_out, net, closings, opening, week0, n_weeks)
        res['chart_html'] = self._build_chart(
            net, closings, week0, n_weeks)
        return res

    # ------------------------------------------------------------------
    # Render
    # ------------------------------------------------------------------
    def _build_table(self, cats_in, cats_out, net, closings,
                     opening, week0, n_weeks):
        heads = ['Quá hạn'] + [
            'T%s<br/><span style="font-weight:400;color:#8a98a5">%s'
            '</span>' % (i + 1, (week0 + relativedelta(weeks=i)
                                 ).strftime('%d/%m'))
            for i in range(n_weeks)]
        td = ('style="padding:4px 8px;text-align:right;'
              'border-bottom:1px solid #eef2f5;white-space:nowrap"')
        th = ('style="padding:5px 8px;text-align:right;'
              'background:#f4f7f9;font-size:11px"')
        thl = th.replace('right', 'left')
        tdl = td.replace('right', 'left')

        def row_html(label, row, color=''):
            cells = ''.join(
                '<td %s>%s</td>' % (
                    td, ('<span style="color:%s">%s</span>' % (
                        color, _fmt(v)) if v and color else
                        (_fmt(v) if v else
                         '<span style="color:#c3ccd3">·</span>')))
                for v in row)
            return '<tr><td %s>%s</td>%s</tr>' % (tdl, label, cells)

        parts = ['<div style="overflow-x:auto"><table style="border-'
                 'collapse:collapse;font-size:12px;min-width:100%%">'
                 '<tr><th %s>Nguồn</th>%s</tr>' % (
                     thl, ''.join('<th %s>%s</th>' % (th, h)
                                  for h in heads))]
        if cats_in:
            parts.append('<tr><td %s colspan="%d" style="padding:6px 8px;'
                         'font-weight:700;color:#2C7A57">DÒNG THU</td>'
                         '</tr>' % (tdl, n_weeks + 2))
            for cat in sorted(cats_in):
                parts.append(row_html(cat, cats_in[cat], '#2C7A57'))
        if cats_out:
            parts.append('<tr><td %s colspan="%d" style="padding:6px 8px;'
                         'font-weight:700;color:#B23A2E">DÒNG CHI</td>'
                         '</tr>' % (tdl, n_weeks + 2))
            for cat in sorted(cats_out):
                parts.append(row_html(cat, cats_out[cat], '#B23A2E'))
        # Net + closing
        parts.append(row_html('<b>Ròng trong kỳ</b>', net))
        closing_row = [''] + closings
        cells = ''.join(
            '<td %s><b style="color:%s">%s</b></td>' % (
                td, '#B23A2E' if isinstance(v, float) and v < 0
                else '#0F2C3F', _fmt(v) if v != '' else '—')
            for v in closing_row)
        parts.append(
            '<tr style="background:#f8fafb"><td %s><b>Số dư lũy kế '
            '(đầu kỳ %s)</b></td>%s</tr>' % (tdl, _fmt(opening), cells))
        parts.append('</table></div>')
        return ''.join(parts)

    def _build_chart(self, net, closings, week0, n_weeks, width=940,
                     height=240):
        vals = closings or [0.0]
        maxv = max(max(vals), 0.0) or 1
        minv = min(min(vals), 0.0)
        rng = (maxv - minv) or 1
        pad_l, pad_r, pad_t, pad_b = 64, 12, 14, 26
        pw, ph = width - pad_l - pad_r, height - pad_t - pad_b

        def X(i):
            return pad_l + pw * i / max(1, len(vals) - 1)

        def Y(v):
            return pad_t + ph * (1 - (v - minv) / rng)

        parts = ['<svg viewBox="0 0 %d %d" width="100%%" '
                 'xmlns="http://www.w3.org/2000/svg">' % (width, height)]
        # trục 0
        y0 = Y(0)
        parts.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" '
                     'stroke="#B23A2E" stroke-dasharray="4 3" '
                     'stroke-width="1"/>' % (pad_l, y0, width - pad_r, y0))
        parts.append('<text x="%d" y="%.1f" font-size="10" fill="#8a98a5" '
                     'text-anchor="end">0</text>' % (pad_l - 6, y0 + 3))
        # đường số dư
        path = 'M ' + ' L '.join(
            '%.1f,%.1f' % (X(i), Y(v)) for i, v in enumerate(vals))
        parts.append('<path d="%s" fill="none" stroke="#1B6CA8" '
                     'stroke-width="2.4"/>' % path)
        for i, v in enumerate(vals):
            color = '#B23A2E' if v < 0 else '#1B6CA8'
            parts.append('<circle cx="%.1f" cy="%.1f" r="3.2" '
                         'fill="%s"/>' % (X(i), Y(v), color))
            if i % max(1, len(vals) // 13) == 0:
                parts.append('<text x="%.1f" y="%d" font-size="9.5" '
                             'fill="#8a98a5" text-anchor="middle">T%d'
                             '</text>' % (X(i), height - 8, i + 1))
        parts.append('<text x="%d" y="%d" font-size="11" fill="#3A4A57">'
                     'Số dư lũy kế dự kiến theo tuần</text>' % (pad_l, 12))
        parts.append('</svg>')
        return ''.join(parts)

    # ------------------------------------------------------------------
    # Drill-down
    # ------------------------------------------------------------------
    def _open(self, name, model, domain):
        return {'type': 'ir.actions.act_window', 'name': name,
                'res_model': model, 'view_mode': 'list,form',
                'domain': domain}

    def action_open_loan_lines(self):
        return self._open(
            'Kỳ trả nợ KW chưa trả', 're.loan.note.interest.line',
            [('state', '!=', 'paid'),
             ('note_id.state', 'in',
              ('active', 'partial_paid', 'overdue', 'restructured'))])

    def action_open_vendor_bills(self):
        return self._open(
            'Hóa đơn NCC chưa trả', 'account.move',
            [('move_type', '=', 'in_invoice'), ('state', '=', 'posted'),
             ('payment_state', 'in', ('not_paid', 'partial'))])

    def action_open_customer_invoices(self):
        return self._open(
            'Hóa đơn bán chờ thu', 'account.move',
            [('move_type', '=', 'out_invoice'), ('state', '=', 'posted'),
             ('payment_state', 'in', ('not_paid', 'partial'))])
