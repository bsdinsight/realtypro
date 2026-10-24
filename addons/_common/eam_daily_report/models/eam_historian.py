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

from odoo import _, api, models

from odoo.addons.eam_historian.models.eam_historian import BANG

_logger = logging.getLogger(__name__)

#: Cách cộng nhiều điểm đo lại thành một con số của nhà máy.
GOP_NHIEU = {'tong': 'sum', 'tb': 'avg', 'max': 'max'}


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

        # ---- Lượt 2: ĐỈNH & GIỜ TRÊN NGƯỠNG — cộng theo từng mốc ------
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
                   count(*)
            FROM theo_moc
        """.format(gn=cach_gop, bang=BANG),
            (tags.ids, tu, den, nguong or 0.0))
        dinh, dinh_luc, n_tren, n_moc = cr.fetchone()

        return {
            'gop': tong,
            'dinh': float(dinh) if dinh is not None else None,
            'dinh_luc': dinh_luc,
            'gio_tren_nguong': (n_tren * nhip / 3600.0) if nhip else None,
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
