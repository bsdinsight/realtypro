# -*- coding: utf-8 -*-
"""Bảo quản hàng lưu kho (KHO-27), dụng cụ cho mượn (KHO-29), hiệu chuẩn
thiết bị đo (KHO-30).

Bảo quản hàng LƯU KHO khác bảo trì phòng ngừa
----------------------------------------------
``eam_pm`` nhắm vào **tài sản đã lắp**, đếm chu kỳ theo giờ máy chạy.
Một con hộp số nằm trong kho thì giờ máy chạy bằng 0 mãi mãi, nên nó
không bao giờ tới hạn — trong khi thực tế nó vẫn phải xoay trục hằng
quý cho dầu tráng đều, vẫn phải thay hạt hút ẩm, vẫn phải kiểm niêm
phong.

Hai thứ khác nhau, hai lịch khác nhau. Gộp vào một chỗ thì hoặc là hàng
trong kho bị bỏ quên, hoặc là báo cáo khả dụng của máy bị tính sai.

Hiệu chuẩn: cái nguy hiểm không phải thiếu giấy
------------------------------------------------
Một cờ-lê lực quá hạn hiệu chuẩn vẫn quay, vẫn kêu tách, vẫn cho một con
số. Con số đó **trông đúng** — và bu-lông bắt non lực thì vài tháng sau
mới gãy. Nên luật ở đây không phải "nhắc gia hạn giấy", mà là **chặn
không cho mượn**.

Mất dụng cụ là mất im lặng
---------------------------
Không có sổ mượn thì dụng cụ biến mất dần mà không ai biết lúc nào, và
không ai chịu trách nhiệm. Sổ mượn có hạn trả là thứ duy nhất làm việc
đó lộ ra.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

LOAI_BAO_QUAN = [
    ('rotate', 'Xoay trục / đảo chiều'),
    ('desiccant', 'Thay hạt hút ẩm'),
    ('recharge', 'Nạp lại ắc-quy'),
    ('preserve', 'Bôi mỡ bảo quản / chống gỉ'),
    ('seal', 'Kiểm tra niêm phong, bao gói'),
    ('inspect', 'Kiểm tra ngoại quan'),
    ('other', 'Khác'),
]


class EamStorageCarePlan(models.Model):
    _name = 'eam.storage.care.plan'
    _description = 'Lịch bảo quản hàng lưu kho'
    _order = 'product_tmpl_id, sequence, id'

    name = fields.Char(string='Việc cần làm', required=True)
    sequence = fields.Integer(default=10)
    product_tmpl_id = fields.Many2one(
        'product.template', string='Áp cho vật tư', required=True,
        ondelete='cascade', index=True)
    care_type = fields.Selection(LOAI_BAO_QUAN, string='Loại việc',
                                 required=True, default='inspect')
    interval_months = fields.Integer(
        string='Chu kỳ (tháng)', required=True, default=3,
        help='Đếm từ lần làm xong GẦN NHẤT, không phải từ ngày nhập kho.')
    instruction = fields.Text(string='Hướng dẫn / yêu cầu OEM')
    active = fields.Boolean(default=True)

    @api.constrains('interval_months')
    def _check_chu_ky(self):
        for p in self:
            if p.interval_months <= 0:
                raise UserError(_(
                    'Chu kỳ phải lớn hơn 0 tháng — chu kỳ 0 nghĩa là lúc '
                    'nào cũng quá hạn, và danh sách quá hạn mà lúc nào '
                    'cũng đầy thì không ai đọc nữa.'))


class EamStorageCare(models.Model):
    _name = 'eam.storage.care'
    _description = 'Lần bảo quản hàng lưu kho'
    _inherit = ['mail.thread']
    _order = 'date_due, id'

    plan_id = fields.Many2one(
        'eam.storage.care.plan', string='Theo lịch', required=True,
        ondelete='restrict')
    lot_id = fields.Many2one(
        'stock.lot', string='Lô / sê-ri', required=True, index=True,
        ondelete='cascade')
    product_id = fields.Many2one(
        'product.product', related='lot_id.product_id', store=True,
        string='Vật tư')
    location_id = fields.Many2one(
        'stock.location', string='Đang ở', compute='_compute_location')
    date_due = fields.Date(string='Đến hạn', required=True, tracking=True)
    date_done = fields.Date(string='Đã làm ngày', tracking=True)
    user_id = fields.Many2one('res.users', string='Người làm')
    state = fields.Selection(
        [('due', 'Chờ làm'), ('done', 'Đã làm'), ('skipped', 'Bỏ qua')],
        string='Trạng thái', default='due', required=True, tracking=True)
    qua_han = fields.Boolean(string='Quá hạn', compute='_compute_qua_han',
                             search='_search_qua_han')
    note = fields.Text(string='Ghi nhận')
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda s: s.env.company)

    def _compute_location(self):
        Q = self.env['stock.quant']
        for r in self:
            q = Q.search([('lot_id', '=', r.lot_id.id),
                          ('location_id.usage', '=', 'internal'),
                          ('quantity', '>', 0)], limit=1)
            r.location_id = q.location_id.id if q else False

    def _compute_qua_han(self):
        hn = fields.Date.context_today(self)
        for r in self:
            r.qua_han = bool(r.state == 'due' and r.date_due
                             and r.date_due < hn)

    def _search_qua_han(self, operator, value):
        hn = fields.Date.context_today(self)
        dom = [('state', '=', 'due'), ('date_due', '<', hn)]
        if (operator == '=' and not value) or (operator == '!=' and value):
            return ['!'] + dom
        return dom

    def action_hoan_thanh(self):
        """Làm xong thì SINH NGAY lần kế tiếp — đếm từ hôm nay.

        Đếm từ ngày đến hạn cũ thì một lần trễ ba tháng sẽ kéo lệch toàn
        bộ chuỗi về sau, và lần nào cũng trễ.
        """
        from dateutil.relativedelta import relativedelta
        hn = fields.Date.context_today(self)
        for r in self:
            if r.state != 'due':
                raise UserError(_('Lần này đã xử lý rồi.'))
            r.write({'state': 'done', 'date_done': hn,
                     'user_id': self.env.user.id})
            self.create({
                'plan_id': r.plan_id.id, 'lot_id': r.lot_id.id,
                'date_due': hn + relativedelta(
                    months=r.plan_id.interval_months),
            })
        return True


class EamToolCalibration(models.Model):
    _name = 'eam.tool.calibration'
    _description = 'Lần hiệu chuẩn dụng cụ đo'
    _inherit = ['mail.thread']
    _order = 'date desc, id desc'

    lot_id = fields.Many2one(
        'stock.lot', string='Dụng cụ (sê-ri)', required=True, index=True,
        ondelete='cascade')
    product_id = fields.Many2one(
        'product.product', related='lot_id.product_id', store=True)
    date = fields.Date(string='Ngày hiệu chuẩn', required=True,
                       default=fields.Date.context_today, tracking=True)
    date_next = fields.Date(string='Hiệu chuẩn lại trước ngày',
                            required=True, tracking=True)
    body = fields.Char(string='Đơn vị hiệu chuẩn', required=True)
    cert_no = fields.Char(string='Số giấy chứng nhận', required=True)
    result = fields.Selection(
        [('pass', 'Đạt'), ('adjusted', 'Đạt sau hiệu chỉnh'),
         ('fail', 'Không đạt')],
        string='Kết quả', required=True, default='pass', tracking=True)
    attachment_ids = fields.Many2many(
        'ir.attachment', 'eam_calib_att_rel', 'calib_id', 'att_id',
        string='Giấy chứng nhận')
    note = fields.Text(string='Ghi chú')
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda s: s.env.company)

    @api.model_create_multi
    def create(self, vals_list):
        r = super().create(vals_list)
        r._cap_nhat_lo()
        return r

    def write(self, vals):
        res = super().write(vals)
        self._cap_nhat_lo()
        return res

    def _cap_nhat_lo(self):
        """Đẩy kết quả mới nhất lên chính dụng cụ, để chỗ cấm mượn đọc
        được mà không phải dò lịch sử."""
        for r in self:
            moi = self.search([('lot_id', '=', r.lot_id.id)],
                              order='date desc', limit=1)
            r.lot_id.write({
                'eam_calib_due': moi.date_next,
                'eam_calib_ok': moi.result in ('pass', 'adjusted'),
            })


class StockLotTool(models.Model):
    _inherit = 'stock.lot'

    eam_calib_due = fields.Date(string='Hiệu chuẩn lại trước ngày')
    eam_calib_ok = fields.Boolean(string='Lần hiệu chuẩn gần nhất đạt',
                                  default=True)
    eam_calib_ids = fields.One2many(
        'eam.tool.calibration', 'lot_id', string='Lịch sử hiệu chuẩn')
    eam_dung_duoc = fields.Boolean(
        string='Còn dùng được', compute='_compute_dung_duoc',
        help='Dụng cụ đo quá hạn hiệu chuẩn vẫn quay, vẫn kêu tách, vẫn '
             'cho một con số — và con số đó TRÔNG ĐÚNG. Nên hết hạn là '
             'cấm mượn, không phải nhắc nhở.')

    @api.depends('eam_calib_due', 'eam_calib_ok')
    def _compute_dung_duoc(self):
        hn = fields.Date.context_today(self)
        for l in self:
            if not l.eam_calib_due:
                l.eam_dung_duoc = True        # không phải dụng cụ đo
            else:
                l.eam_dung_duoc = bool(
                    l.eam_calib_ok and l.eam_calib_due >= hn)


class EamToolLoan(models.Model):
    _name = 'eam.tool.loan'
    _description = 'Phiếu mượn dụng cụ'
    _inherit = ['mail.thread']
    _order = 'date_out desc, id desc'

    name = fields.Char(string='Số phiếu', required=True, copy=False,
                       readonly=True, default=lambda s: _('Mới'))
    lot_id = fields.Many2one(
        'stock.lot', string='Dụng cụ (sê-ri)', tracking=True)
    product_id = fields.Many2one(
        'product.product', string='Dụng cụ', required=True,
        domain="[('eam_part_kind', '=', 'tool')]")
    qty = fields.Float(string='Số lượng', default=1.0, required=True)
    borrower_id = fields.Many2one(
        'res.users', string='Người mượn', required=True, tracking=True,
        default=lambda s: s.env.user)
    work_order_id = fields.Many2one(
        'eam.work.order', string='Dùng cho lệnh')
    date_out = fields.Date(string='Ngày mượn', required=True, tracking=True,
                           default=fields.Date.context_today)
    date_due = fields.Date(string='Hẹn trả', required=True, tracking=True)
    date_in = fields.Date(string='Ngày trả', readonly=True, tracking=True)
    state = fields.Selection(
        [('out', 'Đang mượn'), ('returned', 'Đã trả'),
         ('lost', 'Báo mất')],
        string='Trạng thái', default='out', required=True, tracking=True)
    tinh_trang_tra = fields.Selection(
        [('ok', 'Còn tốt'), ('damaged', 'Hư hỏng'),
         ('calib', 'Cần hiệu chuẩn lại')],
        string='Tình trạng khi trả')
    qua_han = fields.Boolean(string='Quá hạn trả',
                             compute='_compute_qua_han', search='_search_qua_han')
    note = fields.Text(string='Ghi chú')
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda s: s.env.company)

    def _compute_qua_han(self):
        hn = fields.Date.context_today(self)
        for r in self:
            r.qua_han = bool(r.state == 'out' and r.date_due
                             and r.date_due < hn)

    def _search_qua_han(self, operator, value):
        hn = fields.Date.context_today(self)
        dom = [('state', '=', 'out'), ('date_due', '<', hn)]
        if (operator == '=' and not value) or (operator == '!=' and value):
            return ['!'] + dom
        return dom

    @api.model_create_multi
    def create(self, vals_list):
        for v in vals_list:
            if v.get('name', _('Mới')) == _('Mới'):
                v['name'] = self.env['ir.sequence'].next_by_code(
                    'eam.tool.loan') or _('Mới')
        r = super().create(vals_list)
        r._kiem_hieu_chuan()
        return r

    def _kiem_hieu_chuan(self):
        """CHẶN mượn dụng cụ đo quá hạn hiệu chuẩn (KHO-30)."""
        for r in self:
            l = r.lot_id
            if not l or not l.eam_calib_due:
                continue
            if not l.eam_dung_duoc:
                raise UserError(_(
                    'Dụng cụ "%(dc)s" %(ly_do)s — không cho mượn.\n\n'
                    'Dụng cụ đo hết hiệu lực vẫn cho ra một con số, và '
                    'con số đó trông đúng. Bu-lông bắt non lực thì vài '
                    'tháng sau mới gãy.',
                    dc=l.name,
                    ly_do=(_('hiệu chuẩn lần gần nhất KHÔNG ĐẠT')
                           if not l.eam_calib_ok
                           else _('quá hạn hiệu chuẩn từ %s',
                                  l.eam_calib_due))))

    def action_tra(self):
        for r in self:
            if r.state != 'out':
                raise UserError(_('Phiếu "%s" không ở trạng thái đang mượn.',
                                  r.name))
            if not r.tinh_trang_tra:
                raise UserError(_(
                    'Phải khai tình trạng khi trả. Nhận lại mà không nhìn '
                    'thì lần sau người khác mượn phải một cái hỏng.'))
            r.write({'state': 'returned',
                     'date_in': fields.Date.context_today(r)})
            if r.tinh_trang_tra == 'damaged' and r.lot_id:
                r.lot_id.eam_calib_ok = False
                r.message_post(body=_(
                    'Trả về trong tình trạng HƯ HỎNG — dụng cụ đã bị '
                    'khoá, không cho mượn tiếp.'))
            if r.tinh_trang_tra == 'calib' and r.lot_id:
                # Hạ cờ "lần hiệu chuẩn gần nhất đạt" chứ KHÔNG kéo hạn
                # về hôm nay: hạn hôm nay vẫn lọt qua phép so >= và dụng
                # cụ vẫn mượn được — khoá hụt còn tệ hơn không khoá, vì
                # người ta tưởng đã khoá.
                r.lot_id.eam_calib_ok = False
                r.message_post(body=_(
                    'Trả về với yêu cầu hiệu chuẩn lại — dụng cụ đã bị '
                    'khoá, không cho mượn tiếp cho tới khi có kết quả '
                    'hiệu chuẩn mới.'))
        return True

    def action_bao_mat(self):
        for r in self:
            r.state = 'lost'
            r.message_post(body=_(
                'Báo MẤT dụng cụ. Người mượn: %s.', r.borrower_id.name))
        return True
