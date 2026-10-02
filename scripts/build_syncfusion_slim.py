#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dựng gói Syncfusion EJ2 RÚT GỌN cho RealtyPro.

Bản global `ej2.min.js` của Syncfusion gộp MỌI component (spreadsheet,
pdfviewer, diagram, maps…) nên nặng 29 MB — trong khi bộ này chỉ dùng
Gantt (lịch thi công) và Charts (bảng điều khiển EVM). Script tải đúng
những gói cần, theo thứ tự phụ thuộc, rồi nối thành một file JS và một
file CSS.

Chạy lại khi nâng cấp phiên bản EJ2:

    python3 scripts/build_syncfusion_slim.py 33.1.44

Nguồn: bản phát hành chính thức trên unpkg (cùng nội dung với CDN
Syncfusion). Giấy phép vẫn là giấy phép Syncfusion của BSD — script chỉ
đóng gói lại, không sửa mã.

Sau khi chạy, mở Gantt + bảng điều khiển EVM trên trình duyệt và kiểm:
thanh công việc, baseline, mốc sự kiện, đường găng, hộp thoại chuột
phải, và biểu đồ S-curve. Thiếu một gói phụ thuộc thì lỗi chỉ lộ ra lúc
mở đúng tính năng dùng nó.
"""
import json
import sys
import urllib.request
from pathlib import Path

# Hai component dùng thật trong bộ RealtyPro.
ROOTS = ['ej2-gantt', 'ej2-charts']

# Gói CẮT HẲN khỏi cây phụ thuộc.
#
# ej2-richtexteditor chỉ được Gantt dùng cho tab "Notes" trong hộp thoại
# Task Information — mà hộp thoại đó đã bỏ khỏi menu chuột phải: nó sửa
# dữ liệu trong bộ nhớ của EJ2 rồi im lặng vứt đi (Odoo không nhận), nên
# giữ lại còn hại hơn. Cắt nó kéo theo filemanager / markdown-converter /
# interactive-chat: tổng ~1,8 MB mã chưa nén.
EXCLUDE = {'ej2-richtexteditor'}

# Gói không có bản dựng global/CSS riêng, hoặc không cần ở trình duyệt.
SKIP_JS = set()
SKIP_CSS = {
    'ej2-base', 'ej2-data', 'ej2-svg-base', 'ej2-file-utils',
    'ej2-compression', 'ej2-excel-export', 'ej2-pdf-export',
}

BASE = 'https://unpkg.com/@syncfusion'
OUT_DIR = Path(__file__).resolve().parent.parent / \
    'addons/_project/rp_progress/static/lib/syncfusion'


def fetch(url):
    with urllib.request.urlopen(url, timeout=120) as r:
        return r.read()


def resolve_order(version):
    """Duyệt cây phụ thuộc, trả danh sách gói theo thứ tự nạp được."""
    deps = {}

    def visit(pkg):
        if pkg in deps:
            return
        meta = json.loads(fetch(f'{BASE}/{pkg}@{version}/package.json'))
        children = [k.split('/')[-1]
                    for k in meta.get('dependencies', {})
                    if k.startswith('@syncfusion/')
                    and k.split('/')[-1] not in EXCLUDE]
        deps[pkg] = children
        for c in children:
            visit(c)

    for r in ROOTS:
        if r not in EXCLUDE:
            visit(r)

    order, seen = [], set()

    def emit(pkg):
        if pkg in seen:
            return
        seen.add(pkg)
        for c in deps[pkg]:
            emit(c)
        order.append(pkg)

    for r in ROOTS:
        if r not in EXCLUDE:
            emit(r)
    return order


def main():
    version = sys.argv[1] if len(sys.argv) > 1 else '33.1.44'
    order = resolve_order(version)
    print(f'EJ2 {version} — {len(order)} gói, thứ tự nạp:')
    for p in order:
        print('   ', p)

    js_parts, css_parts, total = [], [], 0
    js_parts.append(f'/* Syncfusion EJ2 {version} — bản rút gọn RealtyPro '
                    f'(Gantt + Charts). Sinh bởi '
                    f'scripts/build_syncfusion_slim.py */\n')
    for pkg in order:
        if pkg in SKIP_JS:
            continue
        url = f'{BASE}/{pkg}@{version}/dist/global/{pkg}.min.js'
        try:
            data = fetch(url)
        except Exception as e:                       # noqa: BLE001
            print(f'  ! bỏ qua JS {pkg}: {e}')
            continue
        total += len(data)
        js_parts.append(f'\n/* ---- {pkg} ---- */\n')
        js_parts.append(data.decode('utf-8'))
        print(f'  js  {pkg:<26} {len(data)/1024:8.0f} KB')

    for pkg in order:
        if pkg in SKIP_CSS:
            continue
        url = f'{BASE}/{pkg}@{version}/styles/material.css'
        try:
            data = fetch(url)
        except Exception as e:                       # noqa: BLE001
            print(f'  ! bỏ qua CSS {pkg}: {e}')
            continue
        css_parts.append(f'\n/* ---- {pkg} ---- */\n')
        css_parts.append(data.decode('utf-8'))
        print(f'  css {pkg:<26} {len(data)/1024:8.0f} KB')

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    js_path = OUT_DIR / 'ej2-slim.min.js'
    css_path = OUT_DIR / 'ej2-slim-material.css'
    js_path.write_text(''.join(js_parts), encoding='utf-8')
    css_path.write_text(''.join(css_parts), encoding='utf-8')
    print(f'\n→ {js_path.name}  {js_path.stat().st_size/1048576:.2f} MB')
    print(f'→ {css_path.name} {css_path.stat().st_size/1048576:.2f} MB')


if __name__ == '__main__':
    main()
