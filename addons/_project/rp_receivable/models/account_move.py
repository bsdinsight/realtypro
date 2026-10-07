# -*- coding: utf-8 -*-
from odoo import api, fields, models

NHOM_TUOI = [
    ('current', 'Chưa đến hạn'),
    ('d1_30', 'Quá hạn 1–30 ngày'),
    ('d31_60', 'Quá hạn 31–60 ngày'),
    ('d61_90', 'Quá hạn 61–90 ngày'),
    ('d90', 'Quá hạn trên 90 ngày'),
]


class AccountMove(models.Model):
    _inherit = 'account.move'

    rp_days_overdue = fields.Integer(
        string='Quá hạn (ngày)', compute='_compute_rp_tuoi_no', store=True,
        help='Số ngày đã quá hạn thanh toán. Âm là chưa đến hạn.')
    rp_aging_bucket = fields.Selection(
        NHOM_TUOI, string='Tuổi nợ', compute='_compute_rp_tuoi_no',
        store=True, index=True)
    rp_due_soon = fields.Boolean(
        string='Sắp đến hạn (30 ngày)', compute='_compute_rp_tuoi_no',
        store=True,
        help='Chưa quá hạn nhưng còn dưới 30 ngày. Dùng để xếp lịch chi '
             'tiền: đợi tới lúc quá hạn mới biết thì đã muộn.')

    # Cùng một thước đo cho CẢ HAI CHIỀU. Tuổi nợ phải trả và tuổi nợ
    # phải thu khác nhau ở ý nghĩa quản trị — một bên là tiền mình đòi,
    # một bên là tiền mình nợ — nhưng cách tính thì y hệt: lấy hôm nay
    # trừ hạn thanh toán. Tách thành hai bộ trường chỉ để trùng lặp mã và
    # rồi lệch nhau lúc sửa.
    @api.depends('invoice_date_due', 'payment_state', 'state', 'move_type',
                 'amount_residual')
    def _compute_rp_tuoi_no(self):
        # Mốc so là HÔM NAY, nên giá trị lưu sẽ cũ dần — cron 01:00 tính
        # lại toàn bộ hoá đơn còn nợ (xem data/ir_cron.xml).
        hom_nay = fields.Date.context_today(self)
        for m in self:
            no = (m.move_type in ('out_invoice', 'in_invoice')
                  and m.state == 'posted'
                  and m.payment_state not in ('paid', 'reversed')
                  and m.amount_residual > 0)
            if not (no and m.invoice_date_due):
                m.rp_days_overdue = 0
                m.rp_aging_bucket = False
                m.rp_due_soon = False
                continue
            n = (hom_nay - m.invoice_date_due).days
            m.rp_days_overdue = n
            m.rp_due_soon = -30 <= n < 0
            m.rp_aging_bucket = (
                'current' if n <= 0
                else 'd1_30' if n <= 30
                else 'd31_60' if n <= 60
                else 'd61_90' if n <= 90
                else 'd90')

    @api.model
    def rp_cron_tinh_tuoi_no(self):
        """Tính lại tuổi nợ hằng ngày — mốc so là hôm nay nên nó tự cũ."""
        no = self.search([('move_type', 'in', ('out_invoice', 'in_invoice')),
                          ('state', '=', 'posted'),
                          ('payment_state', 'not in', ('paid', 'reversed'))])
        no._compute_rp_tuoi_no()
        return len(no)
