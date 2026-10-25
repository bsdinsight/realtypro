# -*- coding: utf-8 -*-
"""Hạch toán tổn thất một ngày: từ KỲ VỌNG xuống THỰC TẾ.

Phần dư không được phân bổ ngầm
--------------------------------
Biểu đồ thác nước cộng khít từ kỳ vọng xuống thực tế trông rất thuyết
phục, và đó chính là vấn đề: nó chỉ khít khi ai đó đã chia phần dư vào
các cột. Ở đây phần dư đứng riêng, có tên, và lớn thì tờ giấy nói ra.

Hai mốc kỳ vọng, không phải một
--------------------------------
Mốc KẾ HOẠCH (P50) là cam kết tài chính; chênh với thực tế gồm cả phần
trời: năm nay gió yếu hơn năm P50 thì sản lượng thấp mà chẳng ai làm gì
sai. Mốc TÀI NGUYÊN — đường cong công suất nhân gió ĐO ĐƯỢC — mới là
mốc vận hành chịu trách nhiệm. Gộp hai mốc làm một là đổ cho vận hành
phần trời không cho.
"""
import logging
from datetime import datetime, time, timedelta

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class EamLossDay(models.Model):
    _name = 'eam.loss.day'
    _description = 'Hạch toán tổn thất theo ngày'
    _order = 'date desc, plant_id'
    _rec_name = 'display_name'

    plant_id = fields.Many2one(
        'eam.location', string='Nhà máy', required=True, index=True,
        domain="[('location_type', '=', 'plant')]", ondelete='cascade')
    date = fields.Date(string='Ngày', required=True, index=True)
    company_id = fields.Many2one(related='plant_id.company_id', store=True)
    currency_id = fields.Many2one(related='company_id.currency_id')

    # ----- Ba mốc -------------------------------------------------------
    muc_ke_hoach = fields.Float(
        string='Mốc kế hoạch P50 (kWh)', digits=(16, 1), readonly=True,
        help='Mục tiêu tháng chia đều theo ngày. Là cam kết TÀI CHÍNH, '
             'không phải dự báo của ngày hôm đó.')
    do_duoc_kh = fields.Boolean(string='Có mốc kế hoạch', readonly=True)
    ly_do_kh = fields.Char(string='Vì sao chưa có mốc kế hoạch',
                           readonly=True)

    muc_tai_nguyen = fields.Float(
        string='Mốc tài nguyên (kWh)', digits=(16, 1), readonly=True,
        help='Đường cong công suất nhân tốc độ gió ĐO ĐƯỢC tại từng tổ '
             'máy. Đây mới là mốc vận hành chịu trách nhiệm.')
    do_duoc_tn = fields.Boolean(string='Có mốc tài nguyên', readonly=True)
    ly_do_tn = fields.Char(string='Vì sao chưa có mốc tài nguyên',
                           readonly=True)

    thuc_te = fields.Float(string='Thực tế (kWh)', digits=(16, 1),
                           readonly=True)

    # ----- Phân rã ------------------------------------------------------
    line_ids = fields.One2many('eam.loss.day.line', 'day_id',
                               string='Phân rã')
    tong_mat = fields.Float(string='Tổng đã quy được (kWh)', digits=(16, 1),
                            compute='_compute_tong', store=True)
    tong_tu_dung = fields.Float(string='Tiêu thụ có chủ đích (kWh)',
                                digits=(16, 1), compute='_compute_tong',
                                store=True)
    du = fields.Float(
        string='Phần dư chưa quy được (kWh)', digits=(16, 1),
        compute='_compute_tong', store=True,
        help='Mốc tài nguyên trừ thực tế trừ tổng đã quy được. KHÔNG '
             'phân bổ vào các cột để biểu đồ cộng khít — phần dư lớn là '
             'thông tin, không phải lỗi trình bày.')
    du_pct = fields.Float(string='Phần dư (%)', digits=(6, 2),
                          compute='_compute_tong', store=True)
    du_dang_ke = fields.Boolean(
        string='Phần dư đáng xem', compute='_compute_tong', store=True,
        help='Phần trăm của một con số bé là nhiễu, không phải tín hiệu: '
             'ngày lặng gió chỉ phát 11 MWh thì lệch 3 MWh đã ra 30%, mà '
             '3 MWh ấy chẳng nói gì về vận hành. Chỉ coi là đáng xem khi '
             'phần dư vượt 5% VÀ mốc tài nguyên đạt ít nhất 10% khả năng '
             'phát cả ngày của nhà máy.')
    chenh_tai_nguyen = fields.Float(
        string='Chênh do tài nguyên (kWh)', digits=(16, 1),
        compute='_compute_tong', store=True,
        help='Mốc kế hoạch trừ mốc tài nguyên. Dương nghĩa là trời cho '
             'ít hơn năm P50 — không ai làm gì sai.')

    thac_nuoc = fields.Html(string='Biểu đồ thác nước',
                            compute='_compute_thac', sanitize=False)
    display_name = fields.Char(compute='_compute_display_name')

    _uniq = models.Constraint('UNIQUE(plant_id, date)',
                              'Mỗi nhà máy mỗi ngày chỉ một bản hạch toán.')

    @api.depends('plant_id', 'date')
    def _compute_display_name(self):
        for r in self:
            r.display_name = '%s — %s' % (r.plant_id.name or '', r.date or '')

    @api.depends('line_ids.kwh', 'line_ids.do_duoc',
                 'line_ids.loss_type_id.la_tu_dung',
                 'muc_tai_nguyen', 'muc_ke_hoach', 'thuc_te')
    def _compute_tong(self):
        for r in self:
            co = r.line_ids.filtered('do_duoc')
            tu_dung = co.filtered(lambda l: l.loss_type_id.la_tu_dung)
            r.tong_tu_dung = sum(tu_dung.mapped('kwh'))
            r.tong_mat = sum((co - tu_dung).mapped('kwh'))
            # Phần dư đo từ mốc TÀI NGUYÊN, không từ mốc kế hoạch: chênh
            # với kế hoạch gồm cả phần trời, mà trời thì không phải tổn
            # thất của ai.
            if r.do_duoc_tn:
                r.du = (r.muc_tai_nguyen - r.thuc_te
                        - r.tong_mat - r.tong_tu_dung)
                r.du_pct = (100.0 * r.du / r.muc_tai_nguyen
                            if r.muc_tai_nguyen else 0.0)
            else:
                r.du = 0.0
                r.du_pct = 0.0
            r.chenh_tai_nguyen = ((r.muc_ke_hoach - r.muc_tai_nguyen)
                                  if (r.do_duoc_kh and r.do_duoc_tn) else 0.0)
            kha_nang = (r.plant_id.rated_power_mw or 0.0) * 1000.0 * 24.0
            r.du_dang_ke = bool(
                abs(r.du_pct) > 5.0 and kha_nang
                and r.muc_tai_nguyen > kha_nang * 0.10)

    # ==================================================================
    @api.model
    def _bien_ngay(self, plant, ngay):
        mui = pytz.timezone(plant.mui_gio())
        dau = mui.localize(datetime.combine(ngay, time.min))
        return (dau.astimezone(pytz.UTC).replace(tzinfo=None),
                (dau + timedelta(days=1)).astimezone(pytz.UTC)
                .replace(tzinfo=None))

    @api.model
    def dung_ngay(self, plant, ngay):
        """Dựng hoặc cập nhật bản hạch toán của một ngày."""
        tu, den = self._bien_ngay(plant, ngay)
        v = {'plant_id': plant.id, 'date': ngay}
        v.update(self._moc_ke_hoach(plant, ngay))
        v.update(self._moc_tai_nguyen(plant, tu, den, ngay))
        v['thuc_te'] = self._thuc_te(plant, ngay)

        r = self.search([('plant_id', '=', plant.id),
                         ('date', '=', ngay)], limit=1)
        if r:
            r.write(v)
        else:
            r = self.create(v)
        r._dung_dong(tu, den)
        return r

    @api.model
    def _moc_ke_hoach(self, plant, ngay):
        lk = self.env['eam.energy.target'].luy_ke_den(plant, ngay)
        if not lk.get('do_duoc'):
            return {'muc_ke_hoach': 0.0, 'do_duoc_kh': False,
                    'ly_do_kh': lk.get('ly_do') or _('chưa khai mục tiêu')}
        import calendar
        n = calendar.monthrange(ngay.year, ngay.month)[1]
        return {'muc_ke_hoach': lk['ca_thang']['p50'] / n,
                'do_duoc_kh': True, 'ly_do_kh': False}

    @api.model
    def _moc_tai_nguyen(self, plant, tu, den, ngay=None):
        """Đường cong công suất nhân gió ĐO ĐƯỢC tại từng tổ máy.

        Chỉ tính cho tổ máy ĐÃ GẮN đường cong và CÓ điểm đo gió của
        chính nó. Mượn gió của trạm khí tượng cho mọi tua-bin là bỏ qua
        chính thứ đang muốn đo: trụ đứng chỗ gió kém thì lẽ ra kỳ vọng
        của nó cũng thấp hơn.
        """
        L = self.env['eam.location']
        T = self.env['eam.tag']
        ds = L.search([('id', 'child_of', plant.id),
                       ('la_to_may', '=', True)])
        co = ds.filtered('power_curve_id')
        if not co:
            # ĐIỆN MẶT TRỜI không có đường cong công suất, nhưng có thứ
            # tương đương và đã tính sẵn: MẪU SỐ TỶ SỐ HIỆU SUẤT. Nó
            # chính là "lẽ ra phát bao nhiêu với bức xạ hôm nay".
            pv = self._moc_tai_nguyen_pv(plant, ngay)
            if pv:
                return pv
            return {'muc_tai_nguyen': 0.0, 'do_duoc_tn': False,
                    'ly_do_tn': _(
                        'chưa tổ máy nào gắn đường cong công suất — không '
                        'suy được "lẽ ra phát bao nhiêu với gió hôm nay"')}
        tong = 0.0
        thieu = []
        # Đường cong trả None ngoài dải đã công bố — CỐ Ý, vì kéo dài nó
        # ra ngoài là bịa một cam kết nhà chế tạo chưa từng đưa.
        #
        # DƯỚI dải là gió chưa tới tốc độ khởi động: tua-bin đứng yên,
        # kỳ vọng bằng 0 và đó là sự thật vật lý, không phải giả định.
        #
        # TRÊN dải thì khác: có thể máy đã cắt vì gió bão (kỳ vọng 0), mà
        # cũng có thể đường cong chỉ khai tới đó. Hai chuyện ấy không
        # phân biệt được từ đây, nên ĐẾM RIÊNG và nói ra, thay vì chọn
        # bừa một trong hai.
        n_tren = n_moc = 0
        for vt in co:
            ws = T.search([('location_id', '=', vt.id),
                           ('tag_type', '=', 'wind_speed')], limit=1)
            if not ws:
                thieu.append(vt.code or str(vt.id))
                continue
            self.env.cr.execute(
                'SELECT value FROM eam_tag_reading '
                'WHERE tag_id = %s AND ts >= %s AND ts < %s ORDER BY ts',
                (ws.id, tu, den))
            moc = [float(x[0] or 0) for x in self.env.cr.fetchall()]
            if not moc:
                thieu.append(vt.code or str(vt.id))
                continue
            gio_moi_moc = (ws.sample_seconds or 600) / 3600.0
            dc = vt.power_curve_id
            v_max = max(dc.point_ids.mapped('wind_speed') or [0.0])
            for v in moc:
                n_moc += 1
                kw = dc.tra_cong_suat(v)
                if kw is None:
                    if v > v_max:
                        n_tren += 1
                    # dưới dải: đứng yên, cộng 0
                    continue
                tong += kw * gio_moi_moc
        if not tong:
            return {'muc_tai_nguyen': 0.0, 'do_duoc_tn': False,
                    'ly_do_tn': _('không tổ máy nào có số đo gió trong ngày')}
        vet = []
        if thieu:
            vet.append(_('%(n)d/%(t)d tổ máy thiếu số đo gió: %(d)s',
                         n=len(thieu), t=len(co), d=', '.join(thieu[:6])))
        if n_tren:
            vet.append(_(
                '%(n)d/%(t)d mốc đo có gió VƯỢT dải đường cong — không '
                'biết là máy đã cắt vì bão hay đường cong chỉ khai tới '
                'đó, nên không cộng vào mốc; mốc tài nguyên đang THẤP '
                'hơn thật đúng phần ấy', n=n_tren, t=n_moc))
        return {'muc_tai_nguyen': tong, 'do_duoc_tn': True,
                'ly_do_tn': ' · '.join(vet) if vet else False}

    @api.model
    def _moc_tai_nguyen_pv(self, plant, ngay):
        """Mốc tài nguyên của điện mặt trời — ở điều kiện CHUẨN.

        Bức xạ nhân diện tích nhân hiệu suất tấm pin: tấm pin lẽ ra làm
        ra bấy nhiêu nếu nhiệt độ đúng mốc chuẩn. CỐ Ý chưa nhân hệ số
        hiệu chỉnh nhiệt — phần hụt do tấm nóng là một LOẠI TỔN THẤT có
        tên, phải hiện thành cột riêng trên thác nước. Lấy thẳng mẫu số
        tỷ số hiệu suất (đã nhân hệ số nhiệt) làm mốc thì tổn thất nhiệt
        biến mất khỏi tờ giấy mà tổng vẫn khít.
        """
        if not ngay or 'eam.solar.kpi' not in self.env:
            return None
        k = self.env['eam.solar.kpi'].search(
            [('plant_id', '=', plant.id), ('date', '=', ngay)], limit=1)
        if not k:
            return None
        if not (k.e_nominal and k.module_eff):
            return {'muc_tai_nguyen': 0.0, 'do_duoc_tn': False,
                    'ly_do_tn': _(
                        'hiệu suất ngày %s chưa có điện năng danh định '
                        'hoặc hiệu suất mô-đun', ngay)}
        return {'muc_tai_nguyen': k.e_nominal * k.module_eff / 100.0,
                'do_duoc_tn': True,
                'ly_do_tn': _(
                    'bức xạ × diện tích × hiệu suất mô-đun, ở điều kiện '
                    'chuẩn — phần hụt do nhiệt hiện thành cột riêng')}

    @api.model
    def _thuc_te(self, plant, ngay):
        ds = self.env['eam.unit.day'].search(
            [('plant_id', '=', plant.id), ('date', '=', ngay),
             ('do_duoc_sl', '=', True)])
        return sum(ds.mapped('san_luong'))

    def _dung_dong(self, tu, den):
        """Một dòng cho mỗi loại tổn thất đã khai."""
        self.ensure_one()
        T = self.env['eam.loss.type']
        L = self.env['eam.loss.day.line']
        theo = None
        L.search([('day_id', '=', self.id)]).unlink()
        tao = []
        for lt in T.search([('company_id', '=', self.company_id.id)]):
            kwh, tien, nguon, ly_do = 0.0, 0.0, '', ''
            if lt.cach_do == 'dung_may':
                if theo is None:
                    theo = self.plant_id.gio_theo_nhom(tu, den)
                d = theo.get(lt.group_id.name)
                if d is None:
                    # Không có khoảng dừng nhóm này là sự thật ĐO ĐƯỢC,
                    # bằng không chứ không phải thiếu số.
                    nguon = _('không có khoảng dừng nhóm "%s" trong ngày',
                              lt.group_id.name)
                else:
                    kwh = d['kwh']
                    tien = 0.0 if d.get('chua_tien') else d['tien']
                    nguon = _('%(n)d khoảng dừng · %(g).2f giờ-máy',
                              n=d['so'], g=d['gio'])
            elif lt.cach_do == 'bac_do':
                nut = self.env['eam.chain.node'].search(
                    [('plant_id', '=', self.plant_id.id),
                     ('code', '=', lt.node_code)], limit=1)
                if not nut:
                    # Nhà máy KHÔNG CÓ bậc ấy khác hẳn "có mà chưa đo
                    # được": điện mặt trời không có máy biến áp nâng của
                    # trại gió, và ngược lại. Bỏ hẳn dòng thay vì ghi
                    # "chưa đo được" — danh sách chưa-đo-được là thứ đem
                    # ra bàn lắp thêm đo, đừng độn vào đó những thứ nhà
                    # máy này vĩnh viễn không có.
                    continue
                else:
                    r = self.env['eam.chain.day'].search(
                        [('node_id', '=', nut.id),
                         ('date', '=', self.date)], limit=1)
                    if not r:
                        ly_do = _('bậc "%s" chưa có dòng ngày', lt.node_code)
                    else:
                        # Bậc TIÊU THỤ lấy chính sản lượng của bậc; bậc
                        # sản lượng lấy phần HAO so với bậc trước.
                        kwh = (r.energy if nut.node_type in
                               ('tu_dung', 'ban_dem') else r.loss_kwh)
                        nguon = _('bậc %(m)s · %(t)s', m=lt.node_code,
                                  t=dict(nut._fields['node_type'].selection
                                         ).get(nut.node_type, ''))
            elif lt.cach_do == 'nhiet':
                kwh, nguon, ly_do = self._mat_do_nhiet()
            elif lt.cach_do == 'clipping':
                kwh, nguon, ly_do = self._mat_do_clipping(tu, den)
            else:
                ly_do = _('loại này do người nhập tay')
            tao.append({
                'day_id': self.id, 'loss_type_id': lt.id,
                'kwh': kwh, 'tien': tien, 'nguon': nguon,
                'do_duoc': not ly_do, 'ly_do': ly_do or False,
            })
        if tao:
            L.create(tao)

    # ==================================================================
    def _mat_do_nhiet(self):
        """Phần hụt vì tấm pin nóng hơn điều kiện chuẩn.

        Hệ số hiệu chỉnh nhiệt đã được tính sẵn ở bảng hiệu suất ngày.
        Lấy lại nó chứ không tính lần hai: hệ số ấy dựng trên nhiệt độ
        tham chiếu của HỢP ĐỒNG, mà hợp đồng có thể chốt mốc khác 25 °C
        — tính lại ở đây là hai nơi dùng hai mốc cho cùng một ngày.
        """
        self.ensure_one()
        if 'eam.solar.kpi' not in self.env:
            return 0.0, '', _('hệ chưa có bảng hiệu suất điện mặt trời')
        k = self.env['eam.solar.kpi'].search(
            [('plant_id', '=', self.plant_id.id),
             ('date', '=', self.date)], limit=1)
        if not k:
            return 0.0, '', _('ngày này chưa có dòng hiệu suất')
        if not k.ft:
            return 0.0, '', _(
                'chưa có hệ số hiệu chỉnh nhiệt — thiếu nhiệt độ mô-đun '
                'hoặc hệ số nhiệt của tấm pin')
        chuan = k.e_nominal * k.module_eff / 100.0
        return (chuan * (1.0 - k.ft),
                _('(1 − Ft) × mốc chuẩn · Ft = %(f).4f, mốc tham chiếu '
                  '%(t).1f °C, mô-đun %(m).1f °C',
                  f=k.ft, t=k.temp_ref, m=k.temp_module), '')

    def _mat_do_clipping(self, tu, den):
        """Cắt đỉnh: công suất một chiều vượt trần của bộ nghịch lưu.

        Chỉ đếm những mốc đo mà bộ nghịch lưu ĐANG CHẠM TRẦN. Lấy mọi
        lúc DC lớn hơn AC làm clipping là đếm luôn tổn hao biến đổi —
        khoản ấy đã có cột riêng, cộng hai lần thì thác nước vẫn khít mà
        sai cả hai cột.
        """
        self.ensure_one()
        T = self.env['eam.tag']
        U = self.env['eam.unit.day']
        ds = U.search([('plant_id', '=', self.plant_id.id),
                       ('date', '=', self.date), ('do_duoc_dc', '=', True)])
        if not ds:
            return 0.0, '', _(
                'không tổ máy nào có số phía một chiều — không biết DC có '
                'vượt trần AC hay không')
        tong, n_may = 0.0, 0
        for d in ds:
            cs = d.cong_suat_kw
            if not cs or not d.hieu_suat_bd:
                continue
            ac = T.search([('location_id', '=', d.location_id.id),
                           ('tag_type', '=', 'power')], limit=1)
            dc = T.search([('location_id', '=', d.location_id.id),
                           ('tag_type', '=', 'dc_power')], limit=1)
            if not (ac and dc):
                continue
            eta = d.hieu_suat_bd / 100.0
            nhip = (ac.sample_seconds or 600) / 3600.0
            self.env.cr.execute("""
                SELECT a.value, b.value
                  FROM eam_tag_reading a JOIN eam_tag_reading b
                    ON b.tag_id = %s AND b.ts = a.ts
                 WHERE a.tag_id = %s AND a.ts >= %s AND a.ts < %s
                   AND a.value >= %s
            """, (dc.id, ac.id, tu, den, cs * 0.98))
            co = False
            for p_ac, p_dc in self.env.cr.fetchall():
                du = float(p_dc or 0) * eta - float(p_ac or 0)
                if du > 0:
                    tong += du * nhip
                    co = True
            if co:
                n_may += 1
        if not tong:
            return 0.0, _(
                '%d tổ máy có số hai phía, không mốc nào chạm trần',
                len(ds)), ''
        return tong, _('%(n)d/%(t)d tổ máy có lúc chạm trần',
                       n=n_may, t=len(ds)), ''

    # ==================================================================
    def action_dung_lai(self):
        for r in self:
            self.dung_ngay(r.plant_id, r.date)
        return True

    @api.model
    def _cron_hom_qua(self):
        hom_qua = fields.Date.context_today(self) - timedelta(days=1)
        for nm in self.env['eam.location'].search(
                [('location_type', '=', 'plant')]):
            try:
                self.dung_ngay(nm, hom_qua)
            except Exception:                        # noqa: BLE001
                _logger.exception('eam_loss: %s ngày %s', nm.code, hom_qua)

    # ==================================================================
    @api.depends('line_ids.kwh', 'muc_tai_nguyen', 'thuc_te', 'du')
    def _compute_thac(self):
        """Thác nước vẽ bằng SVG, và nói thẳng khi mốc chưa có."""
        for r in self:
            if not r.do_duoc_tn:
                r.thac_nuoc = (
                    '<p class="text-muted">Chưa vẽ được thác nước: %s.</p>'
                    % (r.ly_do_tn or ''))
                continue
            cot = [('Mốc tài nguyên', r.muc_tai_nguyen, '#1F3864')]
            for l in r.line_ids.filtered(
                    lambda x: x.do_duoc and x.kwh).sorted(
                        lambda x: (x.loss_type_id.sequence,
                                   x.loss_type_id.code)):
                cot.append((l.loss_type_id.name, -l.kwh,
                            '#999999' if l.loss_type_id.la_tu_dung
                            else '#C0392B'))
            if abs(r.du) > 0.01:
                cot.append((_('Chưa quy được'), -r.du, '#E3A008'))
            cot.append((_('Thực tế'), None, '#1a9850'))
            r.thac_nuoc = r._ve_thac(cot)

    def _ve_thac(self, cot):
        """Vẽ thác nước, kể cả khi một bước làm TĂNG thay vì giảm.

        Phần dư ÂM nghĩa là thực tế cộng tổn thất đã quy còn VƯỢT mốc
        tài nguyên — máy phát nhiều hơn đường cong cam kết cho mức gió
        đo được. Vẽ nó thành vạch mảnh sát đáy là giấu mất đúng cái
        thông tin ấy; nó phải là một cột đi LÊN, màu khác, nhìn ra ngay.
        """
        self.ensure_one()
        W, H, PAD = 980, 250, 26
        n = len(cot)
        w = (W - 2 * PAD) / max(n, 1)
        dinh = max(self.muc_tai_nguyen, self.thuc_te, 1.0)
        y0, cao = H - 40, H - 74

        def y(v):
            return y0 - cao * v / dinh

        ra = ['<svg width="100%%" viewBox="0 0 %d %d" '
              'xmlns="http://www.w3.org/2000/svg" '
              'style="font-family:sans-serif">' % (W, H)]
        ra.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#bbb"/>'
                  % (PAD, y0, W - PAD, y0))
        moc = 0.0
        for i, (ten, gt, mau) in enumerate(cot):
            x = PAD + w * i + w * 0.15
            bw = w * 0.70
            if i == 0:
                moc = gt
                a, b, nhan = 0.0, gt, gt
            elif gt is None:                      # cột cuối: thực tế
                a, b, nhan = 0.0, self.thuc_te, self.thuc_te
            else:
                a, b = moc, moc + gt
                moc = b
                nhan = gt
            tren, duoi = max(a, b), min(a, b)
            cao_cot = max(cao * (tren - duoi) / dinh, 1.0)
            # Bước đi LÊN tô màu khác và viền nét đứt: nó không phải
            # tổn thất, nó là phần mô hình đoán thấp hơn thực tế.
            len_ = (gt is not None and i and gt > 0)
            ra.append('<rect x="%f" y="%f" width="%f" height="%f" fill="%s"%s/>'
                      % (x, y(tren), bw, cao_cot,
                         '#2E86C1' if len_ else mau,
                         ' stroke="#1B4F72" stroke-dasharray="2,1"'
                         if len_ else ''))
            ra.append('<text x="%f" y="%f" font-size="8" fill="#333" '
                      'text-anchor="middle">%s</text>'
                      % (x + bw / 2, y(tren) - 3, '{:,.0f}'.format(nhan)))
            # Nối hai cột bằng nét mảnh để mắt theo được bậc thang.
            if 0 < i < n - 1:
                ra.append('<line x1="%f" y1="%f" x2="%f" y2="%f" '
                          'stroke="#ccc" stroke-dasharray="2,2"/>'
                          % (x + bw, y(b), x + w, y(b)))
            for d, t in enumerate(self._cat_chu(ten, 18)):
                ra.append('<text x="%f" y="%f" font-size="7" fill="#666" '
                          'text-anchor="middle">%s</text>'
                          % (x + bw / 2, y0 + 10 + d * 8, t))
        ra.append('</svg>')
        return ''.join(ra)

    @staticmethod
    def _cat_chu(s, n):
        """Cắt nhãn thành dòng ngắn — nhãn dài đè lên nhau thì không
        đọc được cột nào là cột nào."""
        tu, dong, hien = (s or '').split(), [], ''
        for t in tu:
            if len(hien) + len(t) + 1 > n:
                dong.append(hien)
                hien = t
            else:
                hien = (hien + ' ' + t).strip()
        if hien:
            dong.append(hien)
        return dong[:3]


class EamLossDayLine(models.Model):
    _name = 'eam.loss.day.line'
    _description = 'Dòng phân rã tổn thất'
    _order = 'day_id, sequence, id'

    day_id = fields.Many2one('eam.loss.day', required=True,
                             ondelete='cascade', index=True)
    loss_type_id = fields.Many2one('eam.loss.type', string='Loại tổn thất',
                                   required=True, ondelete='restrict')
    sequence = fields.Integer(related='loss_type_id.sequence', store=True)
    nhom = fields.Selection(related='loss_type_id.nhom', store=True)
    plant_id = fields.Many2one(related='day_id.plant_id', store=True)
    date = fields.Date(related='day_id.date', store=True)
    company_id = fields.Many2one(related='day_id.company_id', store=True)
    currency_id = fields.Many2one(related='day_id.currency_id')

    kwh = fields.Float(string='kWh', digits=(16, 1))
    tien = fields.Monetary(string='Doanh thu mất',
                           currency_field='currency_id')
    ty_le = fields.Float(string='% của mốc', digits=(6, 3),
                         compute='_compute_ty_le', store=True)
    do_duoc = fields.Boolean(string='Quy được', default=True)
    ly_do = fields.Char(string='Vì sao chưa quy được', readonly=True)
    nguon = fields.Char(string='Lấy từ đâu', readonly=True)

    @api.depends('kwh', 'day_id.muc_tai_nguyen')
    def _compute_ty_le(self):
        for r in self:
            m = r.day_id.muc_tai_nguyen
            r.ty_le = (100.0 * r.kwh / m) if m else 0.0
