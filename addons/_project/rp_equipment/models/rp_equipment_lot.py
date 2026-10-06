# -*- coding: utf-8 -*-
"""Sổ lô thiết bị chính và chặng vận chuyển.

Với 75,8 triệu USD tua-bin, thứ chủ đầu tư cần KHÔNG phải tồn kho mà là
**bàn giao rủi ro**. Phiếu nhập/xuất kho không trả lời được câu hỏi thật
sự hay được hỏi: "hôm nay cánh quạt số 17 đang ở đâu, và nếu nó gãy thì
ai chịu".

Vì vậy mỗi lô đi qua một chuỗi CHẶNG, và rủi ro ghi ở TỪNG CHẶNG chứ
không ở lô: cùng một kiện hàng, đoạn vận tải biển là rủi ro của bên này,
đoạn vận chuyển nội địa lại là của bên khác. Ghi một "chủ sở hữu" duy
nhất cho cả hành trình là xoá mất chính thông tin cần dùng.

Điều kiện giao hàng cũng ghi ở chặng, vì nó quyết định thời điểm chuyển
rủi ro — CIF thì rủi ro chuyển sang bên mua NGAY KHI hàng lên tàu ở cảng
xuất, dù bảo hiểm vẫn do bên bán mua. Đây là chỗ hay bị hiểu nhầm nhất
và cũng là chỗ mất tiền nếu hiểu nhầm.
"""
from odoo import _, api, fields, models

CHANG = [
    ('ex_works', 'Xuất xưởng'),
    ('sea', 'Vận tải biển'),
    ('port', 'Cập cảng'),
    ('customs', 'Thông quan'),
    ('inland', 'Vận chuyển nội địa'),
    ('site', 'Nhập bãi công trường'),
    ('erected', 'Đã lắp dựng'),
]


class RpEquipmentLot(models.Model):
    _name = 'rp.equipment.lot'
    _description = 'Lô thiết bị chính'
    _inherit = ['mail.thread']
    _order = 'project_id, turbine_no, equip_type, id'

    name = fields.Char(string='Mã lô', required=True, copy=False,
                       default=lambda self: _('Mới'), tracking=True)
    description = fields.Char(string='Mô tả', required=True)
    project_id = fields.Many2one(
        're.project', string='Dự án', required=True, index=True,
        ondelete='cascade')
    contract_id = fields.Many2one(
        'rp.contract', string='Hợp đồng cung cấp', index=True,
        ondelete='restrict')
    package_id = fields.Many2one(
        'rp.tender.package', related='contract_id.tender_package_id',
        store=True, string='Gói thầu', readonly=True)
    supplier_id = fields.Many2one(
        'res.partner', related='contract_id.contractor_id', store=True,
        string='Nhà cung cấp', readonly=True)
    payment_milestone_id = fields.Many2one(
        'rp.contract.payment.milestone', string='Mốc thanh toán',
        domain="[('contract_id', '=', contract_id)]",
        help='Tiền của gói cung cấp trả theo tiến độ GIAO HÀNG, nên lô '
             'hàng và mốc thanh toán phải nối được với nhau.')

    equip_type = fields.Selection(
        [('nacelle', 'Nacelle + Hub'),
         ('blade', 'Bộ cánh'),
         ('tower', 'Tháp'),
         ('anchor_cage', 'Lồng bu-lông neo'),
         ('transformer', 'Máy biến áp'),
         ('switchgear', 'Tủ đóng cắt / RMU'),
         ('other', 'Khác')],
        string='Loại thiết bị', required=True, index=True)
    turbine_no = fields.Char(string='Tua-bin số', index=True)
    quantity = fields.Float(string='Số lượng', default=1.0)
    uom_name = fields.Char(string='Đơn vị', default='bộ')
    value = fields.Monetary(string='Giá trị lô', currency_field='currency_id')
    currency_id = fields.Many2one(
        'res.currency', string='Đồng tiền',
        default=lambda self: self.env.company.currency_id)

    movement_ids = fields.One2many(
        'rp.equipment.movement', 'lot_id', string='Chặng')
    state = fields.Selection(
        CHANG + [('planned', 'Kế hoạch')],
        string='Đang ở', compute='_compute_vi_tri', store=True, index=True)
    location_current = fields.Char(
        string='Vị trí hiện tại', compute='_compute_vi_tri', store=True)
    risk_party_id = fields.Many2one(
        'res.partner', string='Bên chịu rủi ro',
        compute='_compute_vi_tri', store=True,
        help='Bên chịu rủi ro của chặng ĐANG diễn ra, hoặc của chặng vừa '
             'hoàn thành nếu hàng đang nằm chờ.')
    date_eta_site = fields.Date(
        string='Dự kiến tới công trường', compute='_compute_vi_tri',
        store=True)

    insurance_ref = fields.Char(string='Số đơn bảo hiểm')
    insurance_expiry = fields.Date(string='Bảo hiểm đến ngày')
    insurance_alert = fields.Boolean(
        string='Bảo hiểm hết hạn trước khi tới nơi',
        compute='_compute_vi_tri', store=True,
        help='Hàng chưa tới công trường mà bảo hiểm đã hết hạn — khoảng '
             'trống này là lúc không ai chịu nếu có chuyện.')
    note = fields.Char(string='Ghi chú')
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company, index=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('Mới')) == _('Mới'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'rp.equipment.lot') or _('Lô mới')
        return super().create(vals_list)

    @api.depends('movement_ids.state', 'movement_ids.sequence',
                 'movement_ids.risk_party_id', 'movement_ids.location_to',
                 'movement_ids.date_planned', 'insurance_expiry')
    def _compute_vi_tri(self):
        for lot in self:
            ds = lot.movement_ids.sorted('sequence')
            xong = ds.filtered(lambda m: m.state == 'done')
            dang = ds.filtered(lambda m: m.state == 'in_progress')[:1]
            # Chặng "hiện tại" = chặng đang đi, nếu không có thì chặng
            # vừa xong (hàng đang nằm chờ ở đầu kia), nếu chưa đi chặng
            # nào thì chặng đầu tiên của kế hoạch. Viết tách ra vì gộp
            # một dòng ba nhánh thì đọc sai thứ tự ưu tiên rất dễ.
            if dang:
                hien = dang
            elif xong:
                hien = xong[-1:]
            else:
                hien = ds[:1]
            lot.state = (dang.leg_type if dang
                         else (xong[-1].leg_type if xong else 'planned'))
            lot.location_current = (
                dang.location_from if dang
                else (xong[-1].location_to if xong else
                      (ds[:1].location_from if ds else False)))
            lot.risk_party_id = hien.risk_party_id if hien else False
            toi_site = ds.filtered(lambda m: m.leg_type == 'site')[:1]
            lot.date_eta_site = toi_site.date_planned if toi_site else False
            lot.insurance_alert = bool(
                lot.insurance_expiry and lot.date_eta_site
                and lot.insurance_expiry < lot.date_eta_site)


class RpEquipmentMovement(models.Model):
    _name = 'rp.equipment.movement'
    _description = 'Chặng vận chuyển lô thiết bị'
    _order = 'lot_id, sequence, id'

    lot_id = fields.Many2one(
        'rp.equipment.lot', string='Lô', required=True, index=True,
        ondelete='cascade')
    sequence = fields.Integer(default=10)
    leg_type = fields.Selection(CHANG, string='Chặng', required=True)
    name = fields.Char(string='Diễn giải')
    location_from = fields.Char(string='Từ')
    location_to = fields.Char(string='Đến')
    date_planned = fields.Date(string='Ngày KH')
    date_actual = fields.Date(string='Ngày thực tế')
    incoterm = fields.Char(
        string='Điều kiện giao hàng',
        help='Quyết định thời điểm chuyển rủi ro. CIF: rủi ro chuyển sang '
             'bên mua NGAY KHI hàng lên tàu ở cảng xuất, dù bảo hiểm vẫn '
             'do bên bán mua.')
    risk_party_id = fields.Many2one(
        'res.partner', string='Bên chịu rủi ro', required=True)
    carrier_id = fields.Many2one('res.partner', string='Đơn vị vận chuyển')
    state = fields.Selection(
        [('planned', 'Kế hoạch'),
         ('in_progress', 'Đang đi'),
         ('done', 'Xong')],
        string='Trạng thái', default='planned', required=True)
    note = fields.Char(string='Ghi chú')
    project_id = fields.Many2one(
        're.project', related='lot_id.project_id', store=True, readonly=True)
