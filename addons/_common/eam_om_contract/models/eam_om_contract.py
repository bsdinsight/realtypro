# -*- coding: utf-8 -*-
"""Hợp đồng vận hành bảo dưỡng (O&M) và phạm vi nhà máy của nó."""
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

CHU_KY = [
    ('thang', 'Tháng'),
    ('quy', 'Quý'),
    ('nua_nam', 'Nửa năm'),
    ('nam', 'Năm hợp đồng'),
]

#: Số tháng của mỗi chu kỳ. Đếm theo THÁNG chứ không theo ngày, để kỳ
#: luôn rơi đúng ngày giỗ của ngày hiệu lực — hợp đồng ký 31/1 thì kỳ
#: tháng sau kết thúc 28/2, không phải 02/3.
SO_THANG = {'thang': 1, 'quy': 3, 'nua_nam': 6, 'nam': 12}


class EamOmContract(models.Model):
    _name = 'eam.om.contract'
    _description = 'Hợp đồng O&M'
    _inherit = ['mail.thread']
    _order = 'date_start desc, id desc'

    name = fields.Char(
        string='Số hợp đồng', required=True, tracking=True, index=True)
    title = fields.Char(string='Tên hợp đồng', tracking=True)
    partner_id = fields.Many2one(
        'res.partner', string='Nhà thầu O&M', required=True,
        ondelete='restrict', tracking=True)

    date_start = fields.Date(
        string='Hiệu lực từ', required=True, tracking=True)
    date_end = fields.Date(string='Hiệu lực đến', tracking=True)

    chu_ky = fields.Selection(
        CHU_KY, string='Chu kỳ đánh giá', required=True, default='thang',
        tracking=True,
        help='Kỳ sinh ra từ NGÀY HIỆU LỰC, không theo năm dương lịch. '
             'Hợp đồng ký 15/4 thì năm hợp đồng chạy 15/4 → 14/4.')
    so_le = fields.Integer(
        string='Số chữ số thập phân khi chốt', default=2, required=True,
        help='Số đo được LÀM TRÒN tới đây trước khi so với cam kết và '
             'trước khi tính phạt. Lý do: biên bản in ra 97,66 và cam kết '
             '99,5 thì nhà thầu sẽ nhân tay ra khoản phạt — nếu hệ lại '
             'tính theo 97,664765 thì hai con số không khớp và không ai '
             'bảo vệ được biên bản. Số trên giấy phải đúng là số dùng để '
             'tính. Đổi ô này có thể làm một kỳ sát ngưỡng đổi từ đạt '
             'sang không đạt, nên nó thuộc về hợp đồng chứ không phải '
             'tuỳ chọn hiển thị.')
    tz = fields.Char(
        string='Múi giờ của kỳ', required=True,
        default=lambda s: s.env.user.tz or 'Asia/Ho_Chi_Minh',
        help='Kỳ ghi bằng NGÀY còn sổ dừng máy ghi bằng thời điểm UTC, '
             'nên phải biết nửa đêm của kỳ là nửa đêm ở đâu. Khai ngay '
             'trên hợp đồng chứ không lấy theo người đang đăng nhập: '
             'cùng một kỳ mà hai người ở hai múi giờ bấm đo ra hai con '
             'số thì không biên bản nào đứng vững. Người dùng chưa khai '
             'múi giờ thì Odoo coi mọi thứ là UTC — lệch bảy tiếng, và '
             'bảy tiếng đó chuyển giờ dừng sang kỳ bên cạnh đúng ở ranh '
             'giới năm hợp đồng.')

    state = fields.Selection(
        [('nhap', 'Nháp'),
         ('chay', 'Đang hiệu lực'),
         ('het', 'Hết hạn'),
         ('cham_dut', 'Chấm dứt trước hạn')],
        string='Trạng thái', default='nhap', required=True, tracking=True)

    currency_id = fields.Many2one(
        'res.currency', string='Tiền tệ', required=True,
        default=lambda s: s.env.company.currency_id)
    company_id = fields.Many2one(
        'res.company', string='Công ty', required=True,
        default=lambda s: s.env.company, index=True)

    plant_line_ids = fields.One2many(
        'eam.om.contract.plant', 'contract_id', string='Nhà máy trong phạm vi',
        copy=True)
    commitment_ids = fields.One2many(
        'eam.om.commitment', 'contract_id', string='Cam kết', copy=True)
    period_ids = fields.One2many(
        'eam.om.period', 'contract_id', string='Kỳ đánh giá')

    plant_count = fields.Integer(string='Số nhà máy', compute='_compute_dem')
    commitment_count = fields.Integer(string='Số cam kết',
                                      compute='_compute_dem')
    period_count = fields.Integer(string='Số kỳ', compute='_compute_dem')
    phi_moi_ky = fields.Monetary(
        string='Phí mỗi kỳ', compute='_compute_dem',
        help='Tổng phí của các nhà máy trong phạm vi.')

    note = fields.Text(string='Ghi chú')

    _uniq_so = models.Constraint(
        'UNIQUE(company_id, name)',
        'Số hợp đồng O&M không được trùng.')

    # ==================================================================
    @api.depends('plant_line_ids.phi_ky', 'commitment_ids', 'period_ids')
    def _compute_dem(self):
        for rec in self:
            rec.plant_count = len(rec.plant_line_ids)
            rec.commitment_count = len(rec.commitment_ids)
            rec.period_count = len(rec.period_ids)
            rec.phi_moi_ky = sum(rec.plant_line_ids.mapped('phi_ky'))

    @api.depends('name', 'partner_id')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s — %s' % (rec.name or '',
                                            rec.partner_id.name or '')

    @api.constrains('date_start', 'date_end')
    def _check_ngay(self):
        for rec in self:
            if rec.date_end and rec.date_end < rec.date_start:
                raise ValidationError(_(
                    'Hợp đồng "%s": ngày hết hiệu lực trước ngày hiệu lực.',
                    rec.name))

    # ==================================================================
    # Sinh kỳ
    # ==================================================================
    def action_sinh_ky(self):
        """Dựng kỳ đánh giá cho MỌI chu kỳ mà hợp đồng dùng tới.

        Hợp đồng có thể cam kết nhiều tầng: sàn tháng cộng khả dụng năm.
        Mỗi tầng cần kỳ riêng của nó, nếu không thì cam kết năm bị chấm
        bằng số liệu một tháng.

        **Chỉ kỳ theo chu kỳ của HỢP ĐỒNG mới mang phí.** Kỳ của các chu
        kỳ khác chỉ để chấm điểm — không thì một hợp đồng trả phí theo
        tháng lại bị tính thêm một khoản phí năm, và tổng phải trả phồng
        lên gấp đôi mà vẫn trông hợp lý.

        Kỳ ĐÃ CÓ thì bỏ qua: kỳ đã chốt mang số liệu đã chụp, dựng đè lên
        là xoá mất biên bản.
        """
        P = self.env['eam.om.period']
        for rec in self:
            if not rec.date_end:
                raise UserError(_(
                    'Hợp đồng "%s" chưa có ngày hết hiệu lực nên không '
                    'biết dừng sinh kỳ ở đâu.', rec.name))
            can = {rec.chu_ky} | {
                c.chu_ky_hieu_luc for c in rec.commitment_ids
                if c.chu_ky_hieu_luc}
            da_co = {(p.chu_ky, p.date_start, p.date_end)
                     for p in rec.period_ids}
            tao = []
            for ck in sorted(can, key=lambda k: SO_THANG[k]):
                thang = SO_THANG[ck]
                dau = rec.date_start
                while dau <= rec.date_end:
                    cuoi = min(dau + relativedelta(months=thang, days=-1),
                               rec.date_end)
                    if (ck, dau, cuoi) not in da_co:
                        tao.append({
                            'contract_id': rec.id, 'chu_ky': ck,
                            'date_start': dau, 'date_end': cuoi,
                        })
                    dau = cuoi + relativedelta(days=1)
            if tao:
                P.create(tao)
        return True

    def action_xem_ky(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Kỳ đánh giá — %s', self.name),
            'res_model': 'eam.om.period',
            'view_mode': 'list,form',
            'domain': [('contract_id', '=', self.id)],
            'context': {'default_contract_id': self.id},
        }

    def action_chay(self):
        self.write({'state': 'chay'})

    def action_het_han(self):
        self.write({'state': 'het'})


class EamOmContractPlant(models.Model):
    _name = 'eam.om.contract.plant'
    _description = 'Nhà máy trong phạm vi hợp đồng O&M'
    _order = 'contract_id, plant_id'
    _rec_name = 'plant_id'

    contract_id = fields.Many2one(
        'eam.om.contract', string='Hợp đồng', required=True,
        ondelete='cascade', index=True)
    plant_id = fields.Many2one(
        'eam.location', string='Nhà máy', required=True,
        domain="[('location_type', '=', 'plant')]", ondelete='restrict',
        index=True)
    company_id = fields.Many2one(
        related='contract_id.company_id', store=True)
    currency_id = fields.Many2one(
        related='contract_id.currency_id')

    phi_ky = fields.Monetary(
        string='Phí mỗi kỳ',
        help='Phí O&M của riêng nhà máy này trong một kỳ. Khai theo từng '
             'nhà máy chứ không để một cục chung: hợp đồng phủ ba nhà máy '
             'mà chỉ có một con số tổng thì không trả lời được câu hỏi '
             '"nhà máy này tháng này phải trả bao nhiêu" — mà đó đúng là '
             'câu khách hỏi.')
    so_don_vi = fields.Integer(
        string='Số đơn vị đo khả dụng',
        help='Số tổ máy dùng làm MẪU SỐ khi tính khả dụng theo thời gian. '
             'Ba mươi tua-bin chạy một ngày là 720 giờ-máy, không phải '
             '24. Để 0 nghĩa là coi cả nhà máy là MỘT đơn vị — chỉ đúng '
             'khi cam kết đặt ở cấp nhà máy.')
    note = fields.Char(string='Ghi chú')

    _uniq_plant = models.Constraint(
        'UNIQUE(contract_id, plant_id)',
        'Mỗi nhà máy chỉ xuất hiện một lần trong phạm vi hợp đồng.')

    def action_dem_don_vi(self):
        """Đếm thử số vị trí thiết bị con để gợi ý mẫu số.

        Chỉ GỢI Ý rồi để người khai tự quyết: không phải vị trí con nào
        cũng là một tổ máy, và cam kết của từng hợp đồng đếm khác nhau.
        """
        L = self.env['eam.location']
        for rec in self:
            if not rec.plant_id:
                continue
            rec.so_don_vi = L.search_count([
                ('id', 'child_of', rec.plant_id.id),
                ('location_type', '=', 'position')])
        return True
