# -*- coding: utf-8 -*-
"""Facility: base riêng (ring-fence) + khả dụng thực tế 3-min."""
from odoo import api, fields, models


class ReLoanFacility(models.Model):
    _inherit = 're.loan.facility'

    facility_pledge_ids = fields.One2many(
        're.loan.collateral.pledge', 'facility_id',
        string='TSBĐ riêng facility',
        domain=[('pledge_target', '=', 'facility')])
    pledge_allocation_ids = fields.One2many(
        're.loan.pledge.allocation', 'facility_id',
        string='TSBĐ phân bổ cho mục đích này')
    borrowing_base_own = fields.Monetary(
        string='TSBĐ đã phân bổ',
        compute='_compute_borrowing_base', store=True,
        help='Σ giá trị TSBĐ (đã nhân tỷ lệ cho vay) phân bổ cho mục '
             'đích này, chỉ tính văn bản thế chấp đang hiệu lực.')
    has_own_pledges = fields.Boolean(
        compute='_compute_borrowing_base', store=True)
    amount_available_effective = fields.Monetary(
        string='Khả dụng thực tế',
        compute='_compute_available_effective',
        help='= Σ TSBĐ (kể cả IPC) đã PHÂN BỔ cho mục đích này − số tiền '
             'đã sử dụng. Floor 0.\n'
             'Mục đích LIÊN THÔNG thì tính trên cả bể: Σ TSBĐ phân bổ của '
             'nhóm liên thông − Σ đã sử dụng của nhóm.\n'
             'TSBĐ đã thế chấp nhưng CHƯA phân bổ thì không làm tăng khả '
             'dụng của mục đích nào.')
    margin_call = fields.Boolean(
        string='Cảnh báo thiếu bảo đảm',
        compute='_compute_available_effective',
        help='Dư nợ facility đã vượt base riêng — NH sẽ yêu cầu bổ '
             'sung TSBĐ hoặc trả bớt nợ (margin call).')

    @api.depends('pledge_allocation_ids.amount',
                 'pledge_allocation_ids.pledge_state')
    def _compute_borrowing_base(self):
        """Base của mục đích = Σ dòng PHÂN BỔ, không phải Σ pledge.

        Trước đây chỉ đếm pledge gắn thẳng `pledge_target='facility'`.
        Cách đó bỏ sót toàn bộ TSBĐ khai ở cấp HĐTD — mà trong thực tế
        phần lớn TSBĐ khai ở cấp đó, rồi mới chia xuống các mục đích.
        """
        for rec in self:
            live = rec.pledge_allocation_ids.filtered(
                lambda a: a.pledge_state == 'active')
            rec.borrowing_base_own = sum(live.mapped('amount'))
            rec.has_own_pledges = bool(live)

    @api.depends('borrowing_base_own', 'amount_used', 'has_own_pledges',
                 'flexible_limits',
                 'credit_contract_id.facility_ids.borrowing_base_own',
                 'credit_contract_id.facility_ids.amount_used',
                 'credit_contract_id.facility_ids.flexible_limits')
    def _compute_available_effective(self):
        """Khả dụng thực tế = TSBĐ phân bổ riêng cho facility − đã dùng.

        BẢN CŨ LẤY min BA VẾ và sai ở vế thứ ba: nó đưa
        `base toàn HĐTD − dư nợ toàn HĐTD` vào, tức là **cùng một bể TSBĐ
        được hiển thị lại trên MỌI facility**. HĐTD chỉ có một pledge cấp
        HĐTD 10 tỷ mà bốn facility đều hiện "khả dụng 10 tỷ" — người đọc
        cộng ngang thành 40 tỷ, trong khi rút được đúng 10 tỷ. Con số
        càng nhiều facility càng sai to.

        Bản mới đọc theo đúng nghĩa "phân bổ": chỉ tính TSBĐ gắn RIÊNG
        facility này (`pledge_target = 'facility'`), IPC nằm trong đó vì
        IPC vào hệ thống dưới dạng một tài sản bảo đảm rồi được thế chấp
        như mọi tài sản khác. Cộng ngang các facility giờ không vượt quá
        tổng base thật.

        HỆ QUẢ CẦN BIẾT: facility chưa được phân bổ TSBĐ nào sẽ hiện 0 —
        kể cả khi HĐTD có TSBĐ ở cấp hợp đồng. Đó là chủ ý: chưa chia
        xuống thì chưa có gì để nói facility đó rút được bao nhiêu.

        KHÔNG cắt trần theo hạn mức facility. Nếu TSBĐ phân bổ lớn hơn
        hạn mức đã cấp thì cột này lớn hơn hạn mức — cố ý, vì hai thứ trả
        lời hai câu hỏi khác nhau: "được cấp bao nhiêu" (cột Hạn mức) và
        "đang có bao nhiêu bảo đảm đỡ lưng" (cột này).
        """
        for rec in self:
            # Liên thông: gộp theo BỂ, đúng như cách hạn mức đang làm.
            # Không gộp thì mỗi mục đích trong bể nhìn riêng phần TSBĐ
            # của mình và báo thiếu, trong khi bể vẫn còn dư địa.
            pool = rec
            if rec.flexible_limits and rec.credit_contract_id:
                pool = rec.credit_contract_id.facility_ids.filtered(
                    'flexible_limits') or rec
            base = sum(pool.mapped('borrowing_base_own'))
            used = sum(pool.mapped('amount_used'))
            rec.amount_available_effective = max(0.0, base - used)
            rec.margin_call = bool(base) and used > base + 0.01
