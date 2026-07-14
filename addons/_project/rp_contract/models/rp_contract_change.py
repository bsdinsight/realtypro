# -*- coding: utf-8 -*-
"""Thay đổi (Variation / Change) trong thi công.

Nghiệp vụ xây dựng: mọi phát sinh — CĐT yêu cầu, thiết kế đổi, hiện
trường vướng, vật liệu thay thế — được ghi thành 1 "Thay đổi" có giá
trị ước tính (+/-), trình duyệt chủ trương, rồi được GOM vào Phụ lục
HĐ để chốt thương mại.

Quan hệ Thay đổi ↔ Phụ lục là many2many:
- 1 phụ lục thường gom nhiều thay đổi (chốt 1 đợt);
- 1 thay đổi có thể nằm trong nhiều phụ lục (vd phần giá trị chốt ở
  phụ lục A, phần gia hạn tiến độ đi kèm nằm ở phụ lục B).
"""
from odoo import _, api, fields, models


class RpContractChange(models.Model):
    _name = 'rp.contract.change'
    _description = 'Thay đổi (Change) thi công'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    code = fields.Char(
        string='Mã', required=True, copy=False, readonly=True,
        default=lambda self: _('Mới'))
    name = fields.Char(string='Nội dung thay đổi', required=True,
                       tracking=True)
    contract_id = fields.Many2one(
        'rp.contract', string='HĐ', required=True, ondelete='restrict',
        index=True, tracking=True)
    project_id = fields.Many2one(
        related='contract_id.project_id', store=True, readonly=True)
    contractor_id = fields.Many2one(
        related='contract_id.contractor_id', store=True, readonly=True,
        string='Nhà thầu')
    structure_id = fields.Many2one(
        'rp.structure', string='Hạng mục',
        domain="[('project_id', '=', project_id)]")
    date = fields.Date(
        string='Ngày ghi nhận', required=True,
        default=fields.Date.context_today)

    change_type = fields.Selection(
        [('scope_add', 'Phát sinh tăng'),
         ('scope_remove', 'Cắt giảm'),
         ('design', 'Thay đổi thiết kế'),
         ('material', 'Thay đổi vật liệu / đơn giá'),
         ('schedule', 'Điều chỉnh tiến độ'),
         ('other', 'Khác')],
        string='Loại', required=True, default='scope_add', tracking=True)
    source = fields.Selection(
        [('owner', 'CĐT yêu cầu'),
         ('site', 'Phát sinh hiện trường'),
         ('design', 'Hồ sơ thiết kế'),
         ('rfi', 'Từ RFI'),
         ('instruction', 'Từ chỉ thị công trường'),
         ('other', 'Khác')],
        string='Nguồn gốc', required=True, default='site', tracking=True)

    description = fields.Text(string='Diễn giải', required=True)
    amount_estimate = fields.Monetary(
        string='Giá trị ước tính', tracking=True,
        help='Ước tính tác động giá trị HĐ: dương = phát sinh tăng, '
             'âm = cắt giảm. Giá trị chốt nằm ở Phụ lục.')

    amendment_ids = fields.Many2many(
        'rp.contract.amendment', 'rp_change_amendment_rel',
        'change_id', 'amendment_id', string='Phụ lục',
        domain="[('contract_id', '=', contract_id)]")
    amendment_count = fields.Integer(compute='_compute_amendment_count')
    is_covered = fields.Boolean(
        string='Đã vào phụ lục', compute='_compute_amendment_count',
        store=True, help='Đã được gom vào ít nhất 1 phụ lục.')

    state = fields.Selection(
        [('draft', 'Nháp'),
         ('submitted', 'Đã trình'),
         ('approved', 'Duyệt chủ trương'),
         ('rejected', 'Từ chối'),
         ('cancelled', 'Huỷ')],
        string='Trạng thái', default='draft', required=True, tracking=True,
        copy=False)

    currency_id = fields.Many2one(
        related='contract_id.currency_id', store=True, readonly=True)
    company_id = fields.Many2one(
        related='contract_id.company_id', store=True, readonly=True)

    @api.depends('amendment_ids')
    def _compute_amendment_count(self):
        for rec in self:
            rec.amendment_count = len(rec.amendment_ids)
            rec.is_covered = bool(rec.amendment_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code') or vals['code'] == _('Mới'):
                vals['code'] = self.env['ir.sequence'].next_by_code(
                    'rp.contract.change') or _('Mới')
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------
    def action_submit(self):
        self.filtered(lambda r: r.state == 'draft').write(
            {'state': 'submitted'})
        return True

    def action_approve(self):
        self.filtered(lambda r: r.state == 'submitted').write(
            {'state': 'approved'})
        return True

    def action_reject(self):
        self.filtered(lambda r: r.state == 'submitted').write(
            {'state': 'rejected'})
        return True

    def action_reset_draft(self):
        self.filtered(lambda r: r.state in ('rejected', 'cancelled')).write(
            {'state': 'draft'})
        return True

    def action_cancel(self):
        self.filtered(lambda r: r.state in ('draft', 'submitted')).write(
            {'state': 'cancelled'})
        return True
