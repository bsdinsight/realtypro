# -*- coding: utf-8 -*-
from odoo import api, fields, models


class EamTimeCategory(models.Model):
    """Loại thời gian nói thêm: sản lượng mất ở loại này CÓ AI ĐỀN KHÔNG.

    Vì sao cần trường này
    ---------------------
    Chuẩn chỉ phân biệt *có phải thời gian dừng hay không*. Riêng ô
    "không phải thời gian dừng" đang gộp ba thứ khác nhau hoàn toàn về
    tiền:

    * **Cắt giảm do lưới** — máy chạy được, lưới bắt giảm. Sản lượng mất
      THẬT, nhưng điều khoản *deemed energy* của hợp đồng mua bán điện
      vẫn trả, có hợp đồng trả đủ 100%. Tính nó là tổn thất doanh thu là
      khai lỗ cho một khoản đã được đền.
    * **Ngoài dải môi trường** — gió dưới ngưỡng khởi động. KHÔNG mất gì
      cả, vì không có gì để lấy. Ghi ``lost_mwh`` khác 0 ở đây là lỗi dữ
      liệu, không phải tổn thất.
    * **Bất khả kháng** — mất thật, và không đòi được ai.

    Vì sao SUY bằng mã chứ không khai bằng tệp dữ liệu
    --------------------------------------------------
    Các loại thời gian do gói ngành khai với ``noupdate="1"``. Cờ đó ghi
    vào ``ir_model_data``, và từ đó **không module nào ghi đè các bản ghi
    ấy bằng XML được nữa** — Odoo bỏ qua IM LẶNG, không lỗi, không cảnh
    báo. Viết một tệp dữ liệu ghi đè ``eam_wind.tc_curtail_grid`` sẽ chạy
    trót lọt và không đổi gì cả; chỉ phát hiện ra khi soi số.

    Nên giá trị được SUY trong Python, lưu lại, và vẫn cho sửa tay
    (``readonly=False``) vì có dự án không có điều khoản deemed energy —
    khi đó cắt giảm do lưới là tổn thất thật.
    """
    _inherit = 'eam.time.category'

    # Những mã mà luật suy ở dưới không quyết được, phải chỉ định đích
    # danh. Giữ danh sách này ngắn, và mỗi dòng phải có lý do.
    BAT_THEO_MA = {
        # 5.3.3 "Phát một phần": máy chạy nhưng dưới công suất. Chuẩn xếp
        # nó vào nhánh ĐANG HOẠT ĐỘNG, nên luật suy sẽ ra "không mất gì"
        # — sai, vì phần giảm tải là sản lượng mất thật. Nhánh con
        # 5.3.3-GRID do lưới gây thì luật đã bắt đúng thành "được đền".
        '5.3.3': 'loss',
    }

    energy_treatment = fields.Selection(
        [('loss', 'Tổn thất thật — không ai đền'),
         ('deemed', 'Được đền theo điều khoản deemed energy'),
         ('no_loss', 'Không có sản lượng để mất')],
        # KHÔNG khai required=True: Odoo CHÈN giá trị rỗng trước rồi mới
        # tính trường lưu, nên NOT NULL sẽ nổ ngay lúc tạo một loại thời
        # gian mới. Bắt buộc do chính hàm tính bảo đảm — nó luôn trả về
        # một trong ba giá trị.
        string='Cách tính tiền',
        compute='_compute_energy_treatment', store=True, readonly=False,
        help='Quyết định sản lượng mất ở loại này có vào doanh thu tổn '
             'thất hay không. Hệ thống suy sẵn, nhưng SỬA ĐƯỢC: dự án '
             'không có điều khoản deemed energy thì cắt giảm do lưới là '
             'tổn thất thật.')

    @api.depends('counts_as_downtime', 'is_data_gap', 'attributable_to',
                 'code')
    def _compute_energy_treatment(self):
        for c in self:
            c.energy_treatment = c._suy_cach_tinh_tien()

    def _suy_cach_tinh_tien(self):
        self.ensure_one()
        if self.code in self.BAT_THEO_MA:
            return self.BAT_THEO_MA[self.code]
        # Mất kết nối giám sát thì phải GIẢ ĐỊNH MẤT SẢN LƯỢNG. Giả định
        # ngược lại — coi như máy chạy tốt — là cách êm ái nhất để thổi
        # phồng khả dụng, và đó đúng là lý do chuẩn bắt hạch toán riêng
        # khoảng mất dữ liệu.
        if self.is_data_gap:
            return 'loss'
        if self.counts_as_downtime:
            return 'loss'
        if self.attributable_to == 'grid':
            return 'deemed'
        # Bất khả kháng: mất thật, không ai đền. Phần "không đòi được ai"
        # do trường Quy trách nhiệm trên khoảng dừng xử lý, không phải
        # trường này.
        if self.attributable_to == 'force_majeure':
            return 'loss'
        return 'no_loss'
