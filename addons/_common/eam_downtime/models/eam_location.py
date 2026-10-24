# -*- coding: utf-8 -*-
"""Hai cách tính giờ vận hành, và giá điện khai trên nhà máy.

Vì sao PHẢI có hai con số
--------------------------
Tờ báo cáo vận hành ngày thật của một nhà máy đang chạy ghi cả hai, sát
nhau, và chúng khác nhau:

    System Operational hours            11,75 h
    System Operational hours (for PR)   11,47 h
    Curtailment Outage                   0,28 h

Chênh lệch đúng bằng giờ cắt giảm. Lý do: khi lưới yêu cầu giảm phát,
nhà máy **vẫn sẵn sàng** — giờ đó phải tính vào giờ vận hành khi đánh
giá nhà thầu, nhưng **không được** tính vào mẫu số của tỷ số hiệu suất,
vì hiệu suất hỏi *"nắng vào bao nhiêu thì ra được bao nhiêu điện"* và
trong giờ bị cắt giảm thì câu hỏi đó không có nghĩa.

Lấy nhầm một trong hai thì tỷ số hiệu suất lệch đúng bằng tỷ lệ giờ cắt
giảm — vài phần trăm, đủ để một hợp đồng đạt thành không đạt, mà con số
vẫn nằm trong khoảng trông hợp lý.
"""
from datetime import datetime

from odoo import fields, models


class EamLocation(models.Model):
    _inherit = 'eam.location'

    gia_dien_kwh = fields.Float(
        string='Giá điện (/kWh)', digits=(16, 2),
        help='Chỉ khai ở cấp nhà máy, và chỉ dùng khi không có hợp đồng '
             'mua bán điện để tra. Có hợp đồng thì giá lấy từ biểu giá '
             'của hợp đồng — hai nơi khai giá thì sớm muộn hai nơi lệch.')

    # ==================================================================
    def gio_van_hanh(self, tu, den):
        """Giờ vận hành của nhà máy trong một khoảng, theo HAI định nghĩa.

        Trả về dict với ``tong_quat`` (dùng để đánh giá nhà thầu) và
        ``cho_pr`` (dùng làm mẫu số tỷ số hiệu suất), cộng các thành
        phần để người đọc tự kiểm lại phép trừ.
        """
        self.ensure_one()
        O = self.env['eam.outage']
        gio_ky = (den - tu).total_seconds() / 3600.0
        bay_gio = datetime.now()

        khoang = O.search([
            ('location_id', 'child_of', self.id),
            ('state', '=', 'confirmed'),
            ('is_root_cause', '=', False),
            ('date_start', '<', den),
            '|', ('date_end', '=', False), ('date_end', '>', tu),
        ])
        dung = cat_giam = mat_du_lieu = 0.0
        for o in khoang:
            ket = o.date_end or min(bay_gio, den)
            dau, cuoi = max(o.date_start, tu), min(ket, den)
            if cuoi <= dau:
                continue
            g = (cuoi - dau).total_seconds() / 3600.0
            if o.category_id.is_data_gap:
                mat_du_lieu += g
            if o.counts_as_downtime:
                dung += g
            # Cắt giảm KHÔNG phải dừng máy — máy vẫn sẵn sàng — nên nó
            # không nằm trong `dung`, và phải trừ riêng ở con số cho PR.
            if o.group_id.la_cat_giam:
                cat_giam += g

        tong_quat = max(gio_ky - dung, 0.0)
        return {
            'gio_ky': gio_ky,
            'gio_dung': dung,
            'gio_cat_giam': cat_giam,
            'gio_mat_du_lieu': mat_du_lieu,
            'tong_quat': tong_quat,
            'cho_pr': max(tong_quat - cat_giam, 0.0),
        }

    def gio_theo_nhom(self, tu, den):
        """Giờ dừng gộp theo NHÓM BÁO CÁO, kèm dòng chưa xếp nhóm.

        Loại thời gian chưa ánh xạ nhóm vẫn ra một dòng riêng thay vì
        biến mất — tổng sáu dòng nhỏ hơn tổng thật mà không ai báo thiếu
        là cách im lặng nhất để một báo cáo nói sai.
        """
        self.ensure_one()
        O = self.env['eam.outage']
        bay_gio = datetime.now()
        kq = {}
        for o in O.search([
                ('location_id', 'child_of', self.id),
                ('state', '=', 'confirmed'),
                ('is_root_cause', '=', False),
                ('date_start', '<', den),
                '|', ('date_end', '=', False), ('date_end', '>', tu)]):
            ket = o.date_end or min(bay_gio, den)
            dau, cuoi = max(o.date_start, tu), min(ket, den)
            if cuoi <= dau:
                continue
            ten = o.group_id.name if o.group_id else 'Chưa xếp nhóm'
            d = kq.setdefault(ten, {'gio': 0.0, 'kwh': 0.0, 'tien': 0.0,
                                    'so': 0, 'chua_tien': 0})
            d['gio'] += (cuoi - dau).total_seconds() / 3600.0
            d['kwh'] += (o.lost_mwh or 0.0) * 1000.0
            # Tiền đã tính sẵn trên chính khoảng dừng, kèm vết giá lấy
            # từ đâu. Nhân lại ở đây là mở ra khả năng hai nơi dùng hai
            # giá cho cùng một ngày.
            d['tien'] += o.lost_revenue or 0.0
            # Đếm riêng khoảng dừng ĐÃ có sản lượng mất mà CHƯA quy ra
            # tiền: cộng chúng như số 0 thì tổng tiền nhỏ hơn thật mà
            # vẫn là một con số dương, trông như đã tính xong.
            if (o.lost_mwh or 0) and not (o.lost_revenue or 0):
                d['chua_tien'] = d.get('chua_tien', 0) + 1
            d['so'] += 1
        return kq
