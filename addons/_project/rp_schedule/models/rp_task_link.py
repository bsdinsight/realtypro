# -*- coding: utf-8 -*-
"""rp.task.link — quan hệ trước–sau có LOẠI và có ĐỘ LỆCH (lag).

Chỉ có finish-to-start là không mô tả được lịch EPC thật. Lịch của một
nhà máy điện gió chạy fast-track: tổ đổ móng chưa xong batch 1 thì tổ làm
đường đã sang batch 2, đội kéo dây đi sau đội dựng trụ vài tuần chứ không
chờ dựng hết trụ. Khai những chỗ đó là FS thì hoặc lịch sai, hoặc quan hệ
sai — và vì không ai muốn sửa lịch, người ta XOÁ quan hệ. Mạng phụ thuộc
rỗng dần, rồi đường găng thành vô nghĩa.

Bốn loại quan hệ, viết theo "điều kiện của việc SAU":

* **FS** — việc sau bắt đầu sau khi việc trước kết thúc: S(sau) ≥ F(trước) + 1 + lag
* **SS** — việc sau bắt đầu sau khi việc trước bắt đầu: S(sau) ≥ S(trước) + lag
* **FF** — việc sau kết thúc sau khi việc trước kết thúc: F(sau) ≥ F(trước) + lag
* **SF** — việc sau kết thúc sau khi việc trước bắt đầu: F(sau) ≥ S(trước) + lag

``lag_days`` dương là khoảng CHỜ, âm là chồng lấn (lead). Cặp SS + lag
dương là cách chuẩn mô tả fast-track: "đội sau vào sau đội trước N ngày".

Ngoài ra mỗi quan hệ tự soi lại chính nó: ``lag_actual`` là độ lệch mà
NGÀY ĐANG LẬP ngụ ý, ``lag_gap`` là chênh so với lag đã khai. Âm nghĩa là
lịch đang VI PHẠM logic của chính nó — việc sau bắt đầu sớm hơn mức quan
hệ cho phép. Đây là thứ phải sửa trước khi tin bất kỳ đường găng nào.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

LINK_TYPE = [
    ('FS', 'FS — xong trước, mới bắt đầu sau'),
    ('SS', 'SS — bắt đầu sau khi việc trước bắt đầu'),
    ('FF', 'FF — kết thúc sau khi việc trước kết thúc'),
    ('SF', 'SF — kết thúc sau khi việc trước bắt đầu'),
]


class RpTaskLink(models.Model):
    _name = 'rp.task.link'
    _description = 'Quan hệ trước–sau giữa hai công việc'
    _order = 'task_id, id'

    task_id = fields.Many2one(
        'project.task', string='Công việc sau', required=True, index=True,
        ondelete='cascade')
    predecessor_id = fields.Many2one(
        'project.task', string='Công việc trước', required=True, index=True,
        ondelete='cascade')
    link_type = fields.Selection(
        LINK_TYPE, string='Loại', required=True, default='FS')
    lag_days = fields.Integer(
        string='Độ lệch (ngày)', default=0,
        help='Dương là khoảng chờ, âm là chồng lấn. Ví dụ SS+20: việc sau '
             'được bắt đầu sau việc trước 20 ngày.')
    note = fields.Char(string='Lý do')

    project_id = fields.Many2one(
        're.project', related='task_id.rp_project_id', string='Dự án',
        store=True, index=True)
    contract_id = fields.Many2one(
        'rp.contract', related='task_id.rp_contract_id',
        string='HĐ việc sau', store=True, index=True)
    pred_contract_id = fields.Many2one(
        'rp.contract', related='predecessor_id.rp_contract_id',
        string='HĐ việc trước', store=True)
    is_cross_contract = fields.Boolean(
        string='Nối hai hợp đồng', compute='_compute_cross', store=True,
        help='Quan hệ vắt qua hai nhà thầu — chỗ dự án hay hỏng nhất, và '
             'là nguồn của sổ giao diện.')

    lag_actual = fields.Integer(
        string='Độ lệch thực tế', compute='_compute_lag', store=True,
        help='Độ lệch mà ngày đang lập ngụ ý, tính theo đúng loại quan hệ.')
    lag_gap = fields.Integer(
        string='Chênh so khai báo', compute='_compute_lag', store=True,
        help='Độ lệch thực tế trừ độ lệch đã khai. Âm là lịch đang vi '
             'phạm logic của chính nó.')
    is_violated = fields.Boolean(
        string='Lịch vi phạm quan hệ', compute='_compute_lag', store=True,
        index=True)

    @api.depends('contract_id', 'pred_contract_id')
    def _compute_cross(self):
        for rec in self:
            rec.is_cross_contract = bool(
                rec.contract_id and rec.pred_contract_id
                and rec.contract_id != rec.pred_contract_id)

    @api.depends('link_type', 'lag_days',
                 'task_id.planned_start', 'task_id.planned_end',
                 'predecessor_id.planned_start', 'predecessor_id.planned_end')
    def _compute_lag(self):
        for rec in self:
            rec.lag_actual = rec._actual_lag()
            rec.lag_gap = rec.lag_actual - (rec.lag_days or 0)
            rec.is_violated = bool(rec._dates_known()) and rec.lag_gap < 0

    def _dates_known(self):
        s, p = self.task_id, self.predecessor_id
        return bool(s.planned_start and s.planned_end
                    and p.planned_start and p.planned_end)

    def _actual_lag(self):
        """Độ lệch mà ngày hiện hành ngụ ý — mỗi loại một phép đo."""
        if not self._dates_known():
            return 0
        s, p = self.task_id, self.predecessor_id
        if self.link_type == 'FS':
            return (s.planned_start - p.planned_end).days - 1
        if self.link_type == 'SS':
            return (s.planned_start - p.planned_start).days
        if self.link_type == 'FF':
            return (s.planned_end - p.planned_end).days
        return (s.planned_end - p.planned_start).days          # SF

    @api.depends('predecessor_id', 'task_id', 'link_type', 'lag_days')
    def _compute_display_name(self):
        for rec in self:
            lag = rec.lag_days or 0
            tag = '%s%s' % (rec.link_type or 'FS',
                            '+%d' % lag if lag > 0 else
                            ('%d' % lag if lag < 0 else ''))
            rec.display_name = '%s → %s (%s)' % (
                rec.predecessor_id.name or '', rec.task_id.name or '', tag)

    @api.constrains('task_id', 'predecessor_id')
    def _check_not_self(self):
        for rec in self:
            if rec.task_id == rec.predecessor_id:
                raise ValidationError(_(
                    'Một công việc không thể là việc trước của chính nó.'))

    @api.constrains('task_id', 'predecessor_id', 'link_type')
    def _check_unique_pair_type(self):
        """Mỗi cặp việc chỉ có một quan hệ CỦA MỖI LOẠI.

        Cố ý KHÔNG giới hạn một quan hệ cho một cặp. Cặp **SS + FF** là
        cách chuẩn mô tả hai tổ đi nối đuôi nhau: "tổ sau vào sau tổ
        trước 25 ngày, VÀ xong sau tổ trước 10 ngày". Thiếu nhánh FF thì
        tổ trước làm lâu hơn dự kiến mà tổ sau vẫn đứng im trên lịch —
        chậm không truyền về mốc, và đó đúng là lỗi đang muốn tránh.

        Hai quan hệ CÙNG loại cho cùng một cặp thì mới là lỗi: một cái
        luôn nuốt cái kia, chỉ gây hiểu sai.
        """
        for rec in self:
            if self.search_count([
                    ('task_id', '=', rec.task_id.id),
                    ('predecessor_id', '=', rec.predecessor_id.id),
                    ('link_type', '=', rec.link_type),
                    ('id', '!=', rec.id)]):
                raise ValidationError(_(
                    'Giữa "%(a)s" và "%(b)s" đã có một quan hệ %(t)s. Sửa '
                    'quan hệ đó, hoặc thêm quan hệ loại khác (ví dụ ghép '
                    'SS với FF), chứ không thêm cái thứ hai cùng loại.',
                    a=rec.predecessor_id.name, b=rec.task_id.name,
                    t=rec.link_type))

    # ------------------------------------------------------------------
    def action_set_ss_from_dates(self, with_ff=True):
        """Chuyển sang SS với độ lệch đúng bằng thực tế đang lập.

        Dùng cho các quan hệ FS đang bị chồng lấn: lịch fast-track vốn
        đúng, chỉ là quan hệ khai sai loại. Chuyển sang SS giữ được logic
        thay vì xoá quan hệ đi cho hết báo lỗi.

        Kèm thêm nhánh **FF** khi việc sau cũng kết thúc sau việc trước.
        Chỉ SS là chưa đủ: SS neo hai NGÀY BẮT ĐẦU, nên việc trước làm
        lâu hơn dự kiến mà vẫn bắt đầu đúng hạn thì việc sau không nhúc
        nhích, và cái chậm đó không bao giờ tới được mốc COD. Có FF thì
        việc sau buộc xong sau việc trước, nên vỡ thời lượng cũng truyền.
        """
        created = self.browse()
        for rec in self:
            if not rec._dates_known():
                continue
            ff_lag = (rec.task_id.planned_end
                      - rec.predecessor_id.planned_end).days
            rec.link_type = 'SS'
            rec.lag_days = rec._actual_lag()
            if not with_ff or ff_lag < 0:
                continue
            exists = self.search_count([
                ('task_id', '=', rec.task_id.id),
                ('predecessor_id', '=', rec.predecessor_id.id),
                ('link_type', '=', 'FF')])
            if not exists:
                created |= self.create({
                    'task_id': rec.task_id.id,
                    'predecessor_id': rec.predecessor_id.id,
                    'link_type': 'FF', 'lag_days': ff_lag,
                    'note': _('Nhánh FF đi kèm SS — để vỡ thời lượng của '
                              'việc trước cũng truyền sang việc sau.'),
                })
        return created

    def action_align_lag(self):
        """Giữ nguyên loại, lấy độ lệch thực tế làm độ lệch khai báo."""
        for rec in self:
            if rec._dates_known():
                rec.lag_days = rec._actual_lag()
        return True
