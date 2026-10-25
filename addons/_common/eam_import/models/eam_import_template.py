# -*- coding: utf-8 -*-
"""Mẫu nạp — cách đọc một loại tệp, khai một lần rồi dùng mãi.

Vì sao là dữ liệu chứ không phải mã
------------------------------------
Mỗi nhà máy có mẫu báo cáo riêng. Viết một hàm đọc cho mẫu đầu tiên thì
mẫu thứ hai phải viết hàm thứ hai, và tới mẫu thứ ba đã có ba đoạn mã
gần giống nhau mà không ai dám sửa. Khai thành bản ghi thì chỉ có **một**
bộ mã đọc, và thêm nhà máy là việc của người triển khai, không phải của
lập trình viên.

Đây cũng chính là phần "ánh xạ điểm đo ↔ tag": mỗi dòng mẫu nối một địa
chỉ trong tệp nguồn với một đích trong hệ. Nối theo **mã** (mã bậc đo,
mã tag) chứ không theo khoá nội bộ, nên cùng một mẫu chạy được cho mọi
nhà máy dùng chung quy ước đặt mã.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from . import doc_nguon

#: Đích đến và model tương ứng. Thứ tự của dict này là **thứ tự ghi**:
#: tổng xạ và nhiệt độ mô-đun trên bản ghi hiệu suất là trường liên kết
#: lấy từ khí tượng, nên khí tượng phải vào trước; tổn thất của một bậc
#: đọc sản lượng bậc trước nên bậc đo vào sau cùng của phần ngày.
DICH_MODEL = {
    'weather': 'eam.solar.weather',
    'kpi': 'eam.solar.kpi',
    'node': 'eam.chain.day',
    'tag': 'eam.tag',
}

DICH = [
    ('weather', 'Khí tượng ngày'),
    ('kpi', 'Hiệu suất ngày (PR/PA)'),
    ('node', 'Sản lượng bậc đo'),
    ('tag', 'Điểm đo (kho chuỗi thời gian)'),
]


class EamImportTemplate(models.Model):
    _name = 'eam.import.template'
    _description = 'Mẫu nạp dữ liệu'
    _inherit = ['mail.thread']
    _order = 'name'

    name = fields.Char(string='Tên mẫu', required=True, tracking=True)
    active = fields.Boolean(default=True, tracking=True)
    note = fields.Text(
        string='Diễn giải',
        help='Mẫu này đọc tệp của nhà máy nào, do ai gửi, lấy ở đâu. '
             'Sáu tháng sau không ai nhớ nữa.')

    kieu = fields.Selection(
        [('bieu', 'Tờ biểu — nhãn và số nằm ở ô cố định'),
         ('bang', 'Bảng — một dòng tiêu đề, mỗi cột một điểm đo')],
        string='Hình dạng tệp', required=True, default='bieu', tracking=True,
        help='Báo cáo vận hành ngày là TỜ BIỂU: không tra được theo cột vì '
             'cột chứa số đổi theo dòng. Tệp xuất từ SCADA là BẢNG.')

    plant_id = fields.Many2one(
        'eam.location', string='Nhà máy mặc định',
        domain="[('location_type', '=', 'plant')]",
        help='Để trống thì mỗi lượt nạp phải chọn nhà máy. Khai sẵn khi '
             'mẫu này chỉ dùng cho một nhà máy.')

    # ----- Tờ biểu -------------------------------------------------------
    o_ngay = fields.Char(
        string='Ô chứa ngày báo cáo',
        help='Ví dụ A7. Bắt buộc với tờ biểu — không có ngày thì không '
             'biết số rơi vào ngày nào.')
    sheet = fields.Char(
        string='Chỉ đọc sheet',
        help='Để trống thì đọc MỌI sheet trong tệp. Tờ báo cáo thật gửi '
             'theo tuần, mỗi ngày một sheet, nên để trống là đúng.')
    kiem_ten_sheet = fields.Boolean(
        string='Đối chiếu ngày với tên sheet', default=True,
        help='Người trực nhân bản sheet hôm qua rồi quên sửa ô ngày là '
             'chuyện xảy ra thật, và hậu quả là đè lên dữ liệu của ngày '
             'cũ. Tên sheet mang ngày thì đối chiếu được; lệch thì DỪNG, '
             'vì ghi sai ngày tệ hơn không ghi.')

    # ----- Bảng ----------------------------------------------------------
    cot_thoi_diem = fields.Char(
        string='Cột thời điểm',
        help='Tên tiêu đề của cột chứa thời điểm. Bắt buộc với tệp bảng.')
    tz = fields.Char(
        string='Múi giờ của nguồn', default='Asia/Ho_Chi_Minh',
        help='Thời điểm trong tệp hầu như không mang múi giờ, còn Odoo lưu '
             'theo UTC. Đọc giờ địa phương như UTC là dịch cả đường cong 7 '
             'tiếng — biểu đồ vẫn mượt, đỉnh bức xạ rơi vào 5 giờ sáng.')

    map_ids = fields.One2many(
        'eam.import.map', 'template_id', string='Dòng ánh xạ', copy=True,
        help='Một2nhiều của Odoo mặc định KHÔNG nhân bản. Để mặc định thì '
             'nhân bản một mẫu — cách tự nhiên nhất để làm mẫu cho nhà máy '
             'thứ hai — ra một mẫu rỗng, và nó rỗng trong im lặng: màn hình '
             'mở ra trông y như bình thường.')
    map_count = fields.Integer(string='Số dòng', compute='_compute_counts')
    run_count = fields.Integer(string='Số lượt nạp', compute='_compute_counts')

    company_id = fields.Many2one(
        'res.company', default=lambda s: s.env.company)

    def _compute_counts(self):
        gom = self.env['eam.import.run']._read_group(
            [('template_id', 'in', self.ids)], ['template_id'], ['__count'])
        dem = {t.id: n for t, n in gom}
        for rec in self:
            rec.map_count = len(rec.map_ids)
            rec.run_count = dem.get(rec.id, 0)

    @api.constrains('kieu', 'o_ngay', 'cot_thoi_diem')
    def _check_khai_du(self):
        for rec in self:
            if rec.kieu == 'bieu' and not (rec.o_ngay or '').strip():
                raise ValidationError(_(
                    'Mẫu tờ biểu "%s" chưa khai ô chứa ngày báo cáo. Không '
                    'có ngày thì mọi con số đọc được đều không biết xếp vào '
                    'đâu.', rec.name))
            if rec.kieu == 'bieu' and rec.o_ngay:
                try:
                    doc_nguon.tach_o(rec.o_ngay)
                except doc_nguon.LoiNguon as e:
                    raise ValidationError(str(e)) from e
            if rec.kieu == 'bang' and not (rec.cot_thoi_diem or '').strip():
                raise ValidationError(_(
                    'Mẫu bảng "%s" chưa khai cột thời điểm.', rec.name))

    def action_xem_luot_nap(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Lượt nạp — %s', self.name),
            'res_model': 'eam.import.run',
            'view_mode': 'list,form',
            'domain': [('template_id', '=', self.id)],
            'context': {'default_template_id': self.id},
        }


class EamImportMap(models.Model):
    _name = 'eam.import.map'
    _description = 'Dòng ánh xạ của mẫu nạp'
    _order = 'template_id, sequence, id'

    template_id = fields.Many2one(
        'eam.import.template', string='Mẫu', required=True,
        ondelete='cascade', index=True)
    kieu = fields.Selection(related='template_id.kieu')
    sequence = fields.Integer(default=10)

    name = fields.Char(
        string='Nhãn trong tệp', required=True,
        help='Chép nhãn như trong tệp nguồn, ví dụ "Energy Output '
             '(Inverter)". Không dùng để tra cứu — dùng để người đọc nhật '
             'ký đối chiếu được với tờ giấy trên tay.')

    # ----- Nguồn ---------------------------------------------------------
    o = fields.Char(
        string='Ô / vùng',
        help='Tờ biểu: địa chỉ ô, ví dụ B20. Với dải giờ thì khai vùng một '
             'dòng, ví dụ D40:P40 — và ô Vùng giá trị bên cạnh.')
    o2 = fields.Char(
        string='Vùng giá trị',
        help='Chỉ dùng khi ô Ô/vùng là một DẢI thời điểm. Ví dụ D41:P41. '
             'Hai dải phải cùng số ô, nếu không thì không biết giá trị nào '
             'thuộc giờ nào.')
    cot = fields.Char(
        string='Cột trong bảng',
        help='Tên tiêu đề cột trong tệp bảng.')

    # ----- Đích ----------------------------------------------------------
    dich = fields.Selection(
        DICH, string='Đích', required=True, default='weather')
    model_dich = fields.Char(
        string='Model đích', compute='_compute_model_dich', store=True)
    field_id = fields.Many2one(
        'ir.model.fields', string='Trường',
        domain="[('model', '=', model_dich), ('store', '=', True), "
               "('ttype', 'in', ['float','integer','char','text',"
               "'selection','boolean'])]",
        ondelete='cascade',
        help='Bắt buộc với đích Khí tượng và Hiệu suất.')
    node_code = fields.Char(
        string='Mã bậc đo',
        help='Mã bậc trong chuỗi điểm đo, ví dụ INV, MCB, EVN. Tra theo MÃ '
             'chứ không theo khoá nội bộ, nên cùng một mẫu chạy được cho '
             'mọi nhà máy đặt mã theo cùng quy ước.')
    nguon_so = fields.Selection(
        [('cong_to', 'Hiệu số đọc công-tơ'),
         ('scada', 'Tích phân từ SCADA'),
         ('tay', 'Nhập tay')],
        string='Nguồn con số', default='scada', required=True,
        help='Chỉ dùng cho đích Bậc đo. Cùng một tờ báo cáo có dòng lấy từ '
             'SCADA (sản lượng bộ biến tần) và dòng lấy từ công-tơ (điện '
             'nhận tại trạm EVN). Ghi chung một nhãn thì về sau không biết '
             'con số nào có hoá đơn làm chứng.')
    tag_code = fields.Char(
        string='Mã tag',
        help='Mã điểm đo trong kho chuỗi thời gian.')

    # ----- Biến đổi ------------------------------------------------------
    he_so = fields.Float(
        string='Hệ số', default=1.0, required=True, digits=(16, 6),
        help='Nhân trị gốc với số này. Tờ báo cáo ghi MWh mà bảng của ta '
             'lưu kWh thì hệ số là 1000. Thiếu nó thì 255 MWh thành 255 '
             'kWh — một phần nghìn, mà con số vẫn dương và trông hợp lý.')
    anh_xa_tri = fields.Text(
        string='Ánh xạ giá trị',
        help='Mỗi dòng một cặp "trị trong tệp = trị trong hệ", dùng cho '
             'trường lựa chọn. Ví dụ:\n'
             'Sunny = sunny\nSunny/Cloudy = partly\nCloudy = cloudy\n'
             'Trị không có trong bảng thì BỎ QUA kèm một dòng nhật ký, '
             'chứ không ghi bừa.')
    bat_buoc = fields.Boolean(
        string='Bắt buộc',
        help='Thiếu ô này thì cả sheet bị bỏ. Dùng cho ô mà không có nó '
             'thì phần còn lại vô nghĩa.')

    # ----- Chỉ đối chiếu -------------------------------------------------
    chi_doi_chieu = fields.Boolean(
        string='Chỉ đối chiếu',
        help='Đọc lên, so với con số hệ tự tính, ghi khoảng lệch vào nhật '
             'ký — KHÔNG ghi vào dữ liệu. Tờ báo cáo chứa cả kết quả nhà '
             'máy tự tính (PR, mẫu số, hệ số nhiệt), nên mỗi lượt nạp là '
             'một lần công thức của ta được kiểm bằng số của chính họ.')
    sai_so = fields.Float(
        string='Sai số cho phép (%)', default=0.5, digits=(6, 2),
        help='Lệch trong khoảng này thì nhật ký ghi "khớp". Để 0 thì mọi '
             'khác biệt dù nhỏ đều bị nêu.')

    @api.depends('dich')
    def _compute_model_dich(self):
        for rec in self:
            rec.model_dich = DICH_MODEL.get(rec.dich) or ''

    @api.onchange('dich')
    def _onchange_dich(self):
        """Đổi đích thì bỏ trường cũ — trường của model khác không dùng được."""
        for rec in self:
            if rec.field_id and rec.field_id.model != DICH_MODEL.get(rec.dich):
                rec.field_id = False

    @api.constrains('dich', 'field_id', 'node_code', 'tag_code')
    def _check_dich(self):
        for rec in self:
            if rec.dich in ('weather', 'kpi'):
                if not rec.field_id:
                    raise ValidationError(_(
                        'Dòng "%s" đích là %s nhưng chưa chọn trường.',
                        rec.name, dict(DICH)[rec.dich]))
                if rec.field_id.model != DICH_MODEL[rec.dich]:
                    raise ValidationError(_(
                        'Dòng "%(n)s": trường "%(f)s" thuộc model %(m)s, '
                        'không phải %(d)s.',
                        n=rec.name, f=rec.field_id.name,
                        m=rec.field_id.model, d=DICH_MODEL[rec.dich]))
            if rec.dich == 'node' and not (rec.node_code or '').strip():
                raise ValidationError(_(
                    'Dòng "%s" đích là bậc đo nhưng chưa khai mã bậc.',
                    rec.name))
            if rec.dich == 'tag' and not (rec.tag_code or '').strip():
                raise ValidationError(_(
                    'Dòng "%s" đích là điểm đo nhưng chưa khai mã tag.',
                    rec.name))
            if rec.dich == 'node' and rec.field_id and not rec.chi_doi_chieu:
                # Dòng ghi vào bậc đo luôn ghi vào ô sản lượng; để người
                # khai chọn một trường khác rồi vẫn ghi vào sản lượng là
                # cho họ tưởng đã khai được thứ mình không khai được.
                raise ValidationError(_(
                    'Dòng "%(n)s" ghi vào bậc đo thì luôn ghi vào ô sản '
                    'lượng, nên không chọn trường được. Chọn trường chỉ có '
                    'nghĩa khi bật "chỉ đối chiếu" — ví dụ đối chiếu tổn '
                    'thất %% mà nhà máy tự tính với tổn thất hệ tính ra.',
                    n=rec.name))

    @api.constrains('he_so')
    def _check_he_so(self):
        for rec in self:
            if not rec.he_so:
                raise ValidationError(_(
                    'Dòng "%s" có hệ số bằng 0 — mọi giá trị đọc được sẽ '
                    'thành 0 và không có gì báo lỗi. Để 1 nếu không cần '
                    'đổi đơn vị.', rec.name))

    @api.constrains('o', 'o2', 'cot', 'template_id', 'dich')
    def _check_dia_chi(self):
        for rec in self:
            try:
                rec._kiem_dia_chi()
            except doc_nguon.LoiNguon as e:
                raise ValidationError(_(
                    'Dòng "%(n)s": %(e)s', n=rec.name, e=str(e))) from e

    def _kiem_dia_chi(self):
        self.ensure_one()
        if self.template_id.kieu == 'bieu':
            if not (self.o or '').strip():
                raise ValidationError(_(
                    'Dòng "%s" chưa khai ô nguồn.', self.name))
            if ':' not in self.o:
                doc_nguon.tach_o(self.o)
                return
            oo = doc_nguon.tach_vung(self.o)
            if not (self.o2 or '').strip():
                raise ValidationError(_(
                    'Dòng "%s" khai dải thời điểm %s nhưng chưa có vùng '
                    'giá trị tương ứng.', self.name, self.o))
            gt = doc_nguon.tach_vung(self.o2)
            if len(oo) != len(gt):
                raise ValidationError(_(
                    'Dòng "%(n)s": dải thời điểm có %(a)d ô, dải giá trị '
                    'có %(b)d ô. Lệch số ô thì không biết giá trị nào '
                    'thuộc giờ nào.', n=self.name, a=len(oo), b=len(gt)))
            if self.dich != 'tag':
                raise ValidationError(_(
                    'Dòng "%s" khai một dải nhiều ô, nên đích phải là '
                    'điểm đo — một trường đơn không nhận được mười ba '
                    'giá trị.', self.name))
        elif self.template_id.kieu == 'bang':
            if not (self.cot or '').strip():
                raise ValidationError(_(
                    'Dòng "%s" chưa khai cột trong bảng.', self.name))

    # ------------------------------------------------------------------
    def _ban_do_tri(self):
        """Bảng ánh xạ giá trị đã phân tích thành dict, khoá viết thường."""
        self.ensure_one()
        bd = {}
        for dong in (self.anh_xa_tri or '').splitlines():
            if '=' not in dong:
                continue
            k, v = dong.split('=', 1)
            k, v = k.strip(), v.strip()
            if k:
                bd[k.lower()] = v
        return bd

    @api.depends('name', 'o', 'cot')
    def _compute_display_name(self):
        for rec in self:
            dc = rec.o or rec.cot or ''
            rec.display_name = '%s — %s' % (dc, rec.name or '') if dc \
                else (rec.name or '')
