# -*- coding: utf-8 -*-
"""SVG chart helpers — render biểu đồ server-side (self-contained,
KHÔNG cần Chart.js/CDN, chạy offline). Trả về chuỗi SVG cho field
html trên dashboard.

Bảng màu đồng bộ theme RealtyPro (xanh dương đậm + accent).
"""
import math

PALETTE = [
    '#0F2C3F', '#1B6CA8', '#28A0C9', '#5CC8C1', '#F2A93B',
    '#E4572E', '#8E6C88', '#76B041', '#A63D40', '#3D5A80',
]


def _fmt_money(v):
    """Format tiền gọn: 12.3 tỷ / 850 tr."""
    v = float(v or 0)
    if abs(v) >= 1e9:
        return '%.1f tỷ' % (v / 1e9)
    if abs(v) >= 1e6:
        return '%.0f tr' % (v / 1e6)
    return '%.0f' % v


def donut(used, total, label, color='#1B6CA8', size=150):
    """Donut gauge % đã dùng. used/total → phần trăm ở tâm."""
    total = float(total or 0)
    used = float(used or 0)
    pct = (used / total * 100) if total else 0
    pct = max(0, min(100, pct))
    r, cx, cy, sw = size * 0.38, size / 2, size / 2, size * 0.12
    circ = 2 * math.pi * r
    dash = circ * pct / 100
    return (
        '<svg viewBox="0 0 %(s)s %(s)s" width="%(s)s" height="%(s)s" '
        'xmlns="http://www.w3.org/2000/svg">'
        '<circle cx="%(cx)s" cy="%(cy)s" r="%(r)s" fill="none" '
        'stroke="#E6ECF0" stroke-width="%(sw)s"/>'
        '<circle cx="%(cx)s" cy="%(cy)s" r="%(r)s" fill="none" '
        'stroke="%(color)s" stroke-width="%(sw)s" '
        'stroke-dasharray="%(dash).2f %(circ).2f" stroke-linecap="round" '
        'transform="rotate(-90 %(cx)s %(cy)s)"/>'
        '<text x="%(cx)s" y="%(cy)s" text-anchor="middle" '
        'dominant-baseline="central" font-size="%(fs)s" '
        'font-weight="700" fill="%(color)s">%(pct).0f%%</text>'
        '<text x="%(cx)s" y="%(ly)s" text-anchor="middle" '
        'font-size="%(fs2)s" fill="#6B7B8A">%(label)s</text>'
        '</svg>'
    ) % dict(s=size, cx=cx, cy=cy, r=r, sw=sw, color=color,
             dash=dash, circ=circ, pct=pct, fs=size * 0.18,
             fs2=size * 0.085, ly=cy + r + sw, label=label)


def hbar(rows, width=460, bar_h=26, gap=12, unit='money'):
    """Horizontal bar chart. rows = [(label, value), ...].

    Bar dài theo value, nhãn trái + giá trị phải.
    """
    rows = [(str(l), float(v or 0)) for l, v in rows if v]
    if not rows:
        return ('<svg viewBox="0 0 %d 40" xmlns="http://www.w3.org/2000/svg">'
                '<text x="10" y="24" font-size="13" fill="#9AA7B2">'
                'Chưa có dữ liệu</text></svg>') % width
    maxv = max(v for _, v in rows) or 1
    label_w, val_w, pad = 150, 90, 8
    plot_w = width - label_w - val_w - pad * 2
    height = len(rows) * (bar_h + gap) + gap
    parts = ['<svg viewBox="0 0 %d %d" width="%d" height="%d" '
             'xmlns="http://www.w3.org/2000/svg">' % (
                 width, height, width, height)]
    y = gap
    for i, (label, val) in enumerate(rows):
        bw = max(2, plot_w * val / maxv)
        color = PALETTE[i % len(PALETTE)]
        lbl = label if len(label) <= 22 else label[:21] + '…'
        vtext = _fmt_money(val) if unit == 'money' else str(int(val))
        parts.append(
            '<text x="%d" y="%d" font-size="12.5" fill="#3A4A57" '
            'dominant-baseline="central">%s</text>' % (
                pad, y + bar_h / 2, _esc(lbl)))
        parts.append(
            '<rect x="%d" y="%d" width="%.1f" height="%d" rx="4" '
            'fill="%s" opacity="0.9"/>' % (
                label_w + pad, y, bw, bar_h, color))
        parts.append(
            '<text x="%.1f" y="%d" font-size="12.5" font-weight="600" '
            'fill="#0F2C3F" dominant-baseline="central">%s</text>' % (
                label_w + pad + bw + 6, y + bar_h / 2, vtext))
        y += bar_h + gap
    parts.append('</svg>')
    return ''.join(parts)


def vbar(rows, width=460, height=220, unit='count'):
    """Vertical bar chart. rows = [(label, value), ...]."""
    rows = [(str(l), float(v or 0)) for l, v in rows]
    if not any(v for _, v in rows):
        return ('<svg viewBox="0 0 %d 40" xmlns="http://www.w3.org/2000/svg">'
                '<text x="10" y="24" font-size="13" fill="#9AA7B2">'
                'Chưa có dữ liệu</text></svg>') % width
    maxv = max(v for _, v in rows) or 1
    pad_b, pad_t, pad_x = 34, 20, 10
    plot_h = height - pad_b - pad_t
    n = len(rows)
    slot = (width - pad_x * 2) / n
    bw = slot * 0.55
    parts = ['<svg viewBox="0 0 %d %d" width="%d" height="%d" '
             'xmlns="http://www.w3.org/2000/svg">' % (
                 width, height, width, height)]
    # baseline
    parts.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#DCE4EA" '
                 'stroke-width="1"/>' % (
                     pad_x, height - pad_b, width - pad_x, height - pad_b))
    for i, (label, val) in enumerate(rows):
        bh = plot_h * val / maxv
        x = pad_x + slot * i + (slot - bw) / 2
        y = height - pad_b - bh
        color = PALETTE[i % len(PALETTE)]
        parts.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" '
                     'rx="4" fill="%s" opacity="0.9"/>' % (
                         x, y, bw, bh, color))
        if val:
            parts.append('<text x="%.1f" y="%.1f" text-anchor="middle" '
                         'font-size="12" font-weight="700" fill="#0F2C3F">'
                         '%s</text>' % (
                             x + bw / 2, y - 5,
                             _fmt_money(val) if unit == 'money'
                             else str(int(val))))
        parts.append('<text x="%.1f" y="%d" text-anchor="middle" '
                     'font-size="11.5" fill="#6B7B8A">%s</text>' % (
                         x + bw / 2, height - pad_b + 16, _esc(label)))
    parts.append('</svg>')
    return ''.join(parts)


def stacked_bar(segments, width=460, height=54):
    """1 thanh stacked ngang. segments = [(label, value, color), ...]."""
    segments = [(l, float(v or 0), c) for l, v, c in segments if v]
    total = sum(v for _, v, _ in segments) or 1
    parts = ['<svg viewBox="0 0 %d %d" width="%d" height="%d" '
             'xmlns="http://www.w3.org/2000/svg">' % (
                 width, height, width, height)]
    x, bar_h = 0, 26
    for label, val, color in segments:
        w = width * val / total
        parts.append('<rect x="%.1f" y="0" width="%.1f" height="%d" '
                     'fill="%s"/>' % (x, w, bar_h, color))
        if w > 46:
            parts.append('<text x="%.1f" y="%d" text-anchor="middle" '
                         'font-size="11.5" font-weight="700" fill="#fff">'
                         '%.0f%%</text>' % (
                             x + w / 2, bar_h / 2 + 4, val / total * 100))
        x += w
    # legend
    lx = 0
    for label, val, color in segments:
        parts.append('<rect x="%.1f" y="%d" width="11" height="11" rx="2" '
                     'fill="%s"/>' % (lx, bar_h + 12, color))
        parts.append('<text x="%.1f" y="%d" font-size="11.5" fill="#3A4A57">'
                     '%s (%s)</text>' % (
                         lx + 15, bar_h + 21, _esc(label), _fmt_money(val)))
        lx += 15 + len(label) * 6.6 + len(_fmt_money(val)) * 6.6 + 34
    parts.append('</svg>')
    return ''.join(parts)


def _esc(t):
    return (str(t).replace('&', '&amp;').replace('<', '&lt;')
            .replace('>', '&gt;'))
