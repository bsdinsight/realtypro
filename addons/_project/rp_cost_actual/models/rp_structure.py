# -*- coding: utf-8 -*-
"""Roll-up chi phí thực (AC) theo hạng mục từ dòng hóa đơn nhà thầu."""
from odoo import api, fields, models


class RpStructure(models.Model):
    _inherit = 'rp.structure'

    actual_move_line_ids = fields.One2many(
        'account.move.line', 'structure_id',
        string='Dòng chi phí thực')
    cost_allocation_ids = fields.One2many(
        'rp.cost.allocation', 'structure_id',
        string='Phân bổ chi phí (split)')
    actual_cost = fields.Monetary(
        string='Chi phí thực (AC)',
        compute='_compute_actual_cost', store=True,
        currency_field='currency_id',
        help='Σ giá trị (chưa thuế) chi phí ĐÃ POSTED gắn hạng mục này: '
             'dòng hóa đơn trực tiếp (khi KHÔNG split) + phân bổ split. '
             'in_invoice cộng, in_refund trừ. Nguồn AC cho EVM.')

    def _doi(self, mon, val, cur, ngay):
        """Quy đổi ``val`` từ loại tiền của chứng từ ``mon`` về ``cur``.

        Hoá đơn ghi bằng tiền khác hạng mục thì cộng thẳng
        ``price_subtotal`` là sai, mà sai KHÔNG BÁO LỖI — nó chỉ ra một
        con số rồi con số đó được dán ký hiệu tiền của hạng mục. Trên
        một dự án hạng mục ghi USD mà hoá đơn huy động ghi VND, nó cho
        AC = 30,93 tỷ trên nền BAC 181 triệu, kéo CPI của form dự án
        xuống 0,00.
        """
        if not val or not cur:
            return val or 0.0
        src = mon.currency_id
        if not src or src == cur:
            return val
        try:
            return src._convert(
                val, cur, mon.company_id or self.env.company,
                ngay or fields.Date.context_today(self))
        except Exception:
            # Thiếu tỷ giá: giữ số thô hơn là làm đổ cả hàm tính, nhưng
            # bảng điều khiển EVM có chốt `_thieu_ty_gia` báo đỏ việc này.
            return val

    @api.depends('actual_move_line_ids.price_subtotal',
                 'actual_move_line_ids.parent_state',
                 'actual_move_line_ids.move_id.move_type',
                 'actual_move_line_ids.cost_allocation_ids.amount',
                 'actual_move_line_ids.move_id.currency_id',
                 'cost_allocation_ids.amount',
                 'cost_allocation_ids.parent_state',
                 'cost_allocation_ids.move_line_id.move_id.move_type',
                 'cost_allocation_ids.move_line_id.move_id.currency_id',
                 'currency_id')
    def _compute_actual_cost(self):
        for rec in self:
            total = 0.0
            cur = rec.currency_id
            # Dòng hóa đơn gắn trực tiếp — CHỈ khi dòng không bị split
            for line in rec.actual_move_line_ids:
                if line.parent_state != 'posted':
                    continue
                if line.cost_allocation_ids:
                    continue  # đã split → tính theo allocation bên dưới
                mon = line.move_id
                val = self._doi(mon, line.price_subtotal, cur,
                                mon.invoice_date or mon.date)
                if mon.move_type == 'in_invoice':
                    total += val
                elif mon.move_type == 'in_refund':
                    total -= val
            # Phân bổ split trỏ vào hạng mục này
            for alloc in rec.cost_allocation_ids:
                if alloc.parent_state != 'posted':
                    continue
                mon = alloc.move_line_id.move_id
                val = self._doi(mon, alloc.amount, cur,
                                mon.invoice_date or mon.date)
                if mon.move_type == 'in_invoice':
                    total += val
                elif mon.move_type == 'in_refund':
                    total -= val
            rec.actual_cost = total
