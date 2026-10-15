# -*- coding: utf-8 -*-
"""Yêu cầu công việc — cửa vào, KHÁC lệnh công việc.

Vì sao phải có một bảng riêng chứ không cho tạo thẳng lệnh nháp
---------------------------------------------------------------
Người vận hành thấy vết dầu dưới chân trụ thì báo. Đó **chưa phải** một
lệnh công việc: chưa biết làm gì, chưa biết ai làm, chưa biết có đáng
làm không. Cho họ tạo thẳng lệnh nháp thì hai thứ hỏng cùng lúc:

* Danh sách lệnh lẫn giữa *việc đã quyết làm* và *việc mới có người
  nêu*. Mọi con số đếm trên lệnh — tồn đọng, quá hạn, tỷ lệ phòng
  ngừa — đều sai theo.
* Người nêu tự đặt mức ưu tiên, và **mọi thứ sẽ thành khẩn cấp**. Mức
  khẩn ở đây là *mức khẩn người nêu cảm thấy*, còn mức ưu tiên trên
  lệnh do người điều độ đặt sau khi so với phần việc còn lại — hai số
  khác nhau, gộp là mất cả hai.

Yêu cầu BỊ TỪ CHỐI vẫn nằm lại trong sổ
----------------------------------------
Đây là chỗ hầu hết hệ CMMS làm hỏng: từ chối xong thì bản ghi biến mất,
hoặc bị xoá. Hệ quả là không bao giờ trả lời được câu *"hiện trường đã
báo chuyện này 11 lần và 11 lần bị gạt"* — mà đó chính là câu đáng nghe
nhất trong sổ này. Nên từ chối là một **trạng thái**, bắt buộc kèm lý
do, và bản ghi ở lại vĩnh viễn.

Đồng hồ PHẢN HỒI, không phải đồng hồ hoàn thành
------------------------------------------------
Thứ đo ở đây là **bao lâu thì yêu cầu được phân loại**, không phải bao
lâu thì việc xong (việc xong đo ở lệnh). Không có đồng hồ này thì sổ
yêu cầu mục rữa trong im lặng: người nêu không biết có ai đọc không,
vài tháng sau thì không ai nêu nữa, và hệ thống trông rất sạch vì không
còn yêu cầu nào.

Trùng lặp thì CẢNH BÁO chứ không chặn
--------------------------------------
Hai người cùng báo một chuyện không phải lỗi — nó là *bằng chứng việc
đó rõ tới mức hai người độc lập đều thấy*. Chặn là vứt mất tín hiệu đó.
Nên chỉ đếm và hiện ra, rồi người phân loại gộp lại.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

NGUON = [
    ('operation', 'Vận hành báo'),
    ('alarm', 'Từ cảnh báo thiết bị'),
    ('field', 'Phát hiện tại hiện trường'),
    ('inspection', 'Qua kiểm tra, xem xét'),
    ('contractor', 'Nhà thầu báo'),
    ('other', 'Khác'),
]

TRANG_THAI = [
    ('new', 'Mới nêu'),
    ('in_review', 'Đang phân loại'),
    ('converted', 'Đã mở lệnh'),
    ('merged', 'Đã gộp vào lệnh khác'),
    ('rejected', 'Đã từ chối'),
]
DANG_CHO = ('new', 'in_review')


class EamWorkRequest(models.Model):
    _name = 'eam.work.request'
    _description = 'Yêu cầu công việc'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_request desc, id desc'

    name = fields.Char(
        string='Số hiệu', copy=False, index=True, readonly=True,
        default=lambda s: _('Mới'))
    title = fields.Char(string='Nội dung yêu cầu', required=True,
                        tracking=True)
    description = fields.Text(
        string='Mô tả',
        help='Thấy gì, ở đâu, lúc nào. Càng cụ thể thì người phân loại '
             'càng ít phải đi hỏi lại — và đi hỏi lại là chỗ sổ yêu cầu '
             'hay tắc nhất.')

    source = fields.Selection(
        NGUON, string='Nguồn', required=True, default='operation',
        index=True, tracking=True)
    location_id = fields.Many2one(
        'eam.location', string='Vị trí', required=True, ondelete='restrict',
        index=True, tracking=True)
    asset_id = fields.Many2one(
        'eam.asset', string='Thiết bị', compute='_compute_asset', store=True,
        readonly=False, index=True,
        help='Suy từ vị trí: thiết bị đang lắp ở đó. Sửa được khi yêu cầu '
             'chỉ đích danh một cấu phần bên trong.')

    # Mức khẩn NGƯỜI NÊU cảm thấy — KHÁC mức ưu tiên người điều độ đặt
    # trên lệnh. Để người nêu đặt mức ưu tiên thì mọi thứ thành khẩn cấp.
    urgency = fields.Selection(
        [('low', 'Có thể đợi'),
         ('normal', 'Bình thường'),
         ('high', 'Cần sớm'),
         ('immediate', 'Phải xử lý ngay')],
        string='Mức khẩn (người nêu)', required=True, default='normal',
        tracking=True)
    safety_concern = fields.Boolean(
        string='Có nguy cơ mất an toàn', tracking=True,
        help='Tách riêng khỏi mức khẩn: một việc có thể không gấp về sản '
             'lượng nhưng vẫn là nguy cơ an toàn, và nó phải nổi lên bất '
             'kể xếp hàng thế nào.')

    requester_id = fields.Many2one(
        'res.users', string='Người nêu', required=True,
        default=lambda s: s.env.user, tracking=True)
    date_request = fields.Datetime(
        string='Nêu lúc', required=True, default=fields.Datetime.now,
        index=True, tracking=True)

    state = fields.Selection(
        TRANG_THAI, string='Trạng thái', required=True, default='new',
        index=True, tracking=True, copy=False)
    triage_user_id = fields.Many2one(
        'res.users', string='Người phân loại', readonly=True, copy=False)
    date_triage = fields.Datetime(
        string='Phân loại lúc', readonly=True, copy=False, tracking=True)
    reject_reason = fields.Text(
        string='Lý do từ chối', copy=False, tracking=True)

    wo_id = fields.Many2one(
        'eam.work.order', string='Lệnh công việc', copy=False, index=True,
        ondelete='set null', tracking=True)
    wo_state = fields.Selection(related='wo_id.state', string='Trạng thái lệnh')

    # ------------------------------------------------------------------
    # Đồng hồ PHẢN HỒI
    # ------------------------------------------------------------------
    response_hours = fields.Float(
        string='Giờ tới khi phân loại', compute='_compute_phan_hoi',
        store=True, digits=(16, 1), aggregator='avg',
        help='Từ lúc nêu tới lúc có người phân loại. Chưa phân loại thì '
             'tính TỚI HÔM NAY — để nó không đứng im và trông như vẫn còn '
             'trong hạn.')
    is_overdue = fields.Boolean(
        string='Quá hạn phản hồi', compute='_compute_phan_hoi', store=True,
        index=True)
    dup_count = fields.Integer(
        string='Yêu cầu đang chờ cùng vị trí', compute='_compute_dup')

    company_id = fields.Many2one(
        related='location_id.company_id', store=True, index=True)

    # Khoá do APP sinh ra, để gửi lại không tạo trùng.
    #
    # Ngoài hiện trường mất sóng là chuyện thường: app gửi lệnh tạo, sóng
    # rớt đúng lúc máy chủ đã ghi xong nhưng câu trả lời không về tới
    # máy. App không có cách nào biết, nên nó sẽ gửi lại — và thành hai
    # yêu cầu y hệt. Cập nhật theo id thì gửi lại bao nhiêu lần cũng vô
    # hại, nhưng TẠO MỚI thì không: đây là chỗ duy nhất trong hàng đợi
    # offline cần khoá chống trùng.
    client_key = fields.Char(
        string='Khoá chống trùng', copy=False, index=True, readonly=True,
        help='Do app hiện trường sinh ra, duy nhất cho mỗi lần nêu. Gửi '
             'lại cùng khoá thì máy chủ trả về bản ghi cũ chứ không tạo '
             'thêm.')

    _uniq_client_key = models.Constraint(
        'UNIQUE(client_key)', 'Khoá chống trùng đã được dùng.')

    # ------------------------------------------------------------------
    @api.depends('location_id', 'date_request')
    def _compute_asset(self):
        I = self.env['eam.installation']
        for r in self:
            if not r.location_id:
                r.asset_id = False
                continue
            ngay = (r.date_request or fields.Datetime.now()).date()
            lap = I.search(
                [('location_id', '=', r.location_id.id),
                 ('date_install', '<=', ngay),
                 '|', ('date_remove', '=', False),
                 ('date_remove', '>=', ngay)],
                order='date_install desc', limit=1)
            r.asset_id = lap.asset_id.id if lap else False

    @api.depends('date_request', 'date_triage', 'state', 'urgency',
                 'safety_concern')
    def _compute_phan_hoi(self):
        gio = fields.Datetime.now()
        han = self._han_phan_hoi()
        for r in self:
            moc = r.date_triage or gio
            r.response_hours = (
                (moc - r.date_request).total_seconds() / 3600.0
                if r.date_request else 0.0)
            if r.state not in DANG_CHO:
                # Đã phân loại rồi thì "quá hạn" là chuyện đã qua, không
                # còn là việc phải làm — giữ cờ bật sẽ làm danh sách cần
                # xử lý không bao giờ rỗng.
                r.is_overdue = False
                continue
            r.is_overdue = r.response_hours > han.get(
                'safety' if r.safety_concern else r.urgency, 48.0)

    @api.model
    def _han_phan_hoi(self):
        """Hạn phản hồi theo giờ. Đổi được bằng tham số hệ thống."""
        P = self.env['ir.config_parameter'].sudo()

        def lay(k, md):
            try:
                return float(P.get_param('eam_work_order.triage_%s' % k, md))
            except (TypeError, ValueError):
                return md
        return {
            'safety': lay('safety', 4.0),
            'immediate': lay('immediate', 4.0),
            'high': lay('high', 24.0),
            'normal': lay('normal', 48.0),
            'low': lay('low', 168.0),
        }

    def _compute_dup(self):
        for r in self:
            r.dup_count = self.search_count([
                ('location_id', '=', r.location_id.id),
                ('state', 'in', list(DANG_CHO)),
                ('id', '!=', r.id or 0),
            ]) if r.location_id else 0

    @api.depends('name', 'title')
    def _compute_display_name(self):
        for r in self:
            r.display_name = '%s — %s' % (r.name or '', r.title or '')

    @api.constrains('state', 'reject_reason')
    def _check_ly_do_tu_choi(self):
        for r in self:
            if r.state == 'rejected' and not (r.reject_reason or '').strip():
                raise ValidationError(_(
                    'Từ chối yêu cầu "%s" thì phải ghi lý do. Yêu cầu bị '
                    'từ chối vẫn nằm lại trong sổ chính là để sau này trả '
                    'lời được câu "hiện trường đã báo chuyện này mấy lần '
                    'và vì sao lần nào cũng bị gạt" — không có lý do thì '
                    'câu đó vô nghĩa.', r.title or ''))

    @api.model
    def ghi_tu_hien_truong(self, vals):
        """Cửa vào cho app hiện trường — CHỐNG TRÙNG theo ``client_key``.

        Trả về id của bản ghi. Gửi lại cùng khoá thì trả về id cũ, không
        tạo thêm. Phải đi qua đây chứ không gọi thẳng ``create``, vì
        ``create`` không biết gì về việc gửi lại.
        """
        khoa = (vals or {}).get('client_key')
        if khoa:
            cu = self.search([('client_key', '=', khoa)], limit=1)
            if cu:
                return cu.id
        return self.create(vals).id

    @api.model_create_multi
    def create(self, vals_list):
        for v in vals_list:
            if not v.get('name') or v['name'] == _('Mới'):
                v['name'] = self.env['ir.sequence'].next_by_code(
                    'eam.work.request') or _('Mới')
        rs = super().create(vals_list)
        for r in rs:
            if r.dup_count:
                # CẢNH BÁO, không chặn: hai người cùng báo một chuyện là
                # bằng chứng việc đó rõ, không phải lỗi nhập trùng.
                r.message_post(body=_(
                    'Vị trí này đang có %d yêu cầu khác chưa phân loại. '
                    'Nhiều người cùng báo thường nghĩa là việc đã rõ — '
                    'cân nhắc gộp khi phân loại.', r.dup_count))
        return rs

    # ------------------------------------------------------------------
    def _dong_dau_phan_loai(self):
        self.write({'triage_user_id': self.env.uid,
                    'date_triage': fields.Datetime.now()})

    def action_tiep_nhan(self):
        for r in self:
            if r.state != 'new':
                raise UserError(_('Yêu cầu "%s" không còn ở trạng thái mới.',
                                  r.name))
        # Mốc phản hồi tính từ lúc CÓ NGƯỜI NHẬN, không phải lúc mở lệnh:
        # nhận rồi mới đi khảo sát là chuyện bình thường, mà đồng hồ vẫn
        # phải dừng ở lúc nhận.
        self._dong_dau_phan_loai()
        self.write({'state': 'in_review'})
        return True

    def action_mo_lenh(self):
        """Chuyển thành lệnh công việc."""
        W = self.env['eam.work.order']
        for r in self:
            if r.state not in DANG_CHO:
                raise UserError(_(
                    'Yêu cầu "%s" đã được xử lý rồi.', r.name))
            if not r.date_triage:
                r._dong_dau_phan_loai()
            mo_ta = [r.description or '']
            mo_ta.append(_('Mở từ yêu cầu %(s)s do %(n)s nêu ngày %(d)s.',
                           s=r.name, n=r.requester_id.name or '',
                           d=r.date_request and r.date_request.date() or ''))
            if r.dup_count:
                mo_ta.append(_(
                    'Vị trí này còn %d yêu cầu khác chưa phân loại.',
                    r.dup_count))
            w = W.create({
                'title': r.title,
                # Mức ưu tiên do NGƯỜI ĐIỀU ĐỘ đặt, không chép thẳng mức
                # khẩn của người nêu. Chép thẳng là để người nêu quyết
                # thứ tự công việc của cả nhà máy.
                'priority': '3' if r.safety_concern else '1',
                'work_type': 'corrective',
                'location_id': r.location_id.id,
                'asset_id': r.asset_id.id or False,
                'detection_method': (
                    'scada' if r.source == 'alarm'
                    else 'inspection' if r.source == 'inspection'
                    else 'operator'),
                'date_planned_start': fields.Datetime.now(),
                'description': '\n\n'.join(x for x in mo_ta if x),
            })
            r.write({'state': 'converted', 'wo_id': w.id})
            w.message_post(body=_(
                'Lệnh này mở từ yêu cầu %(s)s — mức khẩn người nêu: '
                '%(m)s.%(at)s', s=r.name,
                m=dict(r._fields['urgency'].selection).get(r.urgency, ''),
                at=_(' CÓ NGUY CƠ MẤT AN TOÀN.') if r.safety_concern else ''))
        return True

    def action_gop(self):
        self.ensure_one()
        if self.state not in DANG_CHO:
            raise UserError(_('Yêu cầu "%s" đã được xử lý rồi.', self.name))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Gộp vào lệnh đang mở'),
            'res_model': 'eam.work.request.merge.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_request_ids': self.ids},
        }

    def action_tu_choi(self):
        self.ensure_one()
        if self.state not in DANG_CHO:
            raise UserError(_('Yêu cầu "%s" đã được xử lý rồi.', self.name))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Từ chối yêu cầu'),
            'res_model': 'eam.work.request.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_request_ids': self.ids},
        }

    def action_mo_lai(self):
        """Mở lại yêu cầu đã từ chối — giữ nguyên lý do cũ trong nhật ký."""
        for r in self:
            if r.state not in ('rejected', 'merged'):
                raise UserError(_(
                    'Chỉ mở lại được yêu cầu đã từ chối hoặc đã gộp.'))
            cu = r.reject_reason
            r.write({'state': 'in_review', 'reject_reason': False,
                     'wo_id': False})
            r.message_post(body=_(
                'Mở lại yêu cầu. Lý do từ chối trước đó: %s', cu or '—'))
        return True

    def action_xem_trung(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Yêu cầu đang chờ cùng vị trí'),
            'res_model': 'eam.work.request',
            'view_mode': 'list,form',
            'domain': [('location_id', '=', self.location_id.id),
                       ('state', 'in', list(DANG_CHO)),
                       ('id', '!=', self.id)],
        }


class EamWorkRequestMergeWizard(models.TransientModel):
    """Gộp yêu cầu vào một lệnh đang mở.

    Wizard tạm PHẢI khai quyền trong ``ir.model.access`` — admin cũng bị
    chặn, và lỗi hiện ra là "không có quyền" chứ không nói gì về việc
    thiếu khai báo.
    """
    _name = 'eam.work.request.merge.wizard'
    _description = 'Gộp yêu cầu vào lệnh'

    request_ids = fields.Many2many('eam.work.request', string='Yêu cầu',
                                   required=True)
    wo_id = fields.Many2one(
        'eam.work.order', string='Gộp vào lệnh', required=True,
        domain="[('state', 'in', ('draft','approved','planned','in_progress'))]")
    note = fields.Char(string='Ghi chú')

    @api.onchange('request_ids')
    def _onchange_request(self):
        # Gợi ý lệnh đang mở tại CÙNG VỊ TRÍ — gần như luôn là cái đúng,
        # và không gợi ý thì người dùng phải tự dò trong hàng trăm lệnh.
        vt = self.request_ids.mapped('location_id')
        if vt:
            return {'domain': {'wo_id': [
                ('state', 'in', ('draft', 'approved', 'planned',
                                 'in_progress')),
                ('location_id', 'in', vt.ids)]}}

    def action_xac_nhan(self):
        self.ensure_one()
        for r in self.request_ids:
            if not r.date_triage:
                r._dong_dau_phan_loai()
            r.write({'state': 'merged', 'wo_id': self.wo_id.id})
            self.wo_id.message_post(body=_(
                'Gộp thêm yêu cầu %(s)s: %(t)s%(n)s',
                s=r.name, t=r.title,
                n=' — ' + self.note if self.note else ''))
        return {'type': 'ir.actions.act_window_close'}


class EamWorkRequestRejectWizard(models.TransientModel):
    _name = 'eam.work.request.reject.wizard'
    _description = 'Từ chối yêu cầu'

    request_ids = fields.Many2many('eam.work.request', string='Yêu cầu',
                                   required=True)
    reason = fields.Text(string='Lý do từ chối', required=True)

    def action_xac_nhan(self):
        self.ensure_one()
        for r in self.request_ids:
            if not r.date_triage:
                r._dong_dau_phan_loai()
            r.write({'state': 'rejected', 'reject_reason': self.reason})
            r.message_post(body=_('Từ chối. Lý do: %s', self.reason))
        return {'type': 'ir.actions.act_window_close'}


class EamWorkOrder(models.Model):
    """Nối ngược: lệnh biết nó sinh ra từ những yêu cầu nào.

    Không có chiều ngược này thì người làm lệnh không biết ai đang chờ
    câu trả lời — và sổ yêu cầu mục rữa đúng như đã nói ở trên.
    """
    _inherit = 'eam.work.order'

    request_ids = fields.One2many(
        'eam.work.request', 'wo_id', string='Yêu cầu đã gộp')
    request_count = fields.Integer(string='Số yêu cầu',
                                   compute='_compute_request')

    @api.depends('request_ids')
    def _compute_request(self):
        for o in self:
            o.request_count = len(o.request_ids)

    def action_mo_yeu_cau(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Yêu cầu — %s', self.name),
            'res_model': 'eam.work.request',
            'view_mode': 'list,form',
            'domain': [('wo_id', '=', self.id)],
        }

    def action_dong_lenh(self):
        res = super().action_dong_lenh()
        # Đóng lệnh là lúc trả lời người đã nêu. Không báo lại thì lần
        # sau họ không nêu nữa — và mất hẳn một kênh phát hiện.
        for o in self:
            for r in o.request_ids:
                r.message_post(
                    body=_('Lệnh %s đã đóng. Yêu cầu này đã được xử lý.',
                           o.name),
                    partner_ids=r.requester_id.partner_id.ids)
        return res
