# -*- coding: utf-8 -*-
"""rp.document — Sổ hồ sơ kỹ thuật của nhà thầu (điều 5.2).

Điều 5.2 của hợp đồng không nói về việc lưu trữ file. Nó là một CƠ CHẾ
THỜI HẠN, và ba câu trong đó quyết định ai được thi công khi nào:

1. "each review period shall not exceed 21 days, calculated from the date
   on which the Engineer receives a Contractor's Document AND the
   Contractor's notice" — đồng hồ 21 ngày chỉ chạy khi nhận được CẢ hồ sơ
   LẪN thông báo kèm theo. Nhà thầu gửi bản vẽ mà không kèm thông báo
   "hồ sơ đã sẵn sàng để xem xét" thì đồng hồ CHƯA chạy, và sau này không
   lấy đó làm căn cứ đòi gia hạn được.
2. "execution of such part of the Works shall not commence until the
   Engineer has approved the Contractor's Document" — hồ sơ trình để PHÊ
   DUYỆT thì chưa duyệt là chưa được thi công, không có ngoại lệ.
3. "shall not commence prior to the expiry of the review periods" — hồ sơ
   trình để XEM XÉT thì dù không ai trả lời cũng phải chờ hết hạn mới
   được làm, và làm thì tự chịu rủi ro.

Vậy nên sổ này giữ ba thứ cạnh nhau: đồng hồ xem xét, chuỗi lần trình, và
CỔNG — ngày sớm nhất mà phần việc dựa vào hồ sơ này được phép khởi công.
Thiếu cổng thì sổ hồ sơ chỉ là một cái tủ tài liệu; có cổng thì nó nói
được "việc này chưa làm được vì hồ sơ còn nằm trên bàn ai".

Hai điều khoản con cũng nằm trong sổ, vì chúng chặn BÀN GIAO chứ không
chặn khởi công: điều 5.6 (hồ sơ hoàn công) và 5.7 (tài liệu vận hành &
bảo trì) — "The Works shall not be considered to be completed for the
purposes of taking over … until the Engineer has received" chúng.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

DOC_TYPE = [
    ('design', 'Thiết kế / bản vẽ'),
    ('calculation', 'Tính toán, thuyết minh'),
    ('method', 'Biện pháp thi công'),
    ('spec', 'Đặc tính kỹ thuật, catalogue'),
    ('qa_qc', 'Kế hoạch & hồ sơ chất lượng'),
    ('hse', 'An toàn — sức khoẻ — môi trường'),
    ('test', 'Hồ sơ thí nghiệm, chạy thử'),
    ('permit', 'Hồ sơ xin phép, pháp lý'),
    ('as_built', 'Hồ sơ hoàn công (5.6)'),
    ('om_manual', 'Tài liệu vận hành & bảo trì (5.7)'),
    ('other', 'Khác'),
]

# Hồ sơ của hai điều khoản này chặn việc cấp chứng chỉ bàn giao.
TOC_TYPES = ('as_built', 'om_manual')

REVIEW_TRACK = [
    ('info', 'Chỉ để biết — không chặn thi công'),
    ('review', 'Trình để xem xét — hết hạn được làm, tự chịu rủi ro'),
    ('approval', 'Trình để phê duyệt — chưa duyệt là chưa được làm'),
]

DISCIPLINE = [
    ('civil', 'Xây dựng, nền móng'),
    ('structural', 'Kết cấu, cơ khí lắp dựng'),
    ('electrical', 'Điện, trạm biến áp'),
    ('transmission', 'Đường dây truyền tải'),
    ('scada', 'SCADA, điều khiển, thông tin'),
    ('mechanical', 'Cơ khí, thiết bị'),
    ('hse', 'An toàn, môi trường'),
    ('other', 'Khác'),
]

CLEARED_STATES = ('approved', 'approved_comment')

OUTCOME = [
    ('a', 'A — Duyệt / không có ý kiến'),
    ('b', 'B — Duyệt kèm ý kiến'),
    ('c', 'C — Không tuân thủ, sửa và trình lại'),
    ('d', 'D — Ghi nhận để biết'),
]


class RpDocument(models.Model):
    _name = 'rp.document'
    _description = 'Hồ sơ kỹ thuật phải trình (điều 5.2)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_required, code, id'

    code = fields.Char(string='Mã hồ sơ', copy=False, readonly=True,
                       index=True)
    name = fields.Char(string='Tên hồ sơ', required=True, tracking=True)
    doc_ref = fields.Char(
        string='Số hiệu của nhà thầu', tracking=True,
        help='Số hiệu bản vẽ / tài liệu theo hệ thống của nhà thầu. Đây là '
             'số mà hai bên dẫn chiếu trong công văn.')
    doc_type = fields.Selection(
        DOC_TYPE, string='Loại hồ sơ', required=True, default='design',
        tracking=True)
    discipline = fields.Selection(DISCIPLINE, string='Bộ môn',
                                  default='civil')
    review_track = fields.Selection(
        REVIEW_TRACK, string='Trình để', required=True, default='approval',
        tracking=True,
        help='Điều 5.2 phân biệt rất rõ hai luồng, và hệ quả khác nhau '
             'hoàn toàn: "để phê duyệt" thì phải có phê duyệt mới được '
             'thi công; "để xem xét" thì hết hạn xem xét là được làm, '
             'nhưng tự chịu rủi ro.')

    project_id = fields.Many2one(
        're.project', string='Dự án', required=True, index=True)
    contract_id = fields.Many2one(
        'rp.contract', string='HĐ nhà thầu', index=True, tracking=True,
        domain="[('project_id', '=', project_id)]")
    partner_id = fields.Many2one(
        'res.partner', related='contract_id.contractor_id',
        string='Nhà thầu', store=True, index=True)
    structure_id = fields.Many2one(
        'rp.structure', string='Hạng mục',
        domain="[('project_id', '=', project_id)]")
    description = fields.Text(string='Phạm vi hồ sơ')

    # --- Đồng hồ xem xét của điều 5.2 ------------------------------
    date_required = fields.Date(
        string='Hạn phải trình', tracking=True,
        help='Ngày nhà thầu phải trình theo ma trận hồ sơ của hợp đồng '
             '(Annex 16) hoặc theo lịch thi công.')
    date_submitted = fields.Date(string='Ngày nhận hồ sơ', copy=False,
                                 tracking=True)
    date_notice = fields.Date(
        string='Ngày nhận thông báo 5.2', copy=False, tracking=True,
        help='Ngày nhận được thông báo của nhà thầu nói rằng hồ sơ đã sẵn '
             'sàng để xem xét (và phê duyệt), kèm khẳng định hồ sơ phù hợp '
             'hợp đồng hay không phù hợp đến mức nào. KHÔNG có thông báo '
             'này thì đồng hồ 21 ngày chưa chạy.')
    review_days = fields.Integer(
        string='Hạn xem xét (ngày)', default=21, tracking=True,
        help='Điều 5.2: không quá 21 ngày, trừ khi Yêu cầu của chủ đầu tư '
             'quy định khác. Lấy mặc định theo hợp đồng.')
    clock_start = fields.Date(
        string='Đồng hồ chạy từ', compute='_compute_clock', store=True,
        help='Ngày muộn hơn giữa ngày nhận hồ sơ và ngày nhận thông báo.')
    review_deadline = fields.Date(
        string='Hạn chót xem xét', compute='_compute_clock', store=True,
        index=True)
    submit_late_days = fields.Integer(
        string='Trình trễ (ngày)', compute='_compute_clock', store=True)
    review_late_days = fields.Integer(
        string='Xem xét trễ (ngày)', compute='_compute_clock', store=True,
        help='Số ngày bên xem xét vượt quá hạn 21 ngày. Đây là căn cứ để '
             'nhà thầu đòi gia hạn, nên phải giữ cả sau khi đã trả lời.')
    date_reviewed = fields.Date(string='Ngày có ý kiến', copy=False,
                                tracking=True)
    reviewer_id = fields.Many2one('res.users', string='Người xem xét',
                                  copy=False)
    review_note = fields.Text(
        string='Ý kiến xem xét',
        help='Nội dung không phù hợp (nếu trả lại) hoặc điều kiện kèm theo '
             '(nếu duyệt có ý kiến).')
    # Các chỉ số phụ thuộc NGÀY HÔM NAY — cố ý không lưu, vì số đã lưu sẽ
    # cũ dần mà không ai cập nhật. Lọc danh sách thì lọc trên
    # review_deadline, đó là mốc cố định.
    pending_notice = fields.Boolean(
        string='Chờ thông báo 5.2', compute='_compute_live',
        help='Đã nhận hồ sơ nhưng chưa có thông báo kèm theo — đồng hồ '
             'chưa chạy. Phải nhắc nhà thầu, không phải nhắc người duyệt.')
    is_review_overdue = fields.Boolean(string='Đang quá hạn xem xét',
                                       compute='_compute_live')
    days_left = fields.Integer(string='Còn lại (ngày)',
                              compute='_compute_live')
    gate_state = fields.Selection(
        [('none', 'Không chặn'),
         ('cleared', 'Đã mở cổng'),
         ('waiting', 'Đang chặn')],
        string='Cổng thi công', compute='_compute_live')

    # --- Cổng: hồ sơ này cho phép thi công từ ngày nào -------------
    gate_date = fields.Date(
        string='Được thi công từ', compute='_compute_gate', store=True,
        help='Ngày sớm nhất mà phần việc dựa vào hồ sơ này được phép khởi '
             'công: ngày phê duyệt nếu đã duyệt; hạn chót xem xét nếu đang '
             'trình (điều 5.2 buộc chờ hết hạn xem xét dù không ai trả '
             'lời); để trống nếu chưa trình hoặc bị trả lại.')
    gate_certain = fields.Boolean(
        string='Cổng đã chắc chắn', compute='_compute_gate', store=True,
        help='Đúng khi ngày mở cổng không còn phụ thuộc vào hành động của '
             'ai: đã được duyệt, hoặc là hồ sơ chỉ trình để xem xét nên '
             'chỉ cần hết hạn.')
    task_ids = fields.Many2many(
        'project.task', 'rp_document_task_rel', 'document_id', 'task_id',
        string='Công việc phụ thuộc hồ sơ',
        help='Những công việc không được khởi công trước khi hồ sơ này mở '
             'cổng. Khai vào đây thì lịch thi công tự biết việc nào đang '
             'chờ hồ sơ.')
    task_count = fields.Integer(string='Số việc phụ thuộc',
                                compute='_compute_task_count')

    is_toc_required = fields.Boolean(
        string='Phải có trước khi bàn giao', tracking=True,
        help='Điều 5.6 và 5.7: chưa nhận đủ hồ sơ hoàn công và tài liệu '
             'vận hành thì công trình CHƯA được coi là hoàn thành để bàn '
             'giao, dù hiện trường đã xong.')

    revision_ids = fields.One2many(
        'rp.document.revision', 'document_id', string='Các lần trình')
    revision = fields.Integer(
        string='Lần trình', default=0, readonly=True, copy=False,
        help='Rev 0 là lần trình đầu. Mỗi lần bị trả lại rồi trình lại là '
             'tăng một — và theo điều 5.2, chi phí làm lại là của nhà thầu.')
    claim_id = fields.Many2one('rp.claim', string='Khiếu nại liên quan',
                               copy=False)

    state = fields.Selection([
        ('planned', 'Chưa trình'),
        ('submitted', 'Đang xem xét'),
        ('approved', 'Đã duyệt'),
        ('approved_comment', 'Duyệt kèm ý kiến'),
        ('rejected', 'Trả lại — sửa và trình lại'),
        ('cancelled', 'Không áp dụng'),
    ], string='Trạng thái', default='planned', required=True,
        tracking=True, copy=False, index=True)
    active = fields.Boolean(default=True)

    # ------------------------------------------------------------------
    # Tính toán
    # ------------------------------------------------------------------
    @api.depends('date_submitted', 'date_notice', 'review_days',
                 'date_required', 'date_reviewed')
    def _compute_clock(self):
        for rec in self:
            start = False
            if rec.date_submitted and rec.date_notice:
                # Đồng hồ chạy từ khi có ĐỦ hai thứ, nên lấy ngày muộn hơn.
                start = max(rec.date_submitted, rec.date_notice)
            rec.clock_start = start
            rec.review_deadline = (
                fields.Date.add(start, days=rec.review_days or 0)
                if start else False)
            rec.submit_late_days = (
                (rec.date_submitted - rec.date_required).days
                if rec.date_submitted and rec.date_required
                and rec.date_submitted > rec.date_required else 0)
            rec.review_late_days = (
                (rec.date_reviewed - rec.review_deadline).days
                if rec.date_reviewed and rec.review_deadline
                and rec.date_reviewed > rec.review_deadline else 0)

    def _compute_live(self):
        today = fields.Date.context_today(self)
        for rec in self:
            # "Đang quá hạn" là CHƯA CÓ câu trả lời. Có ý kiến rồi thì số
            # ngày trễ chuyển sang review_late_days và giữ ở đó làm bằng
            # chứng, chứ không còn là việc phải đi nhắc.
            waiting = rec.state == 'submitted' and not rec.date_reviewed
            rec.pending_notice = bool(waiting and rec.date_submitted
                                      and not rec.date_notice)
            rec.is_review_overdue = bool(
                waiting and rec.review_deadline
                and rec.review_deadline < today)
            rec.days_left = ((rec.review_deadline - today).days
                             if waiting and rec.review_deadline else 0)
            if rec.review_track == 'info' or rec.state == 'cancelled':
                rec.gate_state = 'none'
            elif rec.state in CLEARED_STATES:
                rec.gate_state = 'cleared'
            elif (rec.review_track == 'review' and waiting
                    and rec.review_deadline and rec.review_deadline <= today):
                # Hết hạn xem xét mà không ai trả lời: điều 5.2 cho phép
                # thi công, nhưng rủi ro là của nhà thầu.
                rec.gate_state = 'cleared'
            else:
                rec.gate_state = 'waiting'

    @api.depends('review_track', 'state', 'date_reviewed', 'review_deadline')
    def _compute_gate(self):
        for rec in self:
            if rec.review_track == 'info' or rec.state == 'cancelled':
                rec.gate_date = False
                rec.gate_certain = True
            elif rec.state in CLEARED_STATES:
                rec.gate_date = rec.date_reviewed
                rec.gate_certain = True
            elif rec.state == 'submitted':
                rec.gate_date = rec.review_deadline
                # Trình để xem xét: chỉ cần hết hạn là đủ, nên ngày này
                # chắc chắn. Trình để phê duyệt: còn chờ người ta duyệt,
                # nên đây mới chỉ là dự kiến.
                rec.gate_certain = rec.review_track == 'review'
            else:
                rec.gate_date = False
                rec.gate_certain = False

    @api.depends('task_ids')
    def _compute_task_count(self):
        for rec in self:
            rec.task_count = len(rec.task_ids)

    @api.depends('code', 'name', 'revision')
    def _compute_display_name(self):
        for rec in self:
            label = f'[{rec.code}] {rec.name}' if rec.code else (
                rec.name or '')
            if rec.revision:
                label = f'{label} (Rev {rec.revision})'
            rec.display_name = label

    @api.onchange('doc_type')
    def _onchange_doc_type(self):
        """Hồ sơ hoàn công và tài liệu vận hành thì mặc định chặn bàn giao."""
        if self.doc_type in TOC_TYPES:
            self.is_toc_required = True

    @api.onchange('contract_id')
    def _onchange_contract_id(self):
        if self.contract_id:
            if self.contract_id.project_id:
                self.project_id = self.contract_id.project_id
            if self.contract_id.doc_review_days:
                self.review_days = self.contract_id.doc_review_days

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code'):
                vals['code'] = self.env['ir.sequence'].next_by_code(
                    'rp.document') or '/'
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # Luồng xử lý
    # ------------------------------------------------------------------
    def _log_revision(self, transmittal=None):
        """Mở một lần trình mới trong chuỗi hồ sơ."""
        self.ensure_one()
        return self.env['rp.document.revision'].create({
            'document_id': self.id,
            'rev_no': self.revision,
            'date_submitted': self.date_submitted,
            'date_notice': self.date_notice,
            'review_deadline': self.review_deadline,
            'transmittal_id': transmittal.id if transmittal else False,
        })

    def _submit(self, date=None, with_notice=True, transmittal=None):
        """Ghi nhận nhà thầu đã trình hồ sơ.

        ``with_notice`` là thông báo của điều 5.2. Không có nó thì hồ sơ
        vẫn nhận, nhưng đồng hồ xem xét chưa chạy — và sổ phải nói ra điều
        đó, nếu không hai bên sẽ đếm hạn từ hai ngày khác nhau.
        """
        date = date or fields.Date.context_today(self)
        for rec in self:
            if rec.state in CLEARED_STATES:
                raise UserError(_(
                    'Hồ sơ "%s" đã được duyệt. Muốn thay đổi thì dùng '
                    '"Trình lại" để mở lần trình mới — điều 5.2 buộc thông '
                    'báo ngay khi muốn sửa hồ sơ đã trình.', rec.name))
            rec.write({
                'state': 'submitted',
                'date_submitted': date,
                'date_notice': date if with_notice else False,
                'date_reviewed': False,
                'reviewer_id': False,
            })
            rec._log_revision(transmittal)
        return True

    def action_submit(self):
        return self._submit()

    def action_submit_no_notice(self):
        return self._submit(with_notice=False)

    def action_add_notice(self):
        """Nhà thầu gửi bổ sung thông báo 5.2 — đồng hồ bắt đầu chạy."""
        today = fields.Date.context_today(self)
        for rec in self:
            rec.date_notice = today
            rec.revision_ids[:1].write({
                'date_notice': today,
                'review_deadline': rec.review_deadline,
            })

    def _close_review(self, state, outcome):
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.state != 'submitted':
                raise UserError(_(
                    'Hồ sơ "%s" không ở trạng thái đang xem xét.', rec.name))
            rec.write({'state': state, 'date_reviewed': today,
                       'reviewer_id': self.env.user.id})
            rec.revision_ids[:1].write({
                'outcome': outcome, 'date_reviewed': today,
                'reviewer_id': self.env.user.id,
                'review_note': rec.review_note,
            })

    def action_approve(self):
        self._close_review('approved', 'a')

    def action_approve_comment(self):
        self._close_review('approved_comment', 'b')

    def action_reject(self):
        self._close_review('rejected', 'c')

    def action_resubmit(self):
        """Trình lại sau khi bị trả lại — chi phí làm lại của nhà thầu."""
        for rec in self:
            rec.revision += 1
        return self._submit()

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_reset(self):
        self.write({'state': 'planned', 'date_submitted': False,
                    'date_notice': False, 'date_reviewed': False,
                    'reviewer_id': False})

    def action_create_review_claim(self):
        """Mở khiếu nại gia hạn khi bên xem xét để quá hạn 21 ngày.

        Quá hạn xem xét là lỗi của bên chủ đầu tư / nhà tư vấn, và theo
        điều 5.2 công việc liên quan KHÔNG được khởi công trong lúc chờ —
        nên số ngày quá hạn chính là số ngày nhà thầu xin gia hạn.
        """
        self.ensure_one()
        if self.claim_id:
            raise UserError(_('Hồ sơ này đã có hồ sơ khiếu nại.'))
        late = self.review_late_days or (
            self.days_left < 0 and abs(self.days_left)) or 0
        if not late:
            raise UserError(_(
                'Bên xem xét vẫn còn trong hạn %s ngày của điều 5.2 — chưa '
                'có căn cứ khiếu nại.', self.review_days))
        if not self.contract_id:
            raise UserError(_('Hồ sơ chưa gắn hợp đồng nào.'))
        claim = self.env['rp.claim'].create({
            'name': _('Chậm xem xét hồ sơ %s', self.code or self.name),
            'project_id': self.project_id.id,
            'contract_id': self.contract_id.id,
            'direction': 'from_contractor',
            'claim_type': 'eot',
            'cause': 'approval',
            'date_event': self.review_deadline,
            'eot_days_claimed': late,
            'task_ids': [(6, 0, self.task_ids.ids)],
            'description': _(
                '<p>Hồ sơ <b>%(code)s — %(name)s</b> được trình ngày '
                '%(sub)s kèm thông báo theo điều 5.2. Hạn xem xét %(days)s '
                'ngày hết vào ngày %(due)s, bên xem xét trả lời/để quá hạn '
                '%(late)s ngày.</p><p>Điều 5.2 không cho phép khởi công '
                'phần việc liên quan trước khi hồ sơ được duyệt, nên thời '
                'gian quá hạn này là cơ sở xin gia hạn.</p>',
                code=self.code or '', name=self.name,
                sub=self.date_submitted or '', days=self.review_days,
                due=self.review_deadline or '', late=late),
        })
        self.claim_id = claim.id
        return {
            'type': 'ir.actions.act_window',
            'name': _('Khiếu nại chậm xem xét hồ sơ'),
            'res_model': 'rp.claim',
            'res_id': claim.id,
            'view_mode': 'form',
        }

    def action_open_tasks(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Công việc phụ thuộc — %s', self.name),
            'res_model': 'project.task',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.task_ids.ids)],
        }


class RpDocumentRevision(models.Model):
    _name = 'rp.document.revision'
    _description = 'Lần trình hồ sơ'
    _order = 'document_id, rev_no desc, id desc'

    document_id = fields.Many2one(
        'rp.document', string='Hồ sơ', required=True, ondelete='cascade',
        index=True)
    rev_no = fields.Integer(string='Rev', default=0)
    name = fields.Char(string='Lần trình', compute='_compute_name')
    transmittal_id = fields.Many2one(
        'rp.transmittal', string='Phiếu chuyển', index=True)
    date_submitted = fields.Date(string='Ngày trình')
    date_notice = fields.Date(string='Ngày có thông báo 5.2')
    review_deadline = fields.Date(string='Hạn chót xem xét')
    date_reviewed = fields.Date(string='Ngày có ý kiến')
    reviewer_id = fields.Many2one('res.users', string='Người xem xét')
    outcome = fields.Selection(OUTCOME, string='Kết quả')
    review_note = fields.Text(string='Ý kiến')
    days_used = fields.Integer(string='Số ngày xem xét',
                               compute='_compute_days_used')
    attachment_ids = fields.Many2many(
        'ir.attachment', string='Tệp đính kèm')

    @api.depends('rev_no')
    def _compute_name(self):
        for rec in self:
            rec.name = _('Rev %s', rec.rev_no)

    @api.depends('date_submitted', 'date_notice', 'date_reviewed')
    def _compute_days_used(self):
        for rec in self:
            start = (max(rec.date_submitted, rec.date_notice)
                     if rec.date_submitted and rec.date_notice else False)
            rec.days_used = ((rec.date_reviewed - start).days
                             if start and rec.date_reviewed else 0)
