# -*- coding: utf-8 -*-
"""Chỉ số chất lượng dữ liệu — ba con số, cố ý KHÔNG gộp thành một.

Mọi người đều muốn một điểm "chất lượng dữ liệu: 87%". Nhưng ba thứ
dưới đây cần ba cách xử lý khác hẳn nhau, và một con số gộp thì không
phân biệt được:

* **Độ phủ thấp** → mất dữ liệu. Vấn đề ở đường truyền hoặc bộ thu
  thập. Gọi người IT.
* **Tỷ lệ tốt thấp** → đầu đo có vấn đề. Cử người ra hiện trường hiệu
  chuẩn hoặc thay.
* **Tỷ lệ loại trừ cao** → KHÔNG phải vấn đề. Nhà máy đang bảo trì hoặc
  bị tiết giảm. Nhưng phải biết, vì nó làm hai con số kia khó đọc.

Gộp cả ba lại thì một đầu đo chết (tỷ lệ tốt 0%) và một tuần bảo trì
(loại trừ 100%) có thể ra cùng một điểm số — mà một cái là sự cố, cái
kia là kế hoạch.
"""
import html
from datetime import timedelta

from odoo import _, api, fields, models


def _thanh(pct, mau_tot='#2E7D5B', mau_xau='#B3261E', nguong=90.0):
    """Thanh tiến trình nhỏ — dễ quét mắt hơn một cột số."""
    p = max(0.0, min(100.0, pct or 0.0))
    mau = mau_tot if p >= nguong else mau_xau
    return (
        '<div style="display:flex;align-items:center;gap:6px">'
        '<div style="flex:1;height:7px;background:#EFE9DF;border-radius:4px;'
        'overflow:hidden"><div style="width:%.1f%%;height:100%%;'
        'background:%s"></div></div>'
        '<span style="min-width:46px;text-align:right;font-variant-numeric:'
        'tabular-nums">%.1f%%</span></div>' % (p, mau, p))


class EamQualityWizard(models.TransientModel):
    _name = 'eam.quality.wizard'
    _description = 'Chỉ số chất lượng dữ liệu'

    plant_id = fields.Many2one(
        'eam.location', string='Nhà máy',
        domain="[('location_type', '=', 'plant')]")
    tag_ids = fields.Many2many(
        'eam.tag', string='Chỉ riêng điểm đo',
        help='Để trống là xét mọi điểm đo của nhà máy.')
    date_from = fields.Datetime(
        string='Từ', required=True,
        default=lambda s: fields.Datetime.now() - timedelta(days=7))
    date_to = fields.Datetime(
        string='Đến', required=True, default=fields.Datetime.now)
    bao_cao = fields.Html(string='Kết quả', compute='_compute_bao_cao',
                          sanitize=False)

    @api.depends('plant_id', 'tag_ids', 'date_from', 'date_to')
    def _compute_bao_cao(self):
        for w in self:
            w.bao_cao = w._dung() if w.date_from and w.date_to else False

    def _tag(self):
        self.ensure_one()
        if self.tag_ids:
            return self.tag_ids
        dom = [('is_virtual', '=', False)]
        if self.plant_id:
            dom.append(('plant_id', '=', self.plant_id.id))
        return self.env['eam.tag'].search(dom)

    def _dung(self):
        self.ensure_one()
        tags = self._tag()
        if not tags:
            return ('<div style="padding:12px;color:#777">Chưa có điểm đo '
                    'nào trong phạm vi này.</div>')
        ds = self.env['eam.historian'].chi_so_chat_luong(
            tags.ids, self.date_from, self.date_to)
        if not ds:
            return ('<div style="padding:12px;color:#777">Không tính được '
                    'chỉ số — các điểm đo đều là tag tính toán.</div>')

        # Xấu nhất lên đầu: danh sách 84 dòng mà xếp theo mã thì chỗ hỏng
        # nằm lẫn đâu đó giữa chừng và không ai thấy.
        ds.sort(key=lambda r: (r['do_phu'], r['ty_le_tot']))

        hang = []
        for r in ds:
            hang.append(
                '<tr style="border-top:1px solid #F0EAE0">'
                '<td style="padding:5px 6px;font-family:monospace;'
                'font-size:11px">%s</td>'
                '<td style="padding:5px 6px;font-size:12px">%s</td>'
                '<td style="padding:5px 6px;width:170px">%s</td>'
                '<td style="padding:5px 6px;width:170px">%s</td>'
                '<td style="padding:5px 6px;text-align:right;font-size:12px;'
                'color:#777">%s</td>'
                '<td style="padding:5px 6px;text-align:right;font-size:12px;'
                'color:#777">%s</td></tr>'
                % (html.escape(r['ma']), html.escape(r['ten'][:40]),
                   _thanh(r['do_phu']), _thanh(r['ty_le_tot']),
                   '{:,}'.format(r['n']).replace(',', '.'),
                   ('%.1f%%' % r['ty_le_loai_tru'])
                   if r['ty_le_loai_tru'] else '—'))

        kem = [r for r in ds if r['do_phu'] < 90 or r['ty_le_tot'] < 90]
        tom = ''
        if kem:
            mat = [r['ma'] for r in ds if r['do_phu'] < 90][:6]
            do = [r['ma'] for r in ds if r['ty_le_tot'] < 90][:6]
            phan = []
            if mat:
                phan.append(
                    '<b>%d điểm đo thiếu dữ liệu</b> (%s%s) — vấn đề ở '
                    'đường truyền hoặc bộ thu thập, không phải ở đầu đo.'
                    % (len([r for r in ds if r['do_phu'] < 90]),
                       html.escape(', '.join(mat)),
                       '…' if len(mat) == 6 else ''))
            if do:
                phan.append(
                    '<b>%d điểm đo có số đo bị đánh dấu</b> (%s%s) — đầu '
                    'đo cần hiệu chuẩn hoặc thay.'
                    % (len([r for r in ds if r['ty_le_tot'] < 90]),
                       html.escape(', '.join(do)),
                       '…' if len(do) == 6 else ''))
            tom = ('<div style="background:#FDF3E7;border-left:3px solid '
                   '#D98E3B;padding:9px 11px;margin-bottom:10px;'
                   'font-size:12px">%s</div>' % '<br/>'.join(phan))
        else:
            tom = ('<div style="background:#EAF5EE;border-left:3px solid '
                   '#2E7D5B;padding:9px 11px;margin-bottom:10px;'
                   'font-size:12px">Mọi điểm đo đều đạt trên 90% cả về độ '
                   'phủ lẫn tỷ lệ tốt.</div>')

        return (
            tom
            + '<table style="width:100%;border-collapse:collapse">'
            '<tr style="color:#777;font-size:11px;text-align:left">'
            '<th style="padding:4px 6px">Mã</th>'
            '<th style="padding:4px 6px">Điểm đo</th>'
            '<th style="padding:4px 6px">Độ phủ</th>'
            '<th style="padding:4px 6px">Tỷ lệ tốt</th>'
            '<th style="padding:4px 6px;text-align:right">Số đo</th>'
            '<th style="padding:4px 6px;text-align:right">Loại trừ</th></tr>'
            + ''.join(hang) + '</table>'
            + '<div style="margin-top:9px;font-size:11px;color:#777">'
            '<b>Độ phủ</b> = số đo thật ÷ số đáng lẽ phải có (suy từ nhịp '
            'lấy mẫu đã khai). <b>Tỷ lệ tốt</b> = phần không mang cờ chất '
            'lượng. <b>Loại trừ</b> = phần nằm trong khoảng không tính '
            'KPI — cao không phải vấn đề, nhưng làm hai cột kia khó đọc.'
            '</div>')
