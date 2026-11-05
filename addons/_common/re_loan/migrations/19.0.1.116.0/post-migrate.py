# -*- coding: utf-8 -*-
"""Việc 1571 vòng 2: kỳ trả THỪA chưa net-off đọc là "Trả một phần".

Trạng thái kỳ là trường tính có lưu: luật mới chỉ áp cho kỳ được tính
lại. Các kỳ đã "Đã trả" từ trước mà đang thừa tiền trả thẳng vào kỳ
(chưa net-off) phải được tính lại một lần, không thì cùng một tình huống
hiện hai trạng thái khác nhau tuỳ kỳ đó lập trước hay sau bản này.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    IL = env['re.loan.note.interest.line']
    stale = IL.search([('state', '=', 'paid')]).filtered(
        lambda l: l._paid_over_due() - (l.amount_over_net_off or 0.0) > 0.01)
    if not stale:
        return
    env.add_to_compute(IL._fields['state'], stale)
    stale.flush_recordset()
    _logger.info(
        're_loan 116: %s kỳ trả thừa chưa net-off chuyển về "Trả một phần".',
        len(stale.filtered(lambda l: l.state == 'partial_paid')))
