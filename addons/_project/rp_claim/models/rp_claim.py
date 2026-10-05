# -*- coding: utf-8 -*-
"""Khiếu nại hợp đồng: gia hạn thời gian (EOT) và chi phí phát sinh.

Dự án trễ thì câu hỏi tiếp theo luôn là "lỗi của ai, và ai trả tiền".
Trả lời được câu đó cần ba thứ gắn vào nhau mà bảng tính không giữ nổi:

* **Sự kiện gây trễ** — thường chính là một điểm bàn giao hỏng
  (sổ ranh giới gói thầu) hoặc một công việc trượt (lịch thi công).
* **Thời hạn thông báo**. Hợp đồng xây dựng nào cũng có điều khoản: quá
  hạn thông báo thì mất quyền khiếu nại, dù lý do đúng. Đây là chỗ nhà
  thầu mất tiền nhiều nhất, và cũng là chỗ chủ đầu tư hay quên đếm.
* **Kết quả**: số ngày được gia hạn, số tiền được chấp thuận — và ngày
  hoàn thành hợp đồng dời theo, vì đó mới là mốc để tính phạt chậm.

Ghi nhận hai chiều: nhà thầu khiếu nại chủ đầu tư, và chủ đầu tư khiếu
nại nhà thầu. Hai chiều dùng chung một sổ thì mới thấy được bức tranh
"ai nợ ai" trên cùng một hợp đồng.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

GRANTED_STATES = ('agreed', 'partial')


class RpClaim(models.Model):
    _name = 'rp.claim'
    _description = 'Khiếu nại hợp đồng (EOT / chi phí)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_event desc, id desc'

    name = fields.Char(string='Nội dung khiếu nại', required=True,
                       tracking=True)
    code = fields.Char(string='Mã', copy=False, readonly=True, index=True)
    project_id = fields.Many2one(
        're.project', string='Dự án', related='contract_id.project_id',
        store=True, index=True)
    contract_id = fields.Many2one(
        'rp.contract', string='Hợp đồng', required=True, index=True,
        ondelete='cascade', tracking=True)
    partner_id = fields.Many2one(
        'res.partner', string='Nhà thầu',
        related='contract_id.contractor_id', store=True)
    currency_id = fields.Many2one(
        'res.currency', related='contract_id.currency_id', store=True)

    direction = fields.Selection(
        [('from_contractor', 'Nhà thầu khiếu nại chủ đầu tư'),
         ('from_owner', 'Chủ đầu tư khiếu nại nhà thầu')],
        string='Chiều khiếu nại', required=True, default='from_contractor',
        tracking=True)
    claim_type = fields.Selection(
        [('eot', 'Gia hạn thời gian (EOT)'),
         ('cost', 'Chi phí phát sinh'),
         ('eot_cost', 'Gia hạn + chi phí'),
         ('other', 'Khác')],
        string='Loại khiếu nại', required=True, default='eot', tracking=True)
    cause = fields.Selection(
        [('site_access', 'Chậm bàn giao mặt bằng'),
         ('design_change', 'Thay đổi thiết kế / phát sinh'),
         ('owner_supply', 'Chậm cấp vật tư, thiết bị của chủ đầu tư'),
         ('interface', 'Nhà thầu khác bàn giao chậm'),
         ('payment', 'Chậm thanh toán'),
         ('approval', 'Chậm phê duyệt, nghiệm thu'),
         ('weather', 'Thời tiết, bất khả kháng'),
         ('contractor_fault', 'Lỗi của nhà thầu'),
         ('other', 'Khác')],
        string='Nguyên nhân', default='interface', tracking=True)
    description = fields.Html(string='Diễn giải & căn cứ')

    # --- Gắn vào nơi sự việc xảy ra --------------------------------
    interface_id = fields.Many2one(
        'rp.interface', string='Điểm bàn giao liên quan',
        help='Khiếu nại do một điểm bàn giao giữa hai hợp đồng bị trễ '
             'thì trỏ vào đây — đó là bằng chứng gốc.')
    task_ids = fields.Many2many(
        'project.task', string='Công việc bị ảnh hưởng')

    # --- Thời hạn thông báo ----------------------------------------
    date_event = fields.Date(
        string='Ngày xảy ra sự kiện', required=True, tracking=True,
        default=fields.Date.context_today)
    notice_days = fields.Integer(
        string='Hạn thông báo (ngày)', default=28, tracking=True,
        help='Số ngày kể từ sự kiện mà hợp đồng cho phép gửi thông báo '
             'khiếu nại. Quá hạn thường là MẤT QUYỀN khiếu nại, dù lý '
             'do đúng.')
    date_notice = fields.Date(string='Ngày gửi thông báo', tracking=True)
    notice_deadline = fields.Date(
        string='Hạn chót thông báo', compute='_compute_notice',
        store=True)
    notice_late_days = fields.Integer(
        string='Thông báo trễ (ngày)', compute='_compute_notice',
        store=True)
    notice_ok = fields.Boolean(
        string='Thông báo đúng hạn', compute='_compute_notice', store=True)

    # --- Yêu cầu & kết quả -----------------------------------------
    eot_days_claimed = fields.Integer(string='Số ngày xin gia hạn',
                                      tracking=True)
    eot_days_granted = fields.Integer(string='Số ngày được gia hạn',
                                      tracking=True)
    amount_claimed = fields.Monetary(string='Số tiền yêu cầu',
                                     tracking=True)
    amount_granted = fields.Monetary(string='Số tiền chấp thuận',
                                     tracking=True)
    state = fields.Selection(
        [('draft', 'Dự thảo'),
         ('notified', 'Đã thông báo'),
         ('submitted', 'Đã nộp hồ sơ'),
         ('review', 'Đang xem xét'),
         ('agreed', 'Chấp thuận'),
         ('partial', 'Chấp thuận một phần'),
         ('rejected', 'Từ chối'),
         ('closed', 'Đã đóng')],
        string='Trạng thái', default='draft', required=True, tracking=True,
        index=True)
    decision_date = fields.Date(string='Ngày quyết định', tracking=True)
    decision_user_id = fields.Many2one(
        'res.users', string='Người quyết định', tracking=True)
    decision_note = fields.Text(string='Lý do quyết định')
    amendment_id = fields.Many2one(
        'rp.contract.amendment', string='Phụ lục đã lập', readonly=True,
        copy=False,
        help='Gia hạn được chấp thuận phải ra phụ lục hợp đồng thì mốc '
             'hoàn thành mới thay đổi trên giấy tờ.')

    # ------------------------------------------------------------------
    @api.depends('date_event', 'notice_days', 'date_notice')
    def _compute_notice(self):
        for rec in self:
            if rec.date_event and rec.notice_days:
                rec.notice_deadline = fields.Date.add(
                    rec.date_event, days=rec.notice_days)
            else:
                rec.notice_deadline = False
            if rec.date_notice and rec.notice_deadline:
                late = (rec.date_notice - rec.notice_deadline).days
                rec.notice_late_days = max(late, 0)
                rec.notice_ok = late <= 0
            else:
                rec.notice_late_days = 0
                rec.notice_ok = False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code'):
                vals['code'] = self.env['ir.sequence'].next_by_code(
                    'rp.claim') or '/'
        return super().create(vals_list)

    @api.depends('name', 'code')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = (f'[{rec.code}] {rec.name}'
                                if rec.code else rec.name or '')

    @api.constrains('eot_days_granted', 'eot_days_claimed')
    def _check_granted(self):
        for rec in self:
            if rec.eot_days_granted < 0:
                raise UserError(_('Số ngày gia hạn không thể âm.'))

    # ------------------------------------------------------------------
    # Quy trình
    # ------------------------------------------------------------------
    def action_notify(self):
        for rec in self:
            rec.write({
                'state': 'notified',
                'date_notice': rec.date_notice or fields.Date.context_today(rec),
            })
            if not rec.notice_ok:
                rec.message_post(body=_(
                    'Thông báo gửi ngày %(d)s, QUÁ hạn %(n)s ngày so với '
                    'hạn chót %(h)s. Theo hợp đồng, phần lớn trường hợp '
                    'này mất quyền khiếu nại — ghi nhận để hai bên xử lý.',
                    d=rec.date_notice, n=rec.notice_late_days,
                    h=rec.notice_deadline))

    def action_submit(self):
        self.write({'state': 'submitted'})

    def action_review(self):
        self.write({'state': 'review'})

    def action_agree(self):
        for rec in self:
            if rec.claim_type in ('eot', 'eot_cost') \
                    and not rec.eot_days_granted:
                rec.eot_days_granted = rec.eot_days_claimed
            if rec.claim_type in ('cost', 'eot_cost') \
                    and not rec.amount_granted:
                rec.amount_granted = rec.amount_claimed
            partial = (rec.eot_days_granted < rec.eot_days_claimed
                       or rec.amount_granted < rec.amount_claimed)
            rec.write({
                'state': 'partial' if partial else 'agreed',
                'decision_date': fields.Date.context_today(rec),
                'decision_user_id': self.env.user.id,
            })

    def action_reject(self):
        self.write({
            'state': 'rejected',
            'eot_days_granted': 0,
            'amount_granted': 0,
            'decision_date': fields.Date.context_today(self),
            'decision_user_id': self.env.user.id,
        })

    def action_close(self):
        self.write({'state': 'closed'})

    def action_reset(self):
        self.write({'state': 'draft'})

    def action_create_amendment(self):
        """Ra phụ lục gia hạn từ khiếu nại đã chấp thuận.

        Ngày hoàn thành trên hợp đồng mới là mốc tính phạt chậm, nên gia
        hạn chỉ có giá trị khi đã thành phụ lục — không để nó nằm lại
        trong sổ khiếu nại.
        """
        self.ensure_one()
        if self.state not in GRANTED_STATES or not self.eot_days_granted:
            raise UserError(_(
                'Chỉ lập phụ lục khi khiếu nại đã được chấp thuận và có '
                'số ngày gia hạn.'))
        if self.amendment_id:
            raise UserError(_('Khiếu nại này đã có phụ lục %s.',
                              self.amendment_id.name))
        contract = self.contract_id
        if not contract.date_end:
            raise UserError(_(
                'Hợp đồng chưa có ngày hoàn thành thì không gia hạn được.'))
        new_end = fields.Date.add(contract.date_end,
                                  days=self.eot_days_granted)
        am = self.env['rp.contract.amendment'].create({
            'name': _('Gia hạn %(n)s ngày theo khiếu nại %(c)s',
                      n=self.eot_days_granted, c=self.code),
            'contract_id': contract.id,
            'amendment_type': 'extension',
            'description': self.decision_note or self.name,
            'new_date_end': new_end,
        })
        self.amendment_id = am
        self.message_post(body=_(
            'Đã lập phụ lục gia hạn: ngày hoàn thành %(o)s → %(n)s.',
            o=contract.date_end, n=new_end))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'rp.contract.amendment',
            'res_id': am.id,
            'views': [[False, 'form']],
            'target': 'new',
        }
