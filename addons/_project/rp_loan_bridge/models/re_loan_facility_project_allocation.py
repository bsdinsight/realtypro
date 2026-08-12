# -*- coding: utf-8 -*-
"""Phân bổ hạn mức THẲNG cho hợp đồng nhà thầu — dự án tự suy ra.

Anh Đại chốt 2026-08-04 (users phản ánh phải khai hai lần): người dùng chỉ
chọn HỢP ĐỒNG (xây lắp hoặc mua hàng hoá); Dự án tự điền theo hợp đồng —
`rp.contract.project_id` là related từ gói thầu nên luôn có sẵn, không cần
khai lại.

Trục DỰ ÁN vẫn nguyên vẹn (borrowing base ring-fence theo dự án, nhu cầu
vốn dự án, checklist giải ngân đều roll-up theo `project_id` của dòng) —
chỉ bỏ THAO TÁC khai dự án, không bỏ chiều dữ liệu.

Dòng KHÔNG chọn hợp đồng vẫn hợp lệ = phân bổ ở cấp dự án. Cần giữ vì:
- ngân hàng cấp hạn mức TRƯỚC khi ký hợp đồng thầu phụ;
- có khoản vay không gắn hợp đồng nào (vốn lưu động, lãi, chi phí chung).
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ReLoanFacilityProjectAllocation(models.Model):
    _inherit = 're.loan.facility.project.allocation'

    contract_id = fields.Many2one(
        'rp.contract', string='HĐ nhà thầu', ondelete='restrict', index=True,
        help='Phân bổ riêng cho MỘT hợp đồng (xây lắp hoặc mua hàng hoá). '
             'Chọn xong thì Dự án tự điền theo hợp đồng, không phải khai. '
             'Để TRỐNG = phân bổ ở cấp dự án (dùng khi chưa ký hợp đồng, '
             'hoặc khoản vay không gắn hợp đồng nào).')
    contract_partner_id = fields.Many2one(
        related='contract_id.contractor_id', string='Nhà thầu', readonly=True,
        store=True)
    contract_value_total = fields.Monetary(
        related='contract_id.contract_value_total', readonly=True,
        string='Giá trị HĐ')
    is_auto = fields.Boolean(
        string='Tự đồng bộ', default=False, copy=False,
        help='Dòng do hệ thống tự sinh từ Dự án + HĐ khai trên chính hạn '
             'mức này (mô hình 1 hạn mức = 1 hợp đồng). Sửa ở form Hạn '
             'mức, đừng sửa trực tiếp ở đây.')
    alloc_level = fields.Selection(
        [('contract', 'Theo hợp đồng'), ('project', 'Theo dự án')],
        string='Cấp phân bổ', compute='_compute_alloc_level', store=True,
        help='Dòng gắn hợp đồng thì siết theo hợp đồng đó; dòng không gắn '
             'là phần chung của dự án.')

    @api.depends('contract_id')
    def _compute_alloc_level(self):
        for rec in self:
            rec.alloc_level = 'contract' if rec.contract_id else 'project'

    @api.onchange('contract_id')
    def _onchange_contract_fill_project(self):
        """Chọn hợp đồng → dự án tự điền (đây là điểm bỏ bớt thao tác)."""
        if self.contract_id:
            self.project_id = self.contract_id.project_id

    @api.model_create_multi
    def create(self, vals_list):
        Contract = self.env['rp.contract']
        for vals in vals_list:
            if vals.get('contract_id'):
                # ép theo hợp đồng kể cả khi client không gửi project_id
                # (import, tạo từ code, list view không chạy onchange).
                vals['project_id'] = Contract.browse(
                    vals['contract_id']).project_id.id
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('contract_id'):
            vals['project_id'] = self.env['rp.contract'].browse(
                vals['contract_id']).project_id.id
        return super().write(vals)

    @api.constrains('contract_id', 'project_id')
    def _check_contract_project(self):
        for rec in self:
            ct = rec.contract_id
            if ct and ct.project_id != rec.project_id:
                raise ValidationError(_(
                    "Hợp đồng %(c)s thuộc dự án %(cp)s nhưng dòng phân bổ "
                    "đang ghi dự án %(p)s — dự án phải lấy theo hợp đồng.",
                    c=ct.display_name,
                    cp=ct.project_id.display_name or '—',
                    p=rec.project_id.display_name or '—'))

    @api.constrains('contract_id', 'facility_id')
    def _check_contract_not_duplicated(self):
        """Một hợp đồng chỉ có MỘT dòng trên cùng facility.

        Hai dòng cùng hợp đồng sẽ cùng trừ một khoản dư nợ → khả dụng bị
        thổi phồng gấp đôi.
        """
        for rec in self.filtered('contract_id'):
            dup = self.search_count([
                ('id', '!=', rec.id),
                ('facility_id', '=', rec.facility_id.id),
                ('contract_id', '=', rec.contract_id.id)])
            if dup:
                raise ValidationError(_(
                    "Hợp đồng %(c)s đã có dòng phân bổ trên hạn mức "
                    "%(f)s — gộp vào dòng đó thay vì tạo dòng thứ hai.",
                    c=rec.contract_id.display_name,
                    f=rec.facility_id.display_name))
