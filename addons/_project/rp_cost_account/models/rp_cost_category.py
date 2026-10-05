# -*- coding: utf-8 -*-
"""Gắn tài khoản kế toán vào danh mục chi phí.

Mục đích là một việc rất cụ thể: khi đẩy số sang phần mềm kế toán
(Bravo, SAP, Oracle), mỗi dòng chi phí phải nói được nó vào tài khoản
nào. Danh mục chi phí chia theo cách người làm dự án nghĩ; hệ thống tài
khoản chia theo cách kế toán nghĩ; chỗ nối hai bên là trường này.

Trường đặt ở CẢ hai cấp:
* `rp.cost.category.master` — đặt một lần ở cấp công ty;
* `rp.cost.category` — bản copy của từng dự án, vì dự án được phép thêm
  mã riêng (`is_project_specific`) mà master không có, và những mã đó
  cũng phải hạch toán được.

Bản copy nhận tài khoản từ master lúc tạo dự án, sau đó ĐỘC LẬP — đúng
luật vàng của danh mục chi phí: sửa master chỉ ảnh hưởng dự án tạo mới.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

# Bộ gán mặc định cho danh mục chuẩn 10 nhóm, theo cách hạch toán của
# CHỦ ĐẦU TƯ: chi phí đầu tư nằm ở 241 "Xây dựng cơ bản dở dang" cho tới
# khi công trình chạy thương mại rồi mới kết chuyển sang TSCĐ.
#   2412 Xây dựng cơ bản      — phần xây lắp, tư vấn, quản lý dự án
#   2411 Mua sắm TSCĐ         — thiết bị, vận chuyển, lắp đặt, chạy thử
#   2130 TSCĐ vô hình         — giá trị quyền sử dụng đất
#   6350 Chi phí tài chính    — phí vốn KHÔNG được vốn hoá
#   6418 Chi phí bán hàng khác
# Nhà thầu hạch toán khác hẳn (154 / 621 / 622 / 623 / 627) — bộ này
# KHÔNG dùng cho vai nhà thầu.
TK_THEO_NHOM = {
    '01': '2412',   # Đất & mặt bằng — phần làm mặt bằng
    '02': '2412',   # Thiết kế & tư vấn
    '03': '2412',   # Kết cấu & phần thô
    '04': '2412',   # Kiến trúc & hoàn thiện
    '05': '2412',   # Cơ điện (MEP)
    '06': '2412',   # Hạ tầng & ngoài nhà
    '07': '2411',   # Thiết bị & công nghệ
    '08': '2412',   # Quản lý & chi phí khác
    '09': '6350',   # Chi phí tài chính
    '10': None,     # Dự phòng — xem ghi chú bên dưới
}
TK_NGOAI_LE = {
    # Tiền đất, đền bù, chuyển mục đích: không phải chi phí xây lắp mà
    # là giá trị quyền sử dụng đất.
    '01.1': '2130',
    '01.2': '2130',
    '01.3': '2130',
    # Lãi vay trong thời gian xây dựng được VỐN HOÁ → nằm cùng công
    # trình, không phải chi phí tài chính trong kỳ.
    '09.1': '2412',
    # Marketing & bán hàng: danh mục ghi "(capex)" nhưng VAS coi đây là
    # chi phí thời kỳ, không vốn hoá được. Để 641 cho đúng chuẩn mực;
    # bản triển khai nào muốn vốn hoá thì sửa tay.
    '08.7': '6418',
}
# Dự phòng (nhóm 10) CỐ Ý để trống: dự phòng là con số lập kế hoạch, khi
# tiêu thật thì nó biến thành chi phí của nhóm tương ứng. Gán tài khoản
# cho nó sẽ đẻ ra bút toán không bao giờ tồn tại.


class RpCostCategoryAccountMixin(models.AbstractModel):
    _name = 'rp.cost.category.account.mixin'
    _description = 'Tài khoản kế toán của danh mục chi phí'

    # Không khai check_company: danh mục chi phí là master cấp công ty,
    # không mang company_id nên check_company sẽ nổ ngay lúc nạp.
    # Cũng không làm trường "số hiệu TK" related store: ở Odoo 19 `code`
    # của tài khoản lưu theo từng công ty, related store vào đó là tự
    # chuốc rắc rối — mà tên hiển thị của tài khoản đã kèm số hiệu rồi.
    account_id = fields.Many2one(
        'account.account', string='Tài khoản kế toán',
        ondelete='restrict', index=True,
        help='Tài khoản hạch toán chi phí thuộc mã này khi đẩy số sang '
             'phần mềm kế toán. Chủ đầu tư thường để 2412 (Xây dựng cơ '
             'bản) cho xây lắp và 2411 (Mua sắm TSCĐ) cho thiết bị.')

    @api.model
    def _tk_mac_dinh_theo_ma(self, ma_chi_phi):
        """Số hiệu tài khoản mặc định cho một mã chi phí, hoặc None."""
        if not ma_chi_phi:
            return None
        ma = ma_chi_phi.strip()
        if ma in TK_NGOAI_LE:
            return TK_NGOAI_LE[ma]
        return TK_THEO_NHOM.get(ma.split('.')[0])

    def _gan_tai_khoan_tt200(self):
        """Lấp tài khoản theo bộ mặc định. Trả về số bản ghi đã gán."""
        Account = self.env['account.account']
        cache = {}
        da_gan = 0
        thieu = set()
        for rec in self:
            so_hieu = self._tk_mac_dinh_theo_ma(rec.code)
            if not so_hieu:
                continue
            if so_hieu not in cache:
                cache[so_hieu] = Account.search(
                    [('code', '=', so_hieu)], limit=1)
            tk = cache[so_hieu]
            if not tk:
                thieu.add(so_hieu)
                continue
            if rec.account_id != tk:
                rec.account_id = tk
                da_gan += 1
        if thieu:
            raise UserError(_(
                "Hệ thống tài khoản chưa có các số hiệu: %s.\n"
                "Bộ gán này dựng theo hệ thống tài khoản Việt Nam "
                "(Thông tư 200/2014/TT-BTC). Vào Cấu hình > Tài khoản "
                "kế toán nạp hệ thống tài khoản trước, hoặc gán tay.",
                ', '.join(sorted(thieu))))
        return da_gan


class RpCostCategoryMaster(models.Model):
    _name = 'rp.cost.category.master'
    _inherit = ['rp.cost.category.master', 'rp.cost.category.account.mixin']

    def _project_copy_vals(self, project, parent):
        vals = super()._project_copy_vals(project, parent)
        vals['account_id'] = self.account_id.id
        return vals

    def action_gan_tai_khoan_tt200(self):
        """Nút trên danh mục chuẩn: lấp sẵn tài khoản cho cả cây."""
        tat_ca = self.search([])
        da_gan = tat_ca._gan_tai_khoan_tt200()
        chua = tat_ca.filtered(lambda r: not r.account_id)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success' if da_gan else 'warning',
                'title': _('Gán tài khoản theo TT200'),
                'message': _(
                    'Đã gán %(gan)s mã. Còn %(chua)s mã chưa có tài '
                    'khoản (nhóm Dự phòng cố ý để trống).',
                    gan=da_gan, chua=len(chua)),
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }


class RpCostCategory(models.Model):
    _name = 'rp.cost.category'
    _inherit = ['rp.cost.category', 'rp.cost.category.account.mixin']

    def action_lay_tai_khoan_tu_master(self):
        """Kéo tài khoản từ mã master tương ứng xuống danh mục dự án.

        Dành cho các dự án đã tạo TRƯỚC khi có trường này — lúc copy cây
        chưa có gì để copy. Chỉ đụng vào dòng đang trống, không ghi đè
        cái người dùng đã tự sửa.
        """
        can_lay = self.filtered(
            lambda r: not r.account_id and r.master_category_id.account_id)
        for rec in can_lay:
            rec.account_id = rec.master_category_id.account_id
        return len(can_lay)
