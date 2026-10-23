# -*- coding: utf-8 -*-
"""Ca trực và biên bản giao nhận ca.

Thứ thật sự hỏng trong giao ca
-------------------------------
Không phải chuyện ai trực ca nào — bảng phân công nào cũng có. Thứ hỏng
là **việc rơi giữa hai ca**: người ra ca biết một chuyện, người vào ca
không biết, và không ai viết xuống. Sáng hôm sau máy hỏng nặng hơn, và
cuộc truy nguyên dừng ở câu *"tôi không được bàn giao việc đó"*.

Nên module này dựng quanh đúng một trục: **không có gì được phép biến
mất giữa hai ca**.

Bốn quyết định
--------------

**① Việc dở dang CHUYỂN SANG ca sau, có dấu vết.** Đóng ca mà còn việc
chưa xong thì việc đó được tạo lại ở ca sau, trỏ ngược về bản gốc. Nhờ
sợi dây đó, đếm được một việc đã **lăn qua mấy ca** — và việc lăn năm
ca là việc đang bị đùn, không phải việc khó.

Cách sai mà phần mềm hay làm: chỉ hiện "các lệnh công việc còn mở". Nó
bỏ sót đúng thứ hay rơi nhất — lời dặn miệng, cái chưa thành lệnh công
việc, cái vừa phát hiện cuối ca.

**② Chụp trạng thái nhà máy lúc MỞ ca, không tính lại khi mở xem.** Mục
đích của sơ đồ đầu ca là *"người vào ca đã nhìn thấy gì"* — đó là bằng
chứng. Tính lại khi mở xem thì sáu tháng sau nó hiện trạng thái hôm nay,
và biên bản mất sạch giá trị.

**③ Ký HAI ĐẦU, nhưng không chặn vận hành.** Bàn giao chỉ một bên ký là
cái cớ kinh điển khi tranh chấp. Nhưng chặn đóng ca cho tới khi người
vào ca ký thì nhà máy không vì thế mà dừng — người ta sẽ ký hộ nhau, và
chữ ký mất luôn ý nghĩa. Nên: cho đóng, nhưng **cắm cờ bàn giao một
chiều** và cờ đó hiện trên danh sách.

**④ Ca KHÔNG tự sinh vô hạn.** Sinh theo lịch có ngày kết thúc, và ca đã
bàn giao thì không dựng đè — biên bản đã ký là thứ không được viết lại.
"""
from datetime import datetime, time, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class EamShiftPattern(models.Model):
    _name = 'eam.shift.pattern'
    _description = 'Mẫu ca trực'
    _order = 'plant_id, gio_bat_dau'
    _rec_name = 'display_name'

    name = fields.Char(string='Tên ca', required=True)
    code = fields.Char(string='Mã', required=True)
    plant_id = fields.Many2one(
        'eam.location', string='Nhà máy', required=True,
        domain="[('location_type', '=', 'plant')]", ondelete='cascade',
        index=True)
    company_id = fields.Many2one(related='plant_id.company_id', store=True)

    gio_bat_dau = fields.Float(
        string='Bắt đầu (giờ)', required=True, default=6.0,
        help='Giờ trong ngày, ví dụ 6.0 là 6h00, 14.5 là 14h30.')
    so_gio = fields.Float(string='Dài (giờ)', required=True, default=8.0)
    qua_dem = fields.Boolean(
        string='Vắt qua ngày hôm sau', compute='_compute_qua_dem',
        store=True,
        help='Ca đêm bắt đầu 22h và kết thúc 6h hôm sau. Quên chuyện này '
             'thì ca đêm dài âm mười sáu tiếng.')
    active = fields.Boolean(default=True)

    _uniq = models.Constraint(
        'UNIQUE(plant_id, code)',
        'Mã ca không được trùng trong cùng một nhà máy.')

    @api.depends('gio_bat_dau', 'so_gio')
    def _compute_qua_dem(self):
        for rec in self:
            rec.qua_dem = (rec.gio_bat_dau + rec.so_gio) > 24.0

    @api.depends('name', 'plant_id')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s — %s' % (rec.plant_id.code or '',
                                            rec.name or '')

    @api.constrains('so_gio')
    def _check_so_gio(self):
        for rec in self:
            if not (0 < rec.so_gio <= 24):
                raise ValidationError(_(
                    'Ca "%s" dài %s giờ — phải nằm trong khoảng 0–24.',
                    rec.name, rec.so_gio))


class EamShift(models.Model):
    _name = 'eam.shift'
    _description = 'Ca trực'
    _inherit = ['mail.thread']
    _order = 'date_start desc, id desc'
    _rec_name = 'display_name'

    plant_id = fields.Many2one(
        'eam.location', string='Nhà máy', required=True,
        domain="[('location_type', '=', 'plant')]", ondelete='cascade',
        index=True, tracking=True)
    pattern_id = fields.Many2one(
        'eam.shift.pattern', string='Ca', required=True,
        ondelete='restrict', tracking=True)
    company_id = fields.Many2one(related='plant_id.company_id', store=True)

    ngay = fields.Date(string='Ngày', required=True, index=True)
    date_start = fields.Datetime(string='Bắt đầu', required=True, index=True)
    date_end = fields.Datetime(string='Kết thúc', required=True)

    truong_ca_id = fields.Many2one(
        'res.users', string='Trưởng ca', tracking=True)
    user_ids = fields.Many2many('res.users', string='Người trực')

    state = fields.Selection(
        [('ke_hoach', 'Theo kế hoạch'),
         ('dang_truc', 'Đang trực'),
         ('da_ban_giao', 'Đã bàn giao')],
        string='Trạng thái', default='ke_hoach', required=True, tracking=True)

    # ----- Giao nhận --------------------------------------------------
    nguoi_giao_id = fields.Many2one(
        'res.users', string='Người giao ca', readonly=True, tracking=True)
    gio_giao = fields.Datetime(string='Giao lúc', readonly=True)
    nguoi_nhan_id = fields.Many2one(
        'res.users', string='Người nhận ca', readonly=True, tracking=True)
    gio_nhan = fields.Datetime(string='Nhận lúc', readonly=True)
    ban_giao_mot_chieu = fields.Boolean(
        string='Bàn giao MỘT CHIỀU', compute='_compute_mot_chieu', store=True,
        help='Đã giao nhưng chưa ai ký nhận. Không chặn vận hành — chặn '
             'thì người ta ký hộ nhau và chữ ký mất ý nghĩa — nhưng phải '
             'nhìn thấy được, vì đây là cái cớ kinh điển khi tranh chấp.')
    bien_ban = fields.Text(string='Nội dung bàn giao')

    note_ids = fields.One2many('eam.shift.note', 'shift_id', string='Việc & ghi chú')
    snapshot_ids = fields.One2many(
        'eam.shift.snapshot', 'shift_id', string='Trạng thái đầu ca')

    # Cả ba CÓ LƯU: chúng vừa dùng để lọc vừa dùng để cộng tổng trên
    # danh sách, mà trường tính không lưu thì không làm được cả hai.
    so_viec_mo = fields.Integer(
        string='Việc còn mở', compute='_compute_dem', store=True)
    so_viec_lan_lau = fields.Integer(
        string='Việc lăn nhiều ca', compute='_compute_dem', store=True,
        help='Việc đã chuyển qua từ ba ca trở lên. Việc lăn năm ca là '
             'việc đang bị đùn, không phải việc khó.')
    so_may_dung = fields.Integer(
        string='Tổ máy đang dừng', compute='_compute_dem', store=True)

    _uniq_ca = models.Constraint(
        'UNIQUE(plant_id, pattern_id, ngay)',
        'Nhà máy đã có ca này trong ngày đó.')

    # ==================================================================
    @api.depends('plant_id', 'pattern_id', 'ngay')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s · %s · %s' % (
                rec.plant_id.code or '', rec.pattern_id.name or '',
                rec.ngay or '')

    @api.depends('nguoi_giao_id', 'nguoi_nhan_id', 'state')
    def _compute_mot_chieu(self):
        for rec in self:
            rec.ban_giao_mot_chieu = bool(
                rec.state == 'da_ban_giao' and rec.nguoi_giao_id
                and not rec.nguoi_nhan_id)

    @api.depends('note_ids.state', 'note_ids.so_ca_da_lan',
                 'snapshot_ids.dang_dung')
    def _compute_dem(self):
        for rec in self:
            mo = rec.note_ids.filtered(lambda n: n.state != 'xong')
            rec.so_viec_mo = len(mo)
            rec.so_viec_lan_lau = len(mo.filtered(
                lambda n: n.so_ca_da_lan >= 3))
            rec.so_may_dung = len(rec.snapshot_ids.filtered('dang_dung'))

    # ==================================================================
    def action_mo_ca(self):
        """Mở ca: chụp trạng thái nhà máy và kéo việc dở từ ca trước."""
        for rec in self:
            if rec.state != 'ke_hoach':
                raise UserError(_('Ca %s đã mở rồi.', rec.display_name))
            rec._chup_trang_thai()
            rec._keo_viec_ca_truoc()
            rec.write({'state': 'dang_truc'})
        return True

    def _chup_trang_thai(self):
        """Ảnh chụp lúc MỞ ca — không tính lại về sau."""
        self.ensure_one()
        self.snapshot_ids.unlink()
        L = self.env['eam.location']
        O = self.env['eam.outage']
        dong = []
        for vt in L.search([('id', 'child_of', self.plant_id.id),
                            ('location_type', '=', 'position')]):
            od = O.search([
                ('location_id', 'child_of', vt.id),
                ('state', '=', 'confirmed'),
                ('date_start', '<=', self.date_start),
                '|', ('date_end', '=', False),
                ('date_end', '>', self.date_start)], limit=1)
            dong.append({
                'shift_id': self.id, 'location_id': vt.id,
                'dang_dung': bool(od and od.counts_as_downtime),
                'outage_id': od.id if od else False,
                'ghi_chu': od.category_id.complete_name if od else '',
            })
        self.env['eam.shift.snapshot'].create(dong)

    def _keo_viec_ca_truoc(self):
        """Kéo việc còn mở của ca liền trước sang ca này."""
        self.ensure_one()
        truoc = self.search([
            ('plant_id', '=', self.plant_id.id),
            ('date_end', '<=', self.date_start),
            ('state', '=', 'da_ban_giao')],
            order='date_end desc', limit=1)
        if not truoc:
            return 0
        N = self.env['eam.shift.note']
        n = 0
        for v in truoc.note_ids.filtered(lambda x: x.state != 'xong'):
            if N.search_count([('shift_id', '=', self.id),
                               ('nguon_id', '=', v.id)]):
                continue
            v.copy({'shift_id': self.id, 'nguon_id': v.id,
                    'loai': 'chuyen_ca', 'state': v.state})
            n += 1
        return n

    def action_ban_giao(self):
        """Giao ca. Việc còn mở KHÔNG biến mất — nó sang ca sau."""
        for rec in self:
            if rec.state != 'dang_truc':
                raise UserError(_(
                    'Ca %s chưa mở nên chưa giao được.', rec.display_name))
            rec.write({'state': 'da_ban_giao',
                       'nguoi_giao_id': self.env.user.id,
                       'gio_giao': fields.Datetime.now()})
            sau = rec._ca_ke_tiep()
            if sau and sau.state == 'dang_truc':
                sau._keo_viec_ca_truoc()
            elif rec.so_viec_mo and not sau:
                rec.message_post(body=_(
                    'Còn %d việc chưa xong mà CHƯA CÓ ca kế tiếp để '
                    'chuyển sang. Sinh ca kế tiếp rồi mở ca đó, nếu '
                    'không số việc này không ai nhận.', rec.so_viec_mo))
        return True

    def action_nhan_ca(self):
        for rec in self:
            if rec.state != 'da_ban_giao':
                raise UserError(_(
                    'Ca %s chưa được giao.', rec.display_name))
            rec.write({'nguoi_nhan_id': self.env.user.id,
                       'gio_nhan': fields.Datetime.now()})
        return True

    def _ca_ke_tiep(self):
        self.ensure_one()
        return self.search([
            ('plant_id', '=', self.plant_id.id),
            ('date_start', '>=', self.date_end)],
            order='date_start', limit=1)

    def action_xem_lich_su(self):
        """A13.6 — từ màn giao ca nhảy thẳng sang lịch sử sửa chữa."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Lịch sử công việc — %s', self.plant_id.name),
            'res_model': 'eam.work.order',
            'view_mode': 'list,form',
            'domain': [('location_id', 'child_of', self.plant_id.id)],
            'context': {'search_default_group_location': 1},
        }

    # ==================================================================
    @api.model
    def sinh_ca(self, plant, tu_ngay, den_ngay):
        """Dựng ca theo mẫu cho một dải ngày. Ca ĐÃ CÓ thì bỏ qua."""
        mau = self.env['eam.shift.pattern'].search(
            [('plant_id', '=', plant.id)])
        if not mau:
            raise UserError(_(
                'Nhà máy "%s" chưa khai mẫu ca nào.', plant.name))
        tao = []
        d = tu_ngay
        while d <= den_ngay:
            for m in mau:
                if self.search_count([('plant_id', '=', plant.id),
                                      ('pattern_id', '=', m.id),
                                      ('ngay', '=', d)]):
                    continue
                bd = datetime.combine(d, time.min) + timedelta(
                    hours=m.gio_bat_dau)
                tao.append({
                    'plant_id': plant.id, 'pattern_id': m.id, 'ngay': d,
                    'date_start': bd,
                    'date_end': bd + timedelta(hours=m.so_gio),
                })
            d += timedelta(days=1)
        if tao:
            self.create(tao)
        return len(tao)
