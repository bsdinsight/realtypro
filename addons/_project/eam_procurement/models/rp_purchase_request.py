# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class RpPurchaseRequest(models.Model):
    """Thêm nguồn phát sinh EAM vào yêu cầu mua sắm.

    Trước khi có cầu này, yêu cầu mua sắm chỉ neo vào dự án và người đề
    nghị. Mua một con hộp số thay thế thì không ai biết nó mua cho máy
    nào — và sáu tháng sau, lúc cần đối chiếu chi phí bảo trì theo từng
    vị trí, dữ liệu đã mất.

    Hai mức neo, vì thực tế mua phụ tùng có hai kiểu:

    * **Theo tài sản** — thay đúng con này, đã biết sê-ri
    * **Theo loại cấu phần** — mua dự phòng cho kho, chưa biết lắp vào đâu

    Chỗ neo thứ ba — **lệnh công việc** — chưa có vì EAMOne chưa dựng
    phần đó. Khi có, nó cắm vào đây, không phải dựng lại.
    """
    _inherit = 'rp.purchase.request'

    is_spare = fields.Boolean(
        string='Mua phụ tùng bảo trì', tracking=True,
        help='Đánh dấu để phân biệt với mua sắm phục vụ thi công. Chi '
             'phí bảo trì và chi phí đầu tư không được trộn.')
    eam_asset_id = fields.Many2one(
        'eam.asset', string='Mua cho tài sản',
        help='Khi đã biết thay đúng con nào.')
    # TRƯỜNG TÍNH chứ không phải onchange: onchange chỉ chạy trên giao
    # diện, nên yêu cầu tạo bằng mã hay nhập hàng loạt sẽ để trống loại
    # cấu phần — và báo cáo gom chi phí theo loại im lặng thiếu dữ liệu.
    # store + readonly=False: có tài sản thì tự suy, không có thì khai tay.
    eam_category_id = fields.Many2one(
        'eam.asset.category', string='Loại cấu phần',
        compute='_compute_eam_category', store=True, readonly=False,
        help='Khi mua dự phòng cho kho, chưa biết lắp vào đâu. Chọn tài '
             'sản thì trường này tự suy.')

    @api.depends('eam_asset_id')
    def _compute_eam_category(self):
        for r in self:
            r.eam_category_id = (r.eam_asset_id.category_id
                                 or r.eam_category_id)
    eam_location_id = fields.Many2one(
        related='eam_asset_id.current_location_id', store=True,
        string='Vị trí đang lắp',
        help='Suy ra từ tài sản — để sau này cộng được chi phí bảo trì '
             'theo từng vị trí.')

    @api.onchange('eam_asset_id')
    def _onchange_eam_asset(self):
        """Tiện dụng trên giao diện: chọn tài sản thì bật luôn cờ phụ tùng.

        Loại cấu phần KHÔNG đặt ở đây — nó là trường tính, chạy cả khi
        tạo bằng mã.
        """
        for r in self:
            if r.eam_asset_id:
                r.is_spare = True

    @api.constrains('is_spare', 'eam_asset_id', 'eam_category_id')
    def _check_nguon_phat_sinh(self):
        """Mua phụ tùng thì phải nói mua cho cái gì.

        Không ép thì trường này sẽ để trống hết, và việc cộng chi phí
        bảo trì theo tài sản — lý do duy nhất để có cầu nối này — không
        bao giờ chạy được.
        """
        for r in self:
            if r.is_spare and not (r.eam_asset_id or r.eam_category_id):
                raise ValidationError(_(
                    'Yêu cầu "%s" đánh dấu là mua phụ tùng bảo trì thì '
                    'phải nêu mua cho TÀI SẢN nào, hoặc ít nhất cho LOẠI '
                    'CẤU PHẦN nào. Không có thì sau này không cộng được '
                    'chi phí bảo trì theo tài sản.', r.name or ''))
