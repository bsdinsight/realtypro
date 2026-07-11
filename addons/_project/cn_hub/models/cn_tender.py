# -*- coding: utf-8 -*-
"""Gói thầu công bố lên Network + hồ sơ dự thầu của nhà thầu."""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class CnTender(models.Model):
    _name = 'cn.tender'
    _description = 'Gói thầu (Construction Network)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'deadline, id desc'

    name = fields.Char(string='Tên gói thầu', required=True, tracking=True)
    ref = fields.Char(
        string='Mã tham chiếu', copy=False, index=True,
        help='Mã gói thầu bên tổng thầu (đồng bộ qua connector).')
    gc_partner_id = fields.Many2one(
        'res.partner', string='Tổng thầu / Chủ đầu tư', tracking=True,
        help='Đơn vị công bố gói thầu.')
    gc_source = fields.Char(
        string='Nguồn (tenant)', help='Định danh hệ thống tổng thầu gửi lên.')
    description = fields.Text(string='Mô tả / phạm vi')
    specialty = fields.Char(string='Chuyên môn cần', index=True)
    budget = fields.Monetary(string='Dự toán / giá gói')
    currency_id = fields.Many2one(
        'res.currency', default=lambda self: self.env.company.currency_id)
    date_open = fields.Date(string='Ngày mở', default=fields.Date.context_today)
    deadline = fields.Date(string='Hạn nộp')
    state = fields.Selection(
        [('draft', 'Nháp'),
         ('open', 'Đang mời thầu'),
         ('closed', 'Đã đóng thầu'),
         ('awarded', 'Đã trao thầu'),
         ('cancelled', 'Đã hủy')],
        string='Trạng thái', default='draft', required=True, tracking=True)
    bid_ids = fields.One2many('cn.bid', 'tender_id', string='Hồ sơ dự thầu')
    bid_count = fields.Integer(compute='_compute_bid_count')
    awarded_bid_id = fields.Many2one(
        'cn.bid', string='Hồ sơ trúng thầu', copy=False)
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company)

    # Quy trình mời thầu
    dossier_ids = fields.One2many(
        'cn.tender.document', 'tender_id', string='Hồ sơ mời thầu',
        help='Tài liệu bên mời thầu cung cấp cho nhà thầu tải về.')
    doc_req_ids = fields.One2many(
        'cn.tender.doc.req', 'tender_id', string='Tài liệu yêu cầu nộp')
    invite_ids = fields.One2many(
        'cn.tender.invite', 'tender_id', string='Thư mời thầu')
    invite_count = fields.Integer(compute='_compute_invite_count')

    def _compute_invite_count(self):
        data = self.env['cn.tender.invite']._read_group(
            [('tender_id', 'in', self.ids)], groupby=['tender_id'],
            aggregates=['__count'])
        mapped = {t.id: c for t, c in data}
        for rec in self:
            rec.invite_count = mapped.get(rec.id, 0)

    def action_add_default_reqs(self):
        """Nạp checklist tài liệu yêu cầu mặc định (nếu chưa có)."""
        defaults = [
            ('Báo giá', 'quote', True),
            ('Phương án thi công', 'method', True),
            ('Hồ sơ năng lực', 'capability', True),
            ('Bảo lãnh dự thầu', 'guarantee', False),
            ('Tiến độ thi công', 'schedule', False),
        ]
        Req = self.env['cn.tender.doc.req']
        for tender in self:
            have = set(tender.doc_req_ids.mapped('doc_type'))
            seq = 10
            for name, dtype, req in defaults:
                if dtype in have:
                    continue
                Req.create({
                    'tender_id': tender.id, 'name': name, 'doc_type': dtype,
                    'required': req, 'sequence': seq})
                seq += 10
        return True

    def action_view_invites(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Thư mời thầu — %s', self.name),
            'res_model': 'cn.tender.invite',
            'view_mode': 'list,form',
            'domain': [('tender_id', '=', self.id)],
            'context': {'default_tender_id': self.id},
        }

    def action_send_all_invites(self):
        """Gửi thư mời cho các thư còn ở trạng thái Nháp."""
        self.ensure_one()
        drafts = self.invite_ids.filtered(lambda i: i.state == 'draft')
        if not drafts:
            raise UserError(_('Không có thư mời nháp nào để gửi.'))
        drafts.action_send_invite()
        return True

    def _compute_bid_count(self):
        data = self.env['cn.bid']._read_group(
            [('tender_id', 'in', self.ids)], groupby=['tender_id'],
            aggregates=['__count'])
        mapped = {t.id: c for t, c in data}
        for rec in self:
            rec.bid_count = mapped.get(rec.id, 0)

    def action_open(self):
        self.write({'state': 'open'})

    def action_close(self):
        self.write({'state': 'closed'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_view_bids(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Hồ sơ dự thầu — %s', self.name),
            'res_model': 'cn.bid',
            'view_mode': 'list,form',
            'domain': [('tender_id', '=', self.id)],
            'context': {'default_tender_id': self.id},
        }


class CnBid(models.Model):
    _name = 'cn.bid'
    _description = 'Hồ sơ dự thầu (Construction Network)'
    _inherit = ['mail.thread']
    _order = 'price, id'

    tender_id = fields.Many2one(
        'cn.tender', string='Gói thầu', required=True, ondelete='cascade',
        index=True)
    contractor_id = fields.Many2one(
        'res.partner', string='Nhà thầu', required=True, tracking=True,
        index=True)
    price = fields.Monetary(string='Giá dự thầu', tracking=True)
    currency_id = fields.Many2one(related='tender_id.currency_id')
    note = fields.Text(string='Thuyết minh')
    doc = fields.Binary(string='Hồ sơ (file, cũ)')
    doc_filename = fields.Char()
    document_ids = fields.One2many(
        'cn.bid.document', 'bid_id', string='Tài liệu nộp')
    document_count = fields.Integer(compute='_compute_document_count')
    schedule_task_ids = fields.One2many(
        'cn.bid.schedule.task', 'bid_id', string='Kế hoạch thi công')
    schedule_count = fields.Integer(compute='_compute_schedule_count')
    is_submitted = fields.Boolean(
        string='Đã nộp chính thức', tracking=True, copy=False)
    submitted_date = fields.Datetime(string='Ngày nộp chính thức', copy=False)
    date_submit = fields.Datetime(
        string='Ngày tạo/cập nhật', default=fields.Datetime.now)
    state = fields.Selection(
        [('submitted', 'Đã nộp'),
         ('shortlisted', 'Vào danh sách ngắn'),
         ('awarded', 'Trúng thầu'),
         ('rejected', 'Bị loại')],
        string='Trạng thái', default='submitted', required=True,
        tracking=True)
    company_id = fields.Many2one(related='tender_id.company_id', store=True)

    def _compute_document_count(self):
        for rec in self:
            rec.document_count = len(rec.document_ids)

    def _compute_schedule_count(self):
        for rec in self:
            rec.schedule_count = len(rec.schedule_task_ids)

    _uniq_bid = models.Constraint(
        'unique(tender_id, contractor_id)',
        'Mỗi nhà thầu chỉ nộp 1 hồ sơ / gói thầu.')

    def action_award(self):
        for bid in self:
            if bid.tender_id.state not in ('open', 'closed'):
                raise UserError(_(
                    'Chỉ trao thầu khi gói đang mời/đã đóng thầu.'))
            bid.state = 'awarded'
            bid.tender_id.write({
                'state': 'awarded', 'awarded_bid_id': bid.id})
            (bid.tender_id.bid_ids - bid).filtered(
                lambda b: b.state != 'rejected').write({'state': 'rejected'})

    def action_shortlist(self):
        self.write({'state': 'shortlisted'})

    def action_reject(self):
        self.write({'state': 'rejected'})

    # ------------------------------------------------------------------
    # Kế hoạch thi công — import MS Project XML / Excel
    # ------------------------------------------------------------------
    def _import_schedule(self, data, filename):
        """Parse file → thay toàn bộ kế hoạch của hồ sơ. Trả số dòng."""
        from . import cn_schedule
        self.ensure_one()
        fname = (filename or '').lower()
        if fname.endswith('.xml'):
            rows = cn_schedule.parse_mspdi(data)
        else:
            rows = cn_schedule.parse_excel(data)
        if not rows:
            return 0
        self.schedule_task_ids.unlink()
        Task = self.env['cn.bid.schedule.task']
        seq = 10
        for r in rows:
            Task.create({
                'bid_id': self.id, 'sequence': seq,
                'external_uid': r.get('uid') or False,
                'wbs_code': r.get('wbs') or False,
                'name': r['name'],
                'date_start': r.get('start') or False,
                'date_end': r.get('finish') or False,
                'progress_percent': r.get('percent') or 0.0,
                'is_milestone': r.get('milestone') or False,
                'predecessors': r.get('predecessors') or False,
            })
            seq += 10
        return len(rows)

    # ------------------------------------------------------------------
    # Nộp hồ sơ chính thức + thông báo bên mời thầu
    # ------------------------------------------------------------------
    def _missing_required_docs(self):
        """Danh sách tên tài liệu BẮT BUỘC chưa nộp (theo checklist gói)."""
        self.ensure_one()
        req = self.tender_id.doc_req_ids.filtered('required')
        have = self.document_ids.mapped('req_id').ids
        return [r.name for r in req if r.id not in have]

    def action_submit(self):
        """Nhà thầu nộp hồ sơ chính thức → khoá mốc + báo bên mời thầu."""
        for bid in self:
            missing = bid._missing_required_docs()
            if missing:
                raise UserError(_(
                    "Chưa nộp đủ tài liệu bắt buộc:\n- %s",
                    '\n- '.join(missing)))
            bid.write({
                'is_submitted': True,
                'submitted_date': fields.Datetime.now(),
                'date_submit': fields.Datetime.now(),
            })
            bid._notify_gc_submitted()
        return True

    def _notify_gc_submitted(self):
        """Báo bên mời thầu: chatter trên gói + email (nếu có địa chỉ)."""
        self.ensure_one()
        tender = self.tender_id
        body = _(
            "Nhà thầu <b>%(nt)s</b> đã nộp hồ sơ dự thầu"
            "%(price)s.",
            nt=self.contractor_id.name,
            price=(_(" — giá %s") % self.price) if self.price else '')
        gc = tender.gc_partner_id
        tender.message_post(
            body=body,
            partner_ids=gc.ids if gc else [],
            subtype_xmlid='mail.mt_comment')
        template = self.env.ref(
            'cn_hub.mail_template_bid_submitted', raise_if_not_found=False)
        if template and gc and gc.email:
            template.send_mail(self.id, force_send=False)
