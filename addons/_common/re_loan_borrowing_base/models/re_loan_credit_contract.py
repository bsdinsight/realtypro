# -*- coding: utf-8 -*-
"""HĐTD: base tổng (umbrella) + khả dụng + margin call toàn gói."""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ReLoanCreditContract(models.Model):
    _inherit = 're.loan.credit.contract'

    all_pledge_ids = fields.One2many(
        're.loan.collateral.pledge', 'credit_contract_id',
        string='Toàn bộ pledge (mọi cấp)')
    borrowing_base_total = fields.Monetary(
        string='Cơ sở bảo đảm (base tổng)',
        compute='_compute_borrowing_base_total', store=True,
        help='Σ đóng góp của MỌI pledge đang thế chấp thuộc HĐTD '
             '(cấp HĐTD + facility + KW) = trần theo tài sản.')
    has_any_pledges = fields.Boolean(
        compute='_compute_borrowing_base_total', store=True)
    amount_used_total = fields.Monetary(
        string='Tổng dư nợ đã dùng',
        compute='_compute_used_total',
        help='Σ đã sử dụng của các facility dưới HĐTD.')
    amount_available_effective = fields.Monetary(
        string='Khả dụng thực tế (HĐTD)',
        compute='_compute_available_effective',
        help='= min(Tổng hạn mức, Cơ sở bảo đảm) − tổng dư nợ. '
             'Floor 0. Không có pledge nào → bỏ ràng buộc base.')
    margin_call = fields.Boolean(
        string='Cảnh báo thiếu bảo đảm (HĐTD)',
        compute='_compute_available_effective',
        help='Tổng dư nợ vượt cơ sở bảo đảm toàn HĐTD.')
    unrated_pledge_count = fields.Integer(
        string='Pledge chưa khai tỷ lệ',
        compute='_compute_unrated_pledges',
        help='Số TSBĐ đang thế chấp nhưng CHƯA khai Tỷ lệ cho vay (%) '
             '— chưa tham gia cơ sở bảo đảm, định giá lại các TS này '
             'không ảnh hưởng khả dụng.')

    @api.depends('all_pledge_ids.state', 'all_pledge_ids.advance_rate')
    def _compute_unrated_pledges(self):
        for rec in self:
            rec.unrated_pledge_count = len(rec.all_pledge_ids.filtered(
                lambda p: p.state == 'active' and not p.advance_rate))

    # ⚠ GỠ CHẶN CỨNG "Σ hạn mức facility ≤ Cơ sở bảo đảm" (2026-08-10).
    # Tài liệu nghiệp vụ tài liệu nghiệp vụ §2 tách rõ BA con số: (1) hạn mức được PHÊ
    # DUYỆT — trần ngân hàng cam kết; (2) cơ sở bảo đảm — trần thực theo
    # TSBĐ, lên xuống liên tục; (3) khả dụng = min(1,2) − dư nợ. Hạn mức
    # phê duyệt ĐƯỢC PHÉP cao hơn TSBĐ hiện có — đó chính là cảnh báo
    # trung tâm của tài liệu ("nhiều DN chỉ nhìn (1) mà quên (2)"), và ví
    # dụ §9 của họ có sublimit 500 tỷ trên BB 250 tỷ. Chặn cứng ở đây làm
    # hệ thống KHÔNG dựng nổi chính ví dụ của khách.
    # Thiếu bảo đảm vẫn thấy được: `margin_call` trên HĐTD, cột "Đang bị
    # chặn bởi" ở dòng dự án, và khả dụng tự siết qua nhánh ② của min().

    @api.depends('all_pledge_ids.base_contribution',
                 'all_pledge_ids.state')
    def _compute_borrowing_base_total(self):
        for rec in self:
            # Chỉ pledge đã khai tỷ lệ (xem ghi chú ở facility).
            pledges = rec.all_pledge_ids.filtered(
                lambda p: p.state == 'active' and p.advance_rate)
            rec.borrowing_base_total = sum(
                pledges.mapped('base_contribution'))
            rec.has_any_pledges = bool(pledges)

    @api.depends('facility_ids.amount_used')
    def _compute_used_total(self):
        for rec in self:
            rec.amount_used_total = sum(
                rec.facility_ids.mapped('amount_used'))

    @api.depends('amount_total', 'amount_used_total',
                 'has_any_pledges', 'borrowing_base_total')
    def _compute_available_effective(self):
        for rec in self:
            used = rec.amount_used_total
            candidates = [rec.amount_total - used]
            if rec.has_any_pledges:
                candidates.append(rec.borrowing_base_total - used)
            rec.amount_available_effective = max(0.0, min(candidates))
            rec.margin_call = (
                rec.has_any_pledges
                and used > rec.borrowing_base_total + 0.01)


class ReLoanCreditContractProjectView(models.Model):
    """Bảng tổng hợp hạn mức THEO DỰ ÁN trên HĐTD (spec nghiệp vụ khối 2 mục 1:
    'hạn mức còn lại của từng dự án theo từng mục đích')."""
    _inherit = 're.loan.credit.contract'

    project_allocation_all_ids = fields.One2many(
        're.loan.facility.project.allocation', string='Phân bổ theo dự án',
        compute='_compute_project_allocation_all',
        help='Mọi dòng phân bổ dự án của các facility thuộc HĐTD này.')

    @api.depends('facility_ids.project_allocation_ids')
    def _compute_project_allocation_all(self):
        Alloc = self.env['re.loan.facility.project.allocation']
        for rec in self:
            rec.project_allocation_all_ids = Alloc.search(
                [('facility_id.credit_contract_id', '=', rec.id)],
                order='project_id, facility_id')
