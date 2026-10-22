# -*- coding: utf-8 -*-
"""Thuộc tính khai được theo nhóm tài sản.

Vấn đề
------
Mỗi loại thiết bị có bộ thông số riêng: máy biến áp cần điện áp sơ/thứ
cấp và tổ đấu dây; inverter cần công suất DC/AC và số MPPT; tua-bin cần
đường kính rotor và chiều cao trục. Thêm một trường cho mỗi loại nghĩa
là mỗi khách mới lại phải sửa mã — và khách không bao giờ chờ được.

Cách làm
--------
Dùng đúng cơ chế **Properties** có sẵn của Odoo, không tự dựng bảng
thuộc tính. Nhóm tài sản giữ ĐỊNH NGHĨA, từng tài sản giữ GIÁ TRỊ. Người
dùng tự thêm trường ngay trên giao diện: tên, kiểu dữ liệu, giá trị chọn
sẵn — không cần lập trình, không cần nâng cấp module.

Vì sao không tự viết bảng thuộc tính
-------------------------------------
Đã có người viết rồi, và nó nằm trong lõi: tìm kiếm, lọc, gom nhóm, xuất
báo cáo đều hiểu Properties sẵn. Bảng tự dựng thì phải viết lại từng thứ
đó, và sẽ thiếu vài thứ mà không ai nhận ra cho tới lúc khách cần.

Thuộc tính KHÔNG tự chảy xuống nhóm con
----------------------------------------
Odoo giải định nghĩa theo đúng nhóm của tài sản, không gộp nhóm cha. Cố
tình giữ như vậy: gộp ngầm thì sửa một thuộc tính ở nhóm cha làm đổi dữ
liệu của hàng trăm tài sản ở nhánh dưới mà không ai thấy. Thay vào đó có
nút **chép từ nhóm cha** — vẫn nhanh, nhưng là một hành động có người
bấm và có vết.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class EamAssetCategory(models.Model):
    _inherit = 'eam.asset.category'

    attr_definition = fields.PropertiesDefinition(
        string='Thuộc tính của nhóm',
        help='Khai các thông số mà mọi tài sản thuộc nhóm này đều có. '
             'Tài sản sẽ hiện đúng những ô này để điền.')
    attr_count = fields.Integer(
        string='Số thuộc tính', compute='_compute_attr_count')

    @api.depends('attr_definition')
    def _compute_attr_count(self):
        for rec in self:
            rec.attr_count = len(rec.attr_definition or [])

    def action_chep_thuoc_tinh_tu_cha(self):
        """Chép định nghĩa thuộc tính của nhóm cha xuống nhóm này.

        Chỉ thêm thuộc tính còn thiếu, không đụng thuộc tính đã có — nếu
        không thì một lần bấm nhầm xoá mất phần đã khai công phu.
        """
        them = 0
        for rec in self:
            if not rec.parent_id:
                raise UserError(_(
                    'Nhóm "%s" không có nhóm cha để chép.', rec.complete_name))
            cha = rec.parent_id.attr_definition or []
            if not cha:
                raise UserError(_(
                    'Nhóm cha "%s" chưa khai thuộc tính nào.',
                    rec.parent_id.complete_name))
            dang_co = {d.get('name') for d in (rec.attr_definition or [])}
            moi = [d for d in cha if d.get('name') not in dang_co]
            if moi:
                rec.attr_definition = (rec.attr_definition or []) + moi
                them += len(moi)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success' if them else 'info',
                'title': _('Đã chép %s thuộc tính', them),
                'message': _('Chỉ thêm thuộc tính còn thiếu; phần đã khai ở '
                             'nhóm này giữ nguyên.'),
                'sticky': False,
            },
        }
