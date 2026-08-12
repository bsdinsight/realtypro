# -*- coding: utf-8 -*-
"""Dự toán chi phí CẤP DỰ ÁN — hai nguồn, một cây danh mục.

Anh Đại chốt 2026-08-10: dự toán xây ở cấp HẠNG MỤC (BOQ) rồi cộng dồn
lên DỰ ÁN theo cây chi phí 2 cấp. Nhưng có những khoản **không thuộc hạng
mục nào** — quản lý dự án, lán trại, an toàn, bảo hiểm, lãi vay vốn hoá —
nếu chỉ cộng từ hạng mục thì chúng biến mất khỏi CTC, kéo theo Nhu cầu
vốn tính thiếu so với tài liệu nghiệp vụ §3. Vì vậy:

    Dự toán dự án (theo nhóm chi phí)
        = Σ BOQ các hạng mục   (`est_from_structure`)
        + Σ dòng khai riêng cấp dự án (`est_direct`, model dưới đây)

Không dựng model "phiếu dự toán" riêng: chính cây `rp.cost.category` của
dự án đã là 2 cấp và đã gắn với BOQ, nên gắn thẳng chỉ tiêu tiền lên nó —
khỏi đồng bộ hai nơi, khỏi lệch số.

Cách B (anh Đại 2026-08-10): dòng BOQ đang gắn ở CẤP 1 vẫn được cộng đủ,
đánh dấu `needs_detail` để team biết chỗ cần chi tiết hoá xuống cấp 2 —
không ép re-tag ngay, không mất số.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class RpProjectCostLine(models.Model):
    _name = 'rp.project.cost.line'
    _description = 'Chi phí cấp dự án (ngoài hạng mục)'
    _order = 'project_id, category_id, id'

    project_id = fields.Many2one(
        're.project', string='Dự án', required=True, index=True,
        ondelete='cascade')
    category_id = fields.Many2one(
        'rp.cost.category', string='Nhóm chi phí', required=True,
        index=True, ondelete='restrict',
        domain="[('project_id', '=', project_id)]",
        help='Nên chọn nhóm CẤP 2 để dự toán đủ chi tiết.')
    category_level = fields.Integer(
        related='category_id.level', string='Cấp', readonly=True)
    description = fields.Char(
        string='Diễn giải', required=True,
        help='Vd "Chi phí Ban điều hành công trường 18 tháng".')
    amount = fields.Monetary(string='Số tiền', required=True)
    note = fields.Text(string='Ghi chú')

    # re.project KHÔNG có company_id — chỉ lấy currency
    currency_id = fields.Many2one(
        related='project_id.currency_id', store=True, readonly=True)

    @api.constrains('category_id', 'project_id')
    def _check_category_project(self):
        for rec in self:
            if rec.category_id.project_id != rec.project_id:
                raise ValidationError(_(
                    "Nhóm chi phí '%(c)s' thuộc dự án khác — phải chọn "
                    "nhóm của chính dự án %(p)s.",
                    c=rec.category_id.display_name,
                    p=rec.project_id.display_name))

    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount < 0:
                raise ValidationError(_('Số tiền không được âm.'))


class RpCostCategoryEstimate(models.Model):
    """Chỉ tiêu dự toán gắn thẳng lên cây nhóm chi phí của dự án."""
    _inherit = 'rp.cost.category'

    currency_id = fields.Many2one(
        related='project_id.currency_id', readonly=True)
    est_own_boq = fields.Monetary(
        string='BOQ gắn trực tiếp', compute='_compute_estimates',
        help='Tiền BOQ gắn ĐÚNG nhóm này (chưa tính nhóm con).')
    est_from_structure = fields.Monetary(
        string='Từ hạng mục (BOQ)', compute='_compute_estimates',
        help='Σ BOQ của nhóm này và mọi nhóm con.')
    est_direct = fields.Monetary(
        string='Khai riêng cấp dự án', compute='_compute_estimates',
        help='Σ các dòng chi phí cấp dự án (ngoài hạng mục) của nhóm này '
             'và nhóm con.')
    est_total = fields.Monetary(
        string='Dự toán dự án', compute='_compute_estimates',
        help='= Từ hạng mục + Khai riêng cấp dự án.')
    needs_detail = fields.Boolean(
        string='Có thể tách chi tiết', compute='_compute_estimates',
        help='GỢI Ý, không phải lỗi: nhóm cấp 1 này đang ôm tiền gắn '
             'thẳng vào nó, chưa tách xuống nhóm cấp 2.\n'
             'Để nguyên hoàn toàn được — tổng dự toán (BAC), CTC và Nhu '
             'cầu vốn KHÔNG đổi một đồng nào. Chỉ nên tách khi cần đọc '
             'cơ cấu chi phí chi tiết hoặc so với đơn giá chuẩn.')

    @api.depends('parent_path', 'project_id')
    def _compute_estimates(self):
        if not self:
            return
        projects = self.mapped('project_id')
        Boq = self.env['rp.boq.line']
        Line = self.env['rp.project.cost.line']
        # Gom tiền theo TỪNG nhóm (một lượt cho cả recordset)
        boq_by = {
            c.id: amt for c, amt in Boq._read_group(
                [('project_id', 'in', projects.ids),
                 ('category_id', '!=', False)],
                groupby=['category_id'], aggregates=['amount:sum']) if c}
        dir_by = {
            c.id: amt for c, amt in Line._read_group(
                [('project_id', 'in', projects.ids)],
                groupby=['category_id'], aggregates=['amount:sum']) if c}
        # parent_path cho phép roll-up bằng tiền tố, không cần đệ quy
        all_cats = self.search([('project_id', 'in', projects.ids)])
        paths = {c.id: (c.parent_path or '') for c in all_cats}
        for rec in self:
            prefix = rec.parent_path or ''
            kids = [cid for cid, p in paths.items()
                    if prefix and p.startswith(prefix)]
            rec.est_own_boq = boq_by.get(rec.id, 0.0)
            rec.est_from_structure = sum(boq_by.get(k, 0.0) for k in kids)
            rec.est_direct = sum(dir_by.get(k, 0.0) for k in kids)
            rec.est_total = rec.est_from_structure + rec.est_direct
            rec.needs_detail = bool(
                rec.level == 1 and rec.est_own_boq > 0 and rec.child_ids)


class ReProjectCostLines(models.Model):
    _inherit = 're.project'

    project_cost_line_ids = fields.One2many(
        'rp.project.cost.line', 'project_id',
        string='Chi phí cấp dự án')
    project_cost_direct_total = fields.Monetary(
        string='Σ chi phí cấp dự án', compute='_compute_cost_direct_total',
        store=True,
        help='Σ các khoản không thuộc hạng mục nào — CỘNG vào tổng dự '
             'toán (BAC) của dự án.')

    @api.depends('project_cost_line_ids.amount')
    def _compute_cost_direct_total(self):
        for proj in self:
            proj.project_cost_direct_total = sum(
                proj.project_cost_line_ids.mapped('amount'))
