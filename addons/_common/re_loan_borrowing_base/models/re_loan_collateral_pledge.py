# -*- coding: utf-8 -*-
"""Pledge: tỷ lệ cho vay + đóng góp vào borrowing base."""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ReLoanCollateralPledge(models.Model):
    _inherit = 're.loan.collateral.pledge'

    advance_rate = fields.Float(
        string='Tỷ lệ cho vay (%)',
        compute='_compute_advance_rate', store=True, readonly=False,
        help='Mặc định theo loại TSBĐ — sửa được từng pledge (cùng là '
             'phải thu nhưng CĐT uy tín khác nhau → tỷ lệ khác nhau). '
             '0 = không tính vào borrowing base.')
    base_contribution = fields.Monetary(
        string='Đóng góp base',
        compute='_compute_base_contribution', store=True,
        currency_field='currency_id',
        help='= min(Giá trị đảm bảo theo HĐ thế chấp, Giá trị hiện hành '
             'TS theo định giá mới nhất) × tỷ lệ cho vay. Định giá lại '
             'TSĐB GIẢM → base giảm theo (khả dụng HĐTD/facility giảm); '
             'tăng thì vẫn trần ở giá trị đảm bảo đã ký (muốn tăng phải '
             'ký phụ lục). TS chưa định giá → dùng giá trị đảm bảo. '
             'Chỉ tính pledge đang thế chấp.')

    allocation_ids = fields.One2many(
        're.loan.pledge.allocation', 'pledge_id', string='Phân bổ cho mục đích')
    amount_allocated = fields.Monetary(
        string='Đã phân bổ', currency_field='currency_id',
        compute='_compute_allocation', store=True)
    amount_unallocated = fields.Monetary(
        string='Chưa phân bổ', currency_field='currency_id',
        compute='_compute_allocation', store=True,
        help='Phần đóng góp base chưa chia cho mục đích nào. Còn dư ở đây '
             'nghĩa là TSBĐ đã thế chấp nhưng chưa đỡ lưng cho mục đích '
             'nào cả — không mục đích nào tăng khả dụng.')
    over_allocated = fields.Boolean(
        string='Phân bổ vượt giá trị TSBĐ', compute='_compute_allocation',
        store=True,
        help='Tổng phân bổ đang lớn hơn đóng góp base. Thường do định giá '
             'lại làm giá trị tài sản giảm sau khi đã phân bổ. Hệ thống '
             'KHÔNG chặn lúc định giá — phải vào sửa lại phân bổ.')

    @api.depends('allocation_ids.amount', 'base_contribution')
    def _compute_allocation(self):
        for rec in self:
            total = sum(rec.allocation_ids.mapped('amount'))
            base = rec.base_contribution or 0.0
            rec.amount_allocated = total
            rec.amount_unallocated = max(0.0, base - total)
            rec.over_allocated = total > base + 0.01

    @api.model_create_multi
    def create(self, vals_list):
        pledges = super().create(vals_list)
        pledges._auto_allocate()
        return pledges

    def _auto_allocate(self):
        """Tự phân bổ những trường hợp KHÔNG cần người quyết.

        Hai ca, và chỉ hai:

        ① Thế chấp gắn thẳng một mục đích → cả phần base về mục đích đó.
           Không có gì để chọn, chọn hộ là đúng.

        ② TSBĐ là QUYỀN ĐÒI NỢ theo IPC → về mục đích có cùng HĐ với chủ
           đầu tư. IPC luôn đi kèm một hợp đồng CĐT, mục đích vay cũng
           khai hợp đồng đó, nên khớp được chính xác — không phải đoán
           theo dự án (một dự án có thể nhận hạn mức từ nhiều mục đích).

        Khớp ra NHIỀU HƠN MỘT mục đích thì KHÔNG tự chia: để trống cho
        người dùng vào chia. Đoán trong ca này là sai tiền, mà lại sai
        lặng lẽ.
        """
        Alloc = self.env['re.loan.pledge.allocation']
        vals = []
        for p in self:
            if p.state != 'active' or not p.base_contribution:
                continue
            if p.allocation_ids:
                continue
            target = None
            if p.pledge_target == 'facility' and p.facility_id:
                target = p.facility_id
            else:
                ipc = p.collateral_id.owner_ipc_id
                facs = p.credit_contract_id.facility_ids
                if ipc and facs and 'owner_contract_id' in facs._fields:
                    match = facs.filtered(
                        lambda f: f.owner_contract_id
                        and f.owner_contract_id == ipc.contract_id)
                    if len(match) == 1:
                        target = match
            if target:
                vals.append({
                    'pledge_id': p.id,
                    'facility_id': target.id,
                    'amount': p.base_contribution,
                })
        if vals:
            Alloc.create(vals)

    @api.constrains('secured_amount', 'collateral_id', 'state')
    def _check_within_collateral(self):
        """Đem đi thế chấp không vượt phần CÒN LẠI của tài sản.

        Tính trên MỌI văn bản thế chấp của tài sản đó, không riêng HĐTD
        này — một tài sản 100 tỷ không thể đỡ lưng 70 tỷ ở HĐTD A rồi
        lại 70 tỷ ở HĐTD B.
        """
        for rec in self:
            if rec.state != 'active' or not rec.collateral_id:
                continue
            col = rec.collateral_id
            others = col.pledge_ids.filtered(
                lambda p: p.state == 'active' and p.id != rec.id)
            used = sum(others.mapped('secured_amount'))
            room = (col.value_current or 0.0) - used
            if (rec.secured_amount or 0.0) > room + 0.01:
                raise ValidationError(_(
                    'Vượt giá trị còn lại của tài sản bảo đảm.\n\n'
                    'Tài sản: %(c)s\n'
                    'Giá trị hiện hành: %(v)s\n'
                    'Đang thế chấp ở nơi khác: %(u)s\n'
                    'Còn có thể thế chấp: %(r)s\n'
                    'Đang khai: %(s)s',
                    c=col.display_name,
                    v='{:,.0f}'.format(col.value_current or 0.0),
                    u='{:,.0f}'.format(used),
                    r='{:,.0f}'.format(max(0.0, room)),
                    s='{:,.0f}'.format(rec.secured_amount or 0.0)))

    @api.depends('collateral_id.type_id.advance_rate')
    def _compute_advance_rate(self):
        for rec in self:
            if not rec.advance_rate:
                rec.advance_rate = (
                    rec.collateral_id.type_id.advance_rate or 0.0)

    @api.depends('advance_rate', 'secured_amount', 'state',
                 'collateral_id.value_current')
    def _compute_base_contribution(self):
        for rec in self:
            if rec.state != 'active' or not rec.advance_rate:
                rec.base_contribution = 0.0
                continue
            value_current = rec.collateral_id.value_current
            base_value = rec.secured_amount or value_current
            # Định giá lại TSĐB thấp hơn giá trị đảm bảo theo HĐ thế
            # chấp → NH chỉ cho vay trên giá trị thực → cap theo định
            # giá mới nhất. Chỉ cap khi TS ĐÃ có định giá (chưa định
            # giá thì tin giá trị HĐ thế chấp).
            if value_current:
                base_value = min(base_value, value_current)
            rec.base_contribution = base_value * rec.advance_rate / 100.0
