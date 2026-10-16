# -*- coding: utf-8 -*-
"""Biểu đồ xu hướng nhiều tag — vẽ bằng SVG dựng ở máy chủ.

Vì sao SVG máy chủ chứ không phải thư viện biểu đồ
---------------------------------------------------
Một thư viện biểu đồ đầy đủ là thứ nên có cho màn hình giám sát hằng
ngày. Nhưng ở đây mục đích khác: **nhìn thấy được dữ liệu trong kho**.
Kho chuỗi thời gian mà không có cách nào mở ra xem thì không ai kiểm
chứng được là nó đúng — và một tính năng không kiểm chứng được thì coi
như chưa có.

SVG dựng sẵn ở máy chủ chạy được ngay, không thêm tài nguyên tải về,
không phụ thuộc phiên bản thư viện. Khi làm màn hình giám sát thật
(B13 đầy đủ) thì thay phần vẽ, còn phần đọc dữ liệu bên dưới giữ
nguyên.

Mỗi tag một TRỤC RIÊNG, chuẩn hoá về 0–1
-----------------------------------------
Vẽ công suất (0–4000 kW) chung một trục với tốc độ gió (0–25 m/s) thì
đường gió thành một vạch phẳng sát đáy. Nên mỗi đường được chuẩn hoá
theo dải của CHÍNH nó, và giá trị thật ghi ở chú giải. Đổi lại phải
nói rõ: **không so được độ lớn giữa hai đường**, chỉ so được hình dạng
và thời điểm.
"""
import html
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

MAU = ['#0E8C99', '#D98E3B', '#2E7D5B', '#9B4D6B', '#4A5FA5', '#8A6D3B']

BUOC = [
    ('60', '1 phút'),
    ('300', '5 phút'),
    ('900', '15 phút'),
    ('3600', '1 giờ'),
    ('86400', '1 ngày'),
]


class EamTrendWizard(models.TransientModel):
    _name = 'eam.trend.wizard'
    _description = 'Xu hướng nhiều điểm đo'

    tag_ids = fields.Many2many('eam.tag', string='Điểm đo', required=True)
    date_from = fields.Datetime(
        string='Từ', required=True,
        default=lambda s: fields.Datetime.now() - timedelta(days=7))
    date_to = fields.Datetime(
        string='Đến', required=True, default=fields.Datetime.now)
    buoc = fields.Selection(
        BUOC, string='Gộp theo', default='3600', required=True)
    bo_nghi = fields.Boolean(
        string='Bỏ số đo bị đánh dấu',
        help='Mặc định KHÔNG bỏ. Người đọc phải thấy dữ liệu thật trước '
             'rồi mới quyết lọc — lọc sẵn thì không ai biết đã lọc mất '
             'bao nhiêu.')
    bieu_do = fields.Html(string='Biểu đồ', compute='_compute_bieu_do',
                          sanitize=False)

    # ------------------------------------------------------------------
    @api.depends('tag_ids', 'date_from', 'date_to', 'buoc', 'bo_nghi')
    def _compute_bieu_do(self):
        for w in self:
            w.bieu_do = w._ve() if w.tag_ids and w.date_from and w.date_to \
                else False

    def _ve(self):
        self.ensure_one()
        H = self.env['eam.historian']
        du = H.doc_gop(self.tag_ids.ids, self.date_from, self.date_to,
                       int(self.buoc), bo_nghi=self.bo_nghi)
        co_du = {t: du.get(t.id, []) for t in self.tag_ids}
        if not any(co_du.values()):
            return ('<div style="padding:12px;color:#777">Không có số đo '
                    'nào trong khoảng này.</div>')

        W, Hh, L, R, Tp, B = 900, 300, 8, 8, 10, 26
        moc = sorted({d['ts'] for ds in co_du.values() for d in ds})
        if len(moc) < 2:
            return ('<div style="padding:12px;color:#777">Chỉ có một điểm '
                    'dữ liệu — chưa vẽ được đường.</div>')
        t0, t1 = moc[0], moc[-1]
        khoang = (t1 - t0).total_seconds() or 1

        duong, chu_giai = [], []
        for i, (tag, ds) in enumerate(co_du.items()):
            ds = [d for d in ds if d['gt'] is not None]
            if len(ds) < 2:
                chu_giai.append((tag, None, None, MAU[i % len(MAU)], len(ds)))
                continue
            gts = [d['gt'] for d in ds]
            lo, hi = min(gts), max(gts)
            # Dải bằng 0 (đường phẳng) thì chia cho 0 — vẽ giữa khung.
            dai = (hi - lo) or 1.0
            diem = []
            for d in ds:
                x = L + (d['ts'] - t0).total_seconds() / khoang * (W - L - R)
                y = Tp + (1 - (d['gt'] - lo) / dai) * (Hh - Tp - B)
                diem.append('%.1f,%.1f' % (x, y))
            mau = MAU[i % len(MAU)]
            duong.append(
                '<polyline fill="none" stroke="%s" stroke-width="1.6" '
                'points="%s"/>' % (mau, ' '.join(diem)))
            chu_giai.append((tag, lo, hi, mau, len(ds)))

        luoi = ''.join(
            '<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="#E8E2D8" '
            'stroke-width="1"/>' % (L, Tp + k * (Hh - Tp - B) / 4.0,
                                    W - R, Tp + k * (Hh - Tp - B) / 4.0)
            for k in range(5))

        nhan_x = (
            '<text x="%d" y="%d" font-size="10" fill="#777">%s</text>'
            '<text x="%d" y="%d" font-size="10" fill="#777" '
            'text-anchor="end">%s</text>'
            % (L, Hh - 6, html.escape(t0.strftime('%d/%m %H:%M')),
               W - R, Hh - 6, html.escape(t1.strftime('%d/%m %H:%M')))
        )

        svg = (
            '<svg viewBox="0 0 %d %d" style="width:100%%;height:auto;'
            'background:#FFFDF9;border:1px solid #E8E2D8;border-radius:8px">'
            '%s%s%s</svg>' % (W, Hh, luoi, ''.join(duong), nhan_x))

        hang = []
        for tag, lo, hi, mau, n in chu_giai:
            if lo is None:
                hang.append(
                    '<tr><td><span style="display:inline-block;width:10px;'
                    'height:10px;background:%s;border-radius:2px"></span></td>'
                    '<td>%s</td><td colspan="3" style="color:#999">chưa đủ '
                    'dữ liệu (%d điểm)</td></tr>'
                    % (mau, html.escape(tag.display_name), n))
                continue
            hang.append(
                '<tr>'
                '<td><span style="display:inline-block;width:10px;height:10px;'
                'background:%s;border-radius:2px"></span></td>'
                '<td>%s</td><td style="text-align:right">%s</td>'
                '<td style="text-align:right">%s</td>'
                '<td style="color:#777">%s · %d điểm</td></tr>'
                % (mau, html.escape(tag.display_name),
                   self._so(lo), self._so(hi),
                   html.escape(tag.uom_label or ''), n))

        # `%%` chứ không phải `%`: chuỗi này đi qua toán tử `%`, nên một
        # dấu `%` lẻ trong CSS (`width:100%`) bị đọc là ký tự định dạng
        # và nổ ValueError. Đã dính hai lần trong cùng module.
        bang = (
            '<table style="width:100%%;margin-top:10px;font-size:12px;'
            'border-collapse:collapse">'
            '<tr style="color:#777;font-size:11px"><th></th><th '
            'style="text-align:left">Điểm đo</th><th style="text-align:right">'
            'Nhỏ nhất</th><th style="text-align:right">Lớn nhất</th>'
            '<th style="text-align:left">Đơn vị</th></tr>%s</table>'
            % ''.join(hang))

        canh = (
            '<div style="margin-top:8px;font-size:11px;color:#777">'
            'Mỗi đường được chuẩn hoá theo dải của <b>chính nó</b> để cùng '
            'nhìn được trên một khung — nên <b>không so được độ lớn</b> '
            'giữa hai đường, chỉ so được hình dạng và thời điểm. Giá trị '
            'thật xem ở bảng dưới.</div>')

        return svg + bang + canh

    @staticmethod
    def _so(v):
        if v is None:
            return '—'
        if abs(v) >= 1000:
            return '{:,.0f}'.format(v).replace(',', '.')
        return '{:,.2f}'.format(v).replace(',', '@').replace('.', ',') \
            .replace('@', '.')

    def action_ve_lai(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'eam.trend.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
