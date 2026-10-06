# -*- coding: utf-8 -*-
"""Sản lượng theo kỳ và hoá đơn tiền điện.

Chuỗi số của một kỳ, mỗi bước mất đi một ít điện và phải nhìn thấy
từng bước — gộp lại thì không bao giờ biết mất ở đâu:

    phát gộp
      − tự dùng (nhà máy ăn điện của chính nó)
      − tổn thất tới điểm giao (đường dây 220kV sang biên giới)
      = GIAO NHẬN RÒNG            ← cái được trả tiền
    + bị cắt giảm (deemed)        ← lưới bắt giảm, vẫn được trả

Khả dụng để riêng vì nó không sinh tiền từ bên mua mà sinh tiền từ NHÀ
THẦU: hãng tua-bin cam kết mức khả dụng, thiếu thì đền. Cộng khoản đó
vào doanh thu bán điện là che mất việc nhà thầu đang nợ mình.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class RpEnergyPeriod(models.Model):
    _name = 'rp.energy.period'
    _description = 'Sản lượng điện theo kỳ'
    _inherit = ['mail.thread']
    _order = 'date_from desc, id desc'

    name = fields.Char(
        string='Kỳ', required=True, copy=False, tracking=True,
        default=lambda self: _('Mới'))
    project_id = fields.Many2one(
        're.project', string='Dự án', required=True, index=True,
        ondelete='cascade', tracking=True)
    date_from = fields.Date(string='Từ ngày', required=True, tracking=True)
    date_to = fields.Date(string='Đến ngày', required=True, tracking=True)
    is_pre_cod = fields.Boolean(
        string='Kỳ chạy thử (trước COD)', compute='_compute_is_pre_cod',
        store=True,
        help='Điện phát ra trước ngày COD được mua với giá chiết khấu '
             'theo điều khoản của từng hợp đồng.')

    gross_mwh = fields.Float(
        string='Phát gộp (MWh)', digits=(16, 3), tracking=True)
    auxiliary_mwh = fields.Float(
        string='Tự dùng (MWh)', digits=(16, 3),
        help='Điện nhà máy tiêu thụ cho chính nó.')
    loss_mwh = fields.Float(
        string='Tổn thất tới điểm giao (MWh)', digits=(16, 3))
    net_mwh = fields.Float(
        string='Giao nhận ròng (MWh)', digits=(16, 3),
        compute='_compute_net', store=True,
        help='Đây là sản lượng được trả tiền.')
    curtailed_mwh = fields.Float(
        string='Bị cắt giảm (MWh)', digits=(16, 3), tracking=True,
        help='Sản lượng lẽ ra phát được nhưng lưới bắt giảm. Theo điều '
             'khoản deemed energy thì vẫn được trả.')
    availability_percent = fields.Float(
        string='Khả dụng (%)', digits=(6, 2), default=100.0)

    state = fields.Selection(
        [('draft', 'Nháp'),
         ('confirmed', 'Đã chốt công-tơ'),
         ('invoiced', 'Đã xuất hoá đơn')],
        string='Trạng thái', default='draft', required=True, tracking=True,
        copy=False)
    line_ids = fields.One2many(
        'rp.energy.period.line', 'period_id', string='Phân bổ theo hợp đồng')
    revenue_total = fields.Monetary(
        string='Doanh thu kỳ', compute='_compute_tong', store=True,
        currency_field='currency_id')
    deemed_total = fields.Monetary(
        string='Trong đó: bị cắt giảm', compute='_compute_tong', store=True,
        currency_field='currency_id')
    shortfall_mwh = fields.Float(
        string='Hụt do khả dụng (MWh)', digits=(16, 3),
        compute='_compute_tong', store=True,
        help='Phần sản lượng mất vì khả dụng dưới mức hãng cam kết. Đây '
             'là khoản đòi NHÀ THẦU, không phải doanh thu bán điện.')
    currency_id = fields.Many2one(
        'res.currency', string='Đồng tiền',
        default=lambda self: self.env.ref('base.USD',
                                          raise_if_not_found=False)
        or self.env.company.currency_id)
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company, index=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('Mới')) == _('Mới'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'rp.energy.period') or _('Kỳ mới')
        return super().create(vals_list)

    @api.depends('date_to', 'project_id.date_cod')
    def _compute_is_pre_cod(self):
        for rec in self:
            cod = rec.project_id.date_cod
            rec.is_pre_cod = bool(cod and rec.date_to and rec.date_to < cod)

    @api.depends('gross_mwh', 'auxiliary_mwh', 'loss_mwh')
    def _compute_net(self):
        for rec in self:
            rec.net_mwh = ((rec.gross_mwh or 0.0)
                           - (rec.auxiliary_mwh or 0.0)
                           - (rec.loss_mwh or 0.0))

    @api.depends('line_ids.amount', 'line_ids.deemed_amount',
                 'availability_percent', 'net_mwh', 'date_from',
                 'project_id.date_cod')
    def _compute_tong(self):
        for rec in self:
            rec.revenue_total = sum(rec.line_ids.mapped('amount'))
            rec.deemed_total = sum(rec.line_ids.mapped('deemed_amount'))
            rec.shortfall_mwh = rec._tinh_hut_kha_dung()

    def _cam_ket_kha_dung(self):
        """Mức cam kết áp cho kỳ này: năm đầu sau COD khác các năm sau."""
        self.ensure_one()
        ppa = self.line_ids.mapped('ppa_id')[:1] or self.env['rp.ppa'].search(
            [('project_id', '=', self.project_id.id)], limit=1)
        if not ppa:
            return 0.0
        cod = self.project_id.date_cod
        if not cod or not self.date_from:
            return ppa.availability_guarantee_y1
        nam = (self.date_from.year - cod.year) + (
            1 if (self.date_from.month, self.date_from.day)
            >= (cod.month, cod.day) else 0)
        return (ppa.availability_guarantee_y1 if nam < 1
                else ppa.availability_guarantee_y2)

    def _tinh_hut_kha_dung(self):
        self.ensure_one()
        cam_ket = self._cam_ket_kha_dung()
        kd = self.availability_percent or 0.0
        if not cam_ket or kd >= cam_ket or not self.net_mwh:
            return 0.0
        # Quy đổi phần trăm thiếu ra sản lượng: sản lượng thực tế ứng với
        # mức khả dụng hiện có, suy ra mức lẽ ra đạt được nếu đủ cam kết.
        return round(self.net_mwh * (cam_ket - kd) / kd, 3)

    def action_chot_cong_to(self):
        """Chốt số công-tơ rồi phân bổ sản lượng cho các hợp đồng."""
        for rec in self:
            if rec.net_mwh <= 0:
                raise UserError(_(
                    'Kỳ "%s" chưa có sản lượng giao nhận.', rec.name))
            Ppa = self.env['rp.ppa']
            hd = Ppa.search([('project_id', '=', rec.project_id.id),
                             ('state', 'in', ('signed', 'active'))])
            if not hd:
                raise UserError(_(
                    'Dự án chưa có hợp đồng mua bán điện nào đã ký.'))
            tong_tl = sum(hd.mapped('allocation_percent'))
            if abs(tong_tl - 100.0) > 0.01:
                raise UserError(_(
                    'Tổng tỷ lệ sản lượng của các hợp đồng là %.2f%%, '
                    'phải bằng 100%%. Thiếu hoặc thừa thì sẽ có phần '
                    'điện không ai mua hoặc bán hai lần.', tong_tl))
            rec.line_ids.unlink()
            moc = rec.date_to or rec.date_from
            for p in hd:
                tl = (p.allocation_percent or 0.0) / 100.0
                gia = (p._gia_chay_thu() if rec.is_pre_cod
                       else p._gia_tai_ngay(moc))
                rec.line_ids.create({
                    'period_id': rec.id, 'ppa_id': p.id,
                    'energy_mwh': round(rec.net_mwh * tl, 3),
                    'curtailed_mwh': round((rec.curtailed_mwh or 0.0) * tl, 3),
                    'tariff': gia,
                })
            rec.state = 'confirmed'
        return True

    def action_ve_nhap(self):
        self.write({'state': 'draft'})
        return True

    def action_xuat_hoa_don(self):
        """Mỗi hợp đồng một hoá đơn — hai bên mua thì hai hoá đơn."""
        self.ensure_one()
        if self.state != 'confirmed':
            raise UserError(_('Phải chốt công-tơ trước khi xuất hoá đơn.'))
        Move = self.env['account.move']
        tao = Move
        for l in self.line_ids:
            if l.invoice_id:
                continue
            hd = Move.create({
                'move_type': 'out_invoice',
                'partner_id': l.ppa_id.partner_id.id,
                'invoice_date': self.date_to,
                'currency_id': l.ppa_id.currency_id.id,
                'ref': _('Tiền điện %(ky)s — %(hd)s',
                         ky=self.name, hd=l.ppa_id.name),
                'invoice_line_ids': l._dong_hoa_don(),
            })
            l.invoice_id = hd.id
            tao |= hd
        self.state = 'invoiced'
        return {
            'type': 'ir.actions.act_window',
            'name': _('Hoá đơn tiền điện — %s', self.name),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', tao.ids)],
        }


class RpEnergyPeriodLine(models.Model):
    _name = 'rp.energy.period.line'
    _description = 'Sản lượng phân bổ cho một hợp đồng'
    _order = 'period_id, ppa_id'

    period_id = fields.Many2one(
        'rp.energy.period', string='Kỳ', required=True, index=True,
        ondelete='cascade')
    ppa_id = fields.Many2one(
        'rp.ppa', string='Hợp đồng', required=True, ondelete='restrict')
    partner_id = fields.Many2one(
        'res.partner', related='ppa_id.partner_id', store=True,
        string='Bên mua', readonly=True)
    project_id = fields.Many2one(
        're.project', related='period_id.project_id', store=True,
        readonly=True)
    energy_mwh = fields.Float(string='Sản lượng (MWh)', digits=(16, 3))
    curtailed_mwh = fields.Float(string='Bị cắt giảm (MWh)', digits=(16, 3))
    tariff = fields.Float(string='Giá áp dụng (USD/kWh)', digits=(16, 5))
    amount_energy = fields.Monetary(
        string='Tiền điện giao nhận', compute='_compute_tien', store=True,
        currency_field='currency_id')
    deemed_amount = fields.Monetary(
        string='Tiền phần bị cắt giảm', compute='_compute_tien', store=True,
        currency_field='currency_id')
    amount = fields.Monetary(
        string='Tổng phải thu', compute='_compute_tien', store=True,
        currency_field='currency_id')
    invoice_id = fields.Many2one(
        'account.move', string='Hoá đơn', readonly=True, copy=False)
    currency_id = fields.Many2one(
        'res.currency', related='ppa_id.currency_id', readonly=True)

    @api.depends('energy_mwh', 'curtailed_mwh', 'tariff',
                 'ppa_id.deemed_energy', 'ppa_id.deemed_percent')
    def _compute_tien(self):
        for l in self:
            # Giá tính theo kWh, sản lượng ghi theo MWh.
            gia_mwh = (l.tariff or 0.0) * 1000.0
            l.amount_energy = (l.energy_mwh or 0.0) * gia_mwh
            if l.ppa_id.deemed_energy:
                l.deemed_amount = ((l.curtailed_mwh or 0.0) * gia_mwh
                                   * (l.ppa_id.deemed_percent or 0.0) / 100.0)
            else:
                l.deemed_amount = 0.0
            l.amount = l.amount_energy + l.deemed_amount

    def _dong_hoa_don(self):
        self.ensure_one()
        dong = [(0, 0, {
            'name': _('Tiền điện %(ky)s — %(mwh).3f MWh × %(gia).5f USD/kWh',
                      ky=self.period_id.name, mwh=self.energy_mwh,
                      gia=self.tariff),
            'quantity': self.energy_mwh,
            'price_unit': (self.tariff or 0.0) * 1000.0,
        })]
        if self.deemed_amount:
            dong.append((0, 0, {
                'name': _('Sản lượng bị cắt giảm (deemed) %(mwh).3f MWh',
                          mwh=self.curtailed_mwh),
                'quantity': self.curtailed_mwh,
                'price_unit': ((self.tariff or 0.0) * 1000.0
                               * (self.ppa_id.deemed_percent or 0.0) / 100.0),
            }))
        return dong
