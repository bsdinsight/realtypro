# -*- coding: utf-8 -*-
"""Ba lớp của chi phí chủ đầu tư tự mua: dự toán → cam kết → hoá đơn."""
from odoo import api, fields, models


class ReProject(models.Model):
    _inherit = 're.project'

    purchase_order_ids = fields.One2many(
        'purchase.order', 'rp_project_id', string='Đơn mua')
    purchase_order_count = fields.Integer(compute='_compute_mua_hang')
    owner_cost_committed = fields.Monetary(
        string='Chủ đầu tư đã cam kết (đơn mua)',
        compute='_compute_mua_hang', currency_field='currency_id',
        help='Σ đơn mua ĐÃ XÁC NHẬN của dự án. Đơn nháp không tính — '
             'chưa xác nhận thì chưa ràng buộc ai cả.')
    owner_cost_invoiced = fields.Monetary(
        string='Chủ đầu tư đã có hoá đơn',
        compute='_compute_mua_hang', currency_field='currency_id')
    owner_cost_budget = fields.Monetary(
        string='Dự toán CĐT tự mua', compute='_compute_mua_hang',
        currency_field='currency_id',
        help='Dự toán chi phí cấp dự án, ĐÃ TRỪ quỹ dự phòng. Dự phòng '
             'nằm cùng chỗ nhưng không ai đi mua nó — để chung thì con '
             'số "còn lại" lúc nào cũng dư dả giả tạo.')
    owner_cost_gap = fields.Monetary(
        string='Dự toán CĐT còn lại', compute='_compute_mua_hang',
        currency_field='currency_id',
        help='Dự toán tự mua trừ phần đã cam kết. Âm là đã cam kết vượt '
             'dự toán của chính mình.')

    @api.depends('purchase_order_ids.state',
                 'purchase_order_ids.amount_untaxed',
                 'purchase_order_ids.invoice_ids.state',
                 'project_cost_line_ids.amount')
    def _compute_mua_hang(self):
        for p in self:
            don = p.purchase_order_ids
            da_duyet = don.filtered(
                lambda o: o.state in ('purchase', 'done'))
            p.purchase_order_count = len(don)
            p.owner_cost_committed = sum(da_duyet.mapped('amount_untaxed'))
            hoa_don = da_duyet.mapped('invoice_ids').filtered(
                lambda m: m.state == 'posted'
                and m.move_type in ('in_invoice', 'in_refund'))
            p.owner_cost_invoiced = sum(
                (-1.0 if m.move_type == 'in_refund' else 1.0)
                * (m.amount_untaxed or 0.0) for m in hoa_don)
            # Trừ dự phòng ra: nó nằm chung trong dòng chi phí cấp dự
            # án nhưng không phải thứ đi mua được. Cờ dự phòng gắn ở
            # nhóm CẤP 1 nên phải hỏi cả nhóm gốc.
            du_toan = sum(
                l.amount for l in p.project_cost_line_ids
                if not (l.category_id.is_contingency
                        or l.category_id.root_id.is_contingency))
            p.owner_cost_budget = du_toan
            p.owner_cost_gap = du_toan - p.owner_cost_committed

    def action_mo_don_mua(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': 'Đơn mua — %s' % self.name,
            'res_model': 'purchase.order', 'view_mode': 'list,form',
            'domain': [('rp_project_id', '=', self.id)],
            'context': {'default_rp_project_id': self.id},
        }
