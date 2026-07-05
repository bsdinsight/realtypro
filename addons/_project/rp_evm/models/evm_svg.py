# -*- coding: utf-8 -*-
"""SVG chart helpers cho dashboard EVM — render server-side, không CDN,
chạy offline. Màu theo trạng thái chi phí (đèn giao thông)."""

STATUS_COLOR = {
    'on_budget': '#2C7A57',   # xanh — trong ngân sách
    'watch': '#B0801A',       # vàng — cần theo dõi
    'over': '#B23A2E',        # đỏ — vượt chi
    'no_data': '#9AA7B2',     # xám — chưa đủ dữ liệu
}


def _fmt_money(v):
    v = float(v or 0)
    if abs(v) >= 1e9:
        return '%.2f tỷ' % (v / 1e9)
    if abs(v) >= 1e6:
        return '%.0f tr' % (v / 1e6)
    return '%.0f' % v


def _esc(t):
    return (str(t).replace('&', '&amp;').replace('<', '&lt;')
            .replace('>', '&gt;'))


def cpi_bars(rows, width=560, bar_h=24, gap=13):
    """CPI theo hạng mục — thanh ngang màu theo status + vạch mốc CPI=1.0.

    rows = [(name, cpi, status), ...]
    """
    rows = [(str(n), float(c or 0), s) for n, c, s in rows]
    if not rows:
        return ('<svg viewBox="0 0 %d 44" xmlns="http://www.w3.org/2000/svg">'
                '<text x="12" y="26" font-size="13" fill="#9AA7B2">Chưa có '
                'hạng mục nào có dữ liệu chi phí</text></svg>') % width
    # thang hiển thị CPI: 0 → max(1.3, cpi lớn nhất)
    disp_max = max(1.3, max(c for _, c, _ in rows) * 1.05)
    label_w, val_w, pad = 200, 78, 8
    plot_w = width - label_w - val_w - pad * 2
    height = len(rows) * (bar_h + gap) + gap + 16
    x1 = label_w + pad                       # gốc trục
    x_one = x1 + plot_w * (1.0 / disp_max)    # vị trí CPI = 1.0
    parts = ['<svg viewBox="0 0 %d %d" width="%d" height="%d" '
             'xmlns="http://www.w3.org/2000/svg">' % (
                 width, height, width, height)]
    y = gap
    for name, cpi, status in rows:
        bw = max(2, plot_w * min(cpi, disp_max) / disp_max)
        color = STATUS_COLOR.get(status, '#9AA7B2')
        lbl = name if len(name) <= 30 else name[:29] + '…'
        parts.append(
            '<text x="%d" y="%.1f" font-size="12" fill="#3A4A57" '
            'dominant-baseline="central">%s</text>' % (
                pad, y + bar_h / 2, _esc(lbl)))
        parts.append(
            '<rect x="%d" y="%d" width="%.1f" height="%d" rx="4" '
            'fill="%s" opacity="0.92"/>' % (x1, y, bw, bar_h, color))
        cpi_txt = '%.2f' % cpi if cpi else '—'
        parts.append(
            '<text x="%.1f" y="%.1f" font-size="12.5" font-weight="700" '
            'fill="%s" dominant-baseline="central">%s</text>' % (
                x1 + plot_w + 6, y + bar_h / 2, color, cpi_txt))
        y += bar_h + gap
    # vạch mốc CPI = 1.0 (hoà vốn chi phí)
    parts.append(
        '<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="#0F2C3F" '
        'stroke-width="1.2" stroke-dasharray="4 3"/>' % (
            x_one, gap - 4, x_one, y - gap + 4))
    parts.append(
        '<text x="%.1f" y="%d" font-size="10.5" fill="#0F2C3F" '
        'text-anchor="middle">CPI 1.0</text>' % (x_one, y + 4))
    parts.append('</svg>')
    return ''.join(parts)


def cost_compare(bac, ev, ac, eac, width=460, height=210):
    """4 cột: BAC · EV · AC · EAC. EAC đỏ nếu > BAC (dự báo vượt)."""
    bars = [
        ('Ngân sách\n(BAC)', float(bac or 0), '#3D5A80'),
        ('Làm ra\n(EV)', float(ev or 0), '#2C7A57'),
        ('Đã chi\n(AC)', float(ac or 0), '#1B6CA8'),
        ('Dự báo\n(EAC)', float(eac or 0),
         '#B23A2E' if (eac or 0) > (bac or 0) + 1 else '#B0801A'),
    ]
    maxv = max((v for _, v, _ in bars), default=0) or 1
    pad_b, pad_t, pad_x = 40, 24, 12
    plot_h = height - pad_b - pad_t
    n = len(bars)
    slot = (width - pad_x * 2) / n
    bw = slot * 0.5
    parts = ['<svg viewBox="0 0 %d %d" width="%d" height="%d" '
             'xmlns="http://www.w3.org/2000/svg">' % (
                 width, height, width, height)]
    parts.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#DCE4EA"/>' % (
        pad_x, height - pad_b, width - pad_x, height - pad_b))
    for i, (label, val, color) in enumerate(bars):
        bh = plot_h * val / maxv if maxv else 0
        x = pad_x + slot * i + (slot - bw) / 2
        yb = height - pad_b - bh
        parts.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" '
                     'rx="4" fill="%s" opacity="0.92"/>' % (
                         x, yb, bw, bh, color))
        parts.append('<text x="%.1f" y="%.1f" text-anchor="middle" '
                     'font-size="11.5" font-weight="700" fill="#0F2C3F">%s'
                     '</text>' % (x + bw / 2, yb - 5, _fmt_money(val)))
        for k, part in enumerate(label.split('\n')):
            parts.append('<text x="%.1f" y="%d" text-anchor="middle" '
                         'font-size="10.5" fill="#6B7B8A">%s</text>' % (
                             x + bw / 2, height - pad_b + 15 + k * 12,
                             _esc(part)))
    parts.append('</svg>')
    return ''.join(parts)
