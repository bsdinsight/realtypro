# -*- coding: utf-8 -*-
"""Luật cảnh báo: cái gì xảy ra thì coi là bất thường, và rồi làm gì.

Vì sao sổ cảnh báo KHÔNG gắn vào một hệ giám sát cụ thể
--------------------------------------------------------
Hôm nay chưa có bộ kết nối SCADA/OPC. Hàn sổ cảnh báo vào một driver
chưa tồn tại thì cả chuỗi "bất thường → lệnh công việc" phải chờ driver,
mà driver thì chờ dự án. Nên sổ này **bất khả tri về nguồn**: nó nhận
cảnh báo từ đồng hồ đang có, từ người trực, và từ hệ ngoài đẩy vào qua
API. Khi SCADA về, nó chỉ là thêm một nguồn nữa, không phải viết lại.

Ba nguồn tự động, và chỗ hay bị lẫn
-----------------------------------
``meter_threshold`` — số đồng hồ vượt ngưỡng. Dùng cho đồng hồ *trạng
thái* (độ rung, nhiệt độ dầu), không phải cho giờ chạy: bảo trì theo giờ
chạy đã có kế hoạch bảo trì phòng ngừa lo, đặt thêm luật cảnh báo lên đó
là hai cơ chế cùng sinh lệnh cho một việc.

``meter_stall`` và ``feed_silent`` **khác nhau, và lẫn hai cái này là
lỗi kinh điển**:

* ``feed_silent`` — *không có số đọc mới* trong N ngày. Đường truyền
  chết, không phải máy chết. Việc phải làm là gọi người IT.
* ``meter_stall`` — số đọc *vẫn về đều* nhưng giờ chạy **không tăng**.
  Máy đứng im thật. Việc phải làm là ra hiện trường.

Hệ nào gộp hai cái thành một "mất tín hiệu" thì đội vận hành sẽ chạy
nhầm hướng: cử người leo trụ vì tưởng máy dừng, trong khi chỉ đứt cáp
mạng — hoặc tệ hơn, bỏ qua một trụ đứng im cả tuần vì số đọc vẫn về
đều đặn.

Vì sao mặc định KHÔNG tạo lệnh ngay
-----------------------------------
Một đầu đo rung bị nhiễu có thể nổ 500 cảnh báo một đêm. Tạo lệnh ngay
thì sáng ra danh sách lệnh công việc có 500 dòng rác — và cái hỏng thật
đã ở đó rồi vẫn không ai thấy. Thất bại nguy hiểm của tự động hoá ở đây
không phải *bỏ sót một cảnh báo*, mà là **làm cho danh sách lệnh mất
giá trị**, sau đó thì bỏ sót tất cả.

Nên mặc định là ``on_ack``: người trực xác nhận rồi mới có lệnh. Riêng
mức ``critical`` thì tạo ngay, vì ở đó chờ xác nhận đắt hơn chịu rác.
"""
import logging

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

NGUON = [
    ('meter_threshold', 'Ngưỡng đồng hồ'),
    ('meter_stall', 'Đồng hồ đứng im'),
    ('feed_silent', 'Mất số đọc'),
    ('external', 'Hệ ngoài đẩy vào'),
    ('manual', 'Người trực báo'),
]
NGUON_TU_DONG = ('meter_threshold', 'meter_stall', 'feed_silent')

MUC = [
    ('low', 'Thấp'),
    ('medium', 'Trung bình'),
    ('high', 'Cao'),
    ('critical', 'Nghiêm trọng'),
]
THU_TU_MUC = {'low': 0, 'medium': 1, 'high': 2, 'critical': 3}


class EamAlarmRule(models.Model):
    _name = 'eam.alarm.rule'
    _description = 'Luật cảnh báo thiết bị'
    _inherit = ['mail.thread']
    _order = 'sequence, code'

    name = fields.Char(string='Tên luật', required=True, tracking=True)
    code = fields.Char(string='Mã', required=True, index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True, tracking=True)
    note = fields.Text(string='Diễn giải')

    source = fields.Selection(
        NGUON, string='Nguồn cảnh báo', required=True,
        default='meter_threshold', tracking=True)
    severity = fields.Selection(
        MUC, string='Mức nghiêm trọng', required=True, default='medium',
        tracking=True)

    # ------------------------------------------------------------------
    # Áp cho đâu — cùng cách khoanh phạm vi với kế hoạch bảo trì
    # ------------------------------------------------------------------
    plant_id = fields.Many2one(
        'eam.location', string='Giới hạn trong nhà máy',
        domain="[('location_type', '=', 'plant')]", index=True,
        help='Để trống thì áp cho mọi nhà máy. Ngưỡng độ rung của tua-bin '
             '2 MW không dùng được cho tua-bin 4 MW, nên gần như luôn phải '
             'khoanh lại.')
    category_id = fields.Many2one(
        'eam.asset.category', string='Áp cho loại cấu phần',
        ondelete='restrict', index=True)
    location_ids = fields.Many2many(
        'eam.location', string='Vị trí khai đích danh',
        domain="[('location_type', 'in', ('position', 'plant'))]")

    # ------------------------------------------------------------------
    # Điều kiện
    # ------------------------------------------------------------------
    meter_type = fields.Selection(
        [('operating_hours', 'Giờ máy chạy'),
         ('production_mwh', 'Sản lượng luỹ kế (MWh)'),
         ('starts', 'Số lần khởi động'),
         ('other', 'Khác')],
        string='Loại đồng hồ', default='other',
        help='Ngưỡng nên đặt trên đồng hồ TRẠNG THÁI (độ rung, nhiệt độ '
             'dầu). Đặt lên giờ máy chạy là trùng việc với kế hoạch bảo '
             'trì phòng ngừa, và rồi hai cơ chế cùng sinh lệnh cho một '
             'việc.')
    operator = fields.Selection(
        [('gt', 'Vượt quá'), ('lt', 'Thấp hơn')],
        string='So sánh', default='gt')
    threshold = fields.Float(string='Ngưỡng', digits=(16, 4))
    window_days = fields.Integer(
        string='Trong vòng … ngày', default=3,
        help='Dùng cho "đồng hồ đứng im" và "mất số đọc". Đặt ngắn hơn '
             'nhịp gửi số đọc thì luật nổ liên tục — nhịp ngày thì đừng '
             'đặt 1.')

    # ------------------------------------------------------------------
    # Sinh lệnh
    # ------------------------------------------------------------------
    auto_wo = fields.Selection(
        [('off', 'Không tạo lệnh'),
         ('on_ack', 'Tạo sau khi người trực xác nhận'),
         ('immediate', 'Tạo ngay')],
        string='Tự tạo lệnh công việc', required=True, default='on_ack',
        tracking=True,
        help='"Tạo ngay" chỉ nên dùng cho mức nghiêm trọng. Một đầu đo bị '
             'nhiễu nổ 500 cảnh báo một đêm sẽ thành 500 lệnh rác, và sau '
             'đó không ai đọc danh sách lệnh nữa.')
    wo_work_type = fields.Selection(
        [('corrective', 'Sửa chữa khắc phục'),
         ('predictive', 'Bảo trì theo trạng thái'),
         ('inspection', 'Kiểm tra, xem xét'),
         ('other', 'Khác')],
        string='Loại lệnh sẽ tạo', default='inspection', required=True,
        help='Mặc định là KIỂM TRA, không phải sửa chữa: cảnh báo nói có '
             'dấu hiệu bất thường, chưa nói hỏng cái gì. Mở thẳng lệnh '
             'sửa chữa là đã kết luận trước khi ra xem.')
    wo_priority = fields.Selection(
        [('0', 'Thấp'), ('1', 'Bình thường'),
         ('2', 'Cao'), ('3', 'Khẩn cấp')],
        string='Ưu tiên lệnh', default='2', required=True)
    wo_detection = fields.Selection(
        [('scada', 'Báo động từ hệ giám sát'),
         ('condition', 'Giám sát trạng thái, đo rung'),
         ('operator', 'Người vận hành phát hiện'),
         ('production', 'Phát hiện qua sụt sản lượng'),
         ('other', 'Cách khác')],
        string='Ghi "phát hiện bằng"', default='condition', required=True,
        help='Đóng vào lệnh để chỉ số "bao nhiêu phần trăm hỏng hóc được '
             'bắt trước khi mất sản lượng" có số liệu. Không đóng thì cột '
             'đó mãi trống và giám sát trạng thái không chứng minh được là '
             'đáng tiền.')
    pm_plan_id = fields.Many2one(
        'eam.pm.plan', string='Lấy các bước từ kế hoạch',
        help='Chép bước công việc của kế hoạch này sang lệnh. Để trống thì '
             'lệnh chỉ có mô tả — người ra hiện trường phải tự nghĩ làm gì.')
    wo_requires_permit = fields.Boolean(string='Lệnh cần phiếu công tác')
    wo_requires_isolation = fields.Boolean(string='Lệnh phải cắt điện')
    wo_work_at_height = fields.Boolean(string='Lệnh làm trên cao')

    clear_on_wo_done = fields.Boolean(
        string='Lệnh xong thì xoá cảnh báo', default=True,
        help='Bỏ tích khi cảnh báo phải tự tắt bằng số đo trở lại bình '
             'thường — sửa xong mà độ rung vẫn cao thì chưa sửa được.')
    repeat_window_days = fields.Integer(
        string='Coi là TÁI PHÁT nếu quay lại trong … ngày', default=30,
        help='Cảnh báo quay lại ngay sau khi vừa đóng lệnh nghĩa là lần '
             'sửa đó không giữ được. Đây là con số đáng xem nhất của cả '
             'sổ cảnh báo.')

    alarm_ids = fields.One2many('eam.alarm', 'rule_id', string='Cảnh báo')
    alarm_count = fields.Integer(string='Tổng cảnh báo',
                                 compute='_compute_counts')
    open_count = fields.Integer(string='Đang mở', compute='_compute_counts')
    repeat_count = fields.Integer(string='Tái phát',
                                  compute='_compute_counts')

    company_id = fields.Many2one(
        'res.company', string='Công ty', required=True,
        default=lambda self: self.env.company, index=True)

    _uniq_code = models.Constraint(
        'UNIQUE(company_id, code)', 'Mã luật cảnh báo không được trùng.')

    @api.depends('alarm_ids.state', 'alarm_ids.repeat_after_fix')
    def _compute_counts(self):
        for r in self:
            r.alarm_count = len(r.alarm_ids)
            r.open_count = len(r.alarm_ids.filtered(
                lambda a: a.state in ('new', 'ack', 'wo')))
            r.repeat_count = sum(r.alarm_ids.mapped('repeat_after_fix'))

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for r in self:
            r.display_name = '[%s] %s' % (r.code or '', r.name or '')

    @api.constrains('source', 'threshold', 'window_days', 'meter_type')
    def _check_dieu_kien(self):
        for r in self:
            if r.source == 'meter_threshold':
                if not r.meter_type:
                    raise ValidationError(_(
                        'Luật "%s" so ngưỡng thì phải chọn loại đồng hồ.',
                        r.name))
                if not r.threshold:
                    raise ValidationError(_(
                        'Luật "%s" so ngưỡng nhưng ngưỡng để trống — nó sẽ '
                        'nổ cho mọi số đọc, hoặc không nổ bao giờ.', r.name))
            if r.source in ('meter_stall', 'feed_silent') \
                    and r.window_days < 1:
                raise ValidationError(_(
                    'Luật "%s" phải có cửa sổ ít nhất 1 ngày.', r.name))

    @api.onchange('severity')
    def _onchange_severity(self):
        # Gợi ý, không ép: mức nghiêm trọng thì chờ xác nhận đắt hơn chịu
        # rác, nên nghiêng về tạo ngay — nhưng người cấu hình vẫn đổi được.
        if self.severity == 'critical' and self.auto_wo == 'on_ack':
            self.auto_wo = 'immediate'

    # ------------------------------------------------------------------
    def _vi_tri_ap_dung(self):
        """Các vị trí luật này canh."""
        self.ensure_one()
        vt = self.location_ids
        if self.category_id:
            loai = self.env['eam.asset.category'].search(
                [('id', 'child_of', self.category_id.id)])
            ts = self.env['eam.asset'].search(
                [('category_id', 'in', loai.ids), ('is_installed', '=', True)])
            for a in ts:
                l = a.current_location_id
                while l and l.location_type not in ('position', 'plant'):
                    l = l.parent_id
                if l:
                    vt |= l
        if self.plant_id:
            trong = self.env['eam.location'].search(
                [('id', 'child_of', self.plant_id.id)])
            vt = vt & trong
        return vt

    # ------------------------------------------------------------------
    def _danh_gia(self):
        """Chạy luật, ghi cảnh báo mới và tắt cảnh báo đã hết điều kiện.

        Trả về ``(số cảnh báo ghi nhận, số cảnh báo tự tắt)``.
        """
        self.ensure_one()
        if self.source not in NGUON_TU_DONG:
            return 0, 0
        A = self.env['eam.alarm']
        M = self.env['eam.meter']
        hom_nay = fields.Date.context_today(self)
        n_bao = n_tat = 0
        for vt in self._vi_tri_ap_dung():
            dh = M.search([('location_id', '=', vt.id),
                           ('meter_type', '=', self.meter_type)], limit=1)
            vuot, loi, tri = False, '', None

            if not dh:
                # Luật canh một đồng hồ không tồn tại thì IM LẶNG không
                # bao giờ nổ. Đó là cách tệ nhất để một luật an toàn
                # chết, nên nói ra ở nhật ký thay vì bỏ qua.
                _logger.info(
                    'eam_alarm: luật %s không thấy đồng hồ %s tại %s.',
                    self.code, self.meter_type, vt.complete_code)
                continue

            if self.source == 'meter_threshold':
                tri = dh.current_value
                vuot = (tri > self.threshold if self.operator == 'gt'
                        else tri < self.threshold)
                if vuot:
                    loi = _('%(nhan)s đang %(tri).2f %(dv)s, %(huong)s '
                            'ngưỡng %(ng).2f.',
                            nhan=dict(M._fields['meter_type'].selection).get(
                                self.meter_type, ''),
                            tri=tri, dv=dh.uom_label or '',
                            huong=_('vượt') if self.operator == 'gt'
                            else _('thấp hơn'),
                            ng=self.threshold)

            elif self.source == 'feed_silent':
                cuoi = dh.date_last_reading
                if not cuoi:
                    vuot = True
                    loi = _('Đồng hồ chưa có số đọc nào.')
                else:
                    tre = (hom_nay - cuoi).days
                    vuot = tre >= self.window_days
                    if vuot:
                        loi = _('Không có số đọc mới %(n)d ngày (lần cuối '
                                '%(d)s). Nhiều khả năng ĐƯỜNG TRUYỀN chết, '
                                'không phải máy dừng — kiểm tra kết nối '
                                'trước khi cử người ra trụ.',
                                n=tre, d=cuoi)

            elif self.source == 'meter_stall':
                tu = hom_nay - relativedelta(days=self.window_days)
                rs = self.env['eam.meter.reading'].search(
                    [('meter_id', '=', dh.id), ('date', '>=', tu)],
                    order='date')
                if len(rs) >= 2:
                    chenh = (rs[-1].effective_value or 0.0) \
                        - (rs[0].effective_value or 0.0)
                    tri = chenh
                    vuot = chenh <= 0.0
                    if vuot:
                        loi = _('Số đọc vẫn về đều nhưng %(nhan)s KHÔNG '
                                'tăng trong %(n)d ngày. Máy đứng im thật — '
                                'khác với mất tín hiệu.',
                                nhan=dict(
                                    M._fields['meter_type'].selection).get(
                                        self.meter_type, ''),
                                n=self.window_days)

            if vuot:
                A._ghi_nhan(self, vt, loi, value=tri)
                n_bao += 1
            else:
                n_tat += A._tu_tat(self, vt)
        return n_bao, n_tat

    @api.model
    def _cron_quet(self):
        """Quét toàn bộ luật tự động."""
        luat = self.search([('source', 'in', list(NGUON_TU_DONG))])
        tong_bao = tong_tat = 0
        for r in luat:
            try:
                b, t = r._danh_gia()
            except Exception:
                # Một luật cấu hình sai không được làm chết cả lượt quét —
                # nếu không thì luật đầu tiên bị lỗi sẽ che mọi cảnh báo
                # của các luật sau, và không ai biết.
                _logger.exception(
                    'eam_alarm: luật %s lỗi khi đánh giá, bỏ qua.', r.code)
                continue
            tong_bao += b
            tong_tat += t
        _logger.info('eam_alarm: ghi nhận %d cảnh báo, tự tắt %d.',
                     tong_bao, tong_tat)
        return True

    def action_quet_ngay(self):
        for r in self:
            r._danh_gia()
        return True

    def action_mo_canh_bao(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Cảnh báo — %s', self.name),
            'res_model': 'eam.alarm',
            'view_mode': 'list,form',
            'domain': [('rule_id', '=', self.id)],
            'context': {'default_rule_id': self.id},
        }
