# -*- coding: utf-8 -*-
"""Nguồn chi trả trên mốc thanh toán HĐ.

Thực tế VN: 90–100% thanh toán HĐ xây dựng của CĐT/tổng thầu đi qua
KHẾ ƯỚC vay (ngân hàng giải ngân thẳng cho nhà thầu theo hồ sơ
BBN + hoá đơn) — chỉ phần nhỏ chi bằng vốn tự có. Field này trả lời
"mốc này trả bằng tiền nào?" ngay trên Hồ sơ thanh toán.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class RpContractPaymentMilestone(models.Model):
    _inherit = 'rp.contract.payment.milestone'

    funding_source = fields.Selection(
        [('equity', 'Vốn tự có'),
         ('owner_advance', 'Tạm ứng CĐT'),
         ('loan', 'Khế ước vay')],
        # KHÔNG khai `tracking`: model này không kế thừa mail.thread nên
        # Odoo bỏ qua tham số và log warning mỗi lần nạp registry.
        string='Nguồn chi trả',
        help='Ba nguồn tổng thầu dùng để trả nhà thầu/NCC:\n'
             '• Vốn tự có — chi từ tài khoản công ty\n'
             '• Tạm ứng CĐT — tiền chủ đầu tư ứng trước, dùng để trả '
             'thầu phụ; rút tới đâu trừ vào đợt tạm ứng tới đó\n'
             '• Khế ước vay — ngân hàng giải ngân thẳng cho nhà thầu '
             'theo hồ sơ (BBNT + hoá đơn).')
    loan_note_id = fields.Many2one(
        're.loan.note', string='Khế ước (KW)', index=True,
        help='KW dùng để giải ngân cho mốc này (khi nguồn = Khế ước vay).')
    owner_advance_id = fields.Many2one(
        'rp.owner.advance', string='Đợt tạm ứng CĐT', index=True,
        help='Đợt tạm ứng dùng để trả mốc này (khi nguồn = Tạm ứng CĐT). '
             'Hệ thống trừ vào tiền còn lại của đợt đó.')

    @api.onchange('funding_source')
    def _onchange_funding_source_clear(self):
        if self.funding_source != 'loan':
            self.loan_note_id = False
        if self.funding_source != 'owner_advance':
            self.owner_advance_id = False

    @api.constrains('funding_source', 'owner_advance_id', 'amount', 'state')
    def _check_owner_advance_enough(self):
        """Không cho rút quá số tiền còn lại của đợt tạm ứng."""
        for rec in self:
            if rec.funding_source != 'owner_advance':
                continue
            adv = rec.owner_advance_id
            if not adv:
                raise ValidationError(_(
                    "Mốc '%s' chọn nguồn Tạm ứng CĐT thì phải chỉ rõ đợt "
                    "tạm ứng nào.", rec.name))
            if adv.owner_contract_id.project_id != rec.contract_id.project_id:
                raise ValidationError(_(
                    "Đợt tạm ứng %(a)s thuộc dự án %(p1)s, còn mốc thanh "
                    "toán thuộc dự án %(p2)s.",
                    a=adv.name,
                    p1=adv.owner_contract_id.project_id.display_name,
                    p2=rec.contract_id.project_id.display_name))
            # trừ chính mốc này ra khỏi phần đã dùng để so sánh
            used_other = sum(self.search([
                ('funding_source', '=', 'owner_advance'),
                ('owner_advance_id', '=', adv.id),
                ('id', '!=', rec.id)]).mapped('amount'))
            if used_other + rec.amount > adv.amount + 0.01:
                raise ValidationError(_(
                    "Đợt tạm ứng %(a)s chỉ còn %(l)s nhưng mốc '%(m)s' "
                    "cần %(n)s.\nChọn đợt khác, hoặc đổi nguồn sang Vốn "
                    "tự có / Khế ước vay.",
                    a=adv.name,
                    l='{:,.0f}'.format(max(0.0, adv.amount - used_other)),
                    m=rec.name, n='{:,.0f}'.format(rec.amount)))
