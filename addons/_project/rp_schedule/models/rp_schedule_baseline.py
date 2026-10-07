# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class RpScheduleBaseline(models.Model):
    """Một BẢN CHỤP lịch tại một thời điểm — V1, V2, V3…

    Vì sao phải có bảng riêng thay vì hai trường baseline trên công việc:
    hai trường ấy chỉ giữ được MỘT bản gốc, nên mỗi lần tái lập kế hoạch
    là bản cũ bị ghi đè và lịch sử trượt biến mất. Mà câu hỏi người quản
    lý dự án hay hỏi nhất lại chính là câu cần lịch sử đó — "mốc này
    trượt từ bao giờ, trượt ở lần tái lập nào". Giữ nhiều bản thì trả lời
    được; giữ một bản thì chỉ biết hiện tại lệch bản gần nhất bao nhiêu.

    Bản chụp là BẤT BIẾN: chụp xong không sửa ngày trong đó nữa. Sửa được
    thì nó hết là mốc so sánh.
    """
    _name = 'rp.schedule.baseline'
    _description = 'Bản chụp lịch (baseline)'
    _order = 'project_id, sequence, id'

    name = fields.Char(string='Phiên bản', required=True)
    project_id = fields.Many2one(
        're.project', string='Dự án', required=True,
        ondelete='cascade', index=True)
    sequence = fields.Integer(string='Thứ tự', default=10)
    date_set = fields.Date(
        string='Ngày chốt', required=True,
        default=lambda self: fields.Date.context_today(self))
    note = fields.Text(string='Lý do tái lập kế hoạch')
    line_ids = fields.One2many(
        'rp.schedule.baseline.line', 'baseline_id', string='Dòng')
    task_count = fields.Integer(
        string='Số công việc', compute='_compute_task_count', store=True)
    # Bản đang dùng làm gốc so sánh mặc định. Chỉ một bản mỗi dự án.
    is_current = fields.Boolean(string='Bản hiện hành')

    @api.depends('line_ids')
    def _compute_task_count(self):
        data = self.env['rp.schedule.baseline.line']._read_group(
            [('baseline_id', 'in', self.ids)], ['baseline_id'],
            ['__count'])
        dem = {b.id: n for b, n in data}
        for r in self:
            r.task_count = dem.get(r.id, 0)

    @api.model
    def rp_chup(self, project_id, name, note=False, sequence=10,
                make_current=True):
        """Chụp lịch hiện hành của dự án thành một phiên bản mới."""
        P = self.env['re.project'].browse(int(project_id))
        tasks = self.env['project.task'].search([
            ('rp_project_id', '=', P.id),
            ('planned_start', '!=', False)])
        if not tasks:
            raise UserError(_('Dự án chưa có công việc nào có ngày kế hoạch.'))
        ban = self.create({
            'name': name,
            'project_id': P.id,
            'sequence': sequence,
            'note': note or False,
        })
        self.env['rp.schedule.baseline.line'].create([{
            'baseline_id': ban.id,
            'task_id': t.id,
            'planned_start': t.planned_start,
            'planned_end': t.planned_end or t.planned_start,
            'wbs_code': t.wbs_code or '',
            'task_name': t.name or '',
        } for t in tasks])
        if make_current:
            ban.action_dat_hien_hanh()
        return ban

    def action_dat_hien_hanh(self):
        """Đặt bản này làm gốc so sánh mặc định của dự án."""
        self.ensure_one()
        self.search([('project_id', '=', self.project_id.id),
                     ('is_current', '=', True),
                     ('id', '!=', self.id)]).write({'is_current': False})
        self.is_current = True
        # Đổ xuống hai trường trên công việc để các màn cũ (cột "Trễ so
        # gốc", KPI hợp đồng) vẫn đọc được mà không phải sửa gì.
        for ln in self.line_ids:
            ln.task_id.write({
                'baseline_start': ln.planned_start,
                'baseline_end': ln.planned_end,
                'baseline_set_date': fields.Datetime.now(),
            })
        return True

    @api.model
    def rp_danh_sach(self, project_id):
        """Cho Gantt: các phiên bản của dự án, cũ trước mới sau."""
        bans = self.search([('project_id', '=', int(project_id))])
        return [{
            'id': b.id,
            'name': b.name,
            'date': b.date_set.strftime('%d/%m/%Y') if b.date_set else '',
            'count': b.task_count,
            'current': b.is_current,
        } for b in bans]

    @api.model
    def rp_lay_dong(self, baseline_id):
        """Cho Gantt: {id công việc: [bắt đầu, kết thúc]} của một phiên bản."""
        lines = self.env['rp.schedule.baseline.line'].search_read(
            [('baseline_id', '=', int(baseline_id))],
            ['task_id', 'planned_start', 'planned_end'])
        return {
            str(l['task_id'][0]): [
                l['planned_start'] and str(l['planned_start']),
                l['planned_end'] and str(l['planned_end']),
            ] for l in lines
        }


class RpScheduleBaselineLine(models.Model):
    _name = 'rp.schedule.baseline.line'
    _description = 'Dòng bản chụp lịch'
    _order = 'baseline_id, planned_start, id'

    baseline_id = fields.Many2one(
        'rp.schedule.baseline', string='Phiên bản', required=True,
        ondelete='cascade', index=True)
    task_id = fields.Many2one(
        'project.task', string='Công việc', required=True,
        ondelete='cascade', index=True)
    # Chụp lại cả mã và tên dưới dạng CHỮ: công việc có thể bị đổi tên
    # hoặc xoá về sau, mà bản chụp thì phải đọc được nguyên trạng lúc chốt.
    wbs_code = fields.Char(string='Mã WBS')
    task_name = fields.Char(string='Tên lúc chốt')
    planned_start = fields.Date(string='Bắt đầu')
    planned_end = fields.Date(string='Kết thúc')

    # Odoo 19 BỎ `_sql_constraints` mà không báo gì — khai kiểu cũ là
    # ràng buộc không hề được tạo trong CSDL.
    _uniq_task = models.Constraint(
        'UNIQUE(baseline_id, task_id)',
        'Mỗi công việc chỉ có một dòng trong một phiên bản baseline.',
    )
