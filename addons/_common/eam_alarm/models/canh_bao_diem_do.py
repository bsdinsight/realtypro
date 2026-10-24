# -*- coding: utf-8 -*-
"""Cảnh báo đọc KHO CHUỖI THỜI GIAN, không chỉ sổ đồng hồ ghi tay.

Vì sao phải có
---------------
Bộ cảnh báo cũ chỉ đọc ``eam.meter`` — sổ số đọc người ghi tay, mỗi
ngày hoặc mỗi tuần một dòng. Nhưng tín hiệu của một nhà máy điện nằm ở
kho chuỗi thời gian: nhiệt độ hộp số, công suất từng tua-bin, bức xạ,
tốc độ gió — hàng trăm nghìn số đo mà bộ cảnh báo hoàn toàn **mù**.

Một bộ cảnh báo chỉ thấy số người gõ vào thì nó báo chậm đúng bằng
nhịp người gõ. Với hộp số đang nóng lên, nhịp ấy là quá muộn.

Ngưỡng thời gian: thứ phân biệt bộ dùng được với bộ bị tắt
-----------------------------------------------------------
Nhiễu đo một nhịp cũng vượt ngưỡng. Nổ ngay thì mỗi ngày vài chục báo
giả, và người ta chỉ chịu được chừng chục cái trước khi lờ hết — lúc đó
bộ cảnh báo còn tệ hơn không có, vì nó tạo ảo giác đang được canh.

Nên luật khai **vượt liên tục bao nhiêu phút**, và hệ kiểm đúng điều đó
trên chuỗi: mọi số đo trong cửa sổ đều phải vượt.

Lệch cảm biến: cái chỉ lộ khi so HAI cái
-----------------------------------------
Một cảm biến bức xạ trôi dần không tự nói ra — số nó báo vẫn nằm trong
dải hợp lý. Chỉ khi đặt cạnh cảm biến thứ hai mới thấy. Lệch tính theo
phần trăm của trị **lớn hơn**, để một cảm biến chết hẳn về 0 vẫn lộ ra
thay vì làm phép chia cho 0.
"""
import logging
from datetime import timedelta

from odoo import _, api, fields, models

from odoo.addons.eam_historian.models.eam_historian import BANG

_logger = logging.getLogger(__name__)


class EamAlarmRule(models.Model):
    _inherit = 'eam.alarm.rule'

    # ==================================================================
    def _tim_tag(self, ma, trong=None):
        """Tra điểm đo theo mã, giới hạn trong phạm vi áp dụng của luật."""
        self.ensure_one()
        T = self.env['eam.tag']
        ma = (ma or '').strip()
        if not ma:
            return T.browse()
        dk = []
        if trong:
            dk.append(('location_id', 'child_of', trong.id))
        elif self.plant_id:
            dk.append(('plant_id', '=', self.plant_id.id))
        dk.append(('code', '=like', ma.replace('*', '%'))
                  if '*' in ma else ('code', '=', ma))
        return T.search(dk, order='code')

    def _danh_gia_tag(self, luc=None):
        """Chạy luật trên kho chuỗi thời gian.

        ``luc`` cho phép đánh giá tại một MỐC trong quá khứ — dùng để
        chạy thử và để dựng lại cảnh báo của một ngày đã qua. Mặc định
        là bây giờ.
        """
        self.ensure_one()
        A = self.env['eam.alarm']
        luc = luc or fields.Datetime.now()
        if not self._trong_khung_gio(luc):
            return 0, 0
        tags = self._tim_tag(self.tag_code)
        if not tags:
            # Luật canh một điểm đo không tồn tại thì IM LẶNG mãi mãi.
            # Nói ra ở nhật ký chứ không bỏ qua — một luật an toàn chết
            # lặng lẽ là loại hỏng tệ nhất.
            _logger.info('eam_alarm: luật %s không thấy điểm đo nào khớp '
                         'mã "%s".', self.code, self.tag_code)
            return 0, 0
        n_bao = n_tat = 0
        for t in tags:
            vt = t.location_id
            if not vt:
                continue
            if self.chi_khi_phat and not self._dang_phat(vt):
                continue
            vuot, loi, tri = self._kiem_tag(t, vt, luc)
            if vuot:
                A._ghi_nhan(self, vt, loi, value=tri)
                n_bao += 1
            else:
                n_tat += A._tu_tat(self, vt)
        return n_bao, n_tat

    # ==================================================================
    def _kiem_tag(self, t, vt, luc=None):
        """Trả ``(có vượt, câu mô tả, trị số)`` cho một điểm đo."""
        self.ensure_one()
        luc = luc or fields.Datetime.now()
        if self.source == 'tag_deviation':
            return self._kiem_lech(t, vt, luc)
        if self.source == 'tag_silent':
            return self._kiem_im(t, luc)
        phut = max(self.phut_lien_tuc or 0, 0)
        den = luc
        tu = den - timedelta(minutes=phut or 1)
        self.env.cr.execute(
            "SELECT value, ts FROM {b} WHERE tag_id = %s AND ts >= %s "
            "AND ts <= %s ORDER BY ts".format(b=BANG), (t.id, tu, den))
        hang = self.env.cr.fetchall()
        if not hang:
            return False, '', None

        if self.source == 'tag_stall':
            gt = [float(h[0]) for h in hang]
            if len(gt) < 2:
                return False, '', None
            dung = max(gt) - min(gt) == 0.0
            return dung, (_(
                '%(ten)s đứng im ở %(v).3f suốt %(n)d phút — số vẫn về '
                'đều nên KHÔNG phải mất tín hiệu, mà là giá trị không '
                'đổi. Hai chuyện ấy sửa ở hai nơi khác nhau.',
                ten=t.name or t.code, v=gt[0], n=phut) if dung else ''), gt[-1]

        # tag_threshold — MỌI số đo trong cửa sổ phải vượt
        xau = [h for h in hang if self._vuot(float(h[0]))]
        if len(xau) != len(hang):
            return False, '', float(hang[-1][0])
        tri = float(hang[-1][0])
        return True, self._cau_vuot(t, tri, phut, len(hang)), tri

    def _vuot(self, v):
        o = self.operator
        a, b = self.threshold, self.threshold_2
        if o == 'gt':
            return v > a
        if o == 'lt':
            return v < a
        if o == 'between':
            return a <= v <= b
        if o == 'outside':
            return v < a or v > b
        return False

    def _cau_vuot(self, t, tri, phut, so_moc):
        nhan = dict(self._fields['operator'].selection).get(self.operator)
        # Nhãn toán tử đã chứa chữ "dải" rồi, nên ở đây chỉ ghi con số —
        # nếu không ra "nằm ngoài dải dải 44–48".
        dai = ('%.2f–%.2f' % (self.threshold, self.threshold_2)
               if self.operator in ('between', 'outside')
               else _('ngưỡng %.2f', self.threshold))
        return _(
            '%(ten)s đang %(v).3f %(dv)s — %(nhan)s %(dai)s, liên tục '
            '%(p)d phút (%(n)d số đo, không có mốc nào ngược lại).',
            ten=t.name or t.code, v=tri, dv=t.uom_label or '',
            nhan=(nhan or '').lower(), dai=dai, p=phut, n=so_moc)

    def _kiem_im(self, t, luc):
        """Điểm đo ngừng gửi số — cảnh báo QUAN TRỌNG NHẤT của một hệ SCADA.

        Một điểm đo im lặng trông giống hệt một điểm đo bình thường trên
        mọi màn hình: biểu đồ vẫn vẽ tới mốc cuối, con số cuối vẫn hiện.
        Chỉ có phép so với ĐỒNG HỒ mới thấy. Và trong lúc nó im, mọi luật
        ngưỡng canh trên chính điểm đo ấy cũng im theo — mất tín hiệu là
        mất luôn cả lớp canh gác, chứ không chỉ mất một con số.
        """
        self.ensure_one()
        nguong = max(self.phut_lien_tuc or 0, 0) or (
            (self.window_days or 1) * 1440)
        self.env.cr.execute(
            "SELECT max(ts) FROM {b} WHERE tag_id = %s".format(b=BANG),
            (t.id,))
        cuoi = self.env.cr.fetchone()[0]
        if not cuoi:
            return True, _('%s chưa có số đo nào.', t.name or t.code), None
        tre = (luc - cuoi).total_seconds() / 60.0
        if tre < nguong:
            return False, '', tre
        return True, _(
            '%(ten)s ngừng gửi số đã %(gio).1f giờ (mốc cuối %(c)s). Trong '
            'lúc nó im, mọi luật ngưỡng canh trên chính điểm đo này cũng '
            'im theo — kiểm ĐƯỜNG TRUYỀN trước khi cử người ra trụ.',
            ten=t.name or t.code, gio=tre / 60.0, c=cuoi), tre

    # ==================================================================
    def _tri_gan_nhat(self, t, luc):
        """Trị số gần nhất TRƯỚC mốc, đọc thẳng kho chuỗi thời gian.

        KHÔNG dùng ``last_value`` trên điểm đo: đó là trường tổng hợp,
        chỉ được cập nhật khi số đo đi qua cổng nạp. Dữ liệu vào bằng
        đường khác — nạp lô, chuyển đổi, vá tay — thì trường ấy đứng yên
        ở giá trị cũ, và luật so sánh hai cảm biến sẽ so hai con số của
        hai thời điểm khác nhau mà không gì báo.
        """
        self.ensure_one()
        self.env.cr.execute(
            "SELECT value, ts FROM {b} WHERE tag_id = %s AND ts <= %s "
            "ORDER BY ts DESC LIMIT 1".format(b=BANG), (t.id, luc))
        r = self.env.cr.fetchone()
        return (float(r[0]), r[1]) if r else (None, None)

    def _kiem_lech(self, t, vt, luc=None):
        """Hai cảm biến đo cùng đại lượng mà chênh quá ngưỡng."""
        self.ensure_one()
        luc = luc or fields.Datetime.now()
        t2 = self._tim_tag(self.tag_code_2, trong=vt.plant_id or vt)[:1]
        if not t2:
            return False, '', None
        a, ta = self._tri_gan_nhat(t, luc)
        b, tb = self._tri_gan_nhat(t2, luc)
        if a is None or b is None:
            return False, '', None
        if ta != tb:
            # So hai con số của hai thời điểm khác nhau là so nhầm. Một
            # cảm biến chậm mười phút sẽ trông như đang lệch.
            return False, '', None
        lon = max(abs(a), abs(b))
        if not lon:
            return False, '', None
        lech = 100.0 * abs(a - b) / lon
        if lech <= (self.lech_pct or 0):
            return False, '', lech
        return True, _(
            'Hai cảm biến lệch %(l).1f%%: %(a)s đang %(va).3f, %(b)s đang '
            '%(vb).3f. Một trong hai đã trôi — và nhìn riêng từng cái thì '
            'cả hai đều nằm trong dải hợp lý, nên chỉ phép so này mới '
            'thấy.',
            l=lech, a=t.code, va=a, b=t2.code, vb=b), lech
