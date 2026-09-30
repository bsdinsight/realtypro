# -*- coding: utf-8 -*-
"""TSBĐ phần thuộc borrowing base: tỷ lệ cho vay và trục dự án.

Hai thứ này nằm ở LÕI vì phép tính base và khả dụng theo dự án cần
chúng. Phần quyền đòi nợ (gắn HĐ với CĐT / IPC, tự định giá lại theo
sản lượng) cần dữ liệu thi công nên nằm ở re_loan_bb_project.
"""
from odoo import api, fields, models


class ReLoanCollateralType(models.Model):
    _inherit = 're.loan.collateral.type'

    advance_rate = fields.Float(
        string='Tỷ lệ cho vay (%)', default=0.0,
        help='Tỷ lệ NH cho vay trên giá trị TSBĐ loại này (BĐS ~70, '
             'quyền đòi nợ ~50-70, tiền gửi ~95). Mặc định cho pledge — '
             'override được từng pledge. 0 = chưa khai → KHÔNG tính '
             'vào borrowing base.')


class ReLoanCollateralProjectAxis(models.Model):
    """Trục DỰ ÁN cho TSBĐ — nguyên tắc nghiệp vụ: quyền đòi nợ của dự án X chỉ
    bảo đảm cho khoản vay của dự án X, không tự động gánh dự án khác.
    TSBĐ không gắn dự án (BĐS, tiền gửi...) = TSBĐ CHUNG, gánh cả gói."""
    _inherit = 're.loan.collateral'

    # Việc 1414: người dùng cần thấy tỷ lệ cho vay NGAY trên danh sách
    # tài sản, không phải mở sang danh mục loại tài sản mới biết. Số này
    # lấy theo LOẠI tài sản; từng lần thế chấp vẫn sửa đè được (trường
    # advance_rate trên re.loan.collateral.pledge).
    advance_rate = fields.Float(
        string='Tỷ lệ cho vay (%)',
        related='type_id.advance_rate', readonly=True,
        help='Tỷ lệ NH cho vay trên giá trị tài sản, theo loại tài sản. '
             '0 = chưa khai → tài sản KHÔNG được tính vào cơ sở bảo '
             'đảm. Khai ở Cấu hình → Loại tài sản bảo đảm.')
    value_lendable = fields.Monetary(
        string='Giá trị cho vay được',
        compute='_compute_value_lendable',
        help='= Giá trị hiện tại × Tỷ lệ cho vay. Phần ngân hàng chấp '
             'nhận làm cơ sở bảo đảm, chưa trừ phần đã thế chấp.')

    @api.depends('value_current', 'advance_rate')
    def _compute_value_lendable(self):
        for rec in self:
            rec.value_lendable = (rec.value_current or 0.0) * \
                (rec.advance_rate or 0.0) / 100.0

    project_id = fields.Many2one(
        're.project', string='Dự án (ring-fence)',
        compute='_compute_project_id', store=True, index=True,
        readonly=False,
        help='TSBĐ quyền đòi nợ thuộc dự án nào. Có bộ thi công thì tự '
             'lấy từ IPC/HĐ CĐT; không có thì chọn tay. TRỐNG = tài sản '
             'chung của doanh nghiệp, bảo đảm chung cho toàn bộ gói tín '
             'dụng (bể dùng chung).')

    def _compute_project_id(self):
        # Lõi không có nguồn nào để suy ra dự án — giữ nguyên giá trị
        # người dùng chọn. re_loan_bb_project ghi đè hàm này để lấy từ
        # IPC / HĐ với CĐT.
        for rec in self:
            if not rec.project_id:
                rec.project_id = False
