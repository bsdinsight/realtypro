# -*- coding: utf-8 -*-
"""Toàn danh mục nhà máy — số liệu cho màn Fleet overview.

VÌ SAO ĐỌC TỪ `eam.energy.period` CHỨ KHÔNG TỰ CỘNG `eam.unit.day`:
bảng kỳ đã là con số mà màn *Sản lượng* đang bày. Tự cộng lại một kiểu
khác là tạo ra con số thứ hai cho cùng một câu hỏi, và khi hai màn lệch
nhau thì không ai biết màn nào sai — mà cả hai đều "tính đúng" theo
cách của mình.

BẪY ĐÃ BIẾT: `eam.energy.period` lưu CÙNG một lượng điện thành bốn bậc
(ngày/tuần/tháng/năm). Mọi truy vấn ở đây đều kẹp `loai_ky`, bỏ ra là
cộng gấp bốn mà tổng vẫn trông hợp lý.

TOÀN BỘ dữ liệu về trong MỘT lần gọi. Gọi từng khối thì ba nhà máy
thành mươi vòng truy vấn và màn giật mỗi lần đổi ngày.
"""
from datetime import timedelta

from odoo import api, fields, models


class EamFleetDashboard(models.AbstractModel):
    _name = 'eam.fleet.dashboard'
    _description = 'Số liệu bảng điều khiển toàn danh mục'

    # ------------------------------------------------------------------
    @api.model
    def du_lieu(self, ngay=None):
        d = fields.Date.to_date(ngay) if ngay else (
            fields.Date.context_today(self) - timedelta(days=1))
        dau_thang = d.replace(day=1)
        hom_qua = d - timedelta(days=1)

        nha_may = self.env['eam.location'].search(
            [('location_type', '=', 'plant')], order='code')

        ra = {
            'ngay': fields.Date.to_string(d),
            'dau_thang': fields.Date.to_string(dau_thang),
            'tien_te': self.env.company.currency_id.symbol or '',
            'nha_may': [],
        }
        for p in nha_may:
            ra['nha_may'].append(self._mot_nha_may(p, d, dau_thang, hom_qua))

        ra['tong'] = self._tong(ra['nha_may'])
        ra['viec'] = self._viec_phai_lam()
        ra['tin_cay'] = self._tin_cay(dau_thang, d)
        return ra

    # ------------------------------------------------------------------
    def _ky(self, plant, loai, tu_ngay):
        return self.env['eam.energy.period'].search([
            ('plant_id', '=', plant.id),
            ('loai_ky', '=', loai),          # BẮT BUỘC — xem ghi chú đầu tệp
            ('tu_ngay', '=', tu_ngay),
        ], limit=1)

    def _mot_nha_may(self, p, d, dau_thang, hom_qua):
        ngay = self._ky(p, 'ngay', d)
        truoc = self._ky(p, 'ngay', hom_qua)
        thang = self._ky(p, 'thang', dau_thang)

        # Số tổ máy: cờ do người dùng đặt, hệ KHÔNG đoán — đoán là đưa cả
        # trạm khí tượng vào mẫu số khả dụng.
        so_to_may = self.env['eam.location'].search_count([
            ('id', 'child_of', p.id), ('la_to_may', '=', True)])

        # Tổn thất đã QUY RA TIỀN trong tháng.
        #
        # Lọc bằng `do_duoc` (ĐO ĐƯỢC), KHÔNG phải `so_duoc`. Bản đầu tôi
        # dùng nhầm `so_duoc` — nó nghĩa là "SO ĐƯỢC với mức kỳ vọng",
        # tức đòi phải có mốc kỳ vọng khai sẵn. Lọc kiểu đó gạt mất mọi
        # loại tổn thất chưa khai kỳ vọng, và cả đội máy ra đúng 0 đồng
        # trong khi thực tế có 56 dòng mang tiền.
        dong = self.env['eam.loss.day.line'].search([
            ('plant_id', '=', p.id),
            ('date', '>=', dau_thang), ('date', '<=', d),
            ('do_duoc', '=', True),
        ])
        # KHÔNG có dòng nào đo được thì tiền mất là CHƯA BIẾT, không phải
        # bằng 0. `sum([])` ra 0 — đó đúng là cái bẫy mà cả bộ EAMOne
        # dựng lên để tránh, và tôi vừa rơi vào nó ở chính màn này.
        tien_mat = sum(dong.mapped('tien')) if dong else None

        pr = self.env['eam.solar.kpi'].search(
            [('plant_id', '=', p.id), ('date', '=', d)], limit=1)

        def so(rec, f):
            """Trả None khi chưa đo được — KHÔNG trả 0.

            Đây là luật của cả bộ EAMOne, và nó phải đi hết tới tận lớp
            giao diện: một số 0 giả làm người đọc kết luận sai mà vẫn
            thấy báo cáo đầy đủ.
            """
            return rec[f] if rec else None

        sl_ngay = so(ngay, 'san_luong')
        sl_truoc = so(truoc, 'san_luong')
        return {
            'id': p.id,
            'code': p.code or '',
            'ten': p.name or '',
            'la_dmt': bool(pr),
            'so_to_may': so_to_may,
            'sl_ngay': sl_ngay,
            'sl_truoc': sl_truoc,
            'xu_huong': (None if sl_ngay is None or not sl_truoc
                         else (sl_ngay - sl_truoc) / sl_truoc * 100.0),
            'kd_ngay': so(ngay, 'kd_san_luong'),
            'hscs_ngay': so(ngay, 'he_so_cong_suat'),
            'sl_thang': so(thang, 'san_luong'),
            'kd_thang': so(thang, 'kd_san_luong'),
            'hscs_thang': so(thang, 'he_so_cong_suat'),
            # Mẫu số của mọi tỷ lệ ở trên. Luật ② của khuôn: tỷ lệ không
            # kèm mẫu số là con số không bảo vệ được.
            'ngay_co_so': so(thang, 'so_ngay_co_so'),
            'ngay_thieu': so(thang, 'so_ngay_thieu'),
            'so_ngay': so(thang, 'so_ngay'),
            'doanh_thu_thang': so(thang, 'doanh_thu'),
            'ty_le_p50': so(thang, 'ty_le_p50'),
            'co_muc_tieu': bool(thang and thang.co_muc_tieu),
            'tien_mat_thang': tien_mat,
            'pr': pr.pr if pr else None,
            'pr_cam_ket': pr.pr_guaranteed if pr else None,
            'pa': pr.pa if pr else None,
        }

    # ------------------------------------------------------------------
    def _tong(self, ds):
        """Cộng cấp đội máy.

        Khả dụng và hệ số công suất KHÔNG lấy trung bình các phần trăm —
        một nhà máy 48 MW và một nhà máy 4 MW không có cùng trọng số.
        Cộng theo SẢN LƯỢNG rồi mới chia.
        """
        def tong(f):
            # Không nhà máy nào có số thì tổng là CHƯA BIẾT, không phải 0.
            v = [x[f] for x in ds if x[f] is not None]
            return sum(v) if v else None

        def dem_co_so(f):
            return sum(1 for x in ds if x[f] is not None)

        sl_ngay = tong('sl_ngay')
        sl_thang = tong('sl_thang')
        kd = [x for x in ds if x['kd_thang'] is not None
              and x['sl_thang'] is not None]
        kd_td = (sum(x['kd_thang'] * x['sl_thang'] for x in kd)
                 / sum(x['sl_thang'] for x in kd)) if kd and sum(
                     x['sl_thang'] for x in kd) else None
        return {
            'so_nha_may': len(ds),
            'so_to_may': sum(x['so_to_may'] for x in ds),
            'sl_ngay': sl_ngay,
            'sl_thang': sl_thang,
            'kd_thang': kd_td,
            'kd_mau_so': len(kd),           # bao nhiêu nhà máy góp vào
            'doanh_thu_thang': tong('doanh_thu_thang'),
            'tien_mat_thang': tong('tien_mat_thang'),
            # Mẫu số của hai con số tiền: cộng được từ mấy nhà máy.
            'tien_mau_so': dem_co_so('tien_mat_thang'),
            'sl_mau_so': dem_co_so('sl_thang'),
        }

    # ------------------------------------------------------------------
    def _viec_phai_lam(self):
        """Việc đang cháy, xếp theo thứ tự người ta xử.

        Mỗi dòng kèm `action` để bấm vào là sang đúng danh sách — một
        con số không bấm được thì người đọc phải tự đi tìm, và họ sẽ
        không tìm.
        """
        hom_nay = fields.Date.context_today(self)
        A = self.env['eam.alarm']
        W = self.env['eam.work.order']
        P = self.env['eam.pm.schedule']
        MO = ('new', 'ack', 'wo')
        CHUA_XONG = ('draft', 'approved', 'planned', 'in_progress')

        ds = [
            {'ma': 'alarm_critical', 'nhan': 'Cảnh báo nghiêm trọng',
             'phu': 'đang mở, chưa xử lý xong',
             'so': A.search_count([('state', 'in', MO),
                                   ('severity', '=', 'critical')]),
             'muc': 'bad'},
            {'ma': 'alarm_high', 'nhan': 'Cảnh báo mức cao',
             'phu': 'đang mở',
             'so': A.search_count([('state', 'in', MO),
                                   ('severity', '=', 'high')]),
             'muc': 'warn'},
            {'ma': 'wo_overdue', 'nhan': 'Lệnh công việc quá hạn',
             'phu': 'đã qua ngày dự kiến xong mà chưa đóng',
             'so': W.search_count([('state', 'in', CHUA_XONG),
                                   ('date_planned_end', '<', hom_nay)]),
             'muc': 'bad'},
            {'ma': 'pm_overdue', 'nhan': 'Bảo trì quá hạn',
             'phu': 'đã qua hạn, chưa có lệnh',
             'so': P.search_count([('state', '=', 'overdue')]),
             'muc': 'bad'},
            {'ma': 'pm_due_soon', 'nhan': 'Bảo trì sắp tới hạn',
             'phu': 'trong cửa sổ báo trước',
             'so': P.search_count([('state', '=', 'due_soon')]),
             'muc': 'warn'},
            {'ma': 'pm_no_data', 'nhan': 'Bảo trì không đo được hạn',
             'phu': 'chạy theo đồng hồ mà vị trí chưa có số đọc — nó sẽ '
                    'im lặng không bao giờ tới hạn',
             'so': P.search_count([('state', '=', 'no_data')]),
             'muc': 'warn'},
        ]
        return ds

    # ------------------------------------------------------------------
    def _tin_cay(self, tu, den):
        """Số có tin được không.

        Khối này là lý do màn hình này đáng tin hơn một dashboard thường.
        Ba con số dưới đây đều làm cho các con số PHÍA TRÊN đẹp hơn thực
        tế, nên giấu chúng đi là tự lừa mình:

        · dòng chưa đo được  → sản lượng thiếu, nhưng tổng vẫn ra số
        · giờ dừng chưa quy  → khả dụng CAO hơn thật
        · ngày thiếu dữ liệu → mọi tỷ lệ tính trên mẫu số hụt
        """
        U = self.env['eam.unit.day']
        mien = [('date', '>=', tu), ('date', '<=', den)]
        tong_dong = U.search_count(mien)
        return {
            'tong_dong': tong_dong,
            'chua_do_sl': U.search_count(mien + [('do_duoc_sl', '=', False)]),
            'chua_quy': U.search_count(
                mien + [('tinh_trang_dung', '=', 'chua_quy')]),
            'chua_do_kd': U.search_count(mien + [('do_duoc_kd', '=', False)]),
        }
