# -*- coding: utf-8 -*-
from odoo import api, fields, models


class EamOutage(models.Model):
    """Nối khoảng dừng vào kỳ sản lượng để ra tiền thật.

    Chỗ dễ sai nhất ở đây là tưởng mọi MWh mất đều là tiền mất. Không
    phải: phần do lưới bắt giảm vẫn được trả theo điều khoản *deemed
    energy*, nên nó phải tách ra khỏi tổn thất chứ không cộng vào.
    """
    _inherit = 'eam.outage'

    period_id = fields.Many2one(
        'rp.energy.period', string='Kỳ sản lượng',
        compute='_compute_period', store=True, index=True,
        help='Suy từ thời điểm BẮT ĐẦU. Khoảng vắt qua hai kỳ vẫn tính '
             'trọn vào kỳ bắt đầu — xem cờ "vắt qua kỳ".')
    spans_period = fields.Boolean(
        string='Vắt qua kỳ', compute='_compute_period', store=True,
        help='Khoảng kết thúc ở kỳ khác kỳ bắt đầu. Hiện tại tính trọn '
             'vào kỳ bắt đầu — chưa chia theo tỷ lệ. Cờ này để biết chỗ '
             'nào con số chưa thật chính xác, thay vì giấu đi.')
    tariff_applied = fields.Float(
        string='Giá áp dụng (USD/kWh)', compute='_compute_tien', store=True,
        digits=(16, 5),
        help='Giá BÌNH QUÂN GIA QUYỀN theo sản lượng của chính kỳ đó. Dự '
             'án bán cho nhiều bên mua với giá khác nhau thì sản lượng '
             'mất phải định giá theo tỷ trọng thật, không lấy giá của '
             'một hợp đồng.')

    energy_treatment = fields.Selection(
        related='category_id.energy_treatment', store=True, readonly=True,
        string='Cách tính tiền')

    # Giá trị sản lượng mất, CHƯA xét ai đền. Tách khỏi lost_revenue để
    # nhìn được cả hai mặt: mất bao nhiêu, và trong đó lỗ bao nhiêu.
    energy_value = fields.Monetary(
        string='Giá trị sản lượng mất', compute='_compute_tien', store=True,
        help='Sản lượng mất × giá. Chưa trừ phần được đền — xem "Doanh '
             'thu tổn thất" để biết số lỗ thật.')
    revenue_deemed = fields.Monetary(
        string='Được đền (deemed energy)', compute='_compute_tien',
        store=True,
        help='Phần lưới gây ra mà hợp đồng mua bán điện vẫn trả. Tỷ lệ '
             'lấy từ chính hợp đồng của kỳ, không mặc định 100%.')
    # Ghi đè trường của lõi: có kỳ thì tự tính, không có thì vẫn khai tay.
    lost_revenue = fields.Monetary(
        compute='_compute_tien', store=True, readonly=False,
        help='Số LỖ THẬT = giá trị sản lượng mất − phần được đền. Khoảng '
             'bị lưới cắt giảm có giá trị sản lượng lớn nhưng lỗ bằng 0.')

    @api.depends('date_start', 'date_end', 'location_id')
    def _compute_period(self):
        K = self.env['rp.energy.period']
        for o in self:
            o.period_id = False
            o.spans_period = False
            if not o.date_start:
                continue
            d = o.date_start.date()
            k = K.search([('date_from', '<=', d), ('date_to', '>=', d)],
                         limit=1)
            o.period_id = k
            if k and o.date_end and o.date_end.date() > k.date_to:
                o.spans_period = True

    @api.depends('period_id', 'lost_mwh', 'energy_treatment')
    def _compute_tien(self):
        for o in self:
            gia = o.period_id._rp_gia_binh_quan() if o.period_id else 0.0
            o.tariff_applied = gia
            # tariff là USD/kWh, sản lượng là MWh → nhân 1000.
            o.energy_value = (o.lost_mwh or 0.0) * 1000.0 * gia
            if o.energy_treatment == 'deemed':
                ty = o.period_id._rp_ty_le_deemed() if o.period_id else 0.0
                o.revenue_deemed = o.energy_value * ty / 100.0
            else:
                o.revenue_deemed = 0.0
            if o.energy_treatment == 'no_loss':
                # Loại này nghĩa là KHÔNG CÓ GÌ ĐỂ MẤT — gió dưới ngưỡng
                # khởi động. Có số MWh ở đây là lỗi dữ liệu, nên giữ
                # ``energy_value`` để thấy sai cỡ nào, nhưng không cho nó
                # thành tiền lỗ.
                o.lost_revenue = 0.0
            else:
                o.lost_revenue = o.energy_value - o.revenue_deemed
            if o.period_id and o.period_id.currency_id:
                o.currency_id = o.period_id.currency_id
