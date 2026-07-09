# -*- coding: utf-8 -*-
"""Phụ lục hợp đồng thuê (re.lease.annex).

Điều chỉnh HĐ thuê đang hiệu lực bằng phụ lục — căn cứ Điều 403 BLDS 2015
(phụ lục có giá trị như HĐ, không trái HĐ chính) và NĐ 37/2015 (điều chỉnh
giá khi khối lượng phát sinh / bất khả kháng).

Pattern: ghi thay đổi theo LOẠI, mọi tác động số liệu là DELTA và CHỈ chạy
khi bấm "Áp dụng" (không auto khi lưu) — giống phụ lục bảo lãnh. Kỳ đã lên
hóa đơn được GIỮ NGUYÊN; chỉ các kỳ chưa lên hóa đơn được tạo lại.
"""
from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ReLeaseAnnex(models.Model):
    _name = 're.lease.annex'
    _description = 'Phụ lục hợp đồng thuê'
    _order = 'date_effective, id'

    contract_id = fields.Many2one(
        're.lease.contract', string='HĐ thuê', required=True,
        ondelete='cascade', index=True)
    name = fields.Char(string='Số phụ lục')
    annex_type = fields.Selection(
        [('price_adjust', 'Điều chỉnh đơn giá thuê'),
         ('extend', 'Gia hạn thời gian'),
         ('shorten', 'Rút ngắn thời gian'),
         ('add_asset', 'Bổ sung tài sản'),
         ('remove_asset', 'Giảm / rút tài sản'),
         ('replace_asset', 'Thay thế tài sản'),
         ('payment_terms', 'Điều chỉnh điều khoản thanh toán'),
         ('maintenance_terms', 'Điều chỉnh trách nhiệm bảo trì'),
         ('relocation', 'Đổi địa điểm / dự án'),
         ('other', 'Khác')],
        string='Loại phụ lục', required=True, default='price_adjust')
    date_sign = fields.Date(string='Ngày ký')
    date_effective = fields.Date(
        string='Ngày hiệu lực', required=True,
        default=fields.Date.context_today)
    description = fields.Text(string='Diễn giải')
    applied = fields.Boolean(
        string='Đã áp dụng', readonly=True, copy=False)
    currency_id = fields.Many2one(related='contract_id.currency_id')
    company_id = fields.Many2one(related='contract_id.company_id')

    # --- Trường theo loại ---
    new_rent_per_period = fields.Monetary(
        string='Đơn giá thuê mới', help='Đơn giá thuê / kỳ mới (áp dụng '
        'cho các kỳ chưa lên hóa đơn).')
    extra_periods = fields.Integer(
        string='Số kỳ gia hạn', help='Số kỳ cộng thêm.')
    remove_periods = fields.Integer(
        string='Số kỳ rút ngắn', help='Số kỳ cắt bớt (không dưới số kỳ '
        'đã lên hóa đơn).')
    new_asset_name = fields.Char(string='Tên tài sản (mới)')
    new_asset_serial = fields.Char(string='Số serial / khung (mới)')
    new_asset_qty = fields.Float(string='Số lượng (mới)', default=1.0)
    new_asset_value = fields.Monetary(string='Giá trị (mới)')
    new_asset_rent = fields.Monetary(
        string='Đơn giá thuê (mới)',
        help='Đơn giá thuê / kỳ cho tài sản bổ sung.')
    new_asset_date_start = fields.Date(
        string='Bắt đầu thuê (mới)',
        help='Ngày tài sản bổ sung bắt đầu tính tiền thuê (có thể muộn '
             'hơn ngày ký phụ lục).')
    new_asset_date_end = fields.Date(string='Kết thúc thuê (mới)')
    target_asset_line_id = fields.Many2one(
        're.lease.asset', string='Tài sản mục tiêu',
        domain="[('contract_id', '=', contract_id)]",
        help='Dòng tài sản để rút / thay thế.')
    new_period_months = fields.Selection(
        [('1', 'Hằng tháng'), ('3', 'Hằng quý'),
         ('6', '6 tháng'), ('12', 'Hằng năm')],
        string='Chu kỳ mới')
    new_deposit = fields.Monetary(string='Ký cược mới')
    new_project_id = fields.Many2one('re.project', string='Dự án mới')
    new_location = fields.Char(string='Địa điểm mới')

    # snapshot đối chiếu
    value_before = fields.Char(string='Trước', readonly=True)
    value_after = fields.Char(string='Sau', readonly=True)

    @api.onchange('annex_type')
    def _onchange_annex_type(self):
        """Xóa field không liên quan khi đổi loại."""
        t = self.annex_type
        if t != 'price_adjust':
            self.new_rent_per_period = 0.0
        if t != 'extend':
            self.extra_periods = 0
        if t != 'shorten':
            self.remove_periods = 0
        if t not in ('add_asset', 'replace_asset'):
            self.new_asset_name = False
            self.new_asset_serial = False
            self.new_asset_value = 0.0
        if t != 'add_asset':
            self.new_asset_rent = 0.0
            self.new_asset_date_start = False
            self.new_asset_date_end = False
        if t not in ('remove_asset', 'replace_asset', 'maintenance_terms'):
            self.target_asset_line_id = False
        if t != 'payment_terms':
            self.new_period_months = False
            self.new_deposit = 0.0
        if t != 'relocation':
            self.new_project_id = False
            self.new_location = False

    @staticmethod
    def _fmt(amount):
        return '{:,.0f}'.format(amount or 0.0)

    def action_apply(self):
        for rec in self:
            if rec.applied:
                raise UserError(_("Phụ lục này đã áp dụng."))
            c = rec.contract_id
            if c.state in ('ended', 'terminated'):
                raise UserError(_(
                    "HĐ đã kết thúc / chấm dứt — không áp dụng phụ lục."))
            before = after = ''
            handler = getattr(rec, '_apply_%s' % rec.annex_type, None)
            if handler:
                before, after, desc = handler(c)
            else:
                desc = rec.description or _("Điều chỉnh khác")

            rec.applied = True
            rec.value_before = before
            rec.value_after = after
            c.message_post(body=Markup(_(
                "<b>Phụ lục %(n)s</b> (%(t)s): %(d)s")) % {
                'n': rec.name or '',
                't': dict(rec._fields['annex_type'].selection).get(
                    rec.annex_type),
                'd': desc})
        return True

    # --- Handlers theo loại (trả về before, after, desc) ---
    def _apply_price_adjust(self, c):
        if c.lease_type != 'operating':
            raise UserError(_(
                "Điều chỉnh đơn giá hiện hỗ trợ thuê hoạt động."))
        if not self.new_rent_per_period or self.new_rent_per_period <= 0:
            raise UserError(_("Nhập 'Đơn giá thuê mới' (> 0)."))
        old = c.rent_per_period
        c.rent_per_period = self.new_rent_per_period
        c._reschedule_future_operating_lines()
        b, a = self._fmt(old), self._fmt(self.new_rent_per_period)
        return b, a, _("Đơn giá: %(o)s → %(n)s", o=b, n=a)

    def _apply_extend(self, c):
        if self.extra_periods <= 0:
            raise UserError(_("Nhập 'Số kỳ gia hạn' (> 0)."))
        old = c.n_periods
        c.n_periods = old + self.extra_periods
        c._reschedule_future_operating_lines()
        return (str(old), str(c.n_periods),
                _("Số kỳ: %(o)s → %(n)s (gia hạn +%(e)s)",
                  o=old, n=c.n_periods, e=self.extra_periods))

    def _apply_shorten(self, c):
        if self.remove_periods <= 0:
            raise UserError(_("Nhập 'Số kỳ rút ngắn' (> 0)."))
        n_billed = len(c.payment_line_ids.filtered(
            lambda l: l.state != 'draft'))
        new_n = c.n_periods - self.remove_periods
        if new_n < max(1, n_billed):
            raise UserError(_(
                "Không thể rút xuống %(x)s kỳ — đã có %(b)s kỳ lên hóa "
                "đơn.", x=new_n, b=n_billed))
        old = c.n_periods
        c.n_periods = new_n
        c._reschedule_future_operating_lines()
        return (str(old), str(new_n),
                _("Số kỳ: %(o)s → %(n)s (rút %(r)s)",
                  o=old, n=new_n, r=self.remove_periods))

    def _apply_add_asset(self, c):
        if not self.new_asset_name:
            raise UserError(_("Nhập 'Tên tài sản (mới)'."))
        c.asset_ids = [(0, 0, {
            'name': self.new_asset_name,
            'serial': self.new_asset_serial or False,
            'quantity': self.new_asset_qty or 1.0,
            'value': self.new_asset_value or 0.0,
            'rent_unit_price': self.new_asset_rent or 0.0,
            'date_start': self.new_asset_date_start or False,
            'date_end': self.new_asset_date_end or False,
        })]
        # Tài sản mới có đơn giá + cửa sổ thuê riêng → tạo lại lịch kỳ
        # chưa lên hóa đơn (kỳ trong cửa sổ tài sản mới sẽ cộng tiền).
        c._reschedule_future_operating_lines()
        note = self.new_asset_name
        if self.new_asset_date_start:
            note += _(" (từ %s)", self.new_asset_date_start)
        return '', note, _("Bổ sung tài sản: %s", note)

    def _apply_remove_asset(self, c):
        if not self.target_asset_line_id:
            raise UserError(_("Chọn 'Tài sản mục tiêu' để rút."))
        nm = self.target_asset_line_id.name
        self.target_asset_line_id.unlink()
        c._reschedule_future_operating_lines()
        return nm, '', _("Rút tài sản: %s", nm)

    def _apply_replace_asset(self, c):
        if not self.target_asset_line_id or not self.new_asset_name:
            raise UserError(_(
                "Chọn 'Tài sản mục tiêu' và nhập 'Tên tài sản (mới)'."))
        old_nm = self.target_asset_line_id.name
        self.target_asset_line_id.write({
            'name': self.new_asset_name,
            'serial': self.new_asset_serial
            or self.target_asset_line_id.serial,
            'value': self.new_asset_value
            or self.target_asset_line_id.value,
        })
        c._reschedule_future_operating_lines()
        return old_nm, self.new_asset_name, _(
            "Thay thế tài sản: %(o)s → %(n)s",
            o=old_nm, n=self.new_asset_name)

    def _apply_payment_terms(self, c):
        parts = []
        if self.new_period_months and self.new_period_months != c.period_months:
            om = dict(c._fields['period_months'].selection)
            parts.append(_("chu kỳ %(o)s → %(n)s",
                           o=om.get(c.period_months),
                           n=om.get(self.new_period_months)))
            c.period_months = self.new_period_months
            c._reschedule_future_operating_lines()
        if self.new_deposit and c.currency_id.compare_amounts(
                self.new_deposit, c.deposit) != 0:
            parts.append(_("ký cược %(o)s → %(n)s",
                           o=self._fmt(c.deposit),
                           n=self._fmt(self.new_deposit)))
            c.deposit = self.new_deposit
        if not parts:
            raise UserError(_("Nhập chu kỳ mới hoặc ký cược mới."))
        return '', '', _("Điều khoản thanh toán: %s", '; '.join(parts))

    def _apply_maintenance_terms(self, c):
        # Trách nhiệm bảo trì chi tiết (theo dòng) do lớp Enterprise
        # (re_asset) quản lý — ở Community chỉ ghi nhận thỏa thuận.
        return '', '', (self.description
                        or _("Điều chỉnh trách nhiệm / chi phí bảo trì"))

    def _apply_relocation(self, c):
        parts = []
        if self.new_project_id and self.new_project_id != c.project_id:
            parts.append(_("dự án %(o)s → %(n)s",
                           o=c.project_id.display_name or '—',
                           n=self.new_project_id.display_name))
            c.project_id = self.new_project_id
        if self.new_location:
            parts.append(_("địa điểm: %s", self.new_location))
        if not parts:
            raise UserError(_("Chọn dự án mới hoặc nhập địa điểm mới."))
        return '', '', _("Đổi địa điểm: %s", '; '.join(parts))

    def _apply_other(self, c):
        return '', '', (self.description or _("Điều chỉnh khác"))
