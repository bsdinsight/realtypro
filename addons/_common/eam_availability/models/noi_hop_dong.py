# -*- coding: utf-8 -*-
"""Bịt lỗ hổng mà hợp đồng O&M tự khai.

Khi dựng phần hợp đồng, cam kết "khả dụng theo sản lượng" được khai
thẳng là **chưa đo được**, kèm lý do, và mỗi kỳ ra một dòng kết quả nói
rõ như vậy thay vì lặng lẽ thay bằng khả dụng theo thời gian.

Module này làm cho nó đo được. Cách bịt là **kế thừa đúng hai phương
thức** phần hợp đồng đã chừa sẵn, chứ không dựng engine thứ hai:

* ``_ly_do_chua_do`` — bỏ cơ sở này ra khỏi danh sách chưa đo được.
* ``_do_mot`` — trả về số đo thật, cùng hình dạng dict với phần thời
  gian, để chỗ gọi không phải biết nó đến từ module nào.

Nhờ vậy mọi thứ đã dựng quanh hợp đồng — chụp số lúc chốt kỳ, làm tròn
trước khi tính phạt, chặn trần, cảnh báo giờ chưa quy — chạy nguyên vẹn
cho cơ sở mới mà không sửa một dòng nào bên đó.
"""
from odoo import api, fields, models

from . import do_kha_dung_sl as sl


class EamOmCommitment(models.Model):
    _inherit = 'eam.om.commitment'

    @api.model
    def _ly_do_chua_do(self, loai):
        if loai == 'kd_san_luong':
            return ''
        return super()._ly_do_chua_do(loai)


class EamOmPeriod(models.Model):
    _inherit = 'eam.om.period'

    def _do_mot(self, cam, plant_line, tu, den):
        if cam.loai != 'kd_san_luong':
            return super()._do_mot(cam, plant_line, tu, den)

        kq = sl.kha_dung_san_luong(
            self.env, plant_line.plant_id, tu, den,
            chi_om=not cam.tinh_ca_chua_quy)
        if not kq['do_duoc']:
            from odoo.addons.eam_om_contract.models import do_kha_dung as tg
            return tg.chua_do_duoc(kq['ly_do'])

        # Trả về ĐÚNG hình dạng của phần thời gian. Các ô giờ để 0 vì cơ
        # sở này không đếm giờ — nhưng vẫn mang theo số khoảng dừng, để
        # người đọc biết con số dựa trên bao nhiêu lần dừng.
        return {
            'do_duoc': True,
            'gia_tri': kq['gia_tri'],
            'gio_ky': 0.0, 'mau_so': 0.0, 'so_don_vi': 0,
            'gio_dung_tinh': 0.0, 'gio_chua_quy': 0.0,
            'gio_dung_tat_ca': 0.0,
            'so_khoang': kq['so_khoang'],
        }


class EamLocation(models.Model):
    _inherit = 'eam.location'

    so_don_vi_kha_dung = fields.Integer(
        string='Số tổ máy dùng làm mẫu số khả dụng',
        help='Khai ở cấp NHÀ MÁY. Để 0 thì hệ đếm mọi vị trí thiết bị '
             'con — và đếm nhầm: trạm khí tượng cũng là một vị trí thiết '
             'bị nhưng không phát điện, nên nhà máy mười sáu trạm nghịch '
             'lưu ra mười bảy tổ máy. Khả dụng khi đó thấp đi một phần '
             'mười bảy mà vẫn nằm trong khoảng trông hợp lý.')

    power_curve_id = fields.Many2one(
        'eam.power.curve', string='Đường cong công suất',
        help='Khai ở cấp VỊ TRÍ TỔ MÁY. Phải khai tường minh: trên bản '
             'demo, đường cong có sẵn để trống ô loại cấu phần, nên phép '
             'dò "đường cong nào khớp tổ máy này" khớp nhầm vì rỗng khớp '
             'rỗng — một phép so trả về đúng mà không có gì đúng cả.')

    def action_gan_duong_cong(self):
        """Gán đường cong cho mọi tổ máy con, theo model thiết bị đang lắp.

        Chỉ chạy khi model thiết bị khớp ĐÚNG mã model của đường cong.
        Không khớp thì bỏ qua và để người khai tự chọn — đoán ở đây là
        gán nhầm cam kết của hãng khác lên máy của mình.
        """
        PC = self.env['eam.power.curve']
        I = self.env['eam.installation']
        dat = 0
        for nm in self:
            vt = self.search([('id', 'child_of', nm.id),
                              ('location_type', '=', 'position')])
            for v in vt:
                lap = I.search([('location_id', '=', v.id),
                                ('date_remove', '=', False)], limit=1)
                ref = (lap.asset_id.model_id.name
                       if 'model_id' in lap.asset_id._fields else '') or ''
                if not ref:
                    continue
                dc = PC.search([('model_ref', '=', ref)], limit=1)
                if dc:
                    v.power_curve_id = dc.id
                    dat += 1
        return dat
