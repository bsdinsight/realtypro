# -*- coding: utf-8 -*-
"""Bridge: BL chiếm hạn mức của facility có purpose='bank_guarantee'.

2 entity cùng chiếm hạn mức facility purpose='bank_guarantee':
  - re.bank.guarantee (chứng thư BL chính thức) state issued/extended
  - re.guarantee.request (đề nghị BL) state active

Phân loại theo PURPOSE (mục đích) — không theo facility_type — vì NH
có thể cấp BL trên facility revolving/term với purpose=bank_guarantee.

Khi tất toán đề nghị BL (state=settled) → khôi phục hạn mức.
"""
from odoo import api, fields, models


class ReLoanFacility(models.Model):
    _inherit = 're.loan.facility'

    guarantee_ids = fields.One2many(
        're.bank.guarantee', 'facility_id',
        string='Chứng thư BL')
    guarantee_count = fields.Integer(compute='_compute_guarantee_stats')
    guarantee_total_outstanding = fields.Monetary(
        string='Tổng BL đang chiếm hạn mức',
        compute='_compute_guarantee_stats', store=True,
        help='Σ giá trị chứng thư BL ở trạng thái Đã phát hành, Đã gia '
             'hạn hoặc BỊ THU. Chứng thư bị thu vẫn chiếm hạn mức cho '
             'tới khi tất toán.')

    guarantee_request_ids = fields.One2many(
        're.guarantee.request', 'facility_id',
        string='Đề nghị BL')
    guarantee_request_count = fields.Integer(
        compute='_compute_guarantee_request_stats')
    guarantee_request_outstanding = fields.Monetary(
        string='Tổng Đề nghị BL đã kích hoạt',
        compute='_compute_guarantee_request_stats', store=True,
        help='Σ giá trị đề nghị BL đã kích hoạt nhưng CHƯA phát hành '
             'chứng thư. Phần này ĐÃ CHIẾM hạn mức (backlog 732): '
             'kích hoạt là giữ chỗ, không chờ tới lúc ngân hàng phát '
             'hành chứng thư. Phát hành xong thì chứng thư chiếm thay, '
             'tổng không đổi.')

    @api.depends('guarantee_ids', 'guarantee_ids.state',
                 'guarantee_ids.amount')
    def _compute_guarantee_stats(self):
        for rec in self:
            rec.guarantee_count = len(rec.guarantee_ids)
            # 'forfeited' PHẢI nằm trong danh sách này. Bị thu nghĩa
            # là ngân hàng đã trả thay cho bên thụ hưởng — nghĩa vụ
            # không biến mất mà đổi thành khoản doanh nghiệp nợ lại
            # ngân hàng. Thả hạn mức ra lúc đó là cho rút thêm đúng vào
            # lúc rủi ro tín dụng vừa hiện thực hoá. Chỉ khi TẤT TOÁN
            # xong mới khôi phục.
            active = rec.guarantee_ids.filtered(
                lambda g: g.state in ('issued', 'extended', 'forfeited'))
            rec.guarantee_total_outstanding = sum(active.mapped('amount'))

    @api.depends('guarantee_request_ids', 'guarantee_request_ids.state',
                 'guarantee_request_ids.amount')
    def _compute_guarantee_request_stats(self):
        for rec in self:
            rec.guarantee_request_count = len(rec.guarantee_request_ids)
            active = rec.guarantee_request_ids.filtered(
                lambda r: r.state == 'active')
            rec.guarantee_request_outstanding = sum(active.mapped('amount'))

    # ------------------------------------------------------------------
    # Override amount_used: với mục đích thuộc nhóm Bảo lãnh, cộng thêm
    #   - guarantee_request_outstanding: đề nghị BL state='active'
    #     (đã kích hoạt, chưa phát hành chứng thư)
    #   - guarantee_total_outstanding: chứng thư BL state ∈
    #     (issued, extended, forfeited) — chứng thư settled không chiếm.
    # ------------------------------------------------------------------
    @api.depends('purpose',
                 'guarantee_ids',
                 'guarantee_ids.state',
                 'guarantee_ids.amount',
                 'guarantee_request_ids',
                 'guarantee_request_ids.state',
                 'guarantee_request_ids.amount')
    def _compute_amount_used(self):
        """Đề nghị ĐÃ KÍCH HOẠT chiếm hạn mức ngay (backlog 732).

        Đã đổi hai lần, lần này là chốt của người dùng cuối: kích hoạt
        là chiếm. Lý do nghiệp vụ: giữa kích hoạt và phát hành có thể
        vài ngày, không giữ chỗ thì trong khoảng đó hạn mức trông còn
        trống và người khác kích hoạt đè lên — đến lúc ngân hàng phát
        hành mới vỡ ra là không đủ.

        KHÔNG đếm hai lần: đề nghị chỉ tính khi state='active'. Phát
        hành xong đề nghị sang 'issued' và chứng thư chiếm thay, nên
        tổng không đổi qua bước phát hành.

        Hệ quả phải xử ở nơi khác: từ lúc kích hoạt, phần hạn mức đó
        đã nằm trong `amount_used`, nên mọi phép kiểm "còn đủ chỗ
        không" cho CHÍNH đề nghị/chứng thư đó phải cộng ngược phần nó
        đang chiếm — xem `_own_room_contribution` ở re.guarantee.request.
        Thiếu bước đó thì đề nghị chiếm trọn hạn mức sẽ tự chặn chính
        mình lúc phát hành.
        """
        super()._compute_amount_used()
        for rec in self:
            # Theo PHÂN LOẠI chứ không theo mã: mục đích tự khai
            # thuộc nhóm Bảo lãnh cũng phải bị chiếm hạn mức, không
            # thì chọn được mà không bao giờ trừ — một lỗ thủng im
            # lặng trong hạn mức bảo lãnh.
            if rec.purpose_kind == 'guarantee':
                rec.amount_used += (rec.guarantee_total_outstanding
                                    + rec.guarantee_request_outstanding)

    def action_view_guarantees(self):
        self.ensure_one()
        return {
            'name': 'Chứng thư BL — %s' % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 're.bank.guarantee',
            'view_mode': 'list,form',
            'domain': [('facility_id', '=', self.id)],
            'context': {
                'default_facility_id': self.id,
                'default_issuing_bank_partner_id':
                    self.credit_contract_id.partner_id.id,
            },
        }

    def action_view_guarantee_requests(self):
        self.ensure_one()
        return {
            'name': 'Đề nghị BL — %s' % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 're.guarantee.request',
            'view_mode': 'list,form',
            'domain': [('facility_id', '=', self.id)],
            'context': {
                'default_facility_id': self.id,
            },
        }
