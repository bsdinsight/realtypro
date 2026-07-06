# -*- coding: utf-8 -*-
"""TSBĐ Quyền đòi nợ — collateral gắn HĐ với CĐT, giá trị tự động.

Advance rate mặc định khai trên loại TSBĐ (re.loan.collateral.type).
"""
from odoo import _, api, fields, models


class ReLoanCollateralType(models.Model):
    _inherit = 're.loan.collateral.type'

    advance_rate = fields.Float(
        string='Tỷ lệ cho vay (%)', default=0.0,
        help='Tỷ lệ NH cho vay trên giá trị TSBĐ loại này (BĐS ~70, '
             'quyền đòi nợ ~50-70, tiền gửi ~95). Mặc định cho pledge — '
             'override được từng pledge. 0 = chưa khai → KHÔNG tính '
             'vào borrowing base.')


class ReLoanCollateral(models.Model):
    _inherit = 're.loan.collateral'

    owner_contract_id = fields.Many2one(
        'rp.owner.contract', string='HĐ với CĐT (quyền đòi nợ)',
        ondelete='restrict', index=True,
        help='Gắn HĐ đầu ra với Chủ đầu tư → tài sản này là QUYỀN ĐÒI '
             'NỢ: giá trị tự cập nhật = khoản phải thu (sản lượng CĐT '
             'duyệt − CĐT đã trả, floor 0). Mỗi biến động tự sinh bản '
             'ghi định giá (audit).')

    def write(self, vals):
        res = super().write(vals)
        if 'owner_contract_id' in vals:
            self.filtered('owner_contract_id')._sync_receivable_valuation(
                reason=_('Gắn HĐ với CĐT'))
        return res

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs.filtered('owner_contract_id')._sync_receivable_valuation(
            reason=_('Gắn HĐ với CĐT'))
        return recs

    def _sync_receivable_valuation(self, reason=''):
        """Tạo bản ghi định giá = khoản phải thu hiện hành (floor 0).

        Bỏ qua nếu giá trị không đổi so với định giá mới nhất (tránh
        spam record khi không có biến động thực).
        """
        Valuation = self.env['re.loan.collateral.valuation']
        today = fields.Date.context_today(self)
        for col in self:
            if not col.owner_contract_id:
                continue
            value = max(0.0, col.owner_contract_id.receivable)
            latest = col.valuation_ids.sorted(
                key=lambda v: (v.date, v.id), reverse=True)[:1]
            if latest and abs(latest.amount - value) < 0.01:
                continue
            Valuation.create({
                'collateral_id': col.id,
                'date': today,
                'amount': value,
                'method': 'cost',
                'appraiser': _('Tự động theo sản lượng/thanh toán'),
                'note': _(
                    'Auto (%(r)s): phải thu HĐ %(c)s = nghiệm thu '
                    '%(a)s − đã trả %(p)s.',
                    r=reason or _('biến động'),
                    c=col.owner_contract_id.name,
                    a='{:,.0f}'.format(
                        col.owner_contract_id.accepted_to_date),
                    p='{:,.0f}'.format(
                        col.owner_contract_id.paid_to_date)),
            })
