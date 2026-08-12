# -*- coding: utf-8 -*-
"""Hoá đơn phải gắn dự án — nếu không thì rơi khỏi mọi số liệu dự án.

Hoá đơn tạo THẲNG trong app Hoá đơn (Invoicing) của Odoo không mang
ngữ cảnh dự án: `project_id` chỉ tự suy ra khi hoá đơn đi từ mốc thanh
toán HĐ nhà thầu, `owner_project_id` chỉ có khi gắn HĐ với CĐT. Hoá đơn
trống ngữ cảnh sẽ BIẾN MẤT khỏi:

  • ④ Công nợ NCC trong phiếu Nhu cầu vốn dự án  → nhu cầu vay tính THỪA
  • Chi phí đã thực hiện (AC) của EVM            → biên lợi nhuận dự báo
    sai, kéo theo chỉ tiêu ⑦ và tín hiệu §8 ④

Vì có hai cửa nhập cho cùng một việc (app Hoá đơn trần, và Công nợ nhà
thầu / Doanh thu CĐT có sẵn hợp đồng), người dùng sẽ chọn cửa gần nhất
— thường là cửa không có ngữ cảnh.

CẢNH BÁO MỀM, KHÔNG CHẶN: hoá đơn ngoài dự án là có thật (thuê văn
phòng, lương khối gián tiếp, phí ngân hàng). Chặn cứng sẽ buộc kế toán
gắn bừa một dự án — sai còn tệ hơn để trống. Thay vào đó:
  • cờ "Không thuộc dự án nào" để khai báo có chủ đích;
  • băng đỏ trên phiếu khi chưa gắn mà cũng chưa khai;
  • ghi sổ vẫn chạy, nhưng để lại ghi chú trong chatter để còn truy.
"""
from markupsafe import Markup

from odoo import _, api, fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    rp_no_project = fields.Boolean(
        string='Không thuộc dự án nào', copy=False, tracking=True,
        help='Tick khi hoá đơn này thật sự KHÔNG thuộc dự án nào — chi '
             'phí văn phòng, lương khối gián tiếp, phí ngân hàng... '
             'Khai có chủ đích thì hết cảnh báo, và người sau biết đây '
             'là quyết định chứ không phải bỏ sót.')
    rp_project_missing = fields.Boolean(
        string='Chưa gắn dự án', compute='_compute_rp_project_missing',
        store=True,
        help='Hoá đơn mua vào/bán ra chưa gắn dự án và cũng chưa khai '
             '"không thuộc dự án nào".')

    @api.depends('move_type', 'project_id', 'owner_project_id',
                 'rp_no_project')
    def _compute_rp_project_missing(self):
        for mv in self:
            in_scope = mv.move_type in ('in_invoice', 'out_invoice')
            linked = bool(mv.project_id or mv.owner_project_id)
            mv.rp_project_missing = bool(
                in_scope and not linked and not mv.rp_no_project)

    def action_post(self):
        res = super().action_post()
        for mv in self.filtered('rp_project_missing'):
            # Markup: `_()` trả chuỗi thường, message_post sẽ ESCAPE thẻ
            # HTML thành &lt;b&gt; hiện ra màn hình.
            mv.message_post(body=Markup(_(
                '<b>Hoá đơn ghi sổ khi CHƯA gắn dự án.</b><br/>'
                'Số tiền này sẽ không vào Công nợ NCC của phiếu Nhu cầu '
                'vốn, cũng không vào chi phí đã thực hiện (AC) của dự án '
                'nào. Gắn dự án, hoặc tick "Không thuộc dự án nào" nếu '
                'đúng là chi phí chung.')))
        return res
