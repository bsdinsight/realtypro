# -*- coding: utf-8 -*-
"""Sản lượng một ngày của một bậc, và tổn thất so với bậc trước.

Luỹ kế KHÔNG lưu
----------------
Luỹ kế tháng và luỹ kế năm tính lại mỗi lần đọc, không lưu vào cột. Lưu
thì nhanh hơn, nhưng sửa một ngày giữa tháng là mọi ngày sau nó sai cho
tới khi có ai nhớ chạy lại — mà sẽ không ai nhớ. Số bậc nhân số ngày là
nhỏ, nên tính lại rẻ hơn hẳn so với cái giá của một con số luỹ kế sai
nằm im trong báo cáo.

Tổn thất chỉ tính giữa hai bậc SẢN LƯỢNG
-----------------------------------------
Điện tự dùng và tiêu thụ ban đêm bị loại khỏi phép trừ theo bậc. Chúng
là tiêu thụ có chủ đích, hiện thành dòng riêng trong báo cáo.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class EamChainDay(models.Model):
    _name = 'eam.chain.day'
    _description = 'Sản lượng ngày theo bậc đo'
    _order = 'date desc, node_id'
    _rec_name = 'display_name'

    node_id = fields.Many2one(
        'eam.chain.node', string='Bậc đo', required=True, index=True,
        ondelete='cascade')
    chain_id = fields.Many2one(
        related='node_id.chain_id', store=True, index=True)
    plant_id = fields.Many2one(
        related='node_id.plant_id', store=True, index=True)
    company_id = fields.Many2one(related='node_id.company_id', store=True)
    node_type = fields.Selection(
        related='node_id.node_type', store=True)
    sequence = fields.Integer(related='node_id.sequence', store=True)

    date = fields.Date(string='Ngày', required=True, index=True)
    energy = fields.Float(
        string='Sản lượng (kWh)', digits=(16, 1), required=True)
    energy_scada = fields.Float(
        string='SCADA (kWh)', digits=(16, 1),
        help='Số từ điểm đo SCADA, khai để đối chiếu với công-tơ.')
    nguon = fields.Selection(
        [('cong_to', 'Hiệu số đọc công-tơ'),
         ('scada', 'Tích phân từ SCADA'),
         ('tay', 'Nhập tay')],
        string='Nguồn', default='tay', required=True)

    # ----- Tổn thất so với bậc trước -------------------------------------
    energy_truoc = fields.Float(
        string='Bậc trước (kWh)', digits=(16, 1),
        compute='_compute_ton_that')
    loss_kwh = fields.Float(
        string='Tổn thất (kWh)', digits=(16, 1), compute='_compute_ton_that',
        store=True)
    loss_pct = fields.Float(
        string='Tổn thất (%)', digits=(6, 4), compute='_compute_ton_that',
        store=True)

    # ----- Đối chiếu công-tơ vs SCADA ------------------------------------
    lech_scada_pct = fields.Float(
        string='Lệch SCADA (%)', digits=(6, 2), compute='_compute_lech',
        store=True)
    canh_bao_lech = fields.Boolean(
        string='Lệch quá ngưỡng', compute='_compute_lech', store=True)

    # ----- Luỹ kế: TÍNH LẠI, không lưu -----------------------------------
    luy_ke_thang = fields.Float(
        string='Luỹ kế tháng (kWh)', digits=(16, 1), compute='_compute_luy_ke')
    luy_ke_nam = fields.Float(
        string='Luỹ kế năm (kWh)', digits=(16, 1), compute='_compute_luy_ke')

    _uniq_ngay = models.Constraint(
        'UNIQUE(node_id, date)',
        'Mỗi bậc chỉ có một dòng cho một ngày.')

    @api.depends('node_id', 'date')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s — %s' % (rec.node_id.name or '',
                                            rec.date or '')

    @api.depends('energy', 'date', 'node_id', 'node_id.sequence',
                 'node_id.node_type')
    def _compute_ton_that(self):
        for rec in self:
            truoc = rec.node_id._bac_truoc()
            d = self.search([('node_id', '=', truoc.id),
                             ('date', '=', rec.date)], limit=1) if truoc else None
            rec.energy_truoc = d.energy if d else 0.0
            if d and d.energy:
                rec.loss_kwh = d.energy - rec.energy
                rec.loss_pct = 100.0 * rec.loss_kwh / d.energy
            else:
                rec.loss_kwh = 0.0
                rec.loss_pct = 0.0

    @api.depends('energy', 'energy_scada', 'node_id.doi_chieu_nguong')
    def _compute_lech(self):
        for rec in self:
            if rec.energy and rec.energy_scada:
                rec.lech_scada_pct = 100.0 * (rec.energy_scada - rec.energy) / rec.energy
                nguong = rec.node_id.doi_chieu_nguong or 0
                rec.canh_bao_lech = bool(nguong) and abs(rec.lech_scada_pct) > nguong
            else:
                rec.lech_scada_pct = 0.0
                rec.canh_bao_lech = False

    def _compute_luy_ke(self):
        for rec in self:
            if not rec.date or not rec.node_id:
                rec.luy_ke_thang = rec.luy_ke_nam = 0.0
                continue
            dau_thang = rec.date.replace(day=1)
            dau_nam = rec.date.replace(month=1, day=1)
            def tong(tu):
                return sum(self.search([
                    ('node_id', '=', rec.node_id.id),
                    ('date', '>=', tu), ('date', '<=', rec.date),
                ]).mapped('energy'))
            rec.luy_ke_thang = tong(dau_thang)
            rec.luy_ke_nam = tong(dau_nam)

    @api.constrains('energy')
    def _check_energy(self):
        for rec in self:
            if rec.energy < 0:
                raise ValidationError(_(
                    'Sản lượng âm (%s kWh) ở bậc "%s" ngày %s. Hai nguyên '
                    'nhân thường gặp: công-tơ vừa được thay mà chưa đánh '
                    'dấu, hoặc hai số đọc bị đảo ngày.',
                    rec.energy, rec.node_id.name, rec.date))

    # ==================================================================
    # Tổn thất của một bậc đọc sang DÒNG NGÀY CỦA BẬC TRƯỚC — một quan
    # hệ Odoo không theo dõi được, vì nó đi qua ``sequence`` chứ không
    # qua một trường quan hệ. ``eam.chain.node`` đã đỡ trường hợp thêm
    # hoặc đổi thứ tự BẬC; còn thiếu trường hợp thường gặp hơn nhiều:
    # dòng ngày của bậc trước mới được dựng, hoặc vừa sửa số.
    #
    # Hậu quả không hề báo: bậc sau giữ nguyên tổn thất CŨ, mà số cũ
    # trông y hệt số mới. Dựng bậc "đầu vào một chiều" xong thì tổn hao
    # biến đổi của bộ nghịch lưu vẫn hiện là trống, và người đọc kết
    # luận nhà máy không đo được hiệu suất.
    # ==================================================================
    def _tinh_lai_ke_ben(self):
        """Tính lại tổn thất cho mọi dòng CÙNG CHUỖI, CÙNG NGÀY."""
        if not self:
            return
        khoa = {(r.chain_id.id, r.date) for r in self if r.chain_id and r.date}
        if not khoa:
            return
        mien = ['|'] * (len(khoa) - 1)
        for c, d in khoa:
            mien += ['&', ('chain_id', '=', c), ('date', '=', d)]
        ke = self.search(mien)
        if ke:
            ke._compute_ton_that()
            ke.flush_recordset()

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs._tinh_lai_ke_ben()
        return recs

    def write(self, vals):
        res = super().write(vals)
        if {'energy', 'node_id', 'date'} & set(vals):
            self._tinh_lai_ke_ben()
        return res

    def unlink(self):
        ke = self.browse()
        if self:
            khoa = {(r.chain_id.id, r.date)
                    for r in self if r.chain_id and r.date}
            if khoa:
                mien = ['|'] * (len(khoa) - 1)
                for c, d in khoa:
                    mien += ['&', ('chain_id', '=', c), ('date', '=', d)]
                ke = self.search(mien) - self
        res = super().unlink()
        ke.exists()._tinh_lai_ke_ben()
        return res
