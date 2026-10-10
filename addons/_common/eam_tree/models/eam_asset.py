# -*- coding: utf-8 -*-
from odoo import api, fields, models


class EamAsset(models.Model):
    """Dữ liệu cho lưới cây sổ tài sản."""
    _inherit = 'eam.asset'

    @api.model
    def treegrid_data(self, plant_code=None, root_id=None):
        """Toàn bộ cây về trong MỘT lần gọi, dạng PHẲNG có trỏ cha.

        Lưới cây của Syncfusion nhận hai dạng dữ liệu: lồng nhau theo
        trường con, hoặc phẳng kèm khoá cha. Chọn dạng **phẳng**:

        * Odoo đọc ra đã sẵn phẳng, không phải dựng cây trong Python rồi
          lại rã ra trong JavaScript.
        * Lọc và sắp xếp trên lưới chạy thẳng trên mảng phẳng; dạng lồng
          nhau phải duyệt đệ quy mỗi lần gõ phím tìm kiếm.

        Khoá dùng ``id`` SỐ của Odoo, không dùng mã tài sản. EJ2 **mất
        sạch dòng mà khung vẫn vẽ** nếu khoá chứa dấu cách — nhìn như
        lỗi dữ liệu, thực ra là lỗi khoá, và đã dính một lần ở Gantt.
        Mã tài sản hôm nay không có dấu cách, nhưng không có gì bảo đảm
        khách hàng sau cũng vậy.
        """
        mien = []
        if root_id:
            mien.append(('id', 'child_of', int(root_id)))
        elif plant_code:
            nm = self.env['eam.location'].search(
                [('complete_code', '=', plant_code)], limit=1)
            if nm:
                mien.append(('plant_id', '=', nm.id))
        ts = self.search(mien, order='code, id')

        hn = fields.Date.context_today(self)
        nhan_qt = dict(self._fields['criticality'].selection)
        nhan_tt = dict(self._fields['state'].selection)
        dong = []
        co = set(ts.ids)
        for a in ts:
            bh = (a.warranty_end - hn).days if a.warranty_end else None
            dong.append({
                'id': a.id,
                # Cha nằm NGOÀI tập đang xem thì cắt về gốc, không thì
                # cả nhánh biến mất: lưới cây bỏ qua dòng trỏ tới một
                # khoá không tồn tại, im lặng.
                'parent_id': (a.parent_id.id
                              if a.parent_id and a.parent_id.id in co
                              else None),
                'code': a.code or '',
                'name': a.name or '',
                'category': a.category_id.name or '',
                'serial': a.serial_no or '',
                'location': a.current_location_id.complete_code or '',
                'plant': a.plant_id.name or '',
                'criticality': nhan_qt.get(a.criticality, ''),
                'crit_key': a.criticality or '',
                'state': nhan_tt.get(a.state, ''),
                'warranty_days': bh,
                'warranty_end': (fields.Date.to_string(a.warranty_end)
                                 if a.warranty_end else ''),
                'install_count': a.install_count,
                'is_installed': a.is_installed,
                'rotable': a.is_rotable,
            })
        return {
            'rows': dong,
            'count': len(dong),
            'plants': [{'code': n.complete_code, 'name': n.name}
                       for n in self.env['eam.location'].search(
                           [('location_type', '=', 'plant')],
                           order='complete_code')],
            'plant_code': plant_code or False,
        }

    def action_mo_luoi_cay(self):
        """Mở lưới cây, neo vào chính bản ghi đang mở."""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'eam_tree.asset_tree',
            'name': 'Lưới cây — %s' % (self.code or ''),
            'params': {'root_id': self.id},
        }
