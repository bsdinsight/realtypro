from odoo import api, fields, models


class ResBank(models.Model):
    """Thêm ward (Phường-Xã) cho res.bank — chi nhánh ngân hàng theo
    cấu trúc hành chính VN 2025 (Tỉnh/TP TW → Phường-Xã, không còn
    quận-huyện)."""
    _inherit = 'res.bank'

    ward_id = fields.Many2one(
        'vau.ward', string='Ward / Phường-Xã',
        domain="[('state_id', '=', state)]",
        help='Phường / Xã của chi nhánh. Cần chọn Tỉnh/TP (state) trước. '
             'Lưu ý: res.bank dùng field tên `state` (không có _id).')

    @api.onchange('country')
    def _onchange_country_clear_ward(self):
        for bank in self:
            if bank.ward_id and bank.country \
                    and bank.country != bank.ward_id.country_id:
                bank.ward_id = False

    @api.onchange('state')
    def _onchange_state_clear_ward(self):
        for bank in self:
            if bank.ward_id and bank.state != bank.ward_id.state_id:
                bank.ward_id = False
