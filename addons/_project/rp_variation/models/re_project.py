# -*- coding: utf-8 -*-
"""Phát sinh nhìn từ dự án: ngân sách — cam kết — phát sinh — dự báo.

Đây là màn hình trả lời câu hỏi của chủ đầu tư: nhà thầu phát sinh khối
lượng thì ngân sách dự án còn đủ không. Bốn con số phải nằm cạnh nhau:

  ngân sách duyệt (BAC)  ·  đã cam kết theo hợp đồng  ·  phát sinh
  (đã duyệt + đang chờ)  ·  dự báo chi phí cuối kỳ

Thiếu cột "đang chờ" là tự lừa mình: phát sinh chưa duyệt vẫn sẽ phải
trả nếu công việc đã làm ngoài hiện trường.
"""
from odoo import _, api, fields, models


class ReProject(models.Model):
    _inherit = 're.project'

    variation_ids = fields.One2many(
        'rp.variation', 'project_id', string='Phát sinh')
    variation_count = fields.Integer(
        string='Số phát sinh', compute='_compute_variation_rollup')
    variation_open_count = fields.Integer(
        string='Phát sinh đang xử lý', compute='_compute_variation_rollup')
    variation_approved_total = fields.Monetary(
        string='Phát sinh đã duyệt', compute='_compute_variation_rollup',
        currency_field='currency_id')
    variation_pending_total = fields.Monetary(
        string='Phát sinh đang chờ', compute='_compute_variation_rollup',
        currency_field='currency_id')
    contract_committed_total = fields.Monetary(
        string='Đã cam kết theo hợp đồng',
        compute='_compute_variation_rollup', currency_field='currency_id')
    cost_forecast_total = fields.Monetary(
        string='Dự báo chi phí cuối kỳ', compute='_compute_variation_rollup',
        currency_field='currency_id')
    budget_gap = fields.Monetary(
        string='Chênh so ngân sách', compute='_compute_variation_rollup',
        currency_field='currency_id',
        help='Dự báo chi phí cuối kỳ trừ ngân sách duyệt (BAC). Dương là '
             'vượt ngân sách.')

    @api.depends('variation_ids.state', 'variation_ids.amount_approved',
                 'variation_ids.amount_quoted', 'total_bac')
    def _compute_variation_rollup(self):
        Contract = self.env['rp.contract']
        for rec in self:
            vs = rec.variation_ids
            rec.variation_count = len(vs)
            rec.variation_open_count = len(vs.filtered(
                lambda v: v.state in ('draft', 'requested', 'quoted',
                                      'review')))
            rec.variation_approved_total = sum(vs.filtered(
                lambda v: v.state in ('approved', 'instructed', 'applied')
            ).mapped('amount_approved'))
            rec.variation_pending_total = sum(vs.filtered(
                lambda v: v.state in ('draft', 'requested', 'quoted',
                                      'review')).mapped('amount_quoted'))
            contracts = Contract.search([('project_id', '=', rec.id)])
            # Giá hợp đồng hiện hành đã gồm phần phát sinh đã vào phụ lục.
            committed = sum(contracts.mapped('contract_value_pretax'))
            not_yet = sum(vs.filtered(
                lambda v: v.state in ('approved', 'instructed')).mapped(
                    'amount_approved'))
            rec.contract_committed_total = committed
            rec.cost_forecast_total = (committed + not_yet
                                       + rec.variation_pending_total)
            rec.budget_gap = rec.cost_forecast_total - (rec.total_bac or 0.0)

    def action_open_variations(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Phát sinh — %s', self.name),
            'res_model': 'rp.variation',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }
