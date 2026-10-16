# -*- coding: utf-8 -*-
"""Kho chuỗi thời gian — viết bằng SQL thuần, KHÔNG đi qua ORM.

Vì sao không phải một model Odoo bình thường
=============================================
Một nhà máy 12 tua-bin, 50 điểm đo mỗi trụ, lấy mẫu 1 giây là **600
dòng mỗi giây** — 52 triệu dòng một ngày, 19 tỷ dòng một năm. Với nhịp
1 phút vẫn là 315 triệu dòng một năm.

ORM của Odoo không dành cho việc đó, và không phải vì chậm một chút:

* ``create()`` chạy hàm tính, ghi nhật ký, kiểm quyền từng dòng — đắt
  hơn hai bậc độ lớn so với ``INSERT`` hàng loạt.
* Một bảng ``ir.model`` vài tỷ dòng làm hỏng chính công cụ của Odoo:
  màn danh sách sẽ cố đếm tổng số dòng, và câu đếm đó không bao giờ
  xong.

Nên ở đây tách đôi: **siêu dữ liệu** (điểm đo là gì, gộp thế nào) nằm
ở model Odoo ``eam.tag``; **số đo** nằm ở bảng ``eam_tag_reading`` do
module này tự tạo và tự quản bằng SQL.

Vì sao PostgreSQL thuần chứ không phải TimescaleDB
===================================================
Máy chủ đang chạy ``postgres:16`` không có TimescaleDB, và container
cơ sở dữ liệu đó đang phục vụ **bốn** cơ sở dữ liệu sống. Đổi image để
lấy một extension là rủi ro không tương xứng với lợi ích tại quy mô
hiện tại.

Nên kho này dùng **phân mảnh theo tháng** của PostgreSQL 16 — đủ cho
nhịp phút, và giữ mỗi chỉ mục ở kích thước làm việc được. Chỗ nào phụ
thuộc công nghệ đều gom vào đúng file này, nên lắp TimescaleDB sau chỉ
là thay phần tạo bảng và thêm chính sách nén, không đụng tới phần còn
lại của sản phẩm.

Nói thẳng giới hạn: **nhịp 1 giây cho cả nhà máy thì cần nén**, tức
cần TimescaleDB hoặc tương đương. Con số đo được ghi ở cuối file sau
khi chạy thử tải.

Ba luật của kho
===============
**① Gửi lại phải vô hại.** ``ON CONFLICT (tag_id, ts) DO UPDATE``: bộ
kết nối SCADA phát lại một khoảng sau khi mất kết nối là chuyện bình
thường, không được thành lỗi và cũng không được nhân đôi dữ liệu.

**② Không bao giờ xoá số thô.** Luật làm sạch chỉ đóng **cờ chất
lượng**. Lọc xong xoá bản gốc thì không bao giờ chứng minh lại được —
mà yêu cầu R05 nói rõ *không xoá, không nén mất mát dữ liệu gốc*.

**③ Phân mảnh tạo theo nhu cầu.** Thiếu phân mảnh là ``INSERT`` nổ.
Một historian không được phép từ chối dữ liệu chỉ vì người quản trị
quên chạy việc định kỳ, nên mỗi lượt nạp tự bảo đảm phân mảnh cho các
tháng có trong lô.
"""
import logging
from datetime import datetime, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval

from odoo.addons.eam_historian.models.eam_tag import (
    CO_KET, CO_NGOAI_DAI, CO_NGUON_NGHI, CO_NHAY_NHANH, CO_TOT,
)

_logger = logging.getLogger(__name__)

BANG = 'eam_tag_reading'

# Hàm cho phép dùng trong công thức tag tính toán.
HAM_AN_TOAN = {
    'abs': abs, 'min': min, 'max': max, 'round': round,
    'sqrt': lambda x: x ** 0.5, 'pow': pow,
}


class EamHistorian(models.AbstractModel):
    """Lớp truy cập kho chuỗi thời gian. Không có bảng của riêng nó."""
    _name = 'eam.historian'
    _description = 'Kho chuỗi thời gian (historian)'

    # ------------------------------------------------------------------
    # Tạo bảng & phân mảnh
    # ------------------------------------------------------------------
    @api.model
    def _dam_bao_bang(self):
        cr = self.env.cr
        cr.execute("SELECT to_regclass(%s)", (BANG,))
        if cr.fetchone()[0]:
            return False
        _logger.info('eam_historian: tạo bảng %s', BANG)
        cr.execute("""
            CREATE TABLE %s (
                tag_id   integer          NOT NULL,
                ts       timestamp        NOT NULL,
                value    double precision,
                quality  smallint         NOT NULL DEFAULT 0,
                PRIMARY KEY (tag_id, ts)
            ) PARTITION BY RANGE (ts)
        """ % BANG)
        # Chỉ mục phụ cho câu quét theo thời gian xuyên nhiều tag (biểu
        # đồ nhiều tag). BRIN thay vì btree: dữ liệu chèn gần như theo
        # thứ tự thời gian nên BRIN nhỏ hơn hàng trăm lần mà vẫn cắt
        # được khoảng.
        cr.execute("""
            CREATE INDEX %s_ts_brin ON %s USING brin (ts)
            WITH (pages_per_range = 32)
        """ % (BANG, BANG))
        return True

    @api.model
    def _ten_phan_manh(self, d):
        return '%s_p%04d%02d' % (BANG, d.year, d.month)

    @api.model
    def _dam_bao_phan_manh(self, cac_ngay):
        """Tạo phân mảnh tháng cho mọi mốc thời gian trong lô."""
        cr = self.env.cr
        thang = {(d.year, d.month) for d in cac_ngay}
        for nam, th in sorted(thang):
            dau = datetime(nam, th, 1)
            cuoi = datetime(nam + (th == 12), (th % 12) + 1, 1)
            ten = self._ten_phan_manh(dau)
            cr.execute("SELECT to_regclass(%s)", (ten,))
            if cr.fetchone()[0]:
                continue
            _logger.info('eam_historian: tạo phân mảnh %s', ten)
            cr.execute(
                "CREATE TABLE %s PARTITION OF %s "
                "FOR VALUES FROM (%%s) TO (%%s)" % (ten, BANG),
                (dau, cuoi))

    @api.model
    def _cron_phan_manh_truoc(self):
        """Tạo sẵn phân mảnh cho 3 tháng tới.

        Tạo theo nhu cầu lúc nạp vẫn chạy được, nhưng tạo bảng trong
        chính giao dịch đang nạp sẽ **khoá** bảng cha một nhịp. Làm
        trước vào lúc rảnh thì lượt nạp đầu tháng không bị khựng.
        """
        self._dam_bao_bang()
        hn = fields.Datetime.now()
        self._dam_bao_phan_manh([hn + timedelta(days=31 * i)
                                 for i in range(4)])
        return True

    # ------------------------------------------------------------------
    # Nạp dữ liệu
    # ------------------------------------------------------------------
    @api.model
    def nap(self, so_do, nguon_nghi=False):
        """Nạp một lô số đo.

        ``so_do``: danh sách ``(mã_tag, thời_điểm, giá_trị)`` — thời
        điểm là chuỗi ISO hoặc ``datetime``.

        Trả về thống kê, KHÔNG ném lỗi cho từng dòng sai: một lô 10.000
        dòng mà hỏng cả lô vì một dòng lỗi thì bộ kết nối không có cách
        nào đi tiếp. Dòng không nhận được thì báo lại trong ``bo_qua``.
        """
        if not so_do:
            return {'nhan': 0, 'bo_qua': [], 'co_chat_luong': 0}
        self._dam_bao_bang()

        T = self.env['eam.tag']
        ma = {t.code: t for t in T.search([])}
        hang, bo_qua, dem_co = [], [], 0
        moc = []

        # Gom theo tag để kiểm tra chất lượng theo đúng trình tự thời gian.
        theo_tag = {}
        for i, d in enumerate(so_do):
            try:
                c, t, v = d[0], d[1], d[2]
            except (TypeError, IndexError, KeyError):
                bo_qua.append((i, _('dòng không đúng dạng (mã, thời điểm, giá trị)')))
                continue
            tag = ma.get(c)
            if not tag:
                bo_qua.append((i, _('không có tag mã "%s"', c)))
                continue
            if tag.is_virtual:
                # Tag tính toán KHÔNG có số đo riêng. Nhận vào thì sẽ có
                # hai nguồn sự thật cho cùng một điểm, và chúng sẽ lệch.
                bo_qua.append((i, _('"%s" là tag tính toán, không nhận số '
                                    'đo trực tiếp', c)))
                continue
            try:
                tt = fields.Datetime.to_datetime(t)
                gt = float(v) if v is not None else None
            except (ValueError, TypeError):
                bo_qua.append((i, _('thời điểm hoặc giá trị không đọc được')))
                continue
            if not tt:
                bo_qua.append((i, _('thiếu thời điểm')))
                continue
            theo_tag.setdefault(tag, []).append((tt, gt))
            moc.append(tt)

        if not theo_tag:
            return {'nhan': 0, 'bo_qua': bo_qua, 'co_chat_luong': 0}

        self._dam_bao_phan_manh(moc)

        for tag, ds in theo_tag.items():
            ds.sort(key=lambda x: x[0])
            truoc_gt, truoc_ts, run = self._trang_thai_cuoi(tag)
            for tt, gt in ds:
                q = CO_TOT
                if nguon_nghi:
                    q |= CO_NGUON_NGHI
                if gt is not None:
                    q |= self._cho_diem_chat_luong(tag, gt, truoc_gt, truoc_ts, tt)
                    # Đếm chuỗi lặp y hệt để bắt đầu đo "kẹt".
                    if truoc_gt is not None and gt == truoc_gt:
                        run += 1
                    else:
                        run = 1
                    if tag.stuck_count and run >= tag.stuck_count:
                        q |= CO_KET
                    truoc_gt, truoc_ts = gt, tt
                if q:
                    dem_co += 1
                hang.append((tag.id, tt, gt, q))
            # Giữ lại chuỗi lặp để lô sau đếm tiếp — không giữ thì một
            # đầu đo chết trải qua nhiều lô sẽ không bao giờ đủ ngưỡng.
            tag.sudo().write({'stuck_run': run})

        self._ghi_hang_loat(hang)
        return {'nhan': len(hang), 'bo_qua': bo_qua, 'co_chat_luong': dem_co}

    @api.model
    def _trang_thai_cuoi(self, tag):
        """Giá trị + thời điểm cuối đã lưu, và độ dài chuỗi lặp hiện tại."""
        cr = self.env.cr
        cr.execute(
            "SELECT value, ts FROM %s WHERE tag_id = %%s "
            "ORDER BY ts DESC LIMIT 1" % BANG, (tag.id,))
        r = cr.fetchone()
        return (r[0] if r else None, r[1] if r else None,
                tag.stuck_run or 0)

    @api.model
    def _cho_diem_chat_luong(self, tag, gt, truoc_gt, truoc_ts, tt):
        """Cờ chất lượng cho một số đo. KHÔNG bao giờ loại bỏ số đo."""
        q = CO_TOT
        if tag.check_range and (tag.value_min or tag.value_max):
            if tag.value_min and gt < tag.value_min:
                q |= CO_NGOAI_DAI
            if tag.value_max and gt > tag.value_max:
                q |= CO_NGOAI_DAI
        if tag.max_rate and truoc_gt is not None and truoc_ts:
            giay = (tt - truoc_ts).total_seconds()
            if giay > 0 and abs(gt - truoc_gt) / giay > tag.max_rate:
                q |= CO_NHAY_NHANH
        return q

    @api.model
    def _ghi_hang_loat(self, hang):
        """INSERT hàng loạt, gửi lại vô hại."""
        if not hang:
            return
        from psycopg2.extras import execute_values
        sql = (
            "INSERT INTO %s (tag_id, ts, value, quality) VALUES %%s "
            "ON CONFLICT (tag_id, ts) DO UPDATE "
            "SET value = EXCLUDED.value, quality = EXCLUDED.quality" % BANG)
        execute_values(self.env.cr._obj, sql, hang, page_size=5000)

    # ------------------------------------------------------------------
    # Đọc
    # ------------------------------------------------------------------
    @api.model
    def tag_co_du_lieu(self):
        """Id các tag đã có ít nhất một số đo trong kho.

        Dùng `DISTINCT tag_id` chứ không đếm: chỉ cần biết CÓ hay KHÔNG,
        mà đếm đủ trên vài trăm triệu dòng thì tốn gấp nhiều lần.
        """
        cr = self.env.cr
        cr.execute("SELECT to_regclass(%s)", (BANG,))
        if not cr.fetchone()[0]:
            return set()
        cr.execute("SELECT DISTINCT tag_id FROM %s" % BANG)
        return {r[0] for r in cr.fetchall()}

    @api.model
    def thong_ke_tag(self, tag_id):
        cr = self.env.cr
        cr.execute("SELECT to_regclass(%s)", (BANG,))
        if not cr.fetchone()[0]:
            return {}
        cr.execute("""
            SELECT count(*), min(ts), max(ts),
                   count(*) FILTER (WHERE quality <> 0)
            FROM %s WHERE tag_id = %%s
        """ % BANG, (tag_id,))
        n, dau, cuoi, nghi = cr.fetchone()
        gt = None
        if cuoi:
            cr.execute("SELECT value FROM %s WHERE tag_id = %%s AND ts = %%s"
                       % BANG, (tag_id, cuoi))
            r = cr.fetchone()
            gt = r[0] if r else None
        return {'n': n or 0, 'dau': dau, 'cuoi': cuoi,
                'gt_cuoi': gt or 0.0, 'nghi': nghi or 0}

    @api.model
    def _bieu_thuc_gop(self, cach):
        """Câu SQL gộp, theo đúng cách gộp của từng tag.

        Đây là chỗ một historian hay sai IM LẶNG — xem chú thích đầu
        ``eam_tag.py``. Mỗi nhánh dưới đây là một cách sai nếu dùng
        nhầm cho loại đo khác.
        """
        if cach == 'sum':
            return 'sum(value)'
        if cach == 'min':
            return 'min(value)'
        if cach == 'max':
            return 'max(value)'
        if cach == 'last':
            return '(array_agg(value ORDER BY ts DESC))[1]'
        if cach == 'counter_delta':
            # Đồng hồ luỹ kế: hiệu cuối − đầu. Âm nghĩa là đồng hồ đã bị
            # thay hoặc quay vòng; trả NULL chứ KHÔNG trả số âm hay kẹp
            # về 0 — cả hai đều là bịa ra một con số không ai kiểm được.
            return ("CASE WHEN (array_agg(value ORDER BY ts DESC))[1] >= "
                    "          (array_agg(value ORDER BY ts))[1] "
                    "     THEN (array_agg(value ORDER BY ts DESC))[1] - "
                    "          (array_agg(value ORDER BY ts))[1] "
                    "     ELSE NULL END")
        if cach == 'vector_avg':
            # Hướng gió: trung bình VECTƠ. Trung bình số học của 350° và
            # 10° ra 180°, tức ngược hẳn hướng thật.
            return ("mod(degrees(atan2(avg(sin(radians(value))), "
                    "avg(cos(radians(value)))))::numeric + 360, 360)")
        return 'avg(value)'

    @api.model
    def _loc_loai_tru(self, tag_id, tu, den):
        """Mảnh SQL loại bỏ các khoảng không tính vào KPI.

        Nối LÚC ĐỌC chứ không đóng dấu vào từng dòng: khoảng loại trừ
        được ghi SAU (cuối ca, có khi hôm sau), và lý do còn đổi về
        sau nữa. Đóng dấu vào dòng thì mỗi lần ghi sổ phải đi sửa
        hàng chục nghìn bản ghi đã lưu — chậm, khoá bảng, và phá
        chính luật 'không sửa dữ liệu gốc'."""
        khoang = self.env['eam.data.exclusion'].khoang_ap_dung(
            [tag_id], tu, den).get(tag_id) or []
        if not khoang:
            return '', []
        dieu, tham = [], []
        for a, b in khoang:
            dieu.append('(ts >= %s AND ts < %s)')
            tham += [a, b]
        return ' AND NOT (' + ' OR '.join(dieu) + ')', tham

    @api.model
    def doc_gop(self, tag_ids, tu, den, buoc_giay, bo_nghi=False,
                bo_loai_tru=False):
        """Đọc theo khoảng thời gian, gộp theo đúng cách của từng tag.

        ``bo_nghi=True`` thì loại số đo có cờ chất lượng. Mặc định là
        KHÔNG loại: người đọc phải thấy dữ liệu thật trước, rồi mới
        quyết lọc.
        """
        self._dam_bao_bang()
        T = self.env['eam.tag']
        tags = T.browse(tag_ids).exists()
        kq = {}
        that = tags.filtered(lambda t: not t.is_virtual)
        ao = tags - that

        # Có loại trừ thì mỗi tag mang khoảng riêng, không gom chung
        # một câu được nữa — chạy từng tag.
        theo_cach = {}
        for t in that:
            khoa = (t.aggregation, t.id) if bo_loai_tru \
                else (t.aggregation,)
            theo_cach.setdefault(khoa, []).append(t.id)

        cr = self.env.cr
        for khoa, ids in theo_cach.items():
            cach = khoa[0]
            loc_lt, tham_lt = '', []
            if bo_loai_tru:
                loc_lt, tham_lt = self._loc_loai_tru(ids[0], tu, den)
            # Dùng `.format()` nên chỗ cắm tham số phải là `%s` ĐƠN.
            # Viết `%%s` ở đây là sai: `.format()` không đụng tới dấu `%`,
            # nên psycopg2 đọc `%%` thành một dấu `%` thường và câu SQL
            # mất chỗ cắm — lỗi hiện ra là "syntax error at or near %".
            sql = """
                SELECT tag_id,
                       to_timestamp(floor(extract(epoch FROM ts) / %s) * %s)
                           AT TIME ZONE 'UTC' AS buc,
                       {gop} AS gt,
                       count(*) AS n,
                       count(*) FILTER (WHERE quality <> 0) AS n_nghi
                FROM {bang}
                WHERE tag_id = ANY(%s) AND ts >= %s AND ts < %s{loc}{lt}
                GROUP BY 1, 2 ORDER BY 1, 2
            """.format(gop=self._bieu_thuc_gop(cach), bang=BANG,
                       loc=' AND quality = 0' if bo_nghi else '',
                       lt=loc_lt)
            cr.execute(
                sql, [buoc_giay, buoc_giay, ids, tu, den] + tham_lt)
            for tag_id, buc, gt, n, n_nghi in cr.fetchall():
                kq.setdefault(tag_id, []).append({
                    'ts': buc, 'gt': float(gt) if gt is not None else None,
                    'n': n, 'n_nghi': n_nghi,
                })

        for t in ao:
            kq[t.id] = self._tinh_tag_ao(t, tu, den, buoc_giay,
                                         bo_nghi, bo_loai_tru)
        return kq

    # ------------------------------------------------------------------
    @api.model
    def chi_so_chat_luong(self, tag_ids, tu, den):
        """Chỉ số chất lượng dữ liệu theo điểm đo (C07).

        BA con số, và chúng trả lời ba câu khác hẳn nhau:

        * **độ phủ** — có bao nhiêu số đo so với số đáng lẽ phải có
          (suy từ nhịp lấy mẫu đã khai). Thấp nghĩa là MẤT dữ liệu,
          tức vấn đề ở đường truyền hoặc bộ thu thập.
        * **tỷ lệ tốt** — trong số đã có, bao nhiêu phần không mang
          cờ chất lượng. Thấp nghĩa là ĐẦU ĐO có vấn đề.
        * **tỷ lệ loại trừ** — bao nhiêu phần nằm trong khoảng không
          tính KPI. Cao KHÔNG phải vấn đề, nhưng phải biết để đọc
          hai con số kia cho đúng.

        Gộp ba thứ thành một điểm 'chất lượng' duy nhất là mất thông
        tin: mất dữ liệu và đầu đo hỏng cần hai cách xử lý khác
        hẳn nhau, mà một con số gộp thì không phân biệt được."""
        self._dam_bao_bang()
        T = self.env['eam.tag']
        cr = self.env.cr
        ra = []
        giay = max((den - tu).total_seconds(), 1)
        for t in T.browse(tag_ids).exists():
            if t.is_virtual:
                continue
            cr.execute(
                'SELECT count(*), count(*) FILTER (WHERE quality <> 0) '
                'FROM ' + BANG + ' WHERE tag_id = %s AND ts >= %s AND ts < %s',
                (t.id, tu, den))
            n, n_co = cr.fetchone()
            n = n or 0
            n_co = n_co or 0
            mong = giay / max(t.sample_seconds or 60, 1)
            khoang = self.env['eam.data.exclusion'].khoang_ap_dung(
                [t.id], tu, den).get(t.id) or []
            n_lt = 0
            for a, b in khoang:
                cr.execute(
                    'SELECT count(*) FROM ' + BANG + ' WHERE tag_id = %s'
                    ' AND ts >= %s AND ts < %s',
                    (t.id, max(a, tu), min(b, den)))
                n_lt += cr.fetchone()[0]
            ra.append({
                'tag_id': t.id, 'ma': t.code, 'ten': t.name,
                'n': n, 'mong_doi': int(mong),
                'do_phu': round(100.0 * n / mong, 1) if mong else 0.0,
                'n_co': n_co,
                'ty_le_tot': round(100.0 * (n - n_co) / n, 1)
                if n else 0.0,
                'n_loai_tru': n_lt,
                'ty_le_loai_tru': round(100.0 * n_lt / n, 1)
                if n else 0.0,
            })
        return ra

    @api.model
    def _tinh_tag_ao(self, tag, tu, den, buoc_giay, bo_nghi,
                     bo_loai_tru=False):
        """Tính tag ảo theo từng khoảng, từ các tag nó trỏ tới.

        Tính lúc ĐỌC chứ không lưu sẵn: sửa công thức thì mọi biểu đồ cũ
        cũng đổi theo. Đó là điều mong muốn — công thức sai phải sai ở
        mọi chỗ, chứ không để lại số cũ tính bằng công thức cũ mà không
        ai biết là đã khác.
        """
        ma_can = tag._tag_trong_cong_thuc()
        if not ma_can:
            return []
        nguon = self.env['eam.tag'].search([('code', 'in', list(ma_can))])
        if len(nguon) != len(ma_can):
            return []
        du = self.doc_gop(nguon.ids, tu, den, buoc_giay, bo_nghi,
                          bo_loai_tru)
        theo_ma = {t.code: du.get(t.id, []) for t in nguon}

        # Xếp theo khoảng. Khoảng nào THIẾU một tag nguồn thì BỎ, không
        # thay bằng 0: 0 trong mẫu số ra vô cực, 0 trong tử số ra một
        # hiệu suất bằng 0 trông như sự cố thật.
        buc = None
        for ds in theo_ma.values():
            s = {d['ts'] for d in ds}
            buc = s if buc is None else (buc & s)
        if not buc:
            return []

        gt_theo_ma = {m: {d['ts']: d['gt'] for d in ds}
                      for m, ds in theo_ma.items()}
        ra = []
        for b in sorted(buc):
            bien = {m: gt_theo_ma[m].get(b) for m in ma_can}
            if any(v is None for v in bien.values()):
                continue
            try:
                v = safe_eval(tag.formula, {**HAM_AN_TOAN, **bien})
            except ZeroDivisionError:
                continue
            except Exception:
                # Công thức sai thì BÁO một lần rồi dừng, không trả về
                # một đường cong sai.
                _logger.warning(
                    'eam_historian: công thức tag %s không tính được',
                    tag.code)
                return []
            ra.append({'ts': b, 'gt': float(v), 'n': 1, 'n_nghi': 0})
        return ra

    @api.model
    def doc_tho(self, tag_id, tu, den, gioi_han=5000):
        """Số đo THÔ, không gộp — dùng cho xem lại diễn biến (playback)."""
        self._dam_bao_bang()
        self.env.cr.execute("""
            SELECT ts, value, quality FROM %s
            WHERE tag_id = %%s AND ts >= %%s AND ts < %%s
            ORDER BY ts LIMIT %%s
        """ % BANG, (tag_id, tu, den, gioi_han))
        return [{'ts': ts, 'gt': v, 'q': q}
                for ts, v, q in self.env.cr.fetchall()]

    # ------------------------------------------------------------------
    @api.model
    def dung_luong(self):
        """Dung lượng kho và từng phân mảnh — để nói thật về sức chứa."""
        cr = self.env.cr
        cr.execute("SELECT to_regclass(%s)", (BANG,))
        if not cr.fetchone()[0]:
            return {'tong': 0, 'dong': 0, 'manh': []}
        cr.execute("""
            SELECT c.relname,
                   pg_total_relation_size(c.oid),
                   c.reltuples::bigint
            FROM pg_class c
            JOIN pg_inherits i ON i.inhrelid = c.oid
            JOIN pg_class p ON p.oid = i.inhparent
            WHERE p.relname = %s ORDER BY c.relname
        """, (BANG,))
        manh = [{'ten': t, 'bytes': b, 'dong_uoc': n}
                for t, b, n in cr.fetchall()]
        cr.execute("SELECT pg_total_relation_size(%s)", (BANG,))
        cr.execute("SELECT count(*) FROM %s" % BANG)
        dong = cr.fetchone()[0]
        return {'tong': sum(m['bytes'] for m in manh), 'dong': dong,
                'manh': manh}
