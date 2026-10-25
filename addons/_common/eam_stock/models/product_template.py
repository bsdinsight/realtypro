# -*- coding: utf-8 -*-
"""Phụ tùng — phần hồ sơ mà kho phụ tùng điện gió cần thêm.

Dùng lại đúng từ vựng của ``eam.asset`` (hãng chế tạo, mức quan trọng)
thay vì đặt tên khác cho cùng một khái niệm. Hai bộ từ vựng cho cùng một
thứ là cách chắc chắn để sáu tháng sau không ai lọc chéo được.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

LOAI_PHU_TUNG = [
    ('spare', 'Phụ tùng thay thế'),
    ('consumable', 'Vật tư tiêu hao'),
    ('lubricant', 'Dầu mỡ, hoá chất'),
    ('tool', 'Dụng cụ'),
    ('ppe', 'Bảo hộ lao động'),
    ('other', 'Khác'),
]

ANH_HUONG = [
    ('stop', 'Dừng máy hoàn toàn'),
    ('derate', 'Giảm công suất / chạy hạn chế'),
    ('risk', 'Vẫn chạy nhưng tăng rủi ro'),
    ('none', 'Không ảnh hưởng vận hành'),
]


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # ------------------------------------------------ KHO-03 phân loại
    eam_part_kind = fields.Selection(
        LOAI_PHU_TUNG, string='Loại phụ tùng',
        help='Khác với "loại cấu phần" (phụ tùng này thuộc cụm nào). Đây '
             'là phụ tùng thay thế, vật tư tiêu hao, dầu mỡ hay dụng cụ '
             '— ba thứ này đi theo ba luật kho khác nhau.')

    # ---------------------------------------------- KHO-02 mã OEM / NSX
    eam_oem_partner_id = fields.Many2one(
        'res.partner', string='Hãng chế tạo (OEM)', ondelete='restrict')
    eam_oem_code = fields.Char(
        string='Mã OEM', index=True,
        help='Số hiệu hãng chế tạo thiết bị dùng. Đây là mã dùng để đặt '
             'hàng và để đòi bảo hành.')
    eam_mfr_code = fields.Char(
        string='Mã nhà sản xuất phụ tùng',
        help='Nhiều phụ tùng do bên thứ ba sản xuất cho hãng. Mã này in '
             'trên chính con hàng, thường khác mã OEM.')
    eam_xref_ids = fields.One2many(
        'eam.part.xref', 'product_tmpl_id', string='Mã chéo')
    eam_xref_count = fields.Integer(compute='_compute_eam_counts')

    # ------------------------------------- KHO-01 thông số và tài liệu
    eam_spec_ids = fields.One2many(
        'eam.part.spec', 'product_tmpl_id', string='Thông số kỹ thuật')
    eam_spec_key = fields.Char(
        string='Thông số quyết định', compute='_compute_spec_key',
        store=True,
        help='Gom các thông số đã đánh dấu "quyết định" để nhìn thấy ngay '
             'trên danh sách, trước khi đưa hàng ra khỏi kho.')
    eam_doc_ids = fields.One2many(
        'eam.part.doc', 'product_tmpl_id', string='Tài liệu & bản vẽ')
    eam_doc_count = fields.Integer(compute='_compute_eam_counts')

    # ----------------------------------- KHO-05 model thiết bị lắp được
    eam_model_ids = fields.Many2many(
        'eam.equipment.model', 'eam_model_product_rel',
        'product_id', 'model_id', string='Lắp được cho model')

    # ------------------------------ KHO-07 mức quan trọng & cung ứng
    eam_criticality = fields.Selection(
        [('low', 'Thấp'), ('medium', 'Trung bình'),
         ('high', 'Cao'), ('critical', 'Trọng yếu')],
        string='Mức quan trọng', default='medium',
        help='Dùng chung thang với tài sản (eam.asset) để lọc chéo được.')
    eam_shortage_impact = fields.Selection(
        ANH_HUONG, string='Thiếu thì sao',
        help='Hậu quả nếu cần mà không có. Đây mới là thứ quyết định nên '
             'dự trữ bao nhiêu — không phải giá trị con hàng.')
    eam_lead_days = fields.Integer(
        string='Thời gian cung ứng (ngày)', compute='_compute_lead_days',
        store=True,
        help='Lấy từ nhà cung cấp nhanh nhất đã khai. Cộng với "thiếu thì '
             'sao" mới ra được mức dự trữ hợp lý.')
    eam_is_long_lead = fields.Boolean(
        string='Hàng đặt dài ngày', compute='_compute_lead_days', store=True,
        help='Trên 90 ngày. Loại này hết hàng thì không mua kịp, phải dự '
             'trữ trước — khác hẳn hàng mua được trong tuần.')

    # ------------------------------------------------------------------
    @api.depends('eam_doc_ids', 'eam_xref_ids')
    def _compute_eam_counts(self):
        for p in self:
            p.eam_doc_count = len(p.eam_doc_ids)
            p.eam_xref_count = len(p.eam_xref_ids)

    @api.depends('eam_spec_ids.is_key', 'eam_spec_ids.value',
                 'eam_spec_ids.name', 'eam_spec_ids.uom_label')
    def _compute_spec_key(self):
        for p in self:
            ds = p.eam_spec_ids.filtered('is_key')
            p.eam_spec_key = ' · '.join(
                '%s %s%s' % (s.name, s.value,
                             ' %s' % s.uom_label if s.uom_label else '')
                for s in ds) or False

    @api.depends('seller_ids.delay')
    def _compute_lead_days(self):
        for p in self:
            ds = [s.delay for s in p.seller_ids if s.delay]
            p.eam_lead_days = min(ds) if ds else 0
            p.eam_is_long_lead = bool(ds) and min(ds) > 90

    # ------------------------------------------------------------------
    @api.onchange('eam_part_kind')
    def _onchange_part_kind(self):
        """Dầu mỡ gần như luôn có hạn dùng và phải theo lô.

        Gợi ý chứ không ép: có loại dầu đặc chủng lưu được rất lâu, và
        ép cứng thì người ta sẽ khai sai loại để né.
        """
        for p in self:
            if p.eam_part_kind == 'lubricant' and p.tracking == 'none':
                return {'warning': {
                    'title': _('Dầu mỡ thường có hạn dùng'),
                    'message': _(
                        'Vật tư này đang không theo lô nên không cảnh báo '
                        'hạn dùng được. Cân nhắc đặt "Theo dõi theo lô" và '
                        'khai hạn sử dụng ở tab Tồn kho.'),
                }}

    # ---- Chuyển từ eam_procurement sang đây ----
    # "Phụ tùng này thuộc cụm nào" là việc của kho phụ tùng, không phải
    # của chuỗi mua sắm. Để ở eam_procurement thì mọi cài đặt EAMOne
    # muốn dùng trường này đều bị kéo theo cả bộ Mua sắm của Realty.
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
