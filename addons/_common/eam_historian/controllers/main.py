# -*- coding: utf-8 -*-
"""Cổng nạp số đo — mối nối cho hệ giám sát.

Cùng nguyên tắc với sổ cảnh báo: **bất khả tri về nguồn**. Hôm nay
chưa có bộ kết nối SCADA/OPC, nhưng kho chuỗi thời gian không nên chờ
nó. Bất cứ thứ gì đẩy được HTTP đều nạp được: một script Python đọc
Modbus, một gateway OPC-UA, một tệp CSV xuất từ hệ của hãng, hay bộ
kết nối SCADA khi nó về.

Vì sao trả về thống kê thay vì ném lỗi
---------------------------------------
Một lô 10.000 dòng mà hỏng cả lô vì một dòng sai thì bộ kết nối không
có cách nào đi tiếp — nó sẽ thử lại mãi cùng lô đó, và dữ liệu phía
sau dồn lại vô hạn. Nên dòng nào nhận được thì nhận, dòng nào không
thì báo lại kèm lý do và chỉ số dòng.

Vì sao gửi lại là vô hại
-------------------------
Mất kết nối giữa chừng, bộ kết nối phát lại khoảng vừa rồi — chuyện
bình thường, không phải lỗi. Kho dùng ``ON CONFLICT ... DO UPDATE``
nên gửi lại bao nhiêu lần cũng ra đúng một kết quả.
"""
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

TOI_DA = 50000


class EamHistorianController(http.Controller):

    @http.route('/eam/historian/nap', type='jsonrpc', auth='user',
                methods=['POST'], csrf=False)
    def nap(self, so_do=None, nguon_nghi=False, **kw):
        """Nạp một lô số đo.

        Thân yêu cầu::

            {"so_do": [["WTG01_P", "2026-10-16T03:00:00", 1850.5],
                        ["WTG01_WS", "2026-10-16T03:00:00", 7.8]],
             "nguon_nghi": false}

        ``nguon_nghi`` đánh dấu cả lô là đến từ nguồn chưa tin cậy
        (ví dụ nhập tay bù dữ liệu) — số đo vẫn vào kho, chỉ mang thêm
        cờ chất lượng.
        """
        so_do = so_do or []
        if not isinstance(so_do, list):
            return {'ok': False, 'ly_do': 'so_do phải là danh sách'}
        if len(so_do) > TOI_DA:
            # Chặn ở đây chứ không để giao dịch phình ra rồi hết bộ nhớ.
            # Bộ kết nối chia lô nhỏ lại là chạy tiếp được; hết bộ nhớ
            # thì cả tiến trình Odoo chết và mọi người cùng mất dịch vụ.
            return {'ok': False, 'ly_do':
                    'tối đa %d dòng mỗi lô, hãy chia nhỏ' % TOI_DA}
        try:
            kq = request.env['eam.historian'].sudo().nap(
                so_do, nguon_nghi=bool(nguon_nghi))
        except Exception as e:
            _logger.exception('eam_historian: lỗi khi nạp lô')
            return {'ok': False, 'ly_do': str(e)[:300]}
        return {
            'ok': True,
            'nhan': kq['nhan'],
            'co_chat_luong': kq['co_chat_luong'],
            # Trả về TỐI ĐA 50 dòng lỗi: một lô hỏng toàn bộ sẽ sinh
            # 10.000 dòng lý do giống nhau, và câu trả lời đó vừa vô
            # dụng vừa làm nghẽn chính đường truyền đang có vấn đề.
            'bo_qua': [{'dong': i, 'ly_do': r}
                       for i, r in kq['bo_qua'][:50]],
            'tong_bo_qua': len(kq['bo_qua']),
        }

    @http.route('/eam/historian/tags', type='jsonrpc', auth='user',
                methods=['POST'], csrf=False)
    def danh_sach_tag(self, plant=None, **kw):
        """Danh sách mã tag đang khai — để bộ kết nối tự dò, khỏi khai hai nơi."""
        dom = [('is_virtual', '=', False)]
        if plant:
            dom.append(('plant_id.code', '=', plant))
        tags = request.env['eam.tag'].sudo().search(dom)
        return [{'ma': t.code, 'ten': t.name,
                 'vi_tri': t.location_id.complete_code,
                 'don_vi': t.uom_label or '',
                 'nhip_giay': t.sample_seconds,
                 'loai': t.tag_type}
                for t in tags]
