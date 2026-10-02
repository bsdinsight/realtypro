# -*- coding: utf-8 -*-
"""Chặn lỗi 500 của pane lọc bên trái — vá cho MỌI model.

LỖI CỦA LÕI ODOO
================
`search_panel_select_multi_range` trong `addons/web/models/models.py` đọc
tham số bằng `kwargs.get('group_domain', [])`. Mặc định `[]` chỉ đúng khi
client KHÔNG gửi khoá đó. Nhưng client web gửi hẳn `null`:

    _getGroupDomain(filter)                 search_model.js
        let groupDomain = null;
        if (fieldType === "many2one") { ... }   ← chỉ gán khi có ô được tick

Mục lọc many2one có `groupby` + `enable_counters` mà chưa tick giá trị nào
thì hàm trả `null`. `.get()` thấy khoá tồn tại nên trả `null` chứ không
trả `[]`, rồi `Domain(None)` ném:

    TypeError: Domain() invalid argument type for domain: None

Lúc mở trang lần đầu chưa có `groups` nên client đi nhánh khác và gửi `[]`
— chạy ngon. Bấm bất cứ đâu trong pane là nạp lại, `groups` đã có, và lúc
đó mới 500. Đó là lý do lỗi trông như ngẫu nhiên.

VÌ SAO VÁ Ở `base` CHỨ KHÔNG VÁ TỪNG MODEL
==========================================
Lỗi không thuộc về một model nào — nó thuộc về mọi pane lọc có mục
many2one nhiều-chọn. Cứ mỗi màn hình mới thêm pane là lại phải nhớ chép
bản vá sang, mà quên thì người dùng nhận 500 chứ không nhận cảnh báo.
`re_base` là module nền của cả bộ nên vá ở đây là phủ hết.

Bỏ khoá đi để lõi dùng đúng giá trị mặc định của chính nó. Ngày Odoo sửa
`.get('group_domain', [])` thành `.get('group_domain') or []` thì đoạn này
thành vô hại, không cần gỡ.
"""
from odoo import api, models


class Base(models.AbstractModel):
    _inherit = 'base'

    @api.model
    def search_panel_select_multi_range(self, field_name, **kwargs):
        if kwargs.get('group_domain') is None:
            kwargs.pop('group_domain', None)
        return super().search_panel_select_multi_range(field_name, **kwargs)
