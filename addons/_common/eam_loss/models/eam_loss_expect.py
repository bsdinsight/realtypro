# -*- coding: utf-8 -*-
"""Mức tổn thất KỲ VỌNG của từng loại, khai theo từng nhà máy.

Sổ hạch toán tổn thất trước nay chỉ trả lời "mất bao nhiêu". Câu người
mua phần mềm hỏi tiếp luôn là **"mất thế là nhiều hay ít"** — bụi bẩn
ăn 2,1% thì tốt hay tồi? Không có mốc thì con số ấy chỉ là một con số.

Khai theo NHÀ MÁY chứ không khai một bảng dùng chung: hai nhà máy cách
nhau ba trăm cây số có mức bụi khác hẳn nhau, và chính thiết kế
PVsyst/PVGIS của từng dự án đã ghi sẵn tỷ lệ tổn thất kỳ vọng riêng.
Ép chung một con số là xoá mất thứ đắt tiền nhất trong hồ sơ thiết kế.

Mốc so là MỐC TÀI NGUYÊN của ngày, không phải mốc kế hoạch: tổn thất
vận hành phải đo trên lượng điện mà trời thực sự cho hôm đó. Lấy mốc
kế hoạch làm mẫu số là ngày trời xấu thì mọi tỷ lệ tổn thất tự nhiên
đẹp lên, mà chẳng ai làm gì giỏi hơn.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class EamLossExpect(models.Model):
    _name = 'eam.loss.expect'
    _description = 'Tổn thất kỳ vọng theo loại'
    _order = 'plant_id, sequence, id'

    plant_id = fields.Many2one(
        'eam.location', string='Nhà máy', required=True, index=True,
        ondelete='cascade', domain="[('location_type', '=', 'plant')]")
    loss_type_id = fields.Many2one(
        'eam.loss.type', string='Loại tổn thất', required=True,
        ondelete='cascade')
    sequence = fields.Integer(related='loss_type_id.sequence', store=True)
    ty_le_pct = fields.Float(
        string='Kỳ vọng (% mốc tài nguyên)', digits=(6, 3), required=True,
        help='Phần trăm của mốc tài nguyên mà loại tổn thất này được '
             'phép ăn. Lấy từ hồ sơ thiết kế (PVsyst, PVGIS) hoặc từ '
             'cam kết của nhà thầu O&M.')
    nguon = fields.Char(
        string='Căn cứ', help='Hồ sơ nào nói con số này — PVsyst bản '
                              'nào, điều khoản hợp đồng nào.')
    company_id = fields.Many2one(
        related='plant_id.company_id', store=True)
    active = fields.Boolean(default=True)

    _uniq = models.Constraint(
        'UNIQUE(plant_id, loss_type_id)',
        'Mỗi nhà máy chỉ khai MỘT mức kỳ vọng cho một loại tổn thất.')

    @api.constrains('ty_le_pct')
    def _check_ty_le(self):
        for r in self:
            if not 0.0 <= r.ty_le_pct <= 100.0:
                raise ValidationError(_(
                    'Mức kỳ vọng phải nằm trong khoảng 0–100%%. Đang '
                    'khai %(gt)s%% cho "%(loai)s".',
                    gt=r.ty_le_pct, loai=r.loss_type_id.name))

    @api.model
    def muc_cua(self, plant, loss_type):
        """Mức kỳ vọng của một (nhà máy, loại), hoặc None nếu CHƯA KHAI.

        Trả None chứ không trả 0. Chưa khai và khai bằng 0 là hai
        chuyện khác hẳn: cái sau nghĩa là "loại này không được phép mất
        gì", cái trước nghĩa là "chưa ai đặt mốc". Trộn hai thứ ấy làm
        một là đẻ ra số mồ côi — đã dính một lần với sản lượng mất.
        """
        r = self.search([('plant_id', '=', plant.id),
                         ('loss_type_id', '=', loss_type.id)], limit=1)
        return r.ty_le_pct if r else None
