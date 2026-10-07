# -*- coding: utf-8 -*-
"""Hợp đồng mua bán điện (PPA) và biểu giá theo năm hợp đồng.

Thời hạn tính từ COD chứ không từ ngày ký: nhà máy chưa chạy thì chưa
bán được gì, và COD thì trượt theo tiến độ thi công. Vì vậy ngày hiệu
lực LẤY THEO mốc COD của dự án — xây chậm thì cả đời hợp đồng dời theo,
đúng như thực tế.

Trượt giá là mặc định, không phải tuỳ chọn: một con số giá duy nhất cho
20 năm sai ngay từ năm thứ hai.
"""
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class RpPpa(models.Model):
    _name = 'rp.ppa'
    _description = 'Hợp đồng mua bán điện (PPA)'
    _inherit = ['mail.thread']
    _order = 'project_id, sequence, id'

    name = fields.Char(
        string='Số hợp đồng', required=True, copy=False, tracking=True,
        default=lambda self: _('Mới'))
    title = fields.Char(string='Tên hợp đồng', tracking=True)
    sequence = fields.Integer(default=10)
    project_id = fields.Many2one(
        're.project', string='Dự án', required=True, index=True,
        ondelete='cascade', tracking=True)
    partner_id = fields.Many2one(
        'res.partner', string='Bên mua điện', required=True,
        ondelete='restrict', tracking=True)
    meter_id = fields.Many2one(
        'rp.energy.meter', string='Điểm giao nhận',
        domain="[('project_id', '=', project_id)]", tracking=True,
        help='Điểm đo mà sản lượng được tính để thanh toán theo hợp '
             'đồng này.')

    state = fields.Selection(
        [('draft', 'Nháp'),
         ('negotiating', 'Đang đàm phán'),
         ('signed', 'Đã ký'),
         ('active', 'Đang hiệu lực'),
         ('expired', 'Hết hạn')],
        string='Trạng thái', default='draft', required=True, tracking=True,
        copy=False)
    date_signed = fields.Date(string='Ngày ký', tracking=True)
    date_cod = fields.Date(
        string='Ngày COD (từ dự án)', related='project_id.date_cod',
        readonly=True,
        help='Hợp đồng bắt đầu chạy từ mốc này, không phải từ ngày ký — '
             'nhà máy chưa vận hành thương mại thì chưa bán được gì.')
    term_years = fields.Integer(
        string='Thời hạn (năm)', default=20, tracking=True)
    date_end = fields.Date(
        string='Ngày hết hạn', compute='_compute_date_end', store=True)

    payment_term_id = fields.Many2one(
        'account.payment.term', string='Điều khoản thanh toán',
        help='PPA luôn ghi kiểu "thanh toán trong N ngày kể từ ngày nhận '
             'hoá đơn". Khai ở đây thì hạn thanh toán trên hoá đơn tự '
             'tính, không phải gõ tay — mà hạn gõ tay sai một lần là cả '
             'bảng tuổi nợ sai theo.')

    currency_id = fields.Many2one(
        'res.currency', string='Đồng tiền', required=True,
        default=lambda self: self.env.ref('base.USD',
                                          raise_if_not_found=False)
        or self.env.company.currency_id,
        tracking=True,
        help='Giá PPA thường tính USD trong khi thu bằng nội tệ — chênh '
             'lệch tỷ giá là một rủi ro doanh thu riêng, không phải '
             'chuyện kỹ thuật.')
    tariff_base = fields.Float(
        string='Giá gốc (USD/kWh)', digits=(16, 5), tracking=True)
    escalation_percent = fields.Float(
        string='Trượt giá (%/năm)', digits=(6, 3), default=2.0,
        tracking=True,
        help='Áp từ năm hợp đồng thứ 2 trở đi.')
    tariff_line_ids = fields.One2many(
        'rp.ppa.tariff', 'ppa_id', string='Biểu giá theo năm')
    tariff_line_count = fields.Integer(compute='_compute_tariff_count')

    allocation_percent = fields.Float(
        string='Tỷ lệ sản lượng (%)', digits=(6, 2), default=100.0,
        tracking=True,
        help='Phần sản lượng của nhà máy bán theo hợp đồng này. Nhiều '
             'bên mua thì tổng các hợp đồng phải bằng 100%.')
    test_energy_percent = fields.Float(
        string='Giá điện chạy thử (% giá PPA)', digits=(6, 2), default=50.0,
        help='Điện phát ra TRƯỚC ngày COD. Thường được mua với giá chiết '
             'khấu vì chưa được công nhận vận hành thương mại.')
    deemed_energy = fields.Boolean(
        string='Trả cho sản lượng bị cắt giảm', default=True, tracking=True,
        help='Lưới bắt giảm phát thì nhà máy vẫn được trả. Đây thường là '
             'rủi ro doanh thu lớn hơn cả rủi ro gió với điện gió đấu '
             'nối xuyên biên giới.')
    deemed_percent = fields.Float(
        string='Tỷ lệ trả khi bị cắt giảm (%)', digits=(6, 2), default=100.0)

    payment_term_days = fields.Integer(
        string='Hạn thanh toán (ngày)', default=30)
    meter_reading_day = fields.Integer(
        string='Ngày chốt công-tơ', default=31,
        help='31 = ngày cuối tháng.')

    availability_guarantee_y1 = fields.Float(
        string='Cam kết khả dụng năm 1 (%)', digits=(6, 2), default=97.0)
    availability_guarantee_y2 = fields.Float(
        string='Cam kết khả dụng từ năm 2 (%)', digits=(6, 2), default=98.0)

    note = fields.Text(string='Ghi chú điều khoản')
    company_id = fields.Many2one(
        'res.company', string='Công ty',
        default=lambda self: self.env.company, index=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('Mới')) == _('Mới'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'rp.ppa') or _('PPA mới')
        return super().create(vals_list)

    @api.depends('date_cod', 'term_years')
    def _compute_date_end(self):
        for rec in self:
            if rec.date_cod and rec.term_years:
                rec.date_end = rec.date_cod + relativedelta(
                    years=rec.term_years, days=-1)
            else:
                rec.date_end = False

    @api.depends('tariff_line_ids')
    def _compute_tariff_count(self):
        for rec in self:
            rec.tariff_line_count = len(rec.tariff_line_ids)

    def action_sinh_bieu_gia(self):
        """Dựng biểu giá từng năm hợp đồng từ giá gốc + trượt giá."""
        for rec in self:
            if not rec.date_cod:
                raise UserError(_(
                    'Dự án chưa có ngày COD — chưa biết hợp đồng bắt đầu '
                    'chạy từ lúc nào.'))
            if not rec.tariff_base:
                raise UserError(_('Chưa khai giá gốc.'))
            rec.tariff_line_ids.unlink()
            gia = rec.tariff_base
            dong = []
            for nam in range(1, (rec.term_years or 1) + 1):
                tu = rec.date_cod + relativedelta(years=nam - 1)
                den = rec.date_cod + relativedelta(years=nam, days=-1)
                if nam > 1:
                    gia = gia * (1 + (rec.escalation_percent or 0.0) / 100.0)
                dong.append((0, 0, {
                    'contract_year': nam, 'date_from': tu, 'date_to': den,
                    'tariff': round(gia, 5),
                }))
            rec.tariff_line_ids = dong
        return True

    def _gia_tai_ngay(self, ngay):
        """Giá áp dụng cho một ngày. Ngoài thời hạn thì trả 0."""
        self.ensure_one()
        d = self.tariff_line_ids.filtered(
            lambda l: l.date_from <= ngay <= l.date_to)[:1]
        return d.tariff if d else 0.0

    def _gia_chay_thu(self):
        """Giá cho điện phát TRƯỚC COD.

        Không tra được theo ngày: biểu giá bắt đầu từ COD, mà điện chạy
        thử thì phát ra trước đó — tra theo ngày sẽ rơi ra ngoài mọi năm
        hợp đồng và trả về 0, tức là cho không sáu tuần điện. Lấy giá
        năm 1 rồi nhân tỷ lệ chạy thử.
        """
        self.ensure_one()
        nam1 = self.tariff_line_ids.sorted('contract_year')[:1]
        goc = nam1.tariff if nam1 else (self.tariff_base or 0.0)
        return goc * (self.test_energy_percent or 0.0) / 100.0

    def action_mo_bieu_gia(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Biểu giá — %s', self.name),
            'res_model': 'rp.ppa.tariff',
            'view_mode': 'list',
            'domain': [('ppa_id', '=', self.id)],
        }

    @api.constrains('allocation_percent')
    def _check_allocation(self):
        for rec in self:
            if not (0.0 <= rec.allocation_percent <= 100.0):
                raise UserError(_(
                    'Tỷ lệ sản lượng phải trong khoảng 0–100%.'))


class RpPpaTariff(models.Model):
    _name = 'rp.ppa.tariff'
    _description = 'Biểu giá theo năm hợp đồng'
    _order = 'ppa_id, contract_year'

    ppa_id = fields.Many2one(
        'rp.ppa', string='Hợp đồng', required=True, index=True,
        ondelete='cascade')
    contract_year = fields.Integer(string='Năm hợp đồng', required=True)
    date_from = fields.Date(string='Từ ngày', required=True)
    date_to = fields.Date(string='Đến ngày', required=True)
    tariff = fields.Float(string='Giá (USD/kWh)', digits=(16, 5))
    currency_id = fields.Many2one(
        'res.currency', related='ppa_id.currency_id', readonly=True)
    project_id = fields.Many2one(
        're.project', related='ppa_id.project_id', store=True, readonly=True)
