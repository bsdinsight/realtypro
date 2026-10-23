# -*- coding: utf-8 -*-
"""Kỳ đánh giá: đo, đối chiếu cam kết, ra phí và phạt theo từng nhà máy.

Chốt kỳ là ĐÓNG BĂNG
---------------------
Kỳ đã chốt chụp lại mức cam kết, số đo được và phí tại thời điểm chốt.
Sửa hợp đồng hôm nay không được làm đổi biên bản tháng trước — nếu
không thì không ai dám in lại một biên bản cũ, vì nó có thể ra số khác.

Không đo được thì KHÔNG phạt
-----------------------------
Cam kết theo cơ sở hệ chưa đo được vẫn sinh dòng kết quả, nhưng ghi rõ
lý do và để trống phần đánh giá. Thay bằng 0 thì 0 < mức cam kết, dòng
thành "không đạt", và hệ tính ra một khoản phạt cho thứ nó chưa hề đo.
"""
from datetime import datetime, time, timedelta

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from . import do_kha_dung


class EamOmPeriod(models.Model):
    _name = 'eam.om.period'
    _description = 'Kỳ đánh giá hợp đồng O&M'
    _inherit = ['mail.thread']
    _order = 'date_start desc, id desc'
    _rec_name = 'display_name'

    contract_id = fields.Many2one(
        'eam.om.contract', string='Hợp đồng', required=True,
        ondelete='cascade', index=True)
    partner_id = fields.Many2one(
        related='contract_id.partner_id', store=True, string='Nhà thầu')
    company_id = fields.Many2one(related='contract_id.company_id', store=True)
    currency_id = fields.Many2one(related='contract_id.currency_id')

    date_start = fields.Date(string='Từ ngày', required=True, index=True)
    date_end = fields.Date(string='Đến ngày', required=True, index=True)

    chu_ky = fields.Selection(
        [('thang', 'Tháng'), ('quy', 'Quý'), ('nua_nam', 'Nửa năm'),
         ('nam', 'Năm hợp đồng')],
        string='Chu kỳ', required=True, index=True,
        default=lambda s: s.env['eam.om.contract'].browse(
            s.env.context.get('default_contract_id')).chu_ky or 'thang',
        help='Kỳ này chấm những cam kết khai cùng chu kỳ với nó.')
    la_ky_phi = fields.Boolean(
        string='Kỳ tính phí', compute='_compute_la_ky_phi', store=True,
        help='Chỉ kỳ theo chu kỳ của hợp đồng mới mang phí. Kỳ của chu '
             'kỳ khác chỉ để chấm điểm — tính phí cả hai là thu tiền hai '
             'lần cho cùng một quãng thời gian.')

    state = fields.Selection(
        [('nhap', 'Chưa đo'),
         ('da_do', 'Đã đo'),
         ('chot', 'Đã chốt')],
        string='Trạng thái', default='nhap', required=True, tracking=True)
    date_measured = fields.Datetime(string='Đo lúc', readonly=True)

    line_ids = fields.One2many(
        'eam.om.period.line', 'period_id', string='Kết quả cam kết')
    plant_ids = fields.One2many(
        'eam.om.period.plant', 'period_id', string='Thanh toán theo nhà máy')

    tong_phi = fields.Monetary(
        string='Tổng phí', compute='_compute_tong', store=True)
    tong_phat = fields.Monetary(
        string='Tổng phạt', compute='_compute_tong', store=True)
    tong_thanh_toan = fields.Monetary(
        string='Phải trả', compute='_compute_tong', store=True)
    so_khong_dat = fields.Integer(
        string='Cam kết không đạt', compute='_compute_tong', store=True)
    co_canh_bao = fields.Boolean(
        string='Có cảnh báo', compute='_compute_tong', store=True,
        help='Có dòng chưa đo được, hoặc giờ chưa quy trách nhiệm vượt '
             'ngưỡng. Con số ở kỳ này chưa nên đem đi ký.')

    note = fields.Text(string='Ghi chú biên bản')

    _uniq_ky = models.Constraint(
        'UNIQUE(contract_id, chu_ky, date_start, date_end)',
        'Hợp đồng đã có kỳ đúng chu kỳ và khoảng ngày này.')

    @api.depends('chu_ky', 'contract_id.chu_ky')
    def _compute_la_ky_phi(self):
        for rec in self:
            rec.la_ky_phi = rec.chu_ky == rec.contract_id.chu_ky

    # ==================================================================
    @api.depends('date_start', 'date_end', 'contract_id')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s: %s → %s' % (
                rec.contract_id.name or '', rec.date_start or '',
                rec.date_end or '')

    @api.depends('plant_ids.phi', 'plant_ids.phat', 'line_ids.dat',
                 'line_ids.do_duoc', 'line_ids.canh_bao_chua_quy')
    def _compute_tong(self):
        for rec in self:
            rec.tong_phi = sum(rec.plant_ids.mapped('phi'))
            rec.tong_phat = sum(rec.plant_ids.mapped('phat'))
            rec.tong_thanh_toan = rec.tong_phi - rec.tong_phat
            rec.so_khong_dat = len(rec.line_ids.filtered(
                lambda l: l.do_duoc and not l.dat))
            rec.co_canh_bao = bool(rec.line_ids.filtered(
                lambda l: not l.do_duoc or l.canh_bao_chua_quy))

    # ==================================================================
    def action_do(self):
        """Đo lại toàn bộ kỳ. Dựng lại dòng kết quả từ đầu."""
        for rec in self:
            if rec.state == 'chot':
                raise UserError(_(
                    'Kỳ %s đã chốt. Số liệu đã chụp lại làm biên bản nên '
                    'không đo lại được — mở lại kỳ trước nếu thật sự cần.',
                    rec.display_name))
            rec.line_ids.unlink()
            rec.plant_ids.unlink()
            rec._dung_dong()
            rec.write({'state': 'da_do',
                       'date_measured': fields.Datetime.now()})
        return True

    def _dung_dong(self):
        self.ensure_one()
        hd = self.contract_id
        L = self.env['eam.om.period.line']
        P = self.env['eam.om.period.plant']
        tu, den = self._bien_ky_utc()

        if not hd.plant_line_ids:
            raise UserError(_(
                'Hợp đồng "%s" chưa khai nhà máy nào trong phạm vi nên '
                'không có gì để đo.', hd.name))

        phat_theo_nm = {}
        for pl in hd.plant_line_ids:
            phat_theo_nm[pl.plant_id.id] = 0.0

        # Kỳ chỉ chấm những cam kết khai CÙNG chu kỳ với nó. Cam kết năm
        # mà đem chấm bằng số liệu một tháng là phạt oan: hợp đồng cho
        # phép tháng xấu bù bằng các tháng còn lại.
        cam_ids = hd.commitment_ids.filtered(
            lambda c: c.chu_ky_hieu_luc == self.chu_ky)
        if not cam_ids:
            raise UserError(_(
                'Kỳ %(k)s theo chu kỳ "%(c)s" nhưng hợp đồng không có cam '
                'kết nào chấm theo chu kỳ đó.',
                k=self.display_name, c=dict(self._fields['chu_ky'].selection
                                            ).get(self.chu_ky)))

        for cam in cam_ids:
            ap = (hd.plant_line_ids.filtered(
                lambda x: x.plant_id == cam.plant_id)
                if cam.plant_id else hd.plant_line_ids)
            for pl in ap:
                kq = self._do_mot(cam, pl, tu, den)
                dong = L.create(self._vals_dong(cam, pl, kq))
                phat_theo_nm[pl.plant_id.id] = \
                    phat_theo_nm.get(pl.plant_id.id, 0.0) + dong.phat

        for pl in hd.plant_line_ids:
            P.create({
                'period_id': self.id,
                'plant_id': pl.plant_id.id,
                'phi': pl.phi_ky if self.la_ky_phi else 0.0,
                'phat': phat_theo_nm.get(pl.plant_id.id, 0.0),
            })

    def _phi_co_so(self, plant_line):
        """Phí dùng làm GỐC khi chặn trần phạt.

        Kỳ tính phí thì gốc là phí của chính kỳ đó. Kỳ chỉ để chấm điểm
        (ví dụ kỳ năm trên hợp đồng trả phí theo tháng) thì gốc là tổng
        phí của các kỳ phí mà nó phủ — nếu không, trần tính trên phí
        bằng 0 và mọi khoản phạt của kỳ năm bị chặn về 0 trong im lặng.
        """
        self.ensure_one()
        if self.la_ky_phi:
            return plant_line.phi_ky
        n = self.search_count([
            ('contract_id', '=', self.contract_id.id),
            ('la_ky_phi', '=', True),
            ('date_start', '<=', self.date_end),
            ('date_end', '>=', self.date_start)])
        return plant_line.phi_ky * (n or 1)

    def _bien_ky_utc(self):
        """Hai mốc UTC của kỳ, từ hai ngày theo lịch ĐỊA PHƯƠNG.

        Kỳ ghi bằng NGÀY (31/1), còn sổ dừng máy ghi bằng THỜI ĐIỂM UTC.
        Ghép thẳng ngày với giờ 0 là coi nửa đêm địa phương bằng nửa đêm
        UTC — lệch bảy tiếng ở Việt Nam. Trong một kỳ dài thì bảy tiếng
        là nhỏ, nhưng nó **chuyển giờ dừng từ kỳ này sang kỳ kia** đúng
        ở chỗ đắt nhất: ranh giới năm hợp đồng, nơi quyết định tiền.

        Mốc cuối LOẠI TRỪ: 0h ngày hôm sau, khớp với phép so ``<``.
        """
        self.ensure_one()
        try:
            tz = pytz.timezone((self.contract_id.tz or '').strip())
        except Exception:
            raise UserError(_(
                'Hợp đồng "%(h)s" khai múi giờ "%(t)s" không hợp lệ. Đo '
                'kỳ với múi giờ sai là chuyển giờ dừng sang kỳ bên cạnh, '
                'nên dừng ở đây thay vì ra một con số trông bình thường.',
                h=self.contract_id.name, t=self.contract_id.tz))
        dau = tz.localize(datetime.combine(self.date_start, time.min))
        cuoi = tz.localize(datetime.combine(
            self.date_end + timedelta(days=1), time.min))
        return (dau.astimezone(pytz.UTC).replace(tzinfo=None),
                cuoi.astimezone(pytz.UTC).replace(tzinfo=None))

    def _do_mot(self, cam, plant_line, tu, den):
        """Đo một cam kết trên một nhà máy. Luôn trả về cùng hình dạng."""
        ly_do = cam._ly_do_chua_do(cam.loai)
        if ly_do:
            return do_kha_dung.chua_do_duoc(ly_do)
        return do_kha_dung.do_kha_dung_thoi_gian(
            self.env, plant_line.plant_id, tu, den,
            so_don_vi=plant_line.so_don_vi,
            tinh_ca_chua_quy=cam.tinh_ca_chua_quy)

    def _vals_dong(self, cam, plant_line, kq):
        """Chụp lại cam kết và kết quả — kỳ chốt rồi không đọc lại hợp đồng."""
        self.ensure_one()
        dat = False
        thieu = 0.0
        phat = 0.0
        # Làm tròn TRƯỚC khi so và trước khi tính phạt, theo số chữ số
        # hợp đồng khai. Biên bản phải tự nhân lại ra đúng khoản phạt;
        # tính bằng số đầy đủ rồi in ra số đã làm tròn là tự tạo ra một
        # chỗ để nhà thầu cãi, và họ cãi đúng.
        so_le = max(self.contract_id.so_le, 0)
        gia_tri = round(kq['gia_tri'], so_le) if kq['do_duoc'] else 0.0
        phi_goc = self._phi_co_so(plant_line)
        if kq['do_duoc']:
            if cam.huong == 'toi_thieu':
                dat = gia_tri >= cam.muc
                thieu = round(max(cam.muc - gia_tri, 0.0), so_le)
            else:
                dat = gia_tri <= cam.muc
                thieu = round(max(gia_tri - cam.muc, 0.0), so_le)
            phat = cam.tinh_phat(thieu, phi_goc)

        tong_dung = kq['gio_dung_tat_ca']
        ty_le_chua_quy = (100.0 * kq['gio_chua_quy'] / tong_dung
                          if tong_dung else 0.0)
        return {
            'period_id': self.id,
            'commitment_id': cam.id,
            'plant_id': plant_line.plant_id.id,
            'ten_cam_ket': cam.name,
            'loai': cam.loai,
            'muc_cam_ket': cam.muc,
            'huong': cam.huong,
            'do_duoc': kq['do_duoc'],
            'ly_do_chua_do': kq.get('ly_do', ''),
            'gia_tri': gia_tri,
            'gia_tri_tho': kq['gia_tri'],
            'gio_ky': kq['gio_ky'],
            'so_don_vi': kq['so_don_vi'],
            'mau_so': kq['mau_so'],
            'gio_dung_tinh': kq['gio_dung_tinh'],
            'gio_dung_tat_ca': tong_dung,
            'gio_chua_quy': kq['gio_chua_quy'],
            'ty_le_chua_quy': ty_le_chua_quy,
            'canh_bao_chua_quy': bool(
                cam.nguong_chua_quy
                and ty_le_chua_quy > cam.nguong_chua_quy),
            'so_khoang': kq['so_khoang'],
            'dat': dat,
            'thieu_hut': thieu,
            'phi_ky': phi_goc,
            'phat': phat,
        }

    def action_chot(self):
        for rec in self:
            if rec.state != 'da_do':
                raise UserError(_(
                    'Kỳ %s chưa đo. Bấm "Đo kỳ" trước khi chốt.',
                    rec.display_name))
            rec.state = 'chot'
        return True

    def action_mo_lai(self):
        """Mở lại kỳ đã chốt — có vết trong chatter."""
        for rec in self:
            rec.message_post(body=_(
                'Mở lại kỳ đã chốt. Số liệu cũ sẽ bị thay khi đo lại.'))
            rec.state = 'da_do'
        return True


class EamOmPeriodLine(models.Model):
    _name = 'eam.om.period.line'
    _description = 'Kết quả một cam kết trong một kỳ'
    _order = 'period_id, plant_id, id'

    period_id = fields.Many2one(
        'eam.om.period', string='Kỳ', required=True, ondelete='cascade',
        index=True)
    contract_id = fields.Many2one(
        related='period_id.contract_id', store=True, index=True)
    commitment_id = fields.Many2one(
        'eam.om.commitment', string='Cam kết', ondelete='set null')
    plant_id = fields.Many2one(
        'eam.location', string='Nhà máy', required=True, index=True)
    company_id = fields.Many2one(related='period_id.company_id', store=True)
    currency_id = fields.Many2one(related='period_id.currency_id')
    date_start = fields.Date(related='period_id.date_start', store=True)

    # ----- Chụp lại từ cam kết --------------------------------------
    ten_cam_ket = fields.Char(string='Cam kết', readonly=True)
    loai = fields.Selection(
        [('kd_thoi_gian', 'Khả dụng theo thời gian (%)'),
         ('kd_san_luong', 'Khả dụng theo sản lượng (%)'),
         ('pr', 'Tỷ số hiệu suất PR (%)'),
         ('phan_hoi', 'Thời gian phản hồi (giờ)'),
         ('khac_phuc', 'Thời gian khắc phục (giờ)')],
        string='Cơ sở đo', readonly=True)
    muc_cam_ket = fields.Float(string='Mức cam kết', digits=(16, 2),
                               readonly=True)
    huong = fields.Selection(
        [('toi_thieu', '≥'), ('toi_da', '≤')], string='Chiều', readonly=True)

    # ----- Đo được ---------------------------------------------------
    do_duoc = fields.Boolean(string='Đo được', readonly=True)
    ly_do_chua_do = fields.Char(string='Vì sao chưa đo được', readonly=True)
    gia_tri = fields.Float(
        string='Đo được', digits=(16, 2), readonly=True,
        help='Đã làm tròn theo số chữ số hợp đồng khai. Đây là con số đi '
             'vào biên bản VÀ là con số dùng để tính phạt.')
    gia_tri_tho = fields.Float(
        string='Đo được (chưa làm tròn)', digits=(16, 6), readonly=True,
        aggregator=False,
        help='Giữ lại để truy lại khi có tranh cãi về chỗ làm tròn.')

    gio_ky = fields.Float(string='Giờ trong kỳ', digits=(16, 2),
                          readonly=True, aggregator=False)
    so_don_vi = fields.Integer(string='Số đơn vị', readonly=True,
                               aggregator=False)
    mau_so = fields.Float(string='Mẫu số (giờ-máy)', digits=(16, 2),
                          readonly=True, aggregator=False)
    gio_dung_tinh = fields.Float(
        string='Giờ dừng tính cho nhà thầu', digits=(16, 2), readonly=True)
    gio_dung_tat_ca = fields.Float(
        string='Tổng giờ dừng', digits=(16, 2), readonly=True)
    gio_chua_quy = fields.Float(
        string='Giờ chưa quy trách nhiệm', digits=(16, 2), readonly=True)
    ty_le_chua_quy = fields.Float(
        string='Chưa quy (%)', digits=(5, 2), readonly=True,
        aggregator=False)
    canh_bao_chua_quy = fields.Boolean(
        string='Cảnh báo chưa quy', readonly=True,
        help='Giờ chưa quy trách nhiệm vượt ngưỡng của cam kết. Con số '
             'khả dụng có thể đang đẹp vì chưa ai phân loại.')
    so_khoang = fields.Integer(string='Số khoảng dừng', readonly=True,
                               aggregator=False)

    # ----- Kết luận ---------------------------------------------------
    dat = fields.Boolean(string='Đạt', readonly=True)
    thieu_hut = fields.Float(string='Thiếu hụt (điểm)', digits=(16, 2),
                             readonly=True)
    phi_ky = fields.Monetary(
        string='Phí gốc chặn trần', readonly=True,
        help='Phí dùng làm gốc khi chặn trần phạt. Kỳ tính phí thì '
             'bằng phí kỳ của nhà máy; kỳ chỉ để chấm điểm thì bằng '
             'tổng phí các kỳ phí mà nó phủ.')
    phat = fields.Monetary(string='Phạt', readonly=True)

    def action_xem_khoang_dung(self):
        """Mở đúng những khoảng dừng đã đi vào con số này."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Khoảng dừng — %s, %s',
                      self.plant_id.name, self.period_id.display_name),
            'res_model': 'eam.outage',
            'view_mode': 'list,form',
            'domain': [
                ('location_id', 'child_of', self.plant_id.id),
                ('state', '=', 'confirmed'),
                ('counts_as_downtime', '=', True),
                ('is_root_cause', '=', False),
                ('date_start', '<', self.period_id.date_end),
                '|', ('date_end', '=', False),
                ('date_end', '>', self.period_id.date_start),
            ],
        }


class EamOmPeriodPlant(models.Model):
    _name = 'eam.om.period.plant'
    _description = 'Thanh toán theo nhà máy trong một kỳ'
    _order = 'period_id, plant_id'

    period_id = fields.Many2one(
        'eam.om.period', string='Kỳ', required=True, ondelete='cascade',
        index=True)
    contract_id = fields.Many2one(
        related='period_id.contract_id', store=True, index=True)
    partner_id = fields.Many2one(related='period_id.partner_id', store=True)
    plant_id = fields.Many2one(
        'eam.location', string='Nhà máy', required=True, index=True)
    company_id = fields.Many2one(related='period_id.company_id', store=True)
    currency_id = fields.Many2one(related='period_id.currency_id')
    date_start = fields.Date(related='period_id.date_start', store=True)
    state = fields.Selection(related='period_id.state', store=True)

    phi = fields.Monetary(string='Phí kỳ', readonly=True)
    phat = fields.Monetary(string='Phạt', readonly=True)
    thanh_toan = fields.Monetary(
        string='Phải trả', compute='_compute_thanh_toan', store=True)

    @api.depends('phi', 'phat')
    def _compute_thanh_toan(self):
        for rec in self:
            rec.thanh_toan = rec.phi - rec.phat
