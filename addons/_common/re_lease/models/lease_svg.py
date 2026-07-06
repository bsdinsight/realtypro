# -*- coding: utf-8 -*-
"""SVG helpers dashboard Thuê tài sản — server-side, không CDN."""

PALETTE = ['#1B6CA8', '#2C7A57', '#C1782E', '#8E6C88', '#3D5A80',
           '#B23A2E', '#5CC8C1', '#76B041']


def _fmt_money(v):
    v = float(v or 0)
    if abs(v) >= 1e9:
        return '%.1f tỷ' % (v / 1e9)
    if abs(v) >= 1e6:
        return '%.0f tr' % (v / 1e6)
    return '%.0f' % v


def _esc(t):
    return (str(t).replace('&', '&amp;').replace('<', '&lt;')
            .replace('>', '&gt;'))


def matrix_2x2(counts, width=380, height=210):
    """Ma trận HĐ active: counts = dict với key (direction, type)."""
    cells = [
        ('in', 'operating', 'Đi thuê · Hoạt động', '#1B6CA8'),
        ('in', 'finance', 'Đi thuê · Tài chính', '#3D5A80'),
        ('out', 'operating', 'Cho thuê lại · Hoạt động', '#2C7A57'),
        ('out', 'finance', 'Cho thuê lại · Tài chính', '#5CC8C1'),
    ]
    cw, ch, gap = (width - 12) / 2, (height - 12) / 2, 12
    parts = ['<svg viewBox="0 0 %d %d" width="%d" height="%d" '
             'xmlns="http://www.w3.org/2000/svg">' % (
                 width, height, width, height)]
    for idx, (d, t, label, color) in enumerate(cells):
        x = (idx % 2) * (cw + gap)
        y = (idx // 2) * (ch + gap)
        n = counts.get((d, t), 0)
        parts.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" '
                     'rx="10" fill="%s" opacity="%s"/>' % (
                         x, y, cw, ch, color, '0.92' if n else '0.25'))
        parts.append('<text x="%.1f" y="%.1f" text-anchor="middle" '
                     'font-size="30" font-weight="700" fill="#fff">%d'
                     '</text>' % (x + cw / 2, y + ch / 2 + 2, n))
        parts.append('<text x="%.1f" y="%.1f" text-anchor="middle" '
                     'font-size="11" fill="#fff" opacity="0.95">%s</text>'
                     % (x + cw / 2, y + ch - 12, _esc(label)))
    parts.append('</svg>')
    return ''.join(parts)


def hbar(rows, width=460, bar_h=24, gap=12):
    """Thanh ngang tiền theo nhãn. rows = [(label, value), ...]."""
    rows = [(str(l), float(v or 0)) for l, v in rows if v]
    if not rows:
        return ('<svg viewBox="0 0 %d 40" xmlns="http://www.w3.org/2000/svg">'
                '<text x="10" y="24" font-size="13" fill="#9AA7B2">'
                'Chưa có dữ liệu</text></svg>') % width
    maxv = max(v for _, v in rows) or 1
    label_w, val_w, pad = 150, 84, 8
    plot_w = width - label_w - val_w - pad * 2
    height = len(rows) * (bar_h + gap) + gap
    parts = ['<svg viewBox="0 0 %d %d" width="%d" height="%d" '
             'xmlns="http://www.w3.org/2000/svg">' % (
                 width, height, width, height)]
    y = gap
    for i, (label, val) in enumerate(rows):
        bw = max(2, plot_w * val / maxv)
        lbl = label if len(label) <= 20 else label[:19] + '…'
        parts.append('<text x="%d" y="%.1f" font-size="12" fill="#3A4A57" '
                     'dominant-baseline="central">%s</text>' % (
                         pad, y + bar_h / 2, _esc(lbl)))
        parts.append('<rect x="%d" y="%d" width="%.1f" height="%d" rx="4" '
                     'fill="%s" opacity="0.9"/>' % (
                         label_w + pad, y, bw, bar_h,
                         PALETTE[i % len(PALETTE)]))
        parts.append('<text x="%.1f" y="%.1f" font-size="12" '
                     'font-weight="600" fill="#0F2C3F" '
                     'dominant-baseline="central">%s</text>' % (
                         label_w + pad + bw + 6, y + bar_h / 2,
                         _fmt_money(val)))
        y += bar_h + gap
    parts.append('</svg>')
    return ''.join(parts)


def vbar(rows, width=460, height=200):
    """Cột dọc — kỳ đến hạn theo tháng. rows = [(label, value), ...]."""
    rows = [(str(l), float(v or 0)) for l, v in rows]
    if not any(v for _, v in rows):
        return ('<svg viewBox="0 0 %d 40" xmlns="http://www.w3.org/2000/svg">'
                '<text x="10" y="24" font-size="13" fill="#9AA7B2">'
                'Không có kỳ đến hạn</text></svg>') % width
    maxv = max(v for _, v in rows) or 1
    pad_b, pad_t, pad_x = 32, 22, 10
    plot_h = height - pad_b - pad_t
    slot = (width - pad_x * 2) / len(rows)
    bw = slot * 0.55
    parts = ['<svg viewBox="0 0 %d %d" width="%d" height="%d" '
             'xmlns="http://www.w3.org/2000/svg">' % (
                 width, height, width, height)]
    parts.append('<line x1="%d" y1="%d" x2="%d" y2="%d" '
                 'stroke="#DCE4EA"/>' % (
                     pad_x, height - pad_b, width - pad_x, height - pad_b))
    for i, (label, val) in enumerate(rows):
        bh = plot_h * val / maxv
        x = pad_x + slot * i + (slot - bw) / 2
        y = height - pad_b - bh
        parts.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" '
                     'rx="4" fill="%s" opacity="0.9"/>' % (
                         x, y, bw, bh, PALETTE[i % len(PALETTE)]))
        if val:
            parts.append('<text x="%.1f" y="%.1f" text-anchor="middle" '
                         'font-size="11" font-weight="700" '
                         'fill="#0F2C3F">%s</text>' % (
                             x + bw / 2, y - 5, _fmt_money(val)))
        parts.append('<text x="%.1f" y="%d" text-anchor="middle" '
                     'font-size="11" fill="#6B7B8A">%s</text>' % (
                         x + bw / 2, height - pad_b + 15, _esc(label)))
    parts.append('</svg>')
    return ''.join(parts)
