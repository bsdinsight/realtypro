# -*- coding: utf-8 -*-
"""Số liệu cho bảng điều khiển "Ca trực sáng nay".

Màn này trả lời ĐÚNG MỘT câu: *sáng nay tôi phải làm gì trước*. Nó
không phải bản tóm tắt tháng, không phải báo cáo cho lãnh đạo — hai
thứ đó đọc theo nhịp khác và nằm ở màn "Toàn danh mục nhà máy".

HAI LUẬT CỦA KHUÔN, áp ngay ở tầng dữ liệu chứ không để giao diện tự
xoay xở (xem eam_dashboard/KHUON.md):

① **Chưa đo được KHÔNG trả về 0.** Mọi con số đi kèm một cờ `do_duoc`.
   Thiếu cờ ấy thì giao diện không có cách nào phân biệt "khả dụng 0%"
   với "chưa ai đo" — mà hai chuyện ấy dẫn tới hai hành động trái
   ngược: một bên cử người ra trụ, một bên đi sửa đường truyền.

② **Tỷ lệ luôn kèm mẫu số.** Mỗi tỷ lệ trả kèm `mau_so` (số tổ máy có
   số / tổng số tổ máy). Khả dụng 97% trên hai tổ máy có số không nói
   cùng một chuyện với 97% trên cả ba mươi.

KHÔNG dùng `eam.energy.period` cho luỹ kế tháng, dù nó có sẵn con số:
bảng đó lưu CÙNG một lượng điện thành bốn bậc (ngày/tuần/tháng/năm) và
quên lọc `loai_ky` là cộng gấp bốn. Cộng thẳng từ `eam.unit.day` thì
không có bậc nào để quên, và hai màn chắc chắn nói cùng một con số.
"""
from datetime import timedelta

from odoo import _, api, fields, models

# Trạng thái cảnh báo còn phải xử lý. Giữ ở một chỗ vì ba truy vấn
# dưới đây đều dùng, và lệch nhau một giá trị là ba con số không khớp.
ALARM_MO = ('new', 'ack', 'wo')
WO_MO = ('draft', 'approved', 'planned', 'in_progress')


class EamDashShift(models.AbstractModel):
    _name = 'eam.dash.shift'
    _description = 'Số liệu bảng điều khiển ca trực'

    # ------------------------------------------------------------------
    @api.model
    def _nha_may(self):
        return self.env['eam.location'].search(
            [('location_type', '=', 'plant')], order='code')

    @api.model
    def _to_may(self, nm):
        """Tổ máy trong phạm vi — dùng làm MẪU SỐ của mọi tỷ lệ.

        Lấy theo cờ `la_to_may`, vì đó là quyết định nghiệp vụ của
        người dùng; trạm khí tượng, điểm đo giao nhận và nhà điều hành
        cũng là vị trí thiết bị nhưng không phát ra điện.

        Lần đầu tôi lấy `location_type == 'position'` làm phương án dự
        phòng, và mẫu số nhảy từ 28 lên 67: nó vơ cả điểm đo giao nhận
        lẫn 692 vị trí của SAVA1 — nhà máy còn đang xây, chưa có tổ máy
        nào. Mọi tỷ lệ vì thế thấp đi hơn hai lần mà vẫn trông hợp lý.
        Không có cờ thì trả về RỖNG để mẫu số rơi về số tổ máy thật sự
        có số, chứ không đoán bừa.
        """
        L = self.env['eam.location']
        if 'la_to_may' not in L._fields:
            return L.browse()
        mien = [('id', 'child_of', nm.ids)] if nm else []
        return L.search(mien + [('la_to_may', '=', True)])

    # ------------------------------------------------------------------
    @api.model
    def get_data(self, plant_code=None, ngay=None):
        nm = False
        if plant_code:
            nm = self.env['eam.location'].search(
                [('code', '=', plant_code),
                 ('location_type', '=', 'plant')], limit=1)

        hom_nay = fields.Date.context_today(self)
        if ngay:
            d = fields.Date.to_date(ngay)
        else:
            # Mặc định là HÔM QUA: sáng nay mở màn thì ngày gần nhất có
            # số trọn vẹn là hôm qua. Lấy hôm nay thì mọi ô đều dở dang
            # và người trực học được rằng màn này không đáng tin.
            d = hom_nay - timedelta(days=1)

        to_may = self._to_may(nm)
        return {
            'ngay': fields.Date.to_string(d),
            'hom_nay': fields.Date.to_string(hom_nay),
            'plants': [{'code': p.code, 'name': p.name}
                       for p in self._nha_may()],
            'plant': {'code': nm.code, 'name': nm.name} if nm else None,
            'so_to_may': len(to_may),
            'hom_qua': self._hom_qua(nm, to_may, d),
            'thang': self._luy_ke_thang(nm, d),
            'viec': self._viec_phai_lam(nm, hom_nay),
            'to_may': self._bang_to_may(nm, to_may, d),
        }

    # ------------------------------------------------------------------
    def _hom_qua(self, nm, to_may, d):
        """Trại chạy thế nào trong ngày được chọn."""
        mien = [('date', '=', d)]
        if nm:
            mien.append(('plant_id', '=', nm.id))
        dong = self.env['eam.unit.day'].search(mien)

        co_sl = dong.filtered('do_duoc_sl')
        co_kd = dong.filtered('do_duoc_kd')
        co_hs = dong.filtered('do_duoc_hs')
        tong = len(to_may) or len(dong)

        # Khả dụng cộng TỬ SỐ và MẪU SỐ rồi mới chia, không lấy trung
        # bình các phần trăm: tổ máy nhỏ và tổ máy lớn không cùng trọng
        # số, và trung bình các tỷ lệ cho ra một con số không thuộc về
        # ai cả.
        that = sum(co_kd.mapped('sl_that'))
        mat = sum(co_kd.mapped('sl_mat'))
        mat_om = sum(co_kd.mapped('sl_mat_om'))

        def ty_le(tu, mau):
            return round(100.0 * tu / mau, 2) if mau else 0.0

        sl = sum(co_sl.mapped('san_luong'))
        hs = (sum(co_hs.mapped('he_so_cong_suat')) / len(co_hs)) if co_hs else 0.0

        pr = self._pr_ngay(nm, d)

        return {
            'san_luong_mwh': round(sl / 1000.0, 1),
            'san_luong_do_duoc': bool(co_sl),
            'san_luong_mau_so': [len(co_sl), tong],

            'kd': ty_le(that, that + mat),
            'kd_do_duoc': bool(co_kd) and (that + mat) > 0,
            'kd_om': ty_le(that + (mat - mat_om), that + mat),
            'kd_mau_so': [len(co_kd), tong],

            'he_so': round(hs, 2),
            'he_so_do_duoc': bool(co_hs),
            'he_so_mau_so': [len(co_hs), tong],

            'pr': pr['gia_tri'],
            'pr_do_duoc': pr['do_duoc'],
            'pr_ghi_chu': pr['ghi_chu'],

            'sl_mat_mwh': round(mat / 1000.0, 1),
            'so_khoang': sum(dong.mapped('so_khoang')),
            'so_khoang_chua_tinh': sum(dong.mapped('so_khoang_chua_tinh')),
        }

    def _pr_ngay(self, nm, d):
        """PR của ngày — chỉ có nghĩa với nhà máy điện mặt trời.

        Nhà máy điện gió KHÔNG có PR. Trả về `do_duoc=False` kèm lý do,
        chứ không trả 0: một ô PR bằng 0 trên màn của trại gió là con
        số sai, và người đọc sẽ đi tìm nguyên nhân không tồn tại.
        """
        K = self.env.get('eam.solar.kpi')
        if K is None:
            return {'gia_tri': 0.0, 'do_duoc': False, 'ghi_chu': ''}

        # Hỏi có nhà máy ĐMT nào trong phạm vi không TRƯỚC, rồi mới hỏi
        # ngày này có dòng không. Gộp hai câu lại thì màn của PV50 báo
        # "không có nhà máy điện mặt trời" — vừa sai vừa làm người đọc
        # đi tìm một nguyên nhân không tồn tại. Hai lý do khác nhau dẫn
        # tới hai việc phải làm khác nhau.
        L = self.env['eam.location']
        mien_nm = [('location_type', '=', 'plant')]
        if nm:
            mien_nm.append(('id', '=', nm.id))
        co_dmt = ('is_solar' in L._fields
                  and L.search_count(mien_nm + [('is_solar', '=', True)]))
        if not co_dmt:
            return {'gia_tri': 0.0, 'do_duoc': False,
                    'ghi_chu': 'không có nhà máy điện mặt trời trong phạm vi'}

        mien = [('date', '=', d)]
        if nm:
            mien.append(('plant_id', '=', nm.id))
        r = K.search(mien)
        if not r:
            return {'gia_tri': 0.0, 'do_duoc': False,
                    'ghi_chu': 'chưa dựng bản ghi hiệu suất cho ngày này'}
        co = r.filtered(lambda x: x.pr)
        if not co:
            return {'gia_tri': 0.0, 'do_duoc': False,
                    'ghi_chu': 'chưa tính được PR cho ngày này'}
        return {'gia_tri': round(sum(co.mapped('pr')) / len(co), 2),
                'do_duoc': True,
                'ghi_chu': 'trung bình %d nhà máy' % len(co)}

    # ------------------------------------------------------------------
    def _luy_ke_thang(self, nm, d):
        """Luỹ kế từ đầu tháng tới NGÀY ĐANG XEM, không tới hôm nay.

        Nếu người trực mở lại ngày 12 của tháng trước thì luỹ kế phải
        dừng ở ngày 12, không nhảy tới hôm nay — nếu không hai con số
        trên cùng một màn nói về hai khoảng thời gian khác nhau.
        """
        dau = d.replace(day=1)
        mien = [('date', '>=', dau), ('date', '<=', d)]
        if nm:
            mien.append(('plant_id', '=', nm.id))
        dong = self.env['eam.unit.day'].search(mien)
        co_sl = dong.filtered('do_duoc_sl')
        ngay_co = len(set(co_sl.mapped('date')))
        so_ngay = (d - dau).days + 1
        return {
            'tu_ngay': fields.Date.to_string(dau),
            'den_ngay': fields.Date.to_string(d),
            'san_luong_mwh': round(sum(co_sl.mapped('san_luong')) / 1000.0, 1),
            'do_duoc': bool(co_sl),
            'mau_so': [ngay_co, so_ngay],
            'sl_mat_mwh': round(sum(dong.mapped('sl_mat')) / 1000.0, 1),
        }

    # ------------------------------------------------------------------
    def _viec_phai_lam(self, nm, hom_nay):
        """Danh sách việc, xếp theo mức gấp — không xếp theo tên bảng.

        Thứ tự ở đây là thứ tự người trực nên chạm vào. Cảnh báo chưa ai
        xác nhận đứng trước lệnh quá hạn, vì chưa xác nhận nghĩa là chưa
        ai NHÌN, còn quá hạn thì ít nhất đã có người biết.
        """
        def dem(model, mien):
            M = self.env.get(model)
            if M is None:
                return None
            if nm and 'plant_id' in M._fields:
                mien = mien + [('plant_id', '=', nm.id)]
            return M.search_count(mien)

        ra = []

        def them(ma, so, chu, phu, muc):
            if so is None:
                return
            ra.append({'ma': ma, 'so': so, 'chu': chu, 'phu': phu,
                       'muc': muc if so else 'zero'})

        them('alarm_new',
             dem('eam.alarm', [('state', '=', 'new')]),
             _('cảnh báo chưa ai xác nhận'),
             _('chưa xác nhận nghĩa là chưa ai nhìn'), 'bad')
        them('alarm_crit',
             dem('eam.alarm', [('state', 'in', ALARM_MO),
                               ('severity', 'in', ('high', 'critical'))]),
             _('cảnh báo nghiêm trọng đang mở'),
             _('mức cao và nghiêm trọng'), 'bad')
        them('wo_late',
             dem('eam.work.order', [('tre_han', '=', True),
                                    ('state', 'in', WO_MO)]),
             _('lệnh công việc quá hạn'),
             _('đã qua ngày dự kiến xong'), 'warn')
        them('wo_hold',
             dem('eam.work.order', [('is_on_hold', '=', True),
                                    ('state', 'in', WO_MO)]),
             _('lệnh đang chờ'),
             _('chờ vật tư, cẩu, thời tiết hoặc phiếu'), 'warn')
        them('pm_over',
             dem('eam.pm.schedule', [('state', '=', 'overdue')]),
             _('bảo trì quá hạn'),
             _('quá hạn theo lịch hoặc theo đồng hồ'), 'bad')
        them('pm_soon',
             dem('eam.pm.schedule', [('state', '=', 'due_soon')]),
             _('bảo trì sắp tới hạn'),
             _('cần đặt phụ tùng và xếp người'), 'warn')
        them('rpt_draft',
             dem('eam.daily.report', [('state', '=', 'nhap')]),
             _('báo cáo ngày chưa chốt'),
             _('chưa chốt thì chủ đầu tư chưa đọc được'), 'warn')
        them('outage_open',
             dem('eam.outage', [('is_open', '=', True),
                                ('counts_as_downtime', '=', True)]),
             _('khoảng dừng đang mở'),
             _('máy đang dừng ngay lúc này'), 'bad')
        # Ô làm ra tiền: khoảng dừng đã xác nhận mà chưa quy trách nhiệm
        # thì không đòi được ai cả, và nó nằm im mãi nếu không ai nhắc.
        them('outage_liab',
             dem('eam.outage', [('state', '=', 'confirmed'),
                                ('liability', '=', False)]),
             _('khoảng dừng chưa quy trách nhiệm'),
             _('chưa quy thì không đòi được nhà thầu'), 'warn')
        return ra

    # ------------------------------------------------------------------
    def _bang_to_may(self, nm, to_may, d):
        """Từng tổ máy trong ngày — để thấy MÁY NÀO kéo trại xuống.

        Tổ máy không có dòng nào trong ngày vẫn được liệt kê, với cờ
        `co_dong=False`. Bỏ nó ra khỏi bảng là giấu mất chuyện "hôm qua
        máy này không có số" — đúng cái người trực cần biết nhất.
        """
        mien = [('date', '=', d)]
        if nm:
            mien.append(('plant_id', '=', nm.id))
        dong = self.env['eam.unit.day'].search(mien)
        theo_vt = {r.location_id.id: r for r in dong}

        ra = []
        for vt in (to_may or dong.mapped('location_id')):
            r = theo_vt.get(vt.id)
            if r is None:
                ra.append({
                    'ten': vt.name, 'ma': vt.code or '',
                    'nha_may': vt.plant_id.name if 'plant_id' in vt._fields
                    else '',
                    'co_dong': False,
                })
                continue
            kd = r.kd_san_luong if r.do_duoc_kd else None
            muc = ''
            if kd is not None:
                muc = 'bad' if kd < 90 else ('warn' if kd < 95 else '')
            ra.append({
                'ten': vt.name, 'ma': vt.code or '',
                'nha_may': r.plant_id.name,
                'co_dong': True,
                'san_luong': round(r.san_luong / 1000.0, 2)
                if r.do_duoc_sl else None,
                'kd': round(kd, 2) if kd is not None else None,
                'he_so': round(r.he_so_cong_suat, 2) if r.do_duoc_hs else None,
                'so_khoang': r.so_khoang,
                'sl_mat': round(r.sl_mat / 1000.0, 2) if r.do_duoc_kd else None,
                'muc': muc,
            })
        # Kém nhất lên trước. Tổ máy chưa có số xếp CUỐI chứ không xếp
        # đầu: "không biết" không phải "tệ nhất", và đẩy nó lên đầu là
        # ngày nào cũng báo động giả.
        ra.sort(key=lambda x: (x.get('kd') is None, x.get('kd') or 0))
        return ra
