# -*- coding: utf-8 -*-
"""Mốc ngân sách — ảnh chụp ngân sách tại thời điểm phê duyệt.

Điểm cốt tử của model này: `amount_total` và các dòng là số LƯU, không
phải số tính. Nếu để chúng tính lại từ gói thầu/hạng mục thì mốc sẽ
trôi theo đúng cái mà nó sinh ra để canh, và cả module thành vô nghĩa.

Vì vậy mỗi dòng chụp cả `ref_code`/`ref_name` dưới dạng CHỮ, song song
với liên kết tới gói thầu/hạng mục. Gói thầu bị xoá hay đổi tên thì mốc
cũ vẫn đọc được — liên kết đứt nhưng chữ còn.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class RpCostBaseline(models.Model):
    _name = 'rp.cost.baseline'
    _description = 'Mốc ngân sách dự án'
    _inherit = ['mail.thread']
    _order = 'project_id, revision desc, id desc'

    name = fields.Char(
        string='Tên mốc', required=True, tracking=True,
        help='Vd "Ngân sách gốc theo QĐ phê duyệt đầu tư".')
    project_id = fields.Many2one(
        're.project', string='Dự án', required=True, index=True,
        ondelete='cascade', tracking=True)
    revision = fields.Integer(
        string='Lần chốt', readonly=True, copy=False, default=0,
        help='0 là mốc gốc; mỗi lần chốt lại tăng 1.')
    date_approved = fields.Date(
        string='Ngày chốt', required=True, tracking=True,
        default=fields.Date.context_today)
    approved_by_id = fields.Many2one(
        'res.users', string='Người chốt', tracking=True,
        default=lambda self: self.env.user)
    state = fields.Selection(
        [('draft', 'Nháp'),
         ('active', 'Đang hiệu lực'),
         ('superseded', 'Đã thay thế')],
        string='Trạng thái', default='draft', required=True, tracking=True,
        copy=False)
    # SỐ LƯU, không phải số tính — xem ghi chú đầu file.
    amount_total = fields.Monetary(
        string='Ngân sách gốc', readonly=True, copy=False,
        currency_field='currency_id', tracking=True)
    line_ids = fields.One2many(
        'rp.cost.baseline.line', 'baseline_id', string='Chi tiết',
        readonly=True, copy=False)
    line_count = fields.Integer(
        string='Số khoản', compute='_compute_line_count')
    note = fields.Text(string='Căn cứ chốt')
    currency_id = fields.Many2one(
        'res.currency', related='project_id.currency_id',
        store=True, readonly=True)
    company_id = fields.Many2one(
        'res.company', string='Công ty',
        default=lambda self: self.env.company, index=True)

    @api.depends('line_ids')
    def _compute_line_count(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)

    def action_kich_hoat(self):
        """Đưa mốc vào hiệu lực, đẩy mốc đang hiệu lực sang 'đã thay thế'."""
        for rec in self:
            if not rec.line_ids:
                raise UserError(_(
                    "Mốc \"%s\" chưa có khoản nào. Chốt một mốc rỗng thì "
                    "mọi so sánh về sau đều sai.", rec.name))
            cu = self.search([
                ('project_id', '=', rec.project_id.id),
                ('state', '=', 'active'), ('id', '!=', rec.id)])
            cu.write({'state': 'superseded'})
            rec.state = 'active'
        return True

    def action_ve_nhap(self):
        self.write({'state': 'draft'})
        return True

    def action_mo_chi_tiet(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Chi tiết mốc — %s', self.name),
            'res_model': 'rp.cost.baseline.line',
            'view_mode': 'list',
            'domain': [('baseline_id', '=', self.id)],
            'context': {'search_default_group_source': 1},
        }


class RpCostBaselineLine(models.Model):
    _name = 'rp.cost.baseline.line'
    _description = 'Khoản trong mốc ngân sách'
    _order = 'baseline_id, source, ref_code, id'

    baseline_id = fields.Many2one(
        'rp.cost.baseline', string='Mốc ngân sách', required=True,
        index=True, ondelete='cascade')
    project_id = fields.Many2one(
        're.project', related='baseline_id.project_id',
        store=True, readonly=True)
    source = fields.Selection(
        [('package', 'Gói thầu'),
         ('structure', 'Hạng mục'),
         ('project_cost', 'Chi phí cấp dự án')],
        string='Nguồn', required=True, index=True)
    # Liên kết để bấm xem được; ondelete='set null' chứ KHÔNG cascade —
    # xoá gói thầu không được phép xoá mất một dòng của mốc đã chốt.
    package_id = fields.Many2one(
        'rp.tender.package', string='Gói thầu', ondelete='set null')
    structure_id = fields.Many2one(
        'rp.structure', string='Hạng mục', ondelete='set null')
    ref_code = fields.Char(string='Mã')
    ref_name = fields.Char(string='Tên khoản', required=True)
    amount = fields.Monetary(
        string='Số tiền', currency_field='currency_id')
    currency_id = fields.Many2one(
        'res.currency', related='baseline_id.currency_id',
        store=True, readonly=True)
