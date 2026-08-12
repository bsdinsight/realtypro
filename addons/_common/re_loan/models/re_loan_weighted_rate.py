# -*- coding: utf-8 -*-
"""Lãi suất bình quân GIA QUYỀN theo dư nợ — cấp facility và HĐTD.

Trung bình cộng lãi suất là con số SAI mà rất dễ vô tình dùng: một khế
ước 1 tỷ lãi 12%/năm và một khế ước 100 tỷ lãi 8%/năm cho trung bình
cộng 10%, trong khi lãi suất thực trả bình quân là 8,04%. Chênh 2 điểm
phần trăm trên 101 tỷ là hơn 2 tỷ đồng lãi mỗi năm.

Vì vậy con số này phải được TÍNH SẴN và bày ra đúng chỗ, thay vì để
người dùng tự lấy trung bình trong báo cáo.

Trọng số là DƯ NỢ GỐC chứ không phải số tiền khế ước: lãi tính trên phần
còn nợ, khế ước đã trả gần hết thì lãi suất của nó gần như không còn ảnh
hưởng tới chi phí vốn hiện tại.
"""
from odoo import api, fields, models

LIVE_STATES = ('active', 'partial_paid', 'overdue', 'restructured')


def _weighted(notes):
    """Σ(lãi suất × dư nợ) ÷ Σ dư nợ. Không có dư nợ → 0."""
    base = sum(notes.mapped('principal_outstanding'))
    if not base:
        return 0.0
    return sum(n.interest_rate * n.principal_outstanding
               for n in notes) / base


class ReLoanFacilityWeightedRate(models.Model):
    _inherit = 're.loan.facility'

    interest_rate_weighted = fields.Float(
        string='LS bình quân gia quyền (%/năm)', digits=(5, 2),
        compute='_compute_interest_rate_weighted', aggregator=None,
        help='Bình quân lãi suất các khế ước còn dư nợ của hạn mức này, '
             'GIA QUYỀN theo dư nợ gốc. Không phải trung bình cộng — '
             'trung bình cộng cho con số sai lệch tới vài điểm phần '
             'trăm khi các khế ước chênh nhau nhiều về quy mô.')

    @api.depends('note_ids.interest_rate', 'note_ids.principal_outstanding',
                 'note_ids.state')
    def _compute_interest_rate_weighted(self):
        for rec in self:
            rec.interest_rate_weighted = _weighted(
                rec.note_ids.filtered(lambda n: n.state in LIVE_STATES))


class ReLoanCreditContractWeightedRate(models.Model):
    _inherit = 're.loan.credit.contract'

    interest_rate_weighted = fields.Float(
        string='LS bình quân gia quyền (%/năm)', digits=(5, 2),
        compute='_compute_interest_rate_weighted', aggregator=None,
        help='Bình quân lãi suất toàn bộ khế ước còn dư nợ dưới HĐTD '
             'này, gia quyền theo dư nợ gốc — chi phí vốn thực tế đang '
             'trả cho ngân hàng này.')

    @api.depends('facility_ids.note_ids.interest_rate',
                 'facility_ids.note_ids.principal_outstanding',
                 'facility_ids.note_ids.state')
    def _compute_interest_rate_weighted(self):
        for rec in self:
            notes = rec.facility_ids.mapped('note_ids').filtered(
                lambda n: n.state in LIVE_STATES)
            rec.interest_rate_weighted = _weighted(notes)
