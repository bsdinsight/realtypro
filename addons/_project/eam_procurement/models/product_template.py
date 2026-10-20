# -*- coding: utf-8 -*-
"""Trống có chủ đích.

``eam_category_id`` và ``eam_is_rotable`` đã chuyển sang module
``eam_stock`` (EAMOne — Kho phụ tùng) ngày 20/10/2026.

Lý do: chúng trả lời câu "phụ tùng này thuộc cụm nào", là việc của kho
phụ tùng chứ không phải của chuỗi mua sắm. Để ở đây thì mọi cài đặt
EAMOne muốn dùng trường này đều bị kéo theo cả bộ Mua sắm của Realty —
đúng thứ mà chính module này được dựng ra để tránh.
"""
