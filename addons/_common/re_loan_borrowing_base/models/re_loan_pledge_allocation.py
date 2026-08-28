# -*- coding: utf-8 -*-
"""Phân bổ TSBĐ xuống từng mục đích (facility) của HĐTD.

VÌ SAO PHẢI CÓ BẢNG NÀY
=======================

Trước đây khả dụng thực tế của một mục đích lấy theo `min` ba vế, trong
đó có vế "base toàn HĐTD − dư nợ toàn HĐTD". Hệ quả: **cùng một bể TSBĐ
được in lại trên mọi mục đích**. HĐTD chỉ có một pledge cấp hợp đồng 10
tỷ mà bốn mục đích đều hiện "khả dụng 10 tỷ" — người đọc cộng ngang
thành 40 tỷ, trong khi rút được đúng 10 tỷ.

Cách chữa không nằm ở công thức mà ở DỮ LIỆU: phải biết TSBĐ nào đỡ lưng
cho mục đích nào, bao nhiêu. Đó là bảng này. Nghiệp vụ gọi là phân bổ
tài sản bảo đảm; ngân hàng cũng làm đúng như vậy khi cấp hạn mức thành
phần.

BA TẦNG SỐ, ĐỪNG LẪN
====================

    ① Giá trị tài sản          `collateral.value_current`
       còn lại chưa thế chấp   `collateral.value_available`
    ② Đem đi thế chấp          `pledge.secured_amount`   ≤ ①
    ③ Đóng góp vào hạn mức     `pledge.base_contribution` = ② × tỷ lệ cho vay
       phân bổ xuống mục đích  Σ `allocation.amount`      ≤ ③

Số ghi ở đây là số ở tầng ③ — ĐÃ nhân tỷ lệ cho vay. Tài sản 100 tỷ, tỷ
lệ 70% thì phân bổ 70 tỷ, không phải 100 tỷ. Ghi nhầm tầng là sai đúng
bằng phần chênh của tỷ lệ cho vay, và sai theo hướng báo thừa dư địa.

MỘT TÀI SẢN THẾ CHẤP ĐƯỢC Ở NHIỀU HĐTD, miễn tổng đem đi thế chấp không
vượt giá trị của nó — chặn ở tầng ②, dựa vào `value_available` vốn đã
cộng trên MỌI pledge của tài sản, không riêng HĐTD nào.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ReLoanPledgeAllocation(models.Model):
    _name = 're.loan.pledge.allocation'
    _description = 'Phân bổ TSBĐ cho mục đích'
    _order = 'credit_contract_id, collateral_id, facility_id, id'

    pledge_id = fields.Many2one(
        're.loan.collateral.pledge', string='Văn bản thế chấp',
        required=True, ondelete='cascade', index=True)
    facility_id = fields.Many2one(
        're.loan.facility', string='Mục đích', required=True,
        ondelete='restrict', index=True,
        domain="[('credit_contract_id', '=', credit_contract_id)]")

    credit_contract_id = fields.Many2one(
        related='pledge_id.credit_contract_id', string='HĐTD',
        store=True, index=True)
    collateral_id = fields.Many2one(
        related='pledge_id.collateral_id', string='Tài sản',
        store=True, index=True)
    date_pledge = fields.Date(
        related='pledge_id.date_pledge', string='Ngày thế chấp', store=True)
    secured_amount = fields.Monetary(
        related='pledge_id.secured_amount', string='Giá trị đảm bảo')
    advance_rate = fields.Float(
        related='pledge_id.advance_rate', string='Tỷ lệ cho vay (%)')
    base_contribution = fields.Monetary(
        related='pledge_id.base_contribution', string='Đóng góp base')
    # Store để lọc và để compute của facility bám vào được; pledge đổi
    # trạng thái là dòng phân bổ ngừng tính ngay.
    pledge_state = fields.Selection(
        related='pledge_id.state', string='Trạng thái', store=True, index=True)
    currency_id = fields.Many2one(related='pledge_id.currency_id')

    amount = fields.Monetary(
        string='Giá trị phân bổ', currency_field='currency_id',
        help='Phần ĐÓNG GÓP BASE (đã nhân tỷ lệ cho vay) mà văn bản thế '
             'chấp này dành cho mục đích trên. Tài sản 100 tỷ, tỷ lệ cho '
             'vay 70% thì tổng phân bổ tối đa là 70 tỷ.')
    note = fields.Char(string='Ghi chú')

    @api.model_create_multi
    def create(self, vals_list):
        """Trùng cặp (văn bản thế chấp, mục đích) thì GHI ĐÈ dòng cũ.

        Vì sao không để nó báo lỗi: khi văn bản thế chấp khai "Cấp bảo
        đảm = Facility", hệ thống TỰ tạo sẵn một dòng phân bổ lúc lưu —
        người dùng không nhìn thấy dòng đó, vì màn hình chưa nạp lại.
        Họ sang tab Phân bổ TSĐB gõ đúng cặp ấy (việc họ định làm ngay
        từ đầu) và ăn ngay lỗi trùng khoá, ngay lần tạo đầu tiên.

        Một cặp chỉ có một dòng, nên con số người dùng vừa gõ là con số
        họ muốn: ghi đè lên dòng có sẵn và trả về chính dòng đó. Người
        dùng thấy đúng thứ mình nhập, không thấy lỗi kỹ thuật.
        """
        remaining, reused = [], self.browse()
        for vals in vals_list:
            pid, fid = vals.get('pledge_id'), vals.get('facility_id')
            old = self.search([('pledge_id', '=', pid),
                               ('facility_id', '=', fid)], limit=1) \
                if pid and fid else self.browse()
            if old:
                old.write({k: v for k, v in vals.items()
                           if k not in ('pledge_id', 'facility_id')})
                reused |= old
            else:
                remaining.append(vals)
        return reused | super().create(remaining)

    @api.onchange('pledge_id')
    def _onchange_pledge_proposes_amount(self):
        """Chọn văn bản thế chấp thì đề xuất luôn phần CHƯA phân bổ.

        Người dùng vào tab này để chia nốt phần còn dư; bắt họ tự mở văn
        bản thế chấp ra xem còn bao nhiêu rồi gõ lại là thừa một bước và
        dễ gõ sai. Vẫn sửa đè được.
        """
        for rec in self:
            if rec.pledge_id and not rec.amount:
                rec.amount = rec.pledge_id.amount_unallocated

    _uniq = models.Constraint(
        'unique(pledge_id, facility_id)',
        'Văn bản thế chấp này đã có dòng phân bổ cho mục đích đó — sửa '
        'dòng cũ thay vì thêm dòng mới.')

    @api.depends('collateral_id', 'facility_id')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s → %s' % (
                rec.collateral_id.display_name or '?',
                rec.facility_id.display_name or '?')

    @api.constrains('facility_id', 'pledge_id')
    def _check_same_contract(self):
        for rec in self:
            fac_cc = rec.facility_id.credit_contract_id
            if fac_cc and rec.credit_contract_id and fac_cc != rec.credit_contract_id:
                raise ValidationError(_(
                    'Mục đích "%(f)s" thuộc HĐTD khác với văn bản thế chấp '
                    '"%(p)s". TSBĐ chỉ phân bổ được cho mục đích trong '
                    'cùng một HĐTD.',
                    f=rec.facility_id.display_name,
                    p=rec.pledge_id.display_name))

    @api.constrains('amount', 'pledge_id')
    def _check_within_base(self):
        """Σ phân bổ ≤ đóng góp base của chính văn bản thế chấp đó.

        CHẶN CỨNG, và cố ý chỉ chặn Ở ĐÂY — tức là khi người dùng nhập
        hoặc sửa dòng phân bổ. Định giá lại làm giá trị tài sản TỤT thì
        KHÔNG chặn: định giá là sự kiện bên ngoài, chặn thì không lưu
        nổi chứng thư định giá mới. Trường hợp đó bật cờ cảnh báo
        `over_allocated` trên văn bản thế chấp để người dùng đi sửa.
        """
        for rec in self:
            pledge = rec.pledge_id
            total = sum(pledge.allocation_ids.mapped('amount'))
            base = pledge.base_contribution or 0.0
            if total > base + 0.01:
                raise ValidationError(_(
                    'Phân bổ vượt giá trị bảo đảm.\n\n'
                    'Tài sản: %(c)s\n'
                    'Đem đi thế chấp: %(s)s × tỷ lệ cho vay %(r)s%% '
                    '= %(b)s\n'
                    'Đang phân bổ: %(t)s\n'
                    'Vượt: %(o)s',
                    c=pledge.collateral_id.display_name,
                    s='{:,.0f}'.format(pledge.secured_amount or 0.0),
                    r='{:,.4g}'.format(pledge.advance_rate or 0.0),
                    b='{:,.0f}'.format(base),
                    t='{:,.0f}'.format(total),
                    o='{:,.0f}'.format(total - base)))

    @api.constrains('amount')
    def _check_positive(self):
        for rec in self:
            if rec.amount < 0:
                raise ValidationError(_(
                    'Giá trị phân bổ không được âm.'))
