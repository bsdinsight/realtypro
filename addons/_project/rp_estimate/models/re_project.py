# -*- coding: utf-8 -*-
"""Dự án nhìn xuống gói thầu.

Gói thầu đã có ``project_id`` từ lâu, nhưng chiều ngược lại thì không —
nên muốn xem dự án này có bao nhiêu gói, hay mở một gói ra, đều phải đi
vòng qua menu Gói thầu rồi tự lọc. Hai thao tác đó làm mỗi ngày.
"""
from odoo import _, api, fields, models


class ReProjectTender(models.Model):
    _inherit = 're.project'

    tender_package_ids = fields.One2many(
        'rp.tender.package', 'project_id', string='Gói thầu')
    tender_package_count = fields.Integer(
        string='Số gói thầu', compute='_compute_tender_package',
        store=True)

    # KHÔNG cộng tổng giá trị gói thầu ở đây: ``re.project`` của re_base
    # không có trường tiền tệ nào — ``currency_id`` là do rp_evm thêm
    # vào. Khai một Monetary trỏ vào nó sẽ làm VỠ LÚC NẠP REGISTRY
    # ("unknown currency_field"), và vỡ cho mọi cơ sở dữ liệu chưa cài
    # rp_evm chứ không riêng chỗ mình thử.

    @api.depends('tender_package_ids')
    def _compute_tender_package(self):
        for p in self:
            p.tender_package_count = len(p.tender_package_ids)

    def action_mo_goi_thau(self):
        """Danh sách gói thầu của dự án — và TẠO MỚI ngay tại đây.

        ``default_project_id`` trong context là thứ làm nút này khác một
        bộ lọc: bấm Mới trong danh sách vừa mở ra thì gói mới đã thuộc
        sẵn dự án, không phải chọn lại.
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Gói thầu — %s', self.name),
            'res_model': 'rp.tender.package',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }

    def action_tao_goi_thau(self):
        """Mở thẳng form gói thầu mới cho dự án này."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Gói thầu mới — %s', self.name),
            'res_model': 'rp.tender.package',
            'view_mode': 'form',
            'context': {'default_project_id': self.id},
        }
