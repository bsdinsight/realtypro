# -*- coding: utf-8 -*-
"""Ranh giới & bàn giao giữa các gói thầu (interface register).

Dự án lớn chia thành nhiều gói thầu, mỗi gói một nhà thầu. Chỗ hỏng
không nằm TRONG hợp đồng nào cả — nó nằm ở ĐIỂM BÀN GIAO giữa hai hợp đồng:
nhà thầu móng phải bàn giao mặt bằng và bu-lông neo đúng cao độ cho nhà
thầu lắp dựng; hãng thiết bị phải giao bản vẽ tải trọng cho bên thiết kế
móng; bên vận chuyển phải giao tua-bin tại bãi cho bên cẩu lắp.

Mỗi điểm bàn giao như vậy là một bản ghi ở đây, có bên giao, bên nhận, thứ
được giao, ngày bên nhận CẦN và ngày bên giao HỨA — và quan trọng nhất:
**đối chiếu với lịch thi công hiện hành**. Hợp đồng nào cũng báo "đúng
tiến độ của tôi" mà dự án vẫn trễ, là vì không ai giữ sổ này.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

TERMINAL = ('delivered', 'closed', 'cancelled')


class RpInterface(models.Model):
    _name = 'rp.interface'
    _description = 'Điểm bàn giao giữa các gói thầu'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'schedule_need_date, id'

    name = fields.Char(
        string='Nội dung bàn giao', required=True, tracking=True,
        help='Nói rõ thứ được bàn giao, không chỉ tên hai bên. Ví dụ: '
             '"Bàn giao móng WTG-01 đạt cao độ và bu-lông neo".')
    code = fields.Char(
        string='Mã', copy=False, readonly=True, index=True)
    project_id = fields.Many2one(
        're.project', string='Dự án', required=True, index=True,
        ondelete='cascade', tracking=True)

    # --- Hai bên của điểm bàn giao -------------------------------------
    from_contract_id = fields.Many2one(
        'rp.contract', string='Bên giao (HĐ)', required=True, index=True,
        tracking=True, ondelete='cascade')
    to_contract_id = fields.Many2one(
        'rp.contract', string='Bên nhận (HĐ)', required=True, index=True,
        tracking=True, ondelete='cascade')
    from_partner_id = fields.Many2one(
        'res.partner', string='Nhà thầu giao',
        related='from_contract_id.contractor_id', store=True)
    to_partner_id = fields.Many2one(
        'res.partner', string='Nhà thầu nhận',
        related='to_contract_id.contractor_id', store=True)
    from_package_id = fields.Many2one(
        'rp.tender.package', string='Gói thầu giao',
        related='from_contract_id.tender_package_id', store=True)
    to_package_id = fields.Many2one(
        'rp.tender.package', string='Gói thầu nhận',
        related='to_contract_id.tender_package_id', store=True)

    interface_type = fields.Selection(
        [('physical', 'Bàn giao hiện vật / hạng mục'),
         ('document', 'Hồ sơ, bản vẽ, số liệu'),
         ('access', 'Mặt bằng, lối vào, không gian thi công'),
         ('utility', 'Điện, nước, hạ tầng tạm'),
         ('system', 'Đấu nối hệ thống (điện, điều khiển)'),
         ('approval', 'Phê duyệt, nghiệm thu của bên thứ ba'),
         ('other', 'Khác')],
        string='Loại ranh giới', default='physical', required=True,
        tracking=True)
    criticality = fields.Selection(
        [('low', 'Thấp'), ('medium', 'Trung bình'),
         ('high', 'Cao'), ('critical', 'Chịu lực')],
        string='Mức quan trọng', default='medium', required=True,
        tracking=True,
        help='"Chịu lực" = trễ điểm này là trễ ngày về đích của dự án.')
    description = fields.Html(
        string='Phạm vi & điều kiện nghiệm thu',
        help='Bàn giao thế nào thì coi là xong: tiêu chí, dung sai, hồ '
             'sơ kèm theo, ai ký.')

    owner_from_user_id = fields.Many2one(
        'res.users', string='Người phụ trách bên giao', tracking=True)
    owner_to_user_id = fields.Many2one(
        'res.users', string='Người phụ trách bên nhận', tracking=True)

    # --- Cam kết (hợp đồng) ----------------------------------------
    date_required = fields.Date(
        string='Bên nhận cần ngày', tracking=True)
    date_promised = fields.Date(
        string='Bên giao hứa ngày', tracking=True)
    date_actual = fields.Date(
        string='Bàn giao thực tế', tracking=True, copy=False)
    commitment_gap = fields.Integer(
        string='Lệch cam kết (ngày)', compute='_compute_gaps', store=True,
        help='Ngày hứa trừ ngày cần. Dương = bên giao hứa muộn hơn mức '
             'bên nhận cần, tức là đã xung đột ngay trên giấy.')

    # --- Lịch thi công hiện hành -----------------------------------
    from_task_id = fields.Many2one(
        'project.task', string='Việc tạo ra (bên giao)',
        help='Công việc trong lịch của bên giao, kết thúc là có thứ để '
             'bàn giao.')
    to_task_id = fields.Many2one(
        'project.task', string='Việc chờ (bên nhận)',
        help='Công việc trong lịch của bên nhận, không nhận được thì '
             'không khởi công được.')
    schedule_ready_date = fields.Date(
        string='Lịch: sẵn sàng ngày', compute='_compute_schedule_dates',
        store=True)
    schedule_need_date = fields.Date(
        string='Lịch: cần ngày', compute='_compute_schedule_dates',
        store=True)
    gap_days = fields.Integer(
        string='Dư địa bàn giao (ngày)', compute='_compute_gaps',
        store=True,
        help='Ngày bên nhận cần trừ ngày bên giao sẵn sàng, theo lịch '
             'hiện hành. ÂM = lịch đang mâu thuẫn: bên nhận phải chờ.')
    is_conflict = fields.Boolean(
        string='Lịch mâu thuẫn', compute='_compute_gaps', store=True,
        index=True)
    linked_in_schedule = fields.Boolean(
        string='Đã nối vào lịch', compute='_compute_linked', store=True,
        help='Việc bên nhận đã khai việc bên giao là công việc trước '
             'hay chưa — có nối thì đường găng mới chạy qua điểm này.')

    state = fields.Selection(
        [('identified', 'Đã nhận diện'),
         ('agreed', 'Hai bên đã chốt'),
         ('in_progress', 'Đang thực hiện'),
         ('delivered', 'Đã bàn giao'),
         ('closed', 'Đã đóng'),
         ('disputed', 'Tranh chấp'),
         ('cancelled', 'Huỷ')],
        string='Trạng thái', default='identified', required=True,
        tracking=True, index=True)
    active = fields.Boolean(default=True)

    # ------------------------------------------------------------------
    # Tính toán
    # ------------------------------------------------------------------
    @api.depends('from_task_id.planned_end', 'to_task_id.planned_start')
    def _compute_schedule_dates(self):
        for rec in self:
            rec.schedule_ready_date = rec.from_task_id.planned_end or False
            rec.schedule_need_date = rec.to_task_id.planned_start or False

    @api.depends('schedule_ready_date', 'schedule_need_date',
                 'date_required', 'date_promised')
    def _compute_gaps(self):
        for rec in self:
            if rec.schedule_ready_date and rec.schedule_need_date:
                rec.gap_days = (rec.schedule_need_date
                                - rec.schedule_ready_date).days
                rec.is_conflict = rec.gap_days < 0
            else:
                rec.gap_days = 0
                rec.is_conflict = False
            if rec.date_required and rec.date_promised:
                rec.commitment_gap = (rec.date_promised
                                      - rec.date_required).days
            else:
                rec.commitment_gap = 0

    @api.depends('from_task_id', 'to_task_id',
                 'to_task_id.predecessor_ids')
    def _compute_linked(self):
        for rec in self:
            rec.linked_in_schedule = bool(
                rec.from_task_id and rec.to_task_id
                and rec.from_task_id in rec.to_task_id.predecessor_ids)

    # ------------------------------------------------------------------
    # Ràng buộc
    # ------------------------------------------------------------------
    @api.constrains('from_contract_id', 'to_contract_id')
    def _check_two_sides(self):
        for rec in self:
            if rec.from_contract_id == rec.to_contract_id:
                raise UserError(_(
                    'Điểm bàn giao phải nối HAI gói thầu khác nhau. Việc bàn '
                    'giao trong nội bộ một hợp đồng là quan hệ trước-sau '
                    'của lịch thi công, không phải điểm bàn giao.'))

    @api.constrains('from_task_id', 'to_task_id', 'from_contract_id',
                    'to_contract_id')
    def _check_tasks_belong(self):
        for rec in self:
            if rec.from_task_id and rec.from_task_id.rp_contract_id \
                    and rec.from_task_id.rp_contract_id != rec.from_contract_id:
                raise UserError(_(
                    'Việc "%s" không thuộc hợp đồng bên giao.',
                    rec.from_task_id.name))
            if rec.to_task_id and rec.to_task_id.rp_contract_id \
                    and rec.to_task_id.rp_contract_id != rec.to_contract_id:
                raise UserError(_(
                    'Việc "%s" không thuộc hợp đồng bên nhận.',
                    rec.to_task_id.name))

    @api.onchange('from_contract_id')
    def _onchange_from_contract(self):
        if self.from_contract_id and not self.project_id:
            self.project_id = self.from_contract_id.project_id

    # ------------------------------------------------------------------
    # Tạo / hiển thị
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code'):
                vals['code'] = self.env['ir.sequence'].next_by_code(
                    'rp.interface') or '/'
        return super().create(vals_list)

    @api.depends('name', 'code')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = (f'[{rec.code}] {rec.name}'
                                if rec.code else rec.name or '')

    # ------------------------------------------------------------------
    # Hành động
    # ------------------------------------------------------------------
    def action_link_schedule(self):
        """Khai việc bên giao là công việc trước của việc bên nhận.

        Đây là chỗ sổ ranh giới thôi làm danh sách cho đẹp: nối xong thì
        đường găng toàn dự án chạy xuyên qua điểm bàn giao, và trễ ở bên giao
        tự đẩy ngày về đích.
        """
        for rec in self:
            if not (rec.from_task_id and rec.to_task_id):
                raise UserError(_(
                    'Phải chọn cả việc bên giao và việc bên nhận thì mới '
                    'nối vào lịch được.'))
            if rec.from_task_id not in rec.to_task_id.predecessor_ids:
                rec.to_task_id.predecessor_ids = [(4, rec.from_task_id.id)]
            rec.message_post(body=_(
                'Đã nối vào lịch: "%(a)s" là công việc trước của "%(b)s".',
                a=rec.from_task_id.name, b=rec.to_task_id.name))
        return True

    def action_pull_dates(self):
        """Lấy ngày cam kết theo lịch hiện hành (khi hai bên chốt lại)."""
        for rec in self:
            if rec.schedule_ready_date:
                rec.date_promised = rec.schedule_ready_date
            if rec.schedule_need_date:
                rec.date_required = rec.schedule_need_date
        return True

    def action_agree(self):
        self.write({'state': 'agreed'})

    def action_start(self):
        self.write({'state': 'in_progress'})

    def action_deliver(self):
        for rec in self:
            rec.write({
                'state': 'delivered',
                'date_actual': rec.date_actual or fields.Date.context_today(rec),
            })

    def action_close(self):
        self.write({'state': 'closed'})

    def action_dispute(self):
        self.write({'state': 'disputed'})

    def action_reset(self):
        self.write({'state': 'identified'})
