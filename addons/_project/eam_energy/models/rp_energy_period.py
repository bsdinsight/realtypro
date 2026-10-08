# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class RpEnergyPeriod(models.Model):
    """Đối chiếu sổ dừng máy với sản lượng kỳ đã mất.

    Mốc đối chiếu phải chọn đúng, và chỗ này rất dễ chọn sai
    ---------------------------------------------------------

    Kỳ sản lượng có ba con số nghe na ná nhau mà khác hẳn về nghĩa:

    * ``loss_mwh`` — **tổn thất trên đường dây** tới điểm giao nhận. Thuần
      vật lý, không liên quan gì tới dừng máy.
    * ``shortfall_mwh`` — phần hụt **dưới mức cam kết khả dụng**. Đây là
      số đi đòi nhà thầu, và nó chỉ là phần NGỌN: cam kết 98% nghĩa là
      2% dừng máy được phép xảy ra, mất sản lượng mà không ai phải trả.
    * ``unavail_mwh`` (thêm ở đây) — **toàn bộ** sản lượng mất vì máy
      không khả dụng.

    Số liệu thật của SAVA1 cho thấy khoảng cách: một kỳ khả dụng 97,90%
    so với cam kết 98,00% có ``shortfall_mwh`` 46,9 MWh, trong khi tổn
    thất do không khả dụng là **985,3 MWh** — lệch 21 lần. Lấy
    ``shortfall_mwh`` làm mẫu số thì độ bao phủ nhảy lên 348%, và người
    đọc sẽ "sửa" bằng cách bóp sổ dừng máy xuống cho khớp 46,9 — tức là
    xoá dấu 94% lượng dừng máy thật.

    Nên: **đối chiếu với ``unavail_mwh``, đòi tiền theo ``shortfall_mwh``.**
    """
    _inherit = 'rp.energy.period'

    unavail_mwh = fields.Float(
        string='Tổn thất do không khả dụng (MWh)',
        compute='_compute_unavail', store=True, digits=(16, 3),
        help='Suy từ chính phần trăm khả dụng của kỳ: sản lượng lẽ ra đạt '
             'được nếu máy khả dụng 100%. Đây là mẫu số để đối chiếu sổ '
             'dừng máy — KHÁC "Hụt do khả dụng" vốn chỉ là phần dưới mức '
             'cam kết, tức phần đòi được nhà thầu.')

    outage_ids = fields.One2many(
        'eam.outage', 'period_id', string='Khoảng dừng trong kỳ')
    outage_count = fields.Integer(
        string='Số khoảng dừng', compute='_compute_outage', store=True)
    outage_lost_mwh = fields.Float(
        string='MWh mất giải thích được', compute='_compute_outage',
        store=True, digits=(16, 3),
        help='Chỉ cộng khoảng CON — khoảng gốc của sự cố lan nhiều máy bị '
             'loại ra để khỏi đếm đúp. Và chỉ cộng loại tính tiền là tổn '
             'thất thật: phần lưới bắt giảm nằm ở cột riêng.')
    outage_deemed_mwh = fields.Float(
        string='MWh — lưới bắt giảm', compute='_compute_outage', store=True,
        digits=(16, 3),
        help='Đối chiếu với ô "Bị cắt giảm" của kỳ. Theo IEC 61400-26 thì '
             'cắt giảm KHÔNG phải thời gian dừng — máy vẫn khả dụng — nên '
             'nó không nằm trong mẫu số khả dụng.')
    outage_lost_revenue = fields.Monetary(
        string='Doanh thu tổn thất', compute='_compute_outage', store=True,
        help='Số lỗ thật: đã trừ phần được đền theo deemed energy.')
    outage_coverage_percent = fields.Float(
        string='Độ bao phủ của sổ (%)', compute='_compute_outage',
        store=True, digits=(16, 1), aggregator=False,
        help='MWh giải thích được / tổn thất do không khả dụng. Dưới 100% '
             'là CÓ SẢN LƯỢNG MẤT MÀ KHÔNG AI BIẾT VÌ SAO — nên nhìn con '
             'số này trước khi tin bất kỳ báo cáo khả dụng nào. Trên 100% '
             'là sổ ghi nhiều hơn thực mất: trùng khoảng, hoặc ước lượng '
             'MWh quá tay.')
    outage_unexplained_mwh = fields.Float(
        string='MWh chưa giải thích', compute='_compute_outage', store=True,
        digits=(16, 3),
        help='Phần tổn thất khả dụng mà sổ dừng máy không chỉ ra được '
             'nguyên nhân. Đây là chỗ tiền chảy đi mà không ai đòi.')
    outage_warning_count = fields.Integer(
        string='Dòng nghi lỗi dữ liệu', compute='_compute_outage', store=True,
        help='Số khoảng khai MWh mất trên loại thời gian "không có sản '
             'lượng để mất" — gió dưới ngưỡng khởi động thì không mất gì.')

    mwh_warranty = fields.Float(
        string='MWh — thuộc bảo hành', compute='_compute_outage', store=True,
        digits=(16, 3))
    mwh_om = fields.Float(
        string='MWh — thuộc hợp đồng O&M', compute='_compute_outage',
        store=True, digits=(16, 3))
    mwh_owner = fields.Float(
        string='MWh — chủ đầu tư tự chịu', compute='_compute_outage',
        store=True, digits=(16, 3))
    mwh_grid = fields.Float(
        string='MWh — do lưới', compute='_compute_outage', store=True,
        digits=(16, 3))
    mwh_force_majeure = fields.Float(
        string='MWh — bất khả kháng', compute='_compute_outage', store=True,
        digits=(16, 3),
        help='Mất thật và không đòi được ai. Tách riêng để khỏi lẫn vào '
             'phần chủ đầu tư tự chịu do quản lý kém.')

    revenue_economic_loss = fields.Monetary(
        string='Thiệt hại kinh tế — bên thứ ba gây',
        compute='_compute_outage', store=True,
        help='Giá trị sản lượng mất quy cho bảo hành và nghĩa vụ hợp đồng '
             'O&M. ĐÂY CHƯA PHẢI SỐ ĐÒI ĐƯỢC.')
    revenue_claim_cap = fields.Monetary(
        string='Trần đòi theo hợp đồng', compute='_compute_outage',
        store=True,
        help='Giá trị của phần hụt DƯỚI MỨC CAM KẾT khả dụng. Trên mức cam '
             'kết thì nhà thầu không nợ gì, dù sản lượng vẫn mất.')
    revenue_claimable = fields.Monetary(
        string='Doanh thu tổn thất có thể đòi', compute='_compute_outage',
        store=True,
        help='Lấy số NHỎ HƠN giữa thiệt hại do bên thứ ba gây và trần đòi '
             'theo hợp đồng. Vẫn là số ƯỚC: chế tài khả dụng của hợp đồng '
             'O&M còn có công thức riêng, trần trách nhiệm theo năm, và '
             'thường loại trừ giờ do lưới hoặc bất khả kháng khỏi mẫu số '
             'khả dụng. Con số này để đi đàm phán, không phải để ghi sổ.')

    # ------------------------------------------------------------------
    @api.depends('net_mwh', 'availability_percent')
    def _compute_unavail(self):
        for k in self:
            kd = k.availability_percent or 0.0
            k.unavail_mwh = (
                round(k.net_mwh * (100.0 - kd) / kd, 3)
                if kd and k.net_mwh and kd < 100.0 else 0.0)

    @api.depends('outage_ids.lost_mwh', 'outage_ids.lost_revenue',
                 'outage_ids.energy_value', 'outage_ids.liability',
                 'outage_ids.is_root_cause', 'outage_ids.energy_treatment',
                 'unavail_mwh', 'shortfall_mwh')
    def _compute_outage(self):
        for k in self:
            # Loại khoảng GỐC: sự cố trạm làm 30 máy dừng thì giờ-máy và
            # MWh nằm ở 30 khoảng con, cộng cả cha là đếm đúp.
            ds = k.outage_ids.filtered(lambda o: not o.is_root_cause)
            k.outage_count = len(ds)

            # Chỉ cộng loại TỔN THẤT THẬT. Phần lưới bắt giảm sang cột
            # riêng; phần "không có gì để mất" không vào đâu cả — cộng
            # nó vào đây thì một dòng khai sai lại làm ĐỘ BAO PHỦ ĐẸP
            # LÊN, tức thưởng cho việc nhập sai. Nó chỉ hiện ở ô "dòng
            # nghi lỗi dữ liệu". Loại rỗng vẫn tính là tổn thất, để
            # không âm thầm bỏ sót dòng nào.
            tt = ds.filtered(
                lambda o: o.energy_treatment in ('loss', False))
            k.outage_lost_mwh = sum(tt.mapped('lost_mwh'))
            k.outage_deemed_mwh = sum(
                ds.filtered(lambda o: o.energy_treatment == 'deemed')
                .mapped('lost_mwh'))
            k.outage_lost_revenue = sum(ds.mapped('lost_revenue'))
            k.outage_coverage_percent = (
                k.outage_lost_mwh / k.unavail_mwh * 100.0
                if k.unavail_mwh else 0.0)
            k.outage_unexplained_mwh = round(
                max(k.unavail_mwh - k.outage_lost_mwh, 0.0), 3)
            k.outage_warning_count = len(ds.filtered(
                lambda o: o.energy_treatment == 'no_loss' and o.lost_mwh))

            theo = {}
            for o in tt:
                theo[o.liability] = theo.get(o.liability, 0.0) + o.lost_mwh
            k.mwh_warranty = theo.get('warranty', 0.0)
            k.mwh_om = theo.get('om_contract', 0.0)
            k.mwh_owner = theo.get('owner', 0.0)
            k.mwh_grid = k.outage_deemed_mwh + theo.get('grid', 0.0)
            k.mwh_force_majeure = theo.get('force_majeure', 0.0)

            k.revenue_economic_loss = sum(
                tt.filtered(lambda o: o.liability in ('warranty',
                                                      'om_contract'))
                .mapped('lost_revenue'))
            k.revenue_claim_cap = (
                (k.shortfall_mwh or 0.0) * 1000.0 * k._rp_gia_binh_quan())
            k.revenue_claimable = min(k.revenue_economic_loss,
                                      k.revenue_claim_cap)

    # ------------------------------------------------------------------
    def _rp_gia_binh_quan(self):
        """Giá bình quân gia quyền theo sản lượng của kỳ (USD/kWh).

        Dự án bán cho nhiều bên mua với giá khác nhau — có dự án bán cùng
        lúc cho hai nước. Sản lượng mất phải định giá theo TỶ TRỌNG THẬT
        của kỳ đó, không lấy giá của một hợp đồng rồi áp cho tất cả.
        """
        self.ensure_one()
        sl = sum(self.line_ids.mapped('energy_mwh'))
        if not sl:
            return 0.0
        return sum(l.tariff * l.energy_mwh for l in self.line_ids) / sl

    def _rp_ty_le_deemed(self):
        """Tỷ lệ phần trăm được trả cho sản lượng bị cắt giảm.

        Lấy bình quân gia quyền của các hợp đồng trong kỳ, và hợp đồng
        KHÔNG có điều khoản deemed energy thì vào mẫu số với tỷ lệ 0 —
        nếu bỏ nó ra thì tỷ lệ bình quân bị kéo lên, hoá ra khai được đền
        nhiều hơn thực tế.
        """
        self.ensure_one()
        sl = sum(self.line_ids.mapped('energy_mwh'))
        if not sl:
            return 0.0
        return sum((l.ppa_id.deemed_percent or 0.0)
                   * l.energy_mwh if l.ppa_id.deemed_energy else 0.0
                   for l in self.line_ids) / sl

    def action_mo_khoang_dung(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Khoảng dừng — %s', self.name or ''),
            'res_model': 'eam.outage',
            'view_mode': 'list,form',
            'domain': [('period_id', '=', self.id),
                       ('is_root_cause', '=', False)],
            'context': {'search_default_g_li': 1},
        }
