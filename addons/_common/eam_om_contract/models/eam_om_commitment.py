# -*- coding: utf-8 -*-
"""Cam kết của nhà thầu O&M, và chế tài khi không đạt.

Cam kết là DỮ LIỆU, không phải mã
----------------------------------
Mỗi hợp đồng cam kết một kiểu: nhà này 97% khả dụng theo thời gian, nhà
kia 95% theo sản lượng, nhà khác thêm tỷ số hiệu suất và thời gian phản
hồi. Viết cứng một bộ chỉ tiêu là đúng cho hợp đồng đầu tiên và sai cho
mọi hợp đồng sau — mà cái sai đó hiện lên màn hình y hệt cái đúng.

Chế tài có TRẦN
----------------
Hợp đồng O&M thật gần như luôn chặn trần phạt theo phí kỳ. Không có
trần thì một kỳ tệ tính ra khoản phạt lớn hơn cả phí — con số vô nghĩa
mà vẫn in ra được, và người đọc biên bản phải tự biết là nó sai.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

#: Cơ sở đo. Giá trị nào CHƯA đo được thì khai ở ``CHUA_DO`` bên dưới,
#: đừng bỏ ra khỏi danh sách — hợp đồng vẫn cam kết theo nó, và việc hệ
#: chưa đo được phải hiện ra chứ không phải biến mất.
LOAI = [
    ('kd_thoi_gian', 'Khả dụng theo thời gian (%)'),
    ('kd_san_luong', 'Khả dụng theo sản lượng (%)'),
    ('pr', 'Tỷ số hiệu suất PR (%)'),
    ('phan_hoi', 'Thời gian phản hồi (giờ)'),
    ('khac_phuc', 'Thời gian khắc phục (giờ)'),
]

#: Cơ sở hệ CHƯA đo được, kèm lý do nói thẳng cho người dùng.
CHUA_DO = {
    'kd_san_luong': 'khả dụng theo sản lượng cần mô hình sản lượng đáng '
                    'lẽ phát được (đường cong công suất hoặc máy đối '
                    'chứng) — thuộc module Khả dụng, chưa làm',
    'pr': 'tỷ số hiệu suất hiện tính ở phần điện mặt trời theo ngày, '
          'chưa gộp lên theo kỳ hợp đồng',
    'phan_hoi': 'thời gian phản hồi cần mốc tiếp nhận trên lệnh công '
                'việc, chưa nối vào',
    'khac_phuc': 'thời gian khắc phục cần mốc hoàn thành trên lệnh công '
                 'việc, chưa nối vào',
}

CHE_TAI = [
    ('khong', 'Không phạt'),
    ('theo_diem', 'Phạt theo mỗi điểm % thiếu'),
    ('ty_le_phi', 'Phạt theo % phí kỳ cho mỗi điểm % thiếu'),
    ('co_dinh', 'Phạt cố định một lần'),
]


class EamOmCommitment(models.Model):
    _name = 'eam.om.commitment'
    _description = 'Cam kết hợp đồng O&M'
    _inherit = ['mail.thread']
    _order = 'contract_id, sequence, id'
    _rec_name = 'display_name'

    contract_id = fields.Many2one(
        'eam.om.contract', string='Hợp đồng', required=True,
        ondelete='cascade', index=True)
    company_id = fields.Many2one(related='contract_id.company_id', store=True)
    currency_id = fields.Many2one(related='contract_id.currency_id')
    sequence = fields.Integer(default=10)

    name = fields.Char(
        string='Tên cam kết', required=True,
        help='Ghi như trong hợp đồng, ví dụ "Khả dụng năm tối thiểu 97%".')
    loai = fields.Selection(
        LOAI, string='Cơ sở đo', required=True, default='kd_thoi_gian',
        tracking=True)
    do_duoc = fields.Boolean(
        string='Hệ đo được', compute='_compute_do_duoc', store=True,
        help='Cơ sở này hệ đã đo được hay chưa. Chưa đo được thì kỳ vẫn '
             'ra dòng kết quả, nhưng ghi rõ lý do và KHÔNG tính phạt.')
    ly_do_chua_do = fields.Char(
        string='Vì sao chưa đo được', compute='_compute_do_duoc', store=True)

    chu_ky = fields.Selection(
        [('thang', 'Tháng'), ('quy', 'Quý'), ('nua_nam', 'Nửa năm'),
         ('nam', 'Năm hợp đồng')],
        string='Chấm theo chu kỳ',
        help='Để trống là theo chu kỳ của hợp đồng. Khai riêng khi hợp '
             'đồng có NHIỀU tầng cam kết — gió thường có cả sàn tháng lẫn '
             'khả dụng năm. Chấm cam kết năm bằng số liệu một tháng là '
             'phạt oan: một tháng xấu kéo cả năm xuống, trong khi hợp '
             'đồng cho phép bù bằng các tháng còn lại.')
    chu_ky_hieu_luc = fields.Selection(
        [('thang', 'Tháng'), ('quy', 'Quý'), ('nua_nam', 'Nửa năm'),
         ('nam', 'Năm hợp đồng')],
        string='Chu kỳ chấm', compute='_compute_chu_ky', store=True)

    plant_id = fields.Many2one(
        'eam.location', string='Chỉ áp cho nhà máy',
        domain="[('location_type', '=', 'plant')]",
        help='Để trống thì cam kết áp cho MỌI nhà máy trong phạm vi hợp '
             'đồng, mỗi nhà máy một dòng kết quả riêng.')

    muc = fields.Float(
        string='Mức cam kết', required=True, digits=(16, 2), tracking=True)
    huong = fields.Selection(
        [('toi_thieu', 'Phải đạt tối thiểu (≥)'),
         ('toi_da', 'Không được vượt (≤)')],
        string='Chiều so sánh', required=True, default='toi_thieu',
        help='Khả dụng và hiệu suất là "tối thiểu"; thời gian phản hồi và '
             'khắc phục là "không được vượt". Chọn nhầm chiều thì mọi kỳ '
             'đạt thành không đạt, và ngược lại.')

    tinh_ca_chua_quy = fields.Boolean(
        string='Tính cả giờ chưa quy trách nhiệm',
        help='Mặc định TẮT: chỉ giờ dừng đã quy cho nghĩa vụ hợp đồng O&M '
             'mới tính vào phần nhà thầu. Bật lên khi hợp đồng quy định '
             'nhà thầu chịu mặc định cho tới khi chứng minh được ngược '
             'lại. Dù tắt hay bật, số giờ chưa quy vẫn hiện ở dòng kết '
             'quả — con số khả dụng đẹp vì chưa ai phân loại thì phải '
             'nhìn thấy được.')
    nguong_chua_quy = fields.Float(
        string='Ngưỡng cảnh báo giờ chưa quy (%)', default=10.0,
        digits=(5, 2),
        help='Giờ chưa quy vượt tỷ lệ này so với tổng giờ dừng thì dòng '
             'kết quả cắm cờ. Kết quả vẫn tính, nhưng người ký biên bản '
             'thấy trước khi ký.')

    # ----- Chế tài --------------------------------------------------
    che_tai = fields.Selection(
        CHE_TAI, string='Chế tài', required=True, default='khong',
        tracking=True)
    muc_phat = fields.Float(
        string='Mức phạt', digits=(16, 2),
        help='Theo điểm %: số tiền cho mỗi điểm phần trăm thiếu. Theo %% '
             'phí kỳ: phần trăm phí cho mỗi điểm thiếu. Cố định: số tiền.')
    tran_phat_pct = fields.Float(
        string='Trần phạt (% phí kỳ)', default=100.0, digits=(5, 2),
        help='Chặn trần theo phí kỳ của nhà máy. Để 0 là KHÔNG chặn — chỉ '
             'dùng khi hợp đồng thật sự không có trần, vì không trần thì '
             'một kỳ tệ ra khoản phạt lớn hơn cả phí.')

    note = fields.Text(string='Trích điều khoản')

    # ==================================================================
    @api.depends('chu_ky', 'contract_id.chu_ky')
    def _compute_chu_ky(self):
        for rec in self:
            rec.chu_ky_hieu_luc = rec.chu_ky or rec.contract_id.chu_ky

    @api.model
    def _ly_do_chua_do(self, loai):
        """Vì sao hệ chưa đo được cơ sở này — '' nghĩa là đo được.

        Là MỘT PHƯƠNG THỨC chứ không phải tra thẳng hằng số, để module
        làm sau bịt được lỗ hổng mà module này tự khai. Module khả dụng
        kế thừa và bỏ "khả dụng theo sản lượng" ra khỏi danh sách khi nó
        đã đo được — chứ không dựng engine thứ hai rồi hai nơi trả lời
        khác nhau.
        """
        return CHUA_DO.get(loai, '')

    @api.depends('loai')
    def _compute_do_duoc(self):
        for rec in self:
            rec.ly_do_chua_do = rec._ly_do_chua_do(rec.loai)
            rec.do_duoc = not rec.ly_do_chua_do

    @api.depends('name', 'muc', 'loai')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s (%s %s)' % (
                rec.name or '',
                '≥' if rec.huong == 'toi_thieu' else '≤', rec.muc)

    @api.onchange('loai')
    def _onchange_loai(self):
        """Gợi ý chiều so sánh theo cơ sở đo — gợi ý, không ép."""
        if self.loai in ('phan_hoi', 'khac_phuc'):
            self.huong = 'toi_da'
        elif self.loai:
            self.huong = 'toi_thieu'

    @api.constrains('muc', 'loai')
    def _check_muc(self):
        for rec in self:
            if rec.loai in ('kd_thoi_gian', 'kd_san_luong', 'pr') \
                    and not (0 < rec.muc <= 100):
                raise ValidationError(_(
                    'Cam kết "%(n)s" đo bằng phần trăm nên mức phải nằm '
                    'trong 0–100, đang nhận %(m)s.',
                    n=rec.name, m=rec.muc))
            if rec.muc < 0:
                raise ValidationError(_(
                    'Cam kết "%s" có mức âm.', rec.name))

    @api.constrains('che_tai', 'muc_phat')
    def _check_phat(self):
        for rec in self:
            if rec.che_tai != 'khong' and not rec.muc_phat:
                raise ValidationError(_(
                    'Cam kết "%s" khai có chế tài nhưng mức phạt bằng 0 — '
                    'mọi kỳ không đạt sẽ ra khoản phạt bằng 0 mà không có '
                    'gì báo. Để "Không phạt" nếu hợp đồng không có chế '
                    'tài.', rec.name))

    @api.constrains('plant_id', 'contract_id')
    def _check_plant_trong_pham_vi(self):
        for rec in self:
            if not rec.plant_id:
                continue
            trong = rec.contract_id.plant_line_ids.mapped('plant_id')
            if rec.plant_id not in trong:
                raise ValidationError(_(
                    'Cam kết "%(n)s" trỏ tới nhà máy "%(p)s" không nằm '
                    'trong phạm vi hợp đồng. Thêm nhà máy đó vào phạm vi '
                    'trước, nếu không cam kết sẽ không bao giờ sinh dòng '
                    'kết quả nào.', n=rec.name, p=rec.plant_id.name))

    # ==================================================================
    def tinh_phat(self, thieu_hut, phi_ky):
        """Khoản phạt cho một kỳ, đã chặn trần."""
        self.ensure_one()
        if self.che_tai == 'khong' or thieu_hut <= 0:
            return 0.0
        if self.che_tai == 'co_dinh':
            phat = self.muc_phat
        elif self.che_tai == 'theo_diem':
            phat = self.muc_phat * thieu_hut
        else:                                    # ty_le_phi
            phat = phi_ky * (self.muc_phat / 100.0) * thieu_hut
        if self.tran_phat_pct:
            phat = min(phat, phi_ky * self.tran_phat_pct / 100.0)
        return max(phat, 0.0)
