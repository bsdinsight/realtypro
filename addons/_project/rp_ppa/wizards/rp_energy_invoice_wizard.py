# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class RpEnergyInvoiceWizard(models.TransientModel):
    """Gộp nhiều KỲ của MỘT bên mua vào một hoá đơn.

    Hai luật không đổi được, và chúng kéo nhau:

    * **Một hoá đơn chỉ một bên mua.** Một kỳ sản lượng phân bổ cho nhiều
      hợp đồng (AMI bán cho cả EVN lẫn EDL), nên không bao giờ được xuất
      hoá đơn "theo kỳ" — phải xuất theo DÒNG phân bổ, mỗi bên mua một tờ.
    * **Một hoá đơn có thể gồm nhiều kỳ.** Thực tế hiếm khi phát hành
      tháng nào tờ nấy: chốt công-tơ xong còn đối soát, nên thường dồn
      vài tháng ra một tờ. Mỗi kỳ là một dòng trên hoá đơn để bên mua còn
      lần được số.

    Nút "Xuất hoá đơn" trên chính kỳ vẫn giữ, cho trường hợp phát hành
    từng tháng — nó là lối tắt của wizard này với đúng một kỳ.
    """
    _name = 'rp.energy.invoice.wizard'
    _description = 'Xuất hoá đơn tiền điện (gộp nhiều kỳ)'

    project_id = fields.Many2one(
        're.project', string='Dự án', required=True,
        default=lambda self: self.env.context.get('default_project_id'))
    partner_id = fields.Many2one(
        'res.partner', string='Bên mua', required=True,
        help='Mỗi lần chạy chỉ ra hoá đơn cho MỘT bên mua.')
    date_from = fields.Date(string='Kỳ từ ngày')
    date_to = fields.Date(string='Kỳ đến ngày')
    invoice_date = fields.Date(
        string='Ngày hoá đơn', required=True,
        default=lambda self: fields.Date.context_today(self))
    line_ids = fields.Many2many(
        'rp.energy.period.line', string='Các kỳ sẽ đưa vào hoá đơn')
    ky_count = fields.Integer(string='Số kỳ', compute='_compute_tong')
    tong_mwh = fields.Float(
        string='Tổng sản lượng (MWh)', compute='_compute_tong', digits=(16, 3))
    tong_tien = fields.Monetary(
        string='Tổng tiền', compute='_compute_tong')
    currency_id = fields.Many2one(
        'res.currency', compute='_compute_tong')

    @api.depends('line_ids')
    def _compute_tong(self):
        for w in self:
            w.ky_count = len(w.line_ids)
            w.tong_mwh = sum(w.line_ids.mapped('energy_mwh'))
            w.tong_tien = sum(w.line_ids.mapped('amount'))
            w.currency_id = w.line_ids[:1].currency_id

    def _domain_dong(self):
        self.ensure_one()
        d = [('period_id.project_id', '=', self.project_id.id),
             ('ppa_id.partner_id', '=', self.partner_id.id),
             ('invoice_id', '=', False),
             # Chưa chốt công-tơ thì số còn thay đổi, không xuất hoá đơn.
             ('period_id.state', 'in', ('confirmed', 'invoiced'))]
        if self.date_from:
            d.append(('period_id.date_from', '>=', self.date_from))
        if self.date_to:
            d.append(('period_id.date_to', '<=', self.date_to))
        return d

    @api.onchange('project_id', 'partner_id', 'date_from', 'date_to')
    def _onchange_lay_ky(self):
        for w in self:
            if not (w.project_id and w.partner_id):
                w.line_ids = [(5, 0, 0)]
                continue
            dong = self.env['rp.energy.period.line'].search(
                w._domain_dong(), order='period_id')
            w.line_ids = [(6, 0, dong.ids)]

    def action_tao_hoa_don(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_('Không có kỳ nào chưa xuất hoá đơn cho bên '
                              'mua này.'))
        # Chốt chặn cuối: dù giao diện có lọc sẵn, vẫn không cho một tờ
        # hoá đơn mang hai bên mua.
        ben_mua = self.line_ids.mapped('ppa_id.partner_id')
        if len(ben_mua) > 1:
            raise UserError(_(
                'Các kỳ đang chọn thuộc %s bên mua khác nhau (%s). Một hoá '
                'đơn chỉ được có một bên mua.',
                len(ben_mua), ', '.join(ben_mua.mapped('display_name'))))
        tien_te = self.line_ids.mapped('ppa_id.currency_id')
        if len(tien_te) > 1:
            raise UserError(_('Các kỳ đang chọn dùng %s loại tiền khác nhau.',
                              len(tien_te)))
        # Điều khoản thanh toán lấy từ PPA → Odoo tự tính hạn thanh toán.
        # Một bên mua có thể có nhiều PPA; khác điều khoản thì không gộp
        # chung một tờ được, vì một hoá đơn chỉ mang được một hạn.
        dieu_khoan = self.line_ids.mapped('ppa_id.payment_term_id')
        if len(dieu_khoan) > 1:
            raise UserError(_(
                'Các kỳ đang chọn thuộc %s điều khoản thanh toán khác nhau '
                '(%s). Một hoá đơn chỉ mang được một hạn thanh toán — hãy '
                'lọc theo khoảng thời gian để tách ra.',
                len(dieu_khoan), ', '.join(dieu_khoan.mapped('name'))))
        dong_hd = []
        for l in self.line_ids.sorted(lambda x: x.period_id.date_from):
            dong_hd += l._dong_hoa_don()
        ky = self.line_ids.mapped('period_id').sorted('date_from')
        hd = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_id.id,
            'invoice_date': self.invoice_date,
            'currency_id': tien_te.id,
            'ref': _('Tiền điện %(tu)s–%(den)s — %(hd)s',
                     tu=ky[0].date_from.strftime('%m/%Y'),
                     den=ky[-1].date_to.strftime('%m/%Y'),
                     hd=', '.join(self.line_ids.mapped('ppa_id.name'))),
            'invoice_payment_term_id': dieu_khoan.id or False,
            'invoice_line_ids': dong_hd,
        })
        self.line_ids.invoice_id = hd.id
        # Kỳ chỉ chuyển sang "đã xuất hoá đơn" khi MỌI dòng của nó đã có
        # hoá đơn — kỳ bán cho hai bên mà mới xuất một bên thì chưa xong.
        for k in ky:
            if all(x.invoice_id for x in k.line_ids):
                k.state = 'invoiced'
        return {
            'type': 'ir.actions.act_window',
            'name': _('Hoá đơn tiền điện'),
            'res_model': 'account.move',
            'res_id': hd.id,
            'view_mode': 'form',
        }
