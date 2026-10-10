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

        # ── Gom một lượt trạng thái bảo trì và lệnh công việc theo VỊ TRÍ.
        #
        # Đọc từng dòng thì 966 tài sản thành gần hai nghìn vòng truy
        # vấn và lưới chờ hàng chục giây. Hai bảng này tra theo vị trí
        # chứ không theo tài sản, nên gom theo location_id.
        #
        # Cấu phần nằm ở vị trí con (T04/GBX) vốn KHÔNG có kế hoạch bảo
        # trì — kế hoạch gắn ở cấp thiết bị. Nên dòng cấu phần để trống,
        # KHÔNG kế thừa của máy cha: kế thừa là nói dối rằng con hộp số
        # có lịch bảo trì riêng.
        vt_ids = ts.mapped('current_location_id').ids
        bt = {}
        PS = self.env.get('eam.pm.schedule')
        if PS is not None and vt_ids:
            for x in PS.search([('location_id', 'in', vt_ids),
                                ('active', '=', True)]):
                o = bt.setdefault(x.location_id.id, {'n': 0, 'tre': 0})
                o['n'] += 1
                ngay = x.days_to_due or 0
                # "Đã có lệnh" KHÔNG đồng nghĩa với đã xong. Tám kế
                # hoạch quá hạn ở đây đã được cron sinh lệnh, nên trạng
                # thái chuyển sang `wo_open` — và nếu chỉ đọc trạng thái
                # thì một việc trễ 97 ngày hiện ra y như một việc còn 5
                # ngày nữa mới tới hạn. Tách ra thành `wo_late`.
                st = ('wo_late' if x.state == 'wo_open' and ngay < 0
                      else x.state)
                o[st] = o.get(st, 0) + 1
                o['tre'] = min(o['tre'], ngay)
        lenh = {}
        W = self.env.get('eam.work.order')
        if W is not None and vt_ids:
            for w in W.search([('location_id', 'in', vt_ids),
                               ('state', 'not in',
                                ('done', 'closed', 'cancelled'))]):
                lenh[w.location_id.id] = lenh.get(w.location_id.id, 0) + 1

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
                # id vị trí để menu chuột phải dựng được domain thật;
                # mã đầy đủ chỉ để NHÌN, không lọc được bằng nó.
                'loc_id': a.current_location_id.id or False,
                'plant': a.plant_id.name or '',
                'criticality': nhan_qt.get(a.criticality, ''),
                'crit_key': a.criticality or '',
                'state': nhan_tt.get(a.state, ''),
                'state_key': a.state or '',
                'warranty_days': bh,
                # Các khoá `*_key` dưới đây là để LỌC, không để đọc.
                #
                # Mỗi nút lọc nhanh trên lưới phải quy về MỘT phép so
                # sánh bằng trên một chuỗi. Hai lý do:
                #
                # ① "Bảo hành sắp hết" vốn là hai điều kiện (>= 0 và
                #    <= 90). Ghép hai vị từ trên cùng một cột trong EJ2
                #    thì phải thay cả `filterSettings`, dễ vỡ và không
                #    thử được ở máy chủ. Quy sẵn về một khoá thì hết.
                # ② Lọc theo kiểu luận lý trong EJ2 có lúc đem so với
                #    chuỗi "false". Chuỗi thì không có chuyện đó.
                #
                # Tô màu dòng cũng dùng khoá, KHÔNG dò nhãn: nhãn đã
                # dịch, sửa một chữ trong bản dịch là mất màu.
                'bh_key': ('' if bh is None
                           else 'het' if bh < 0
                           else 'sap' if bh <= 90 else 'con'),
                'lap_key': 'lap' if a.is_installed else 'chua',
                'wo_key': 'mo' if lenh.get(
                    a.current_location_id.id) else '',
                'warranty_end': (fields.Date.to_string(a.warranty_end)
                                 if a.warranty_end else ''),
                'install_count': a.install_count,
                'is_installed': a.is_installed,
                'rotable': a.is_rotable,
                'pm': self._nhan_bao_tri(bt.get(a.current_location_id.id)),
                'pm_key': self._ma_bao_tri(bt.get(a.current_location_id.id)),
                'wo_open': lenh.get(a.current_location_id.id, 0),
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

    # Thứ tự ưu tiên khi một vị trí có nhiều kế hoạch bảo trì: lấy cái
    # XẤU NHẤT. Một tua-bin có cả "bảo dưỡng 6 tháng" lẫn "kiểm định
    # nâng hạ 12 tháng" — hiện "còn hạn" vì cái thứ hai còn hạn là che
    # mất cái thứ nhất đã quá hạn.
    #
    # `wo_open` và `no_data` KHÔNG gộp vào "còn hạn": đã có lệnh là việc
    # đang chạy chứ không phải chưa tới hạn, còn thiếu số đọc đồng hồ là
    # KHÔNG BIẾT — gộp vào "còn hạn" là báo yên tâm trong khi thực tế
    # không ai đọc đồng hồ máy đó mấy tháng nay.
    _BAO_TRI = [
        ('overdue', 'Quá hạn'),
        ('wo_late', 'Có lệnh, đã trễ'),
        ('due_soon', 'Sắp tới hạn'),
        ('wo_open', 'Đã có lệnh'),
        ('no_data', 'Thiếu số đọc'),
        ('ok', 'Còn hạn'),
    ]

    @classmethod
    def _ma_bao_tri(cls, o):
        if not o:
            return ''
        for ma, _nhan in cls._BAO_TRI:
            if o.get(ma):
                return ma
        return ''

    @classmethod
    def _nhan_bao_tri(cls, o):
        if not o:
            return ''
        for ma, nhan in cls._BAO_TRI:
            if not o.get(ma):
                continue
            # Trễ bao nhiêu NGÀY, không chỉ "đã trễ": con số mới xếp
            # được thứ tự việc nào làm trước.
            if ma in ('overdue', 'wo_late') and o.get('tre'):
                nhan = '%s %d ngày' % (nhan, -o['tre'])
            return ('%s (%d)' % (nhan, o['n']) if o[ma] == o['n']
                    else '%s %d/%d' % (nhan, o[ma], o['n']))
        return ''

    def action_mo_luoi_cay(self):
        """Mở lưới cây, neo vào chính bản ghi đang mở."""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'eam_tree.asset_tree',
            'name': 'Lưới cây — %s' % (self.code or ''),
            'params': {'root_id': self.id},
        }
