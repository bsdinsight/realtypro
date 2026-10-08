# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    """Gắn sản phẩm kho vào cây loại cấu phần, và ép sê-ri cho vật tư
    quay vòng.

    Vật tư quay vòng là vật tư **tháo ra, đem đi đại tu, rồi lắp lại** —
    hộp số, máy phát, cánh, bộ biến đổi. Khác hẳn vật tư tiêu hao.

    Không theo dõi theo sê-ri thì sau lần đại tu thứ hai không ai biết
    con nào đang nằm ở đâu. Mà đó đúng là câu quyết định quyền đòi bảo
    hành: hãng chỉ bảo hành con mang số sê-ri đó, không bảo hành "một cái
    hộp số".

    Nên đây là ràng buộc chặn, không phải lời khuyên.
    """
    _inherit = 'product.template'

    eam_category_id = fields.Many2one(
        'eam.asset.category', string='Loại cấu phần EAM',
        help='Nối sản phẩm kho với cây cấu phần. Nhờ đó tra được "phụ '
             'tùng này lắp cho cụm nào" và ngược lại.')
    eam_is_rotable = fields.Boolean(
        related='eam_category_id.is_rotable_default', store=True,
        string='Vật tư quay vòng')

    @api.onchange('eam_category_id')
    def _onchange_eam_category(self):
        """Loại quay vòng thì gợi ý sê-ri ngay, đừng đợi lúc lưu mới báo."""
        for p in self:
            if p.eam_category_id.is_rotable_default:
                p.tracking = 'serial'

    @api.constrains('eam_category_id', 'tracking')
    def _check_rotable_serial(self):
        for p in self:
            if p.eam_category_id.is_rotable_default and p.tracking != 'serial':
                raise ValidationError(_(
                    'Sản phẩm "%(sp)s" thuộc loại cấu phần quay vòng '
                    '"%(loai)s" nên BẮT BUỘC theo dõi theo sê-ri.\n\n'
                    'Vật tư quay vòng tháo ra rồi lắp lại. Không có sê-ri '
                    'thì sau lần đại tu thứ hai không ai biết con nào đang '
                    'ở đâu — mà hãng chỉ bảo hành con mang đúng số sê-ri '
                    'đó, không bảo hành "một cái %(loai)s".',
                    sp=p.display_name, loai=p.eam_category_id.name))
