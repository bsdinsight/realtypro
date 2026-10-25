# -*- coding: utf-8 -*-
"""Tóm tắt NGÀY của một hoặc nhiều điểm đo.

Vì sao không dùng thẳng ``doc_gop``
------------------------------------
``doc_gop`` trả chuỗi theo bậc thời gian và gộp đúng cách của từng điểm
đo — đúng việc của nó. Ba con số tờ báo cáo ngày cần lại không nằm trong
đó:

* **thời điểm đạt đỉnh** — gộp ``max`` cho ra giá trị, không cho ra lúc
  nào. "Đỉnh 42,1 MW" không kèm giờ thì không đối chiếu được với tờ của
  nhà máy;
* **số giờ trên ngưỡng** — giờ hoà lưới là số giờ công suất lớn hơn 0;
* và cả hai cần cùng một lượt quét.

Gộp NHIỀU điểm đo: hai lượt, không phải một
--------------------------------------------
Nhà máy điện gió không có chuỗi bậc đo như điện mặt trời — sản lượng
ngày là **tổng của mười hai tua-bin**. Gộp nhiều điểm đo tưởng dễ, và
đây là chỗ sai im lặng:

* **tổng ngày** phải gộp TỪNG ĐIỂM TRƯỚC rồi mới cộng. Đồng hồ luỹ kế
  cộng thô rồi lấy hiệu thì một đồng hồ bị thay giữa ngày sẽ kéo tụt cả
  tổng nhà máy, mà kết quả vẫn là một con số trông bình thường;
* **đỉnh và giờ trên ngưỡng** thì ngược lại: phải cộng theo TỪNG MỐC
  THỜI GIAN trước rồi mới lấy đỉnh. Lấy đỉnh từng tua-bin rồi cộng ra
  "đỉnh nhà máy" là cộng mười hai đỉnh xảy ra ở mười hai thời điểm khác
  nhau — con số ấy chưa bao giờ tồn tại.

Nên hai câu, không phải một.

Cách gộp nhiều điểm KHÔNG được đoán
------------------------------------
Cộng mười hai công suất ra công suất nhà máy: đúng. Cộng mười hai nhiệt
độ: vô nghĩa. Hệ không đoán — chưa khai cách gộp mà có nhiều hơn một
điểm đo khớp thì **từ chối và nói rõ**, chứ không chọn bừa một cách rồi
để con số trông như thật.
"""
import logging

import math

from odoo import _, api, models

from .eam_historian import BANG

_logger = logging.getLogger(__name__)

#: Cách cộng nhiều điểm đo lại thành một con số của nhà máy.
#: Dưới mức này thì không công bố hướng trung bình. 0,3 là mức quen
#: dùng trong thống kê hướng: dưới đó phân bố coi như không có hướng
#: trội, và mọi số đo hướng trung bình đều là ngẫu nhiên.
NGUONG_TAP_TRUNG = 0.30

GOP_NHIEU = {'tong': 'sum', 'tb': 'avg', 'max': 'max',
             # Gộp nhiều điểm đo HƯỚNG: trung bình số học của 350° và
             # 10° ra 180°, tức ngược hẳn hướng thật. Mỗi điểm đo đã có
             # thể khai vector_avg cho riêng nó, nhưng cộng mười hai kết
             # quả ấy lại bằng phép cộng thường thì vẫn vỡ ở chỗ vòng
             # qua 0°.
             'vector': 'vector'}


class EamHistorian(models.AbstractModel):
    _inherit = 'eam.historian'

    @api.model
    def tom_tat_ngay(self, tag_ids, tu, den, nguong=0.0, gop_nhieu=None):
        """Bốn con số của một ngày, cho một hoặc nhiều điểm đo.

        Trả ``None`` khi không có điểm đo nào; ``{'n': 0}`` khi có điểm
        đo nhưng không có số nào trong ngày; ``{'loi': ...}`` khi thiếu
        khai báo cách gộp.
        """
        self._dam_bao_bang()
        tags = self.env['eam.tag'].browse(tag_ids).exists()
        if not tags:
            return None
        if len(tags) > 1 and not gop_nhieu:
            return {'loi': _(
                '%(n)d điểm đo cùng khớp nhưng chưa khai cách gộp. Cộng '
                'công suất các tua-bin ra công suất nhà máy thì đúng, '
                'cộng nhiệt độ thì vô nghĩa — hệ không đoán hộ.',
                n=len(tags))}
        cach_gop = GOP_NHIEU.get(gop_nhieu or 'tong', 'sum')
        cr = self.env.cr

        if cach_gop == 'vector':
            # Gộp VECTƠ phải làm MỘT LƯỢT trên toàn bộ số đo của mọi
            # điểm, không gộp từng điểm rồi cộng lại: trung bình của các
            # trung bình chỉ đúng khi các điểm có cùng số mẫu, và sai ở
            # chỗ vòng qua 0° ngay cả khi cùng số mẫu.
            cr.execute("""
                SELECT avg(sin(radians(value))), avg(cos(radians(value))),
                       count(*), count(*) FILTER (WHERE quality <> 0)
                FROM {bang}
                WHERE tag_id = ANY(%s) AND ts >= %s AND ts < %s
            """.format(bang=BANG), (tags.ids, tu, den))
            s_tb, c_tb, n, n_nghi = cr.fetchone()
            if not n or s_tb is None:
                return {'n': 0}
            goc = (math.degrees(math.atan2(float(s_tb), float(c_tb)))
                   + 360.0) % 360.0
            # ĐỘ TẬP TRUNG: độ dài vectơ tổng hợp, 1 là gió một hướng,
            # 0 là gió toả đều. Dưới ngưỡng này thì "hướng trung bình"
            # KHÔNG có nghĩa — gió thổi hai hướng ngược nhau triệt tiêu
            # nhau và kim chỉ đâu cũng được, mà kết quả vẫn là một con
            # số hợp lệ trong 0–360 nên không ai nghi. Trả về kèm cờ để
            # nơi in ra từ chối thay vì in bừa.
            R = math.hypot(float(s_tb), float(c_tb))
            if R < NGUONG_TAP_TRUNG:
                return {'n': n, 'n_nghi': n_nghi, 'gop': None,
                        'do_tap_trung': R, 'loi': _(
                            'gió trong ngày toả đều (độ tập trung %(r).3f '
                            '< %(g).2f) — không có hướng trội nào, nên '
                            '"hướng trung bình" là con số vô nghĩa. Xem '
                            'hoa gió để thấy phân bố thật.',
                            r=R, g=NGUONG_TAP_TRUNG)}
            return {'gop': goc, 'do_tap_trung': R,
                    'dinh': None, 'dinh_luc': None,
                    'gio_tren_nguong': None, 'moc_dau': None,
                    'moc_cuoi': None, 'n': n, 'n_nghi': n_nghi,
                    'n_moc': n, 'so_diem_do': len(tags),
                    'nhip': max(tags.mapped('sample_seconds') or [0])}

        # ---- Lượt 1: TỔNG NGÀY — gộp từng điểm trước, rồi mới cộng ----
        tong = None
        n = n_nghi = 0
        for cach, ids in self._theo_cach_gop(tags).items():
            cr.execute("""
                SELECT tag_id, {gop} AS gt, count(*) AS n,
                       count(*) FILTER (WHERE quality <> 0) AS n_nghi
                FROM {bang}
                WHERE tag_id = ANY(%s) AND ts >= %s AND ts < %s
                GROUP BY tag_id
            """.format(gop=self._bieu_thuc_gop(cach), bang=BANG),
                (ids, tu, den))
            for _tid, gt, so, nghi in cr.fetchall():
                n += so
                n_nghi += nghi
                if gt is None:
                    # Đồng hồ luỹ kế bị thay hay quay vòng: KHÔNG cộng 0
                    # vào tổng nhà máy. Bỏ qua lặng lẽ thì tổng vẫn ra
                    # một con số trông bình thường mà thiếu hẳn một máy.
                    continue
                gt = float(gt)
                tong = gt if tong is None else (
                    max(tong, gt) if cach_gop == 'max' else tong + gt)
        if not n:
            return {'n': 0}
        if tong is not None and cach_gop == 'avg' and len(tags) > 1:
            tong = tong / len(tags)

        # ---- Lượt 2: ĐỈNH, GIỜ TRÊN NGƯỠNG, MỐC ĐẦU/CUỐI --------------
        #
        # Mốc đầu và mốc cuối phải lấy ở ĐÂY, trên chuỗi đã cộng theo
        # từng mốc, chứ không phải min/max của bảng số đo: nhà máy gửi
        # số suốt đêm với giá trị 0, nên min(ts) của bảng là 00:00 mọi
        # ngày — một con số luôn đúng cú pháp và luôn vô nghĩa. Cái cần
        # biết là lúc nhà máy BẮT ĐẦU PHÁT, tức mốc đầu tiên vượt ngưỡng.
        nhip = max(tags.mapped('sample_seconds') or [0])
        cr.execute("""
            WITH theo_moc AS (
                SELECT ts, {gn}(value) AS v
                FROM {bang}
                WHERE tag_id = ANY(%s) AND ts >= %s AND ts < %s
                GROUP BY ts
            )
            SELECT max(v),
                   (array_agg(ts ORDER BY v DESC NULLS LAST))[1],
                   count(*) FILTER (WHERE v > %s),
                   count(*),
                   min(ts) FILTER (WHERE v > %s),
                   max(ts) FILTER (WHERE v > %s)
            FROM theo_moc
        """.format(gn=cach_gop, bang=BANG),
            (tags.ids, tu, den, nguong or 0.0, nguong or 0.0, nguong or 0.0))
        dinh, dinh_luc, n_tren, n_moc, moc_dau, moc_cuoi = cr.fetchone()

        return {
            'gop': tong,
            'dinh': float(dinh) if dinh is not None else None,
            'dinh_luc': dinh_luc,
            'gio_tren_nguong': (n_tren * nhip / 3600.0) if nhip else None,
            'moc_dau': moc_dau, 'moc_cuoi': moc_cuoi,
            'n': n, 'n_nghi': n_nghi, 'n_moc': n_moc,
            'so_diem_do': len(tags), 'nhip': nhip,
        }

    @api.model
    def _theo_cach_gop(self, tags):
        """Nhóm điểm đo theo cách gộp của chính nó."""
        kq = {}
        for t in tags:
            kq.setdefault(t.aggregation, []).append(t.id)
        return kq
