# -*- coding: utf-8 -*-
"""Đơn giá tổng hợp — §5.2 của vn_cost_data_pattern.md.

Đây là chỗ **Core × Dự án = Đơn giá**: định mức (hao phí, quốc gia) nhân với
công bố giá (giá tài nguyên, theo dự án) → ra đơn giá.

Giá trị lõi: 3 con số **material_amount / labor_amount / machine_amount** —
đúng thứ `rp_ai` cần để đối chiếu giá thầu Ở MỨC HAO PHÍ, không phải mức
dòng. Biết "nhà thầu chào cao 18%" là báo động; biết "ca máy +47% vì tính
3,1 ca/md thay vì 2,1" là bằng chứng đàm phán.

Thang markup nằm BÊN TRONG đơn giá (đặc thù VN): đơn giá dự thầu đã gói CP
chung + TNCTT + VAT + dự phòng. Muốn so công bằng với dự toán phải bóc ngược
thang — model này giữ đủ các bậc để bóc.

Trung thực: khi một tài nguyên trong định mức KHÔNG có giá trong công bố, hoặc
giá VAT không rõ, phải HIỆN RA (missing_price / price_uncertain), không lặng
lẽ tính bừa.
"""
from odoo import _, api, fields, models


class RpMarkupScheme(models.Model):
    _name = 'rp.markup.scheme'
    _description = 'Thang markup (chi phí chung, TNCTT, VAT, dự phòng)'
    _order = 'name'

    name = fields.Char(string='Tên', required=True)
    project_type = fields.Char(string='Loại công trình')
    overhead_pct = fields.Float(string='Chi phí chung %', default=6.5)
    profit_pct = fields.Float(string='Thu nhập chịu thuế tính trước %',
                              default=5.5)
    vat_pct = fields.Float(string='Thuế GTGT %', default=8.0)
    contingency_pct = fields.Float(string='Chi phí dự phòng %', default=0.0)
    note = fields.Text(string='Ghi chú')
    active = fields.Boolean(default=True)


class RpUnitPrice(models.Model):
    _name = 'rp.unit.price'
    _description = 'Đơn giá tổng hợp (định mức × giá)'
    _order = 'norm_id'
    _rec_name = 'display_name'

    norm_id = fields.Many2one(
        'rp.norm', string='Định mức', required=True, ondelete='cascade',
        index=True, domain="[('is_leaf','=',True)]")
    publication_id = fields.Many2one(
        'rp.price.publication', string='Công bố giá', required=True,
        ondelete='cascade', index=True,
        help='Bộ giá dùng để tính — theo dự án.')
    markup_scheme_id = fields.Many2one(
        'rp.markup.scheme', string='Thang markup')
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda s: s.env.ref('base.VND', raise_if_not_found=False))

    # ── 3 con số rp_ai cần ──
    material_amount = fields.Float(
        string='Vật liệu', compute='_compute_amounts', digits=(16, 2))
    labor_amount = fields.Float(
        string='Nhân công', compute='_compute_amounts', digits=(16, 2))
    machine_amount = fields.Float(
        string='Máy', compute='_compute_amounts', digits=(16, 2))
    subcontract_amount = fields.Float(
        string='Thầu phụ', compute='_compute_amounts', digits=(16, 2))

    # ── thang markup (bóc ngược được) ──
    direct_cost = fields.Float(
        string='Chi phí trực tiếp', compute='_compute_amounts',
        digits=(16, 2))
    overhead = fields.Float(string='Chi phí chung',
                            compute='_compute_amounts', digits=(16, 2))
    profit = fields.Float(string='TNCTT', compute='_compute_amounts',
                          digits=(16, 2))
    pre_tax = fields.Float(string='CP xây dựng trước thuế',
                           compute='_compute_amounts', digits=(16, 2))
    vat_amount = fields.Float(string='Thuế GTGT',
                              compute='_compute_amounts', digits=(16, 2))
    contingency = fields.Float(string='Dự phòng',
                               compute='_compute_amounts', digits=(16, 2))
    bid_price = fields.Float(string='Đơn giá dự thầu',
                             compute='_compute_amounts', digits=(16, 2))

    # ── trung thực: chỗ nào không tính được ──
    missing_price_count = fields.Integer(
        string='Thiếu giá', compute='_compute_amounts',
        help='Số tài nguyên trong định mức KHÔNG có giá trong công bố này. '
             'Nếu > 0 thì đơn giá CHƯA ĐỦ.')
    price_uncertain = fields.Boolean(
        string='Giá không chắc', compute='_compute_amounts',
        help='True nếu có tài nguyên dùng giá VAT không rõ.')

    display_name = fields.Char(compute='_compute_display_name')

    _uniq = models.Constraint(
        'unique(norm_id, publication_id, markup_scheme_id)',
        'Đơn giá cho (định mức, công bố, thang markup) này đã có.')

    def _best_price(self, resource):
        """Giá của một tài nguyên trong công bố này. Nhiều nguồn (cát 2 bãi)
        → lấy giá THẤP NHẤT (chuẩn về trước-VAT). Trả (giá, có_chắc_VAT)."""
        lines = self.publication_id.line_ids.filtered(
            lambda l: l.resource_id == resource)
        if not lines:
            return (None, True)
        best = None
        certain = True
        for l in lines:
            val = l.price_ex_vat if l.vat_certain else l.price
            if best is None or val < best:
                best = val
                certain = l.vat_certain
        return (best, certain)

    @api.depends('norm_id', 'norm_id.line_ids', 'publication_id',
                 'publication_id.line_ids', 'markup_scheme_id')
    def _compute_amounts(self):
        for up in self:
            mat = aux = lab = mac = sub = 0.0
            missing = 0
            uncertain = False
            for nl in up.norm_id.line_ids:
                price, certain = up._best_price(nl.resource_id)
                if price is None:
                    missing += 1
                    continue
                if not certain:
                    uncertain = True
                amt = (nl.quantity or 0.0) * price
                rt = nl.resource_id.resource_type
                if rt == 'material':
                    mat += amt
                elif rt == 'material_aux':
                    aux += amt
                elif rt == 'labor':
                    lab += amt
                elif rt == 'machine':
                    mac += amt
                elif rt == 'subcontract':
                    sub += amt
            up.material_amount = mat + aux
            up.labor_amount = lab
            up.machine_amount = mac
            up.subcontract_amount = sub
            up.missing_price_count = missing
            up.price_uncertain = uncertain

            direct = mat + aux + lab + mac + sub
            s = up.markup_scheme_id
            oh = direct * (s.overhead_pct or 0.0) / 100.0 if s else 0.0
            pre_profit = direct + oh
            pf = pre_profit * (s.profit_pct or 0.0) / 100.0 if s else 0.0
            pretax = pre_profit + pf
            vat = pretax * (s.vat_pct or 0.0) / 100.0 if s else 0.0
            after = pretax + vat
            cont = after * (s.contingency_pct or 0.0) / 100.0 if s else 0.0
            up.direct_cost = direct
            up.overhead = oh
            up.profit = pf
            up.pre_tax = pretax
            up.vat_amount = vat
            up.contingency = cont
            up.bid_price = after + cont

    @api.depends('norm_id.code', 'publication_id.doc_no')
    def _compute_display_name(self):
        for up in self:
            up.display_name = '%s @ %s' % (
                up.norm_id.code or '', up.publication_id.doc_no or '')
