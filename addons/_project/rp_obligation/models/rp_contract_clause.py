# -*- coding: utf-8 -*-
"""Điều khoản hợp đồng (rp.contract.clause).

Vì sao cần một bảng riêng cho điều khoản
-----------------------------------------
Trước module này, số điều khoản nằm trong ``help=`` của trường Python —
``'Điều 13.3: nhà thầu phải trả lời trong 14 ngày.'``. Đó là chữ viết cho
lập trình viên đọc, không phải dữ liệu: báo cáo không trỏ tới được, máy
không trích được, và hợp đồng nào đánh số điều khác thì **không sửa được
mà cũng không ai biết là đang sai**.

Đưa điều khoản thành bản ghi thì ba thứ mở ra cùng lúc: mọi nghĩa vụ neo
được vào đúng điều + đúng trang; mọi đồng hồ hạn đọc số ngày từ chính
hợp đồng thay vì hằng số mặc định; và lớp đọc hợp đồng bằng máy có chỗ
để ghi kết quả xuống.

Điều khoản thuộc BẢN KÝ, không sửa đè
--------------------------------------
Phụ lục sửa điều 13.3 thì **sinh bản ghi mới** trỏ về bản cũ qua
``replaces_id``, chứ không sửa tại chỗ. Sửa đè là sáu tháng sau không ai
trả lời nổi *"lúc ký thì hạn là bao nhiêu ngày"* — mà đó đúng là câu
trọng tài sẽ hỏi. Cùng bài học đã trả giá ở đợt thanh toán bên Realty
CRM: điều khoản là thứ có phiên bản, không phải thứ cập nhật.

``is_current`` suy ra từ việc *không có ai thay thế mình*, chứ không lấy
theo ngày mới nhất — hai phụ lục cùng ngày là chuyện có thật, và lúc đó
"mới nhất" không còn là một.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class RpContractClause(models.Model):
    _name = 'rp.contract.clause'
    _description = 'Điều khoản hợp đồng'
    _inherit = ['mail.thread']
    _order = 'contract_id, sequence, number, id'
    _rec_name = 'display_name'

    contract_id = fields.Many2one(
        'rp.contract', string='Hợp đồng', required=True,
        ondelete='cascade', index=True, tracking=True)
    project_id = fields.Many2one(
        related='contract_id.project_id', string='Dự án', store=True)

    sequence = fields.Integer(default=10)
    number = fields.Char(
        string='Số điều', required=True, tracking=True,
        help='Ghi đúng như trong hợp đồng: "13.3", "5.2", "Phụ lục A.4". '
             'Không tự chuẩn hoá — đối chiếu với bản giấy phải khớp từng '
             'ký tự.')
    name = fields.Char(string='Tiêu đề điều', tracking=True)

    page = fields.Integer(
        string='Trang', tracking=True,
        help='Trang trong file hợp đồng. Thiếu trang thì người đọc vẫn '
             'phải lật cả quyển, nên neo điều khoản mất gần hết tác dụng.')
    text = fields.Text(
        string='Trích đoạn nguyên văn',
        help='Chép nguyên văn, không diễn giải. Đây là thứ sẽ đi vào thư '
             'gửi nhà thầu — diễn giải sai một chữ là mất lý.')

    notice_days = fields.Integer(
        string='Số ngày điều này quy định',
        help='Để trống nếu điều khoản không đặt ra thời hạn nào. Có số ở '
             'đây thì các sổ nghĩa vụ đọc theo, thay vì dùng mặc định '
             'của phần mềm.')

    # ----- Phiên bản ------------------------------------------------------
    amendment_id = fields.Many2one(
        'rp.contract.amendment', string='Theo phụ lục', tracking=True,
        help='Để trống nghĩa là điều khoản của bản hợp đồng gốc.')
    date_effective = fields.Date(
        string='Hiệu lực từ', compute='_compute_date_effective', store=True,
        help='Lấy từ phụ lục nếu có, nếu không thì ngày ký hợp đồng.')
    replaces_id = fields.Many2one(
        'rp.contract.clause', string='Thay thế cho', tracking=True,
        help='Điều khoản bản cũ mà bản này thay thế.')
    replaced_by_ids = fields.One2many(
        'rp.contract.clause', 'replaces_id', string='Bị thay thế bởi')
    is_current = fields.Boolean(
        string='Bản hiện hành', compute='_compute_is_current', store=True,
        help='Không có bản nào thay thế mình thì là bản đang có hiệu lực.')

    obligation_ids = fields.One2many(
        'rp.obligation', 'clause_id', string='Nghĩa vụ phát sinh')
    obligation_count = fields.Integer(
        string='Số nghĩa vụ', compute='_compute_obligation_count')

    # ----- Nguồn trích ----------------------------------------------------
    source = fields.Selection(
        [('nguoi', 'Người nhập'),
         ('mau', 'Mẫu FIDIC — chưa đối chiếu hợp đồng'),
         ('may', 'Máy trích — chờ xác nhận'),
         ('xac_nhan', 'Máy trích — đã xác nhận')],
        string='Nguồn', default='nguoi', required=True, tracking=True,
        help='Điều khoản do máy đọc ra phải có người xác nhận trước khi '
             'đem ra dùng. Một điều khoản trích sai mà trông như đã kiểm '
             'thì nguy hơn là không có.')
    confidence = fields.Float(
        string='Độ tin cậy', digits=(3, 2),
        help='Chỉ có nghĩa với bản ghi do máy trích.')

    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        related='contract_id.company_id', store=True)

    _uniq_number = models.Constraint(
        'UNIQUE(contract_id, number, amendment_id)',
        'Mỗi hợp đồng chỉ có một điều khoản mang số đó trong cùng một bản '
        'ký. Điều khoản bị phụ lục sửa thì khai phụ lục ở ô "Theo phụ lục".')

    # ======================================================================
    # Compute
    # ======================================================================
    @api.depends('number', 'name')
    def _compute_display_name(self):
        for rec in self:
            phan = [_('Điều %s', rec.number) if rec.number else '']
            if rec.name:
                phan.append(rec.name)
            rec.display_name = ' — '.join(p for p in phan if p)

    @api.depends('amendment_id.date_effective', 'contract_id.contract_date')
    def _compute_date_effective(self):
        for rec in self:
            rec.date_effective = (rec.amendment_id.date_effective
                                  or rec.contract_id.contract_date)

    @api.depends('replaced_by_ids')
    def _compute_is_current(self):
        for rec in self:
            rec.is_current = not rec.replaced_by_ids

    def _compute_obligation_count(self):
        gom = self.env['rp.obligation']._read_group(
            [('clause_id', 'in', self.ids)], ['clause_id'], ['__count'])
        dem = {c.id: n for c, n in gom}
        for rec in self:
            rec.obligation_count = dem.get(rec.id, 0)

    # ======================================================================
    # Ràng buộc
    # ======================================================================
    @api.constrains('replaces_id')
    def _check_replaces(self):
        for rec in self:
            if not rec.replaces_id:
                continue
            if rec.replaces_id == rec:
                raise ValidationError(
                    _('Điều khoản không thể thay thế chính nó.'))
            if rec.replaces_id.contract_id != rec.contract_id:
                raise ValidationError(_(
                    'Chỉ thay thế được điều khoản của cùng một hợp đồng. '
                    '"%(a)s" thuộc hợp đồng %(b)s.',
                    a=rec.replaces_id.display_name,
                    b=rec.replaces_id.contract_id.name))

    # ======================================================================
    # Tra cứu
    # ======================================================================
    @api.model
    def han_theo_dieu(self, contract, number, mac_dinh):
        """Số ngày mà hợp đồng này quy định cho một điều — hoặc mặc định.

        Dùng ở các sổ nghĩa vụ thay cho hằng số viết cứng. Trả về mặc
        định khi chưa khai điều khoản, để bật module lên không làm đổi
        hành vi của dữ liệu đang chạy.
        """
        if not contract:
            return mac_dinh
        dieu = self.search([
            ('contract_id', '=', contract.id),
            ('number', '=', number),
            ('is_current', '=', True),
            ('notice_days', '>', 0)], limit=1)
        return dieu.notice_days or mac_dinh
