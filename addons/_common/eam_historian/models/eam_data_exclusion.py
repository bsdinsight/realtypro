# -*- coding: utf-8 -*-
"""Khoảng loại trừ khỏi KPI — KHÁC hẳn cờ chất lượng.

Hai khái niệm dễ gộp nhầm, và gộp là mất cả hai
================================================
**Cờ chất lượng** (xem ``eam_tag.py``) nói: *số đo này có thể SAI* —
ngoài dải, nhảy quá nhanh, đầu đo kẹt.

**Khoảng loại trừ** nói ngược lại: *số đo hoàn toàn ĐÚNG, nhưng khoảng
thời gian này không được tính vào KPI.* Tua-bin đang bảo trì theo kế
hoạch thì sản lượng bằng 0 là đúng — tính nó vào hệ số khả dụng là
phạt nhà máy vì đã làm đúng việc phải làm. Điều độ yêu cầu tiết giảm
thì sản lượng thấp là đúng, và đó là chuyện của lưới chứ không phải
của thiết bị.

Gộp hai khái niệm vào một cờ thì hoặc là vứt mất dữ liệu đúng, hoặc là
tính vào KPI những khoảng lẽ ra không tính. Cả hai đều sai, và sai theo
hai hướng ngược nhau.

Vì sao loại trừ là BẢNG RIÊNG, không đóng dấu vào số đo
========================================================
Hai lý do, cả hai đều quyết định:

**① Khoảng loại trừ được ghi SAU.** Người ta ghi sổ dừng máy vào cuối
ca, có khi hôm sau. Dữ liệu đã nằm trong kho từ lâu. Nếu loại trừ là
một cờ đóng vào từng dòng thì mỗi lần ghi sổ phải đi sửa hàng chục
nghìn dòng đã lưu — chậm, khoá bảng, và vi phạm chính luật "không sửa
dữ liệu gốc".

**② Lý do loại trừ thay đổi.** Hôm nay ghi là "mất kết nối", tuần sau
điều tra ra là "tiết giảm theo lệnh điều độ". Sửa một dòng trong bảng
loại trừ thì mọi KPI tính lại đúng ngay; sửa cờ trên 30.000 dòng số đo
thì không ai dám làm.

Nên: số đo thô **không bao giờ bị đụng tới**, và việc loại trừ là một
phép nối lúc đọc.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

LY_DO = [
    ('maintenance', 'Bảo trì theo kế hoạch'),
    ('repair', 'Sửa chữa sự cố'),
    ('curtailment', 'Tiết giảm theo lệnh điều độ'),
    ('grid', 'Sự cố lưới / mất điện lưới'),
    ('comms', 'Mất kết nối thu thập dữ liệu'),
    ('commissioning', 'Chạy thử, nghiệm thu'),
    ('test', 'Thử nghiệm, hiệu chuẩn'),
    ('force_majeure', 'Bất khả kháng'),
    ('other', 'Khác'),
]

# Lý do nào thì KHÔNG phải lỗi của thiết bị — dùng để tính hệ số khả
# dụng cho đúng. Tách ra vì "dừng vì lưới" và "dừng vì hỏng hộp số" đều
# là dừng, nhưng chỉ một trong hai bị trừ vào cam kết khả dụng.
NGOAI_TAM = {'curtailment', 'grid', 'force_majeure'}


class EamDataExclusion(models.Model):
    _name = 'eam.data.exclusion'
    _description = 'Khoảng loại trừ khỏi KPI'
    _inherit = ['mail.thread']
    _order = 'date_from desc, id desc'

    name = fields.Char(string='Diễn giải', required=True, tracking=True)
    reason = fields.Selection(
        LY_DO, string='Lý do', required=True, default='maintenance',
        index=True, tracking=True)
    ngoai_tam = fields.Boolean(
        string='Ngoài tầm kiểm soát', compute='_compute_ngoai_tam',
        store=True,
        help='Tiết giảm, sự cố lưới, bất khả kháng thì KHÔNG trừ vào cam '
             'kết khả dụng của thiết bị. Hỏng hóc thì có. Hai thứ đều là '
             '"dừng máy" nhưng hậu quả hợp đồng khác hẳn.')

    date_from = fields.Datetime(string='Từ', required=True, index=True,
                                tracking=True)
    date_to = fields.Datetime(string='Đến', required=True, index=True,
                              tracking=True)
    gio = fields.Float(string='Số giờ', compute='_compute_gio', store=True,
                       digits=(16, 2), aggregator='sum')

    # ------------------------------------------------------------------
    # Áp cho đâu — từ rộng tới hẹp
    # ------------------------------------------------------------------
    plant_id = fields.Many2one(
        'eam.location', string='Nhà máy',
        domain="[('location_type', '=', 'plant')]", index=True,
        help='Để trống và cũng không khai vị trí/điểm đo thì áp cho MỌI '
             'nhà máy — hiếm khi đúng, nên có cảnh báo.')
    location_ids = fields.Many2many(
        'eam.location', string='Vị trí',
        domain="[('location_type', 'in', ('position', 'plant'))]",
        help='Để trống là áp cho cả nhà máy.')
    tag_ids = fields.Many2many(
        'eam.tag', string='Chỉ riêng điểm đo',
        help='Để trống là áp cho MỌI điểm đo trong phạm vi trên. Khai '
             'đích danh khi chỉ một đầu đo hỏng chứ không phải cả trụ '
             'dừng.')

    outage_id = fields.Many2one(
        'eam.outage', string='Khoảng dừng', ondelete='set null', index=True,
        help='Sinh từ sổ dừng máy. Sửa sổ dừng thì sửa luôn ở đây.')
    exclude_kpi = fields.Boolean(
        string='Loại khỏi KPI', default=True, tracking=True,
        help='Bỏ tích thì khoảng này chỉ được GHI NHẬN để tra cứu, không '
             'ảnh hưởng số liệu. Dùng khi còn đang tranh luận trách '
             'nhiệm — ghi lại trước, quyết sau.')
    note = fields.Text(string='Ghi chú')
    company_id = fields.Many2one(
        'res.company', string='Công ty', required=True,
        default=lambda self: self.env.company, index=True)

    @api.depends('reason')
    def _compute_ngoai_tam(self):
        for e in self:
            e.ngoai_tam = e.reason in NGOAI_TAM

    @api.depends('date_from', 'date_to')
    def _compute_gio(self):
        for e in self:
            e.gio = ((e.date_to - e.date_from).total_seconds() / 3600.0
                     if e.date_from and e.date_to else 0.0)

    @api.constrains('date_from', 'date_to')
    def _check_khoang(self):
        for e in self:
            if e.date_from and e.date_to and e.date_to <= e.date_from:
                raise ValidationError(_(
                    'Khoảng loại trừ "%s": "Đến" phải sau "Từ".', e.name))

    @api.depends('name', 'date_from', 'date_to')
    def _compute_display_name(self):
        for e in self:
            e.display_name = '%s (%s → %s)' % (
                e.name or '',
                e.date_from and e.date_from.strftime('%d/%m %H:%M') or '',
                e.date_to and e.date_to.strftime('%d/%m %H:%M') or '')

    # ------------------------------------------------------------------
    @api.model
    def khoang_ap_dung(self, tag_ids, tu, den):
        """Các khoảng loại trừ chạm vào (tag, tu..den).

        Trả về ``{tag_id: [(tu, den), ...]}``. Khoảng nào chỉ chạm một
        phần thì vẫn trả nguyên — phép lọc ở SQL tự cắt.
        """
        T = self.env['eam.tag']
        tags = T.browse(tag_ids).exists()
        if not tags:
            return {}
        ds = self.search([
            ('exclude_kpi', '=', True),
            ('date_from', '<', den), ('date_to', '>', tu),
        ])
        ra = {}
        for t in tags:
            cho = []
            for e in ds:
                if e.tag_ids and t not in e.tag_ids:
                    continue
                if not e.tag_ids:
                    if e.location_ids and t.location_id not in e.location_ids:
                        continue
                    if e.plant_id and t.plant_id != e.plant_id:
                        continue
                    if not e.location_ids and not e.plant_id and not e.tag_ids:
                        # Không khoanh phạm vi gì cả — áp cho tất cả. Cho
                        # phép, nhưng form có dải cảnh báo vì gần như
                        # luôn là khai sót.
                        pass
                cho.append((e.date_from, e.date_to))
            if cho:
                ra[t.id] = cho
        return ra

    def action_tu_khoang_dung(self):
        """Sinh khoảng loại trừ từ một khoảng dừng máy đã ghi."""
        return True


class EamOutage(models.Model):
    """Nút trên sổ dừng máy: ghi dừng xong thì loại luôn khỏi KPI.

    Không có nút này thì hai sổ sống tách nhau: người ghi sổ dừng tưởng
    đã xong, còn KPI vẫn tính cả khoảng đó. Và vì KPI vẫn ra số nên
    không ai phát hiện là đã thiếu một bước.
    """
    _inherit = 'eam.outage'

    exclusion_ids = fields.One2many(
        'eam.data.exclusion', 'outage_id', string='Khoảng loại trừ KPI')
    exclusion_count = fields.Integer(
        string='Số khoảng loại trừ', compute='_compute_exclusion')

    @api.depends('exclusion_ids')
    def _compute_exclusion(self):
        for o in self:
            o.exclusion_count = len(o.exclusion_ids)

    def action_loai_khoi_kpi(self):
        E = self.env['eam.data.exclusion']
        # Suy lý do loại trừ từ cách quy trách nhiệm của khoảng dừng, vì
        # hai thứ nói về cùng một sự kiện. Không suy được thì để "khác"
        # chứ không đoán bừa — đoán sai ở đây làm lệch hệ số khả dụng.
        # Khớp đúng các giá trị `liability` của eam.outage. Viết sai
        # một mã ở đây thì `.get()` lặng lẽ rơi về mặc định và cả nhóm
        # khoảng dừng bị gán nhầm lý do — sai im lặng.
        anh_xa = {
            'grid': 'grid',
            'force_majeure': 'force_majeure',
            'warranty': 'repair',
            'om_contract': 'repair',
            'owner': 'repair',
            'undetermined': 'other',
        }
        tao = E.browse()
        for o in self:
            if not o.date_start or not o.date_end:
                continue
            ly_do = anh_xa.get(o.liability or 'undetermined', 'other')
            tao |= E.create({
                'name': _('Dừng máy %s', o.display_name),
                'reason': ly_do,
                'date_from': o.date_start,
                'date_to': o.date_end,
                'location_ids': [(6, 0, o.location_id.ids)]
                if o.location_id else False,
                'outage_id': o.id,
            })
            o.message_post(body=_(
                'Đã tạo khoảng loại trừ KPI cho khoảng dừng này. Số đo '
                'THÔ không bị đụng tới — việc loại trừ chỉ áp lúc đọc, '
                'nên sửa lý do sau này là mọi chỉ số tính lại đúng ngay.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Khoảng loại trừ KPI'),
            'res_model': 'eam.data.exclusion',
            'view_mode': 'list,form',
            'domain': [('id', 'in', tao.ids)],
        }
