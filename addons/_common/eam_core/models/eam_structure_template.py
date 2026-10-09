# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class EamStructureTemplate(models.Model):
    """Mẫu cấu trúc cấu phần — sinh cây vị trí con dưới một thiết bị.

    Vì sao cần mẫu, không khai tay
    -------------------------------
    Một tua-bin gió có khoảng mười lăm cấu phần đáng theo dõi riêng. Nhà
    máy ba mươi trụ là bốn trăm rưởi vị trí. Khai tay thì vừa lâu vừa
    lệch nhau — trụ này gọi ``GEN``, trụ kia gọi ``GENERATOR``, và sáu
    tháng sau không gộp được báo cáo nào theo cấu phần.

    Ba thứ hay bị gọi chung là "cấu trúc tài sản"
    ---------------------------------------------

    **① Danh mục LOẠI cấu phần** (``eam.asset.category``) — bảng chủng
    loại dùng chung: hộp số, máy phát, cánh. Nó nói *trên đời có những
    loại gì*, không nói *cây T07 gồm những gì*.

    **② Cây VỊ TRÍ chức năng** (``eam.location``) — cái mẫu này sinh ra.
    `T07/GBX` là một CHỖ, tồn tại suốt 25 năm, và hộp số thay mấy lần
    thì chỗ đó vẫn thế. Lịch sử bám vào đây trả lời câu *"vị trí này hỏng
    hộp số mấy lần"* — câu chỉ ra lỗi nền móng, lỗi dòng gió hay lỗi lắp
    đặt.

    **③ Cây LẮP RÁP tài sản** (``eam.asset.parent_id``) — vật nằm trong
    vật, đi theo vật. Trả lời câu ngược lại: *"con hộp số này đã hỏng ở
    mấy vị trí"* — câu chỉ ra lỗi lô hàng.

    Hai câu đó khác nhau, và trộn hai cây làm một là mất một trong hai.
    """
    _name = 'eam.structure.template'
    _description = 'Mẫu cấu trúc cấu phần'
    _order = 'code'

    name = fields.Char(string='Tên mẫu', required=True, translate=True)
    code = fields.Char(string='Mã', required=True, index=True)
    category_id = fields.Many2one(
        'eam.asset.category', string='Áp cho loại thiết bị',
        ondelete='restrict', index=True,
        help='Mẫu này mô tả cấu trúc bên trong một thiết bị thuộc loại '
             'nào. Thường là loại gốc — ví dụ "Tua-bin gió".')
    line_ids = fields.One2many(
        'eam.structure.template.line', 'template_id', string='Vị trí con')
    line_count = fields.Integer(string='Số vị trí',
                                compute='_compute_count')
    note = fields.Text(string='Ghi chú')
    active = fields.Boolean(default=True)

    _uniq_code = models.Constraint(
        'UNIQUE(code)', 'Mã mẫu cấu trúc không được trùng.')

    @api.depends('line_ids')
    def _compute_count(self):
        for t in self:
            t.line_count = len(t.line_ids)

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for t in self:
            t.display_name = '[%s] %s' % (t.code or '', t.name or '')

    # ------------------------------------------------------------------
    def ap_dung(self, locations):
        """Sinh cây vị trí con dưới các vị trí thiết bị đã cho.

        Chạy lại được: chỉ tạo vị trí CÒN THIẾU, không đụng cái đã có.
        Thêm một cấu phần vào mẫu giữa chừng là chuyện bình thường, và
        lúc đó phải sinh bù cho cả đội máy mà không xoá mất lịch sử lắp
        đặt đã ghi ở những vị trí cũ.
        """
        self.ensure_one()
        L = self.env['eam.location']
        tao = 0
        for goc in locations:
            if goc.location_type != 'position':
                raise UserError(_(
                    'Mẫu cấu trúc chỉ áp cho VỊ TRÍ THIẾT BỊ. "%s" là '
                    '%s.', goc.display_name,
                    dict(L._fields['location_type'].selection).get(
                        goc.location_type)))
            # Sinh theo thứ tự cây: cha trước con, nên duyệt theo cấp.
            ban_do = {}
            for d in self.line_ids.sorted(lambda x: (x.level, x.sequence)):
                cha = (ban_do.get(d.parent_line_id.id) if d.parent_line_id
                       else goc)
                if not cha:
                    continue
                co = L.search([('parent_id', '=', cha.id),
                               ('code', '=', d.code)], limit=1)
                if not co:
                    co = L.create({
                        'name': d.name, 'code': d.code,
                        'parent_id': cha.id,
                        'location_type': 'component',
                        'category_id': d.category_id.id or False,
                        'company_id': goc.company_id.id,
                        'note': d.note or False,
                    })
                    tao += 1
                ban_do[d.id] = co
        return tao

    def action_ap_dung_toan_bo(self):
        """Áp mẫu cho mọi vị trí thiết bị đang lắp đúng loại."""
        self.ensure_one()
        if not self.category_id:
            raise UserError(_(
                'Mẫu "%s" chưa khai áp cho loại thiết bị nào — không biết '
                'sinh cho vị trí nào.', self.name))
        L = self.env['eam.location']
        A = self.env['eam.asset']
        loai = self.env['eam.asset.category'].search(
            [('id', 'child_of', self.category_id.id)])
        ts = A.search([('category_id', 'in', loai.ids),
                       ('is_installed', '=', True)])
        vt = L.browse()
        for a in ts:
            l = a.current_location_id
            while l and l.location_type != 'position':
                l = l.parent_id
            if l:
                vt |= l
        n = self.ap_dung(vt)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': _('Đã sinh %(n)d vị trí mới cho %(v)d thiết bị.',
                             n=n, v=len(vt)),
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }


class EamStructureTemplateLine(models.Model):
    """Một vị trí con trong mẫu."""
    _name = 'eam.structure.template.line'
    _description = 'Vị trí trong mẫu cấu trúc'
    _order = 'sequence, id'

    template_id = fields.Many2one(
        'eam.structure.template', string='Mẫu', required=True,
        ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    code = fields.Char(string='Mã vị trí', required=True)
    name = fields.Char(string='Tên vị trí', required=True, translate=True)
    category_id = fields.Many2one(
        'eam.asset.category', string='Loại cấu phần chấp nhận',
        ondelete='restrict',
        help='Khai vào thì hệ thống cảnh báo khi lắp nhầm loại thiết bị '
             'vào vị trí này.')
    parent_line_id = fields.Many2one(
        'eam.structure.template.line', string='Nằm trong',
        ondelete='cascade',
        help='Để trống thì nằm thẳng dưới thiết bị. Khai vào thì sinh cây '
             'nhiều cấp — ví dụ ba cánh nằm trong rotor.')
    level = fields.Integer(
        string='Cấp', compute='_compute_level', store=True, recursive=True)
    is_rotable_slot = fields.Boolean(
        string='Vị trí cấu phần quay vòng',
        help='Chỗ chứa thứ tháo ra đem đại tu rồi lắp lại — hộp số, máy '
             'phát, cánh, bộ biến đổi. Đây là những vị trí mà lịch sử '
             'theo sê-ri đáng tiền nhất.')
    note = fields.Char(string='Ghi chú')

    _uniq = models.Constraint(
        'UNIQUE(template_id, parent_line_id, code)',
        'Hai vị trí cùng một cha không được trùng mã.')

    @api.depends('parent_line_id.level')
    def _compute_level(self):
        for l in self:
            l.level = (l.parent_line_id.level or 0) + 1 \
                if l.parent_line_id else 1

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for l in self:
            l.display_name = '%s — %s' % (l.code or '', l.name or '')
