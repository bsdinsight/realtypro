# -*- coding: utf-8 -*-
"""Màn hình "Cấu trúc tín dụng" — thay bố cục cũ của re.loan.dashboard.

Việc riêng của màn này: **vay ở những ngân hàng nào · hạn mức chia ra sao
giữa cho vay và bảo lãnh · chỗ nào sắp hết hiệu lực**. Đây là màn hình
CẤU TRÚC, không phải màn hình HÀNH ĐỘNG — việc tồn hằng ngày đã có
dashboard "Việc hôm nay", phân tích theo dự án đã có "Vốn theo dự án".

Bố cục cũ có 30 thẻ số và trùng khoảng hai phần ba với ba dashboard mới
(workflow chờ, cảnh báo, KW/BL sắp đến hạn). Bản này bỏ hết phần trùng,
giữ phần không màn nào khác có (HĐTD, tách cho vay/bảo lãnh, 5 biểu đồ)
và thêm hai thứ đang thiếu: bảng theo ngân hàng và dòng thời gian hiệu
lực HĐTD.

MỘT ĐIỂM PHẢI GIỮ ĐÚNG: thẻ "Hạn mức chưa dùng" = hạn mức − đã dùng,
**chưa trừ ràng buộc tài sản bảo đảm**, nên LỚN HƠN số rút được thật.
Bản cũ gọi nó là "Cho vay còn lại" và người đọc tưởng đó là tiền rút
được — trên dữ liệu thật lệch tới hàng trăm tỷ so với "Khả dụng thực tế"
ở dashboard Vốn & Ngân quỹ. Vì vậy nhãn phải khác tên và luôn kèm dòng
chú thích chỉ sang chỗ có con số đúng.
"""
from markupsafe import Markup, escape

from odoo import _, api, fields, models

from . import dc_render as R

BANK_PALETTE = ['#0E8C99', '#3E5A68', '#7FB6BE', '#0F2C3F', '#5E7683',
                '#A9CFD4']


class ReCreditStructure(models.TransientModel):
    _name = 're.credit.structure'
    _description = 'Cấu trúc tín dụng'

    body_html = fields.Html(
        string='Nội dung', sanitize=False, compute='_compute_body')

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = _('Cấu trúc tín dụng')

    @api.model
    def action_open(self):
        rec = self.create({})
        return {
            'type': 'ir.actions.act_window',
            'name': _('Cấu trúc tín dụng'),
            'res_model': self._name,
            'res_id': rec.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # ------------------------------------------------------------------
    def _url(self, xmlid):
        act = self.env.ref(xmlid, raise_if_not_found=False)
        return '/odoo/action-%s' % act.id if act else None

    @staticmethod
    def _link(url, inner):
        if not url:
            return inner
        return Markup('<a href="%s" style="text-decoration:none;'
                      'color:inherit;display:block">%s</a>') % (url, inner)

    # ------------------------------------------------------------------
    def _collect(self):
        """Gom số liệu. KPI cơ bản lấy lại từ re.loan.dashboard bằng
        `default_get` — không tạo bản ghi, không chép lại công thức, nên
        hai màn không bao giờ lệch nhau."""
        env = self.env
        Dash = env['re.loan.dashboard']
        kpi_fields = [
            'kpi_hdtd_active', 'kpi_hdtd_total_limit',
            'kpi_hdtd_facility_granted', 'kpi_hdtd_remaining',
            'kpi_hdtd_expiring_90d',
            'kpi_facility_loan_limit', 'kpi_facility_loan_used',
            'kpi_facility_loan_avail', 'kpi_facility_loan_used_pct',
            'kpi_facility_bg_limit', 'kpi_facility_bg_used',
            'kpi_facility_bg_avail', 'kpi_facility_bg_used_pct',
            'kpi_kw_active', 'kpi_kw_principal_outstanding',
            'kpi_kw_interest_paid_ytd',
            'kpi_bg_outstanding', 'kpi_bg_count_active',
            # 3 chỉ số borrowing base: trước đây sống trên form dashboard
            # cũ (module re_loan_borrowing_base chèn vào). Màn đó đã bị
            # thay nên chúng mất chỗ — kéo về đây, vì cơ sở bảo đảm
            # chính là một phần của cấu trúc tín dụng.
            'kpi_bb_base_total', 'kpi_bb_available_effective',
            'kpi_bb_margin_call',
        ]
        kpi = Dash.default_get(kpi_fields)

        contracts = env['re.loan.credit.contract'].search(
            [('state', '=', 'active')])
        notes = env['re.loan.note'].search(
            [('state', 'not in', ('draft', 'cancelled', 'fully_paid'))])
        G = env['re.bank.guarantee'] if 're.bank.guarantee' in env else None
        bgs = (G.search([('state', 'in', ('issued', 'extended'))])
               if G is not None else None)

        # ---- gom theo ngân hàng ----
        banks = {}
        for cc in contracts:
            p = cc.partner_id
            b = banks.setdefault(p.id, {
                'name': p.display_name or _('(chưa khai ngân hàng)'),
                'contracts': 0, 'limit': 0.0, 'granted': 0.0,
                'debt': 0.0, 'bg': 0.0, 'rate_w': 0.0})
            b['contracts'] += 1
            b['limit'] += cc.amount_total or 0.0
            b['granted'] += cc.amount_facility_total or 0.0
        for n in notes:
            cc = n.facility_id.credit_contract_id
            if cc and cc.partner_id.id in banks:
                banks[cc.partner_id.id]['debt'] += \
                    n.principal_outstanding or 0.0
                # tử số của lãi suất bình quân GIA QUYỀN theo dư nợ —
                # trung bình cộng lãi suất là con số sai
                banks[cc.partner_id.id]['rate_w'] += \
                    (n.interest_rate or 0.0) \
                    * (n.principal_outstanding or 0.0)
        if bgs is not None:
            for g in bgs:
                cc = g.credit_contract_id
                if cc and cc.partner_id.id in banks:
                    banks[cc.partner_id.id]['bg'] += g.amount or 0.0
        bank_rows = sorted(banks.values(), key=lambda b: -b['limit'])

        # ---- KW đáo hạn theo mốc (cơ cấu kỳ hạn, KHÔNG phải việc tồn) --
        today = fields.Date.context_today(self)
        buckets = [('≤ 90', 'ngày', 0, 90), ('91 – 180', 'ngày', 91, 180),
                   ('181 – 365', 'ngày', 181, 365),
                   ('> 365', 'ngày', 366, 10 ** 6)]
        mat = []
        for l1, l2, lo, hi in buckets:
            amt = cnt = 0
            for n in notes:
                if not n.date_maturity or n.principal_outstanding <= 0:
                    continue
                d = (n.date_maturity - today).days
                if lo <= max(d, 0) <= hi:
                    amt += n.principal_outstanding
                    cnt += 1
            mat.append({'l1': l1, 'l2': l2, 'value': amt, 'count': cnt,
                        'color': R.C['teal'] if hi <= 180
                        else R.C['ink'] if hi <= 365 else '#7FB6BE'})

        # ---- bảo lãnh theo loại ----
        bg_rows = []
        if bgs is not None and bgs:
            labels = dict(bgs._fields['guarantee_type'].selection)
            per = {}
            for g in bgs:
                per[g.guarantee_type] = per.get(g.guarantee_type, 0.0) \
                    + (g.amount or 0.0)
            bg_rows = [{'label': labels.get(k, k), 'value': v}
                       for k, v in sorted(per.items(), key=lambda x: -x[1])]

        # ---- dòng thời gian HĐTD ----
        tl = []
        for cc in contracts:
            end = cc.date_end
            tl.append({
                'code': cc.name or '—',
                'bank': cc.partner_id.display_name or '—',
                'date_from': cc.date_start or cc.sign_date,
                'date_to': end,
                'days': (end - today).days if end else None,
            })
        tl.sort(key=lambda x: (x['days'] is None, x['days'] or 0))
        return {'kpi': kpi, 'banks': bank_rows, 'mat': mat,
                'bg_rows': bg_rows, 'timeline': tl, 'today': today,
                'contracts': contracts, 'n_banks': len(banks),
                'n_facilities': sum(len(c.facility_ids)
                                    for c in contracts)}

    # ------------------------------------------------------------------
    @api.depends_context('uid')
    def _compute_body(self):
        for rec in self:
            rec.body_html = rec._render()

    def _render(self):
        d = self._collect()
        k = d['kpi']
        return Markup(
            '<div style="background:%s;color:%s;font-size:13px;'
            'line-height:1.35;padding:16px 4px 24px">%s%s%s%s%s%s</div>'
        ) % (R.C['bg'], R.C['navy'],
             self._head(d), self._cards(k, d), self._split_and_gauge(k, d),
             self._bank_table(d), self._charts(k, d), self._timeline(d))

    def _head(self, d):
        return Markup(
            '<div style="display:flex;align-items:baseline;'
            'justify-content:space-between;margin-bottom:12px">'
            '<div style="display:flex;align-items:baseline;gap:10px">'
            '<h1 style="margin:0;font-size:17px;font-weight:700">Cấu trúc '
            'tín dụng</h1><span style="font-size:12px;color:%s">Vay ở '
            'những ngân hàng nào · hạn mức chia ra sao giữa cho vay và '
            'bảo lãnh · chỗ nào sắp hết hiệu lực</span></div>'
            '<span style="font-size:11px;color:%s">Ảnh cấu trúc tại %s · '
            'việc tồn hằng ngày xem dashboard Vốn &amp; Ngân quỹ</span>'
            '</div>'
        ) % (R.C['muted'], R.C['faint'],
             d['today'].strftime('%d/%m/%Y'))

    def _card(self, label, value, foot, top_color, value_color=None,
              title='', url=None):
        card = Markup(
            '<div style="background:#fff;border:1px solid %s;'
            'border-top:3px solid %s;border-radius:4px;padding:14px 16px">'
            '<div style="font-size:11.5px;font-weight:600;color:%s;'
            'text-transform:uppercase;letter-spacing:.04em">%s</div>'
            '<div title="%s" style="margin-top:8px;font-size:30px;'
            'font-weight:700;color:%s;font-variant-numeric:tabular-nums">'
            '%s</div><div style="margin-top:6px;font-size:11.5px;'
            'color:%s">%s</div></div>'
        ) % (R.C['line'], top_color, R.C['muted'], label, title,
             value_color or R.C['navy'], value, R.C['faint'], foot)
        return self._link(url, card)

    def _cards(self, k, d):
        total = k.get('kpi_hdtd_total_limit') or 0.0
        granted = k.get('kpi_hdtd_facility_granted') or 0.0
        pct_granted = (granted / total * 100.0) if total else 0.0
        u_cc = self._url('re_loan.action_re_loan_credit_contract')
        u_fac = self._url('re_loan.action_re_loan_facility')
        return Markup(
            '<div style="display:grid;grid-template-columns:repeat(4,1fr);'
            'gap:12px">%s%s%s%s</div>'
        ) % (
            self._card('HĐTD đang hiệu lực',
                       str(k.get('kpi_hdtd_active') or 0),
                       _('%s ngân hàng · %s facility')
                       % (d['n_banks'], d['n_facilities']),
                       R.C['navy'], url=u_cc),
            self._card('Tổng hạn mức HĐTD', R.fmt(total),
                       'Trần toàn bộ các HĐTD', R.C['teal'],
                       value_color=R.C['teal'], title=R.full(total),
                       url=u_cc),
            self._card('Đã cấp thành facility', R.fmt(granted),
                       _('%s tổng hạn mức') % R.pct(pct_granted),
                       R.C['teal'], title=R.full(granted), url=u_fac),
            self._card('HĐTD còn chưa cấp',
                       R.fmt(k.get('kpi_hdtd_remaining') or 0.0),
                       'Phần trần chưa chia thành facility',
                       R.C['amber'], value_color='#9A6412',
                       title=R.full(k.get('kpi_hdtd_remaining') or 0.0),
                       url=u_cc),
        )

    # ------------------------------------------------------------------
    def _side(self, title, dot, limit, used, used_label, avail, pct_v,
              note):
        """Một cột của khối 'Cho vay vs Bảo lãnh'."""
        bar_color = (R.C['red'] if pct_v >= 90 else R.C['amber']
                     if pct_v >= 75 else R.C['green'])
        return Markup(
            '<div><div style="display:flex;align-items:center;gap:7px;'
            'font-size:12.5px;font-weight:700;color:%s;'
            'text-transform:uppercase;letter-spacing:.04em">'
            '<span style="width:9px;height:9px;border-radius:2px;'
            'background:%s;display:inline-block"></span>%s</div>'
            '<div style="display:grid;grid-template-columns:1fr 185px;'
            'gap:6px 10px;margin-top:10px;align-items:baseline">'
            '<span style="font-size:12px;color:%s">Hạn mức được cấp</span>'
            '<span title="%s" style="text-align:right;font-size:17px;'
            'font-weight:600;font-variant-numeric:tabular-nums">%s</span>'
            '<span style="font-size:12px;color:%s">%s</span>'
            '<span title="%s" style="text-align:right;font-size:17px;'
            'font-weight:700;color:%s;font-variant-numeric:tabular-nums">'
            '%s</span>'
            '<span style="font-size:12px;color:%s;font-weight:600">Hạn mức '
            'chưa dùng</span>'
            '<span title="%s" style="text-align:right;font-size:22px;'
            'font-weight:700;font-variant-numeric:tabular-nums">%s</span>'
            '</div>'
            '<div style="margin-top:8px;display:flex;align-items:center;'
            'gap:10px"><div style="flex:1 1 auto;height:9px;background:%s;'
            'border-radius:4px;overflow:hidden"><div style="width:%.1f%%;'
            'height:100%%;background:%s"></div></div>'
            '<span style="font-size:14px;font-weight:700;color:%s;'
            'font-variant-numeric:tabular-nums">%s</span></div>'
            '<div style="margin-top:8px;background:#FDF1DD;'
            'border-left:3px solid %s;border-radius:2px;padding:7px 9px;'
            'font-size:11px;color:#6B4A0F">%s</div></div>'
        ) % (dot[1], dot[0], title, R.C['muted'], R.full(limit),
             R.fmt(limit), R.C['muted'], used_label, R.full(used),
             R.C['teal'], R.fmt(used), R.C['muted'], R.full(avail),
             R.fmt(avail), R.C['line2'], min(100.0, max(0.0, pct_v)),
             bar_color, bar_color, R.pct(pct_v), R.C['amber'], note)

    def _split_and_gauge(self, k, d):
        loan_lim = k.get('kpi_facility_loan_limit') or 0.0
        loan_used = k.get('kpi_facility_loan_used') or 0.0
        bg_lim = k.get('kpi_facility_bg_limit') or 0.0
        bg_used = k.get('kpi_facility_bg_used') or 0.0
        granted = k.get('kpi_hdtd_facility_granted') or 0.0
        overall = ((loan_used + bg_used) / granted * 100.0) if granted \
            else 0.0

        left = self._side(
            'Hạn mức cho vay', ('#0E8C99', R.C['teal']), loan_lim,
            loan_used, 'Đã dùng (dư nợ KW)',
            k.get('kpi_facility_loan_avail') or 0.0,
            # `*_used_pct` của re.loan.dashboard lưu dạng TỈ LỆ 0–1
            # (view cũ hiển thị bằng widget="percentage" nên tự nhân 100).
            # Không nhân ở đây thì 19,6% hiện ra thành 0,2%.
            (k.get('kpi_facility_loan_used_pct') or 0.0) * 100.0,
            Markup('Chưa trừ ràng buộc tài sản bảo đảm. Số rút được thật '
                   'xem <b>Khả dụng thực tế</b> ở dashboard Vốn &amp; '
                   'Ngân quỹ.'))
        right = self._side(
            'Hạn mức bảo lãnh', ('#7FB6BE', R.C['ink']), bg_lim, bg_used,
            'Đã dùng (BL outstanding)',
            k.get('kpi_facility_bg_avail') or 0.0,
            (k.get('kpi_facility_bg_used_pct') or 0.0) * 100.0,
            Markup('Chưa trừ ràng buộc tài sản bảo đảm. Số phát hành được '
                   'thật còn phụ thuộc TSBĐ và điều kiện từng facility.'))

        small = Markup(
            '<div style="display:grid;grid-template-columns:1fr 1fr;'
            'gap:12px">'
            '<div style="background:#fff;border:1px solid %s;'
            'border-left:3px solid %s;border-radius:4px;padding:11px 13px">'
            '<div style="font-size:11px;font-weight:600;color:%s">Lãi vay '
            'đã trả trong năm</div><div title="%s" style="margin-top:5px;'
            'font-size:21px;font-weight:700;color:%s;'
            'font-variant-numeric:tabular-nums">%s</div>'
            '<div style="font-size:11px;color:%s;margin-top:3px">01/01 – '
            '%s</div></div>'
            '<div style="background:#fff;border:1px solid %s;'
            'border-left:3px solid %s;border-radius:4px;padding:11px 13px">'
            '<div style="font-size:11px;font-weight:600;color:%s">Tổng dư '
            'nợ gốc</div><div title="%s" style="margin-top:5px;'
            'font-size:21px;font-weight:700;'
            'font-variant-numeric:tabular-nums">%s</div>'
            '<div style="font-size:11px;color:%s;margin-top:3px">%s KW còn '
            'dư nợ</div></div>'
            '<div style="background:#fff;border:1px solid %s;'
            'border-left:3px solid %s;border-radius:4px;padding:11px 13px">'
            '<div style="font-size:11px;font-weight:600;color:%s">Cơ sở bảo '
            'đảm (borrowing base)</div><div title="%s" '
            'style="margin-top:5px;font-size:21px;font-weight:700;'
            'font-variant-numeric:tabular-nums">%s</div>'
            '<div style="font-size:11px;color:%s;margin-top:3px">khả dụng '
            'theo TSBĐ %s</div></div>'
            '<div style="background:#fff;border:1px solid %s;'
            'border-left:3px solid %s;border-radius:4px;padding:11px 13px">'
            '<div style="font-size:11px;font-weight:600;color:%s">Thiếu bảo '
            'đảm (margin call)</div><div style="margin-top:5px;'
            'font-size:21px;font-weight:700;color:%s;'
            'font-variant-numeric:tabular-nums">%s</div>'
            '<div style="font-size:11px;color:%s;margin-top:3px">%s</div>'
            '</div></div>'
        ) % (R.C['line'], R.C['teal'], R.C['muted'],
             R.full(k.get('kpi_kw_interest_paid_ytd') or 0.0), R.C['teal'],
             R.fmt(k.get('kpi_kw_interest_paid_ytd') or 0.0), R.C['faint'],
             d['today'].strftime('%d/%m/%Y'),
             R.C['line'], R.C['navy'], R.C['muted'],
             R.full(k.get('kpi_kw_principal_outstanding') or 0.0),
             R.fmt(k.get('kpi_kw_principal_outstanding') or 0.0),
             R.C['faint'], k.get('kpi_kw_active') or 0,
             R.C['line'], '#7FB6BE', R.C['muted'],
             R.full(k.get('kpi_bb_base_total') or 0.0),
             R.fmt(k.get('kpi_bb_base_total') or 0.0), R.C['faint'],
             R.fmt(k.get('kpi_bb_available_effective') or 0.0),
             R.C['line'],
             R.C['red'] if (k.get('kpi_bb_margin_call') or 0) else R.C['green'],
             R.C['muted'],
             R.C['red'] if (k.get('kpi_bb_margin_call') or 0) else R.C['green'],
             '%s hạn mức' % (k.get('kpi_bb_margin_call') or 0),
             R.C['faint'],
             'dư nợ vượt cơ sở bảo đảm riêng' if (k.get('kpi_bb_margin_call') or 0)
             else 'không hạn mức nào vượt')

        return Markup(
            '<div style="display:grid;grid-template-columns:1fr 386px;'
            'gap:12px;margin-top:12px">'
            '<div style="background:#fff;border:1px solid %s;'
            'border-radius:4px;padding:14px 16px">'
            '<div style="font-size:13px;font-weight:700">Cho vay vs Bảo '
            'lãnh</div><div style="display:grid;'
            'grid-template-columns:1fr 1px 1fr;gap:16px;margin-top:12px">'
            '%s<div style="background:%s"></div>%s</div></div>'
            '<div style="display:flex;flex-direction:column;gap:12px">'
            '<div style="background:#fff;border:1px solid %s;'
            'border-radius:4px;padding:12px 14px">'
            '<div style="font-size:13px;font-weight:700">Tỷ lệ sử dụng hạn '
            'mức</div>%s</div>%s</div></div>'
        ) % (R.C['line'], left, R.C['line2'], right, R.C['line'],
             R.gauge(overall, R.pct(overall),
                     '(dư nợ + BL) / đã cấp facility'), small)

    # ------------------------------------------------------------------
    COLS = '190px 70px 175px 175px 175px 165px 96px 160px'

    def _bank_table(self, d):
        head = Markup(
            '<div style="display:grid;grid-template-columns:%s;'
            'gap:0 10px;padding:0 4px 7px;border-bottom:1px solid %s;'
            'font-size:10.5px;font-weight:700;color:%s;'
            'text-transform:uppercase;letter-spacing:.04em">'
            '<div>Ngân hàng</div><div style="text-align:right">Số HĐTD</div>'
            '<div style="text-align:right">Tổng hạn mức</div>'
            '<div style="text-align:right">Đã cấp facility</div>'
            '<div style="text-align:right">Dư nợ</div>'
            '<div style="text-align:right">BL outstanding</div>'
            '<div style="text-align:right">LS bình quân</div>'
            '<div>Tỷ lệ sử dụng</div></div>'
        ) % (Markup(self.COLS), R.C['line'], R.C['muted'])

        rows = []
        tot = {'contracts': 0, 'limit': 0.0, 'granted': 0.0, 'debt': 0.0,
               'bg': 0.0, 'rate_w': 0.0}
        for i, b in enumerate(d['banks']):
            for key in tot:
                tot[key] += b[key]
            used = b['debt'] + b['bg']
            p = (used / b['granted'] * 100.0) if b['granted'] else None
            color = (R.C['gray'] if p is None else R.C['red'] if p >= 90
                     else R.C['amber'] if p >= 75 else R.C['green'])
            rows.append(Markup(
                '<div style="display:grid;grid-template-columns:%s;'
                'gap:0 10px;padding:9px 4px;border-bottom:1px solid #F1F4F5;'
                'align-items:center">'
                '<div style="display:flex;align-items:center;gap:8px;'
                'font-size:13px;font-weight:600">'
                '<span style="width:9px;height:9px;border-radius:50%%;'
                'flex:0 0 auto;background:%s"></span>%s</div>'
                '<div style="text-align:right;font-size:13px;'
                'font-variant-numeric:tabular-nums;color:%s">%d</div>'
                '<div title="%s" style="text-align:right;font-size:14px;'
                'font-variant-numeric:tabular-nums">%s</div>'
                '<div title="%s" style="text-align:right;font-size:14px;'
                'font-variant-numeric:tabular-nums;color:%s">%s</div>'
                '<div title="%s" style="text-align:right;font-size:14px;'
                'font-weight:600;color:%s;'
                'font-variant-numeric:tabular-nums">%s</div>'
                '<div title="%s" style="text-align:right;font-size:14px;'
                'font-variant-numeric:tabular-nums;color:%s">%s</div>'
                '<div title="Bình quân gia quyền theo dư nợ gốc — KHÔNG '
                'phải trung bình cộng" style="text-align:right;'
                'font-size:14px;font-weight:600;'
                'font-variant-numeric:tabular-nums;color:%s">%s</div>'
                '<div style="display:flex;align-items:center;gap:9px">'
                '<div style="flex:1 1 auto;height:8px;background:%s;'
                'border-radius:4px;overflow:hidden"><div style="height:100%%;'
                'width:%.1f%%;background:%s"></div></div>'
                '<span style="font-size:13px;font-weight:700;'
                'font-variant-numeric:tabular-nums;color:%s;'
                'min-width:52px;text-align:right">%s</span></div></div>'
            ) % (Markup(self.COLS),
                 BANK_PALETTE[i % len(BANK_PALETTE)], escape(b['name']),
                 R.C['ink'], b['contracts'],
                 R.full(b['limit']), R.fmt(b['limit']),
                 R.full(b['granted']), R.C['ink'], R.fmt(b['granted']),
                 R.full(b['debt']), R.C['teal'], R.fmt(b['debt']),
                 R.full(b['bg']), R.C['ink'], R.fmt(b['bg']),
                 R.C['navy'],
                 R.pct(b['rate_w'] / b['debt'], 2) if b['debt'] else '—',
                 R.C['line2'], min(100.0, p or 0.0), color, color,
                 R.pct(p) if p is not None else '—'))

        if not rows:
            return Markup(
                '<div style="background:#fff;border:1px solid %s;'
                'border-radius:4px;padding:14px 16px;margin-top:12px">'
                '<div style="font-size:13px;font-weight:700">Cấu trúc theo '
                'ngân hàng</div><div style="padding:28px;text-align:center;'
                'color:%s"><div style="font-weight:600;color:%s">Chưa có '
                'HĐTD nào đang hiệu lực</div><div style="font-size:11.5px;'
                'margin-top:5px">Tạo hợp đồng tín dụng rồi kích hoạt để '
                'thấy cấu trúc theo ngân hàng.</div></div></div>'
            ) % (R.C['line'], R.C['faint'], R.C['muted'])

        tot_used = tot['debt'] + tot['bg']
        tot_pct = (tot_used / tot['granted'] * 100.0) if tot['granted'] \
            else None
        total_row = Markup(
            '<div style="display:grid;grid-template-columns:%s;'
            'gap:0 10px;padding:10px 4px 0;align-items:center;'
            'font-weight:700">'
            '<div style="font-size:12.5px">Tổng cộng</div>'
            '<div style="text-align:right;font-size:13px;'
            'font-variant-numeric:tabular-nums">%d</div>'
            '<div style="text-align:right;font-size:14px;'
            'font-variant-numeric:tabular-nums">%s</div>'
            '<div style="text-align:right;font-size:14px;'
            'font-variant-numeric:tabular-nums">%s</div>'
            '<div style="text-align:right;font-size:14px;color:%s;'
            'font-variant-numeric:tabular-nums">%s</div>'
            '<div style="text-align:right;font-size:14px;'
            'font-variant-numeric:tabular-nums">%s</div>'
            '<div style="text-align:right;font-size:14px;'
            'font-variant-numeric:tabular-nums">%s</div>'
            '<div style="text-align:right;font-size:13px;color:%s;'
            'font-variant-numeric:tabular-nums">%s</div></div>'
        ) % (Markup(self.COLS), tot['contracts'], R.fmt(tot['limit']),
             R.fmt(tot['granted']), R.C['teal'], R.fmt(tot['debt']),
             R.fmt(tot['bg']),
             R.pct(tot['rate_w'] / tot['debt'], 2) if tot['debt'] else '—',
             R.C['amber'],
             R.pct(tot_pct) if tot_pct is not None else '—')

        return Markup(
            '<div style="background:#fff;border:1px solid %s;'
            'border-radius:4px;padding:14px 16px;margin-top:12px">'
            '<div style="display:flex;align-items:baseline;'
            'justify-content:space-between;margin-bottom:10px"><div>'
            '<div style="font-size:13px;font-weight:700">Cấu trúc theo '
            'ngân hàng</div><div style="font-size:11px;color:%s">Đọc cả '
            'hàng khi chuẩn bị đàm phán với một nhà tài trợ</div></div>'
            '<div style="font-size:11px;color:%s">Tỷ lệ sử dụng = (dư nợ + '
            'BL outstanding) / đã cấp facility</div></div>%s%s%s</div>'
        ) % (R.C['line'], R.C['faint'], R.C['faint'], head,
             Markup('').join(rows), total_row)

    # ------------------------------------------------------------------
    def _chart_box(self, title, sub, svg):
        return Markup(
            '<div style="background:#fff;border:1px solid %s;'
            'border-radius:4px;padding:12px 14px">'
            '<div style="font-size:12.5px;font-weight:700">%s</div>'
            '<div style="font-size:11px;color:%s">%s</div>%s</div>'
        ) % (R.C['line'], title, R.C['faint'], sub, svg)

    def _charts(self, k, d):
        loan_lim = k.get('kpi_facility_loan_limit') or 0.0
        bg_lim = k.get('kpi_facility_bg_limit') or 0.0
        rest = k.get('kpi_hdtd_remaining') or 0.0
        donut = R.donut(
            [{'label': 'Hạn mức cho vay', 'value': loan_lim,
              'color': R.C['teal']},
             {'label': 'Hạn mức bảo lãnh', 'value': bg_lim,
              'color': '#7FB6BE'},
             {'label': 'Chưa cấp facility', 'value': rest,
              'color': '#C6D2D8'}],
            R.fmt(k.get('kpi_hdtd_total_limit') or 0.0), 'tổng hạn mức')
        debt_rows = [{'label': b['name'], 'value': b['debt'],
                      'color': BANK_PALETTE[i % len(BANK_PALETTE)]}
                     for i, b in enumerate(d['banks'])]
        bg_svg = (R.h_bars(d['bg_rows'], '#7FB6BE') if d['bg_rows']
                  else self._chart_empty('Chưa có bảo lãnh nào hiệu lực'))
        return Markup(
            '<div style="display:grid;grid-template-columns:repeat(4,1fr);'
            'gap:12px;margin-top:12px">%s%s%s%s</div>'
        ) % (
            self._chart_box('Cơ cấu hạn mức',
                            'Cho vay · bảo lãnh · chưa cấp', donut),
            self._chart_box('Dư nợ theo ngân hàng', 'Dư nợ gốc KW',
                            R.h_bars(debt_rows) if debt_rows
                            else self._chart_empty('Chưa có dư nợ')),
            self._chart_box('KW đáo hạn theo mốc',
                            'Cơ cấu kỳ hạn, không phải danh sách việc',
                            R.col_bars(d['mat'])),
            self._chart_box('Bảo lãnh theo loại',
                            'BL outstanding đang hiệu lực', bg_svg),
        )

    def _chart_empty(self, msg):
        return Markup(
            '<div style="height:176px;display:flex;align-items:center;'
            'justify-content:center;color:%s;font-size:11.5px">%s</div>'
        ) % (R.C['faint'], msg)

    # ------------------------------------------------------------------
    def _timeline(self, d):
        tl = d['timeline']
        if not tl:
            return Markup('')
        soon = [x for x in tl if x['days'] is not None and x['days'] < 90]
        missing = [x for x in tl if x['days'] is None]
        msgs = []
        if soon:
            msgs.append(_(
                '%(n)s HĐTD hết hiệu lực trong 90 ngày (%(list)s) — mở hồ '
                'sơ tái cấp hạn mức.',
                n=len(soon),
                list='; '.join('%s · %s còn %d ngày'
                               % (x['bank'], x['code'], x['days'])
                               for x in soon[:3])))
        if missing:
            msgs.append(_(
                '%(n)s HĐTD chưa khai ngày hết hiệu lực (%(list)s), cần '
                'cập nhật để tính được thời hạn.',
                n=len(missing),
                list=', '.join(x['code'] for x in missing[:3])))
        if msgs:
            note = Markup(
                '<div style="margin-top:8px;background:#FDF1DD;'
                'border-left:3px solid %s;border-radius:2px;'
                'padding:8px 10px;font-size:11.5px;color:#6B4A0F">'
                '<b>Việc cần làm tiếp:</b> %s</div>'
            ) % (R.C['amber'], ' '.join(msgs))
        else:
            note = Markup(
                '<div style="margin-top:8px;background:#EAF6EE;'
                'border-left:3px solid %s;border-radius:2px;'
                'padding:8px 10px;font-size:11.5px;color:#2E5A41">'
                'Không HĐTD nào hết hiệu lực trong 90 ngày tới.</div>'
            ) % R.C['green']

        legend = Markup(
            '<div style="display:flex;gap:14px;font-size:11px;color:%s">%s'
            '</div>') % (R.C['muted'], Markup('').join([Markup(
                '<span><span style="display:inline-block;width:14px;'
                'height:8px;background:%s;border-radius:2px"></span> %s'
                '</span>') % (c, t) for t, c in [
                    ('Còn dài', R.C['teal']),
                    ('Còn < 90 ngày', R.C['amber']),
                    ('Chưa đủ dữ liệu', R.C['gray'])]]))

        return Markup(
            '<div style="background:#fff;border:1px solid %s;'
            'border-radius:4px;padding:14px 16px;margin-top:12px">'
            '<div style="display:flex;align-items:baseline;'
            'justify-content:space-between;margin-bottom:4px"><div>'
            '<div style="font-size:13px;font-weight:700">Dòng thời gian '
            'hiệu lực HĐTD</div><div style="font-size:11px;color:%s">Từ '
            'ngày ký tới ngày hết hiệu lực · tô cam khi còn dưới 90 ngày'
            '</div></div>%s</div>%s%s</div>'
        ) % (R.C['line'], R.C['faint'], legend,
             R.timeline(tl, d['today']), note)
