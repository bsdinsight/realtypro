# -*- coding: utf-8 -*-
"""Chuỗi điểm đo của một nhà máy và hạch toán tổn thất theo bậc.

Vấn đề
------
Điện đi từ thiết bị phát tới công-tơ bán điện qua nhiều bậc, và mỗi bậc
ăn mất một ít. Tờ báo cáo vận hành ngày của cả điện gió lẫn điện mặt
trời đều có đúng khối này, chỉ khác tên bậc::

    mặt trời:  inverter → thanh cái → ranh giới → công-tơ bán điện
    điện gió:  tua-bin  → trạm 331  → máy biến áp nâng áp → điểm đấu nối

Cách KHÔNG làm
--------------
Viết cứng năm dòng cộng trừ cho nhà máy đầu tiên. Nhà máy thứ hai có
bốn bậc tên khác, thế là viết lại. Tới nhà máy thứ ba thì có ba đoạn mã
gần giống nhau và không ai dám sửa cái nào.

Cách làm
--------
Chuỗi là **dữ liệu**: khai bậc, khai thứ tự, khai mỗi bậc lấy số từ đâu.
Tổn thất là hiệu giữa hai bậc liền kề — một phép tính duy nhất chạy cho
mọi nhà máy, mọi công nghệ.

Ba loại bậc, và vì sao phải tách
---------------------------------
Không phải chênh lệch nào cũng là tổn thất. Điện tự dùng của nhà máy và
điện tiêu thụ ban đêm là **tiêu thụ có chủ đích**, không phải thất
thoát. Gộp chúng vào tổn thất kỹ thuật thì con số tổn thất phồng lên mà
không ai truy được tại sao — và đó đúng là con số đi vào đánh giá nhà
thầu O&M.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class EamChain(models.Model):
    _name = 'eam.chain'
    _description = 'Chuỗi điểm đo của nhà máy'
    _inherit = ['mail.thread']
    _order = 'plant_id, name'

    name = fields.Char(string='Tên chuỗi', required=True, tracking=True)
    plant_id = fields.Many2one(
        'eam.location', string='Nhà máy', required=True, index=True,
        domain="[('location_type', '=', 'plant')]", ondelete='cascade',
        tracking=True)
    company_id = fields.Many2one(related='plant_id.company_id', store=True)
    node_ids = fields.One2many('eam.chain.node', 'chain_id', string='Các bậc')
    node_count = fields.Integer(string='Số bậc', compute='_compute_counts')
    day_count = fields.Integer(string='Số ngày', compute='_compute_counts')
    active = fields.Boolean(default=True)
    note = fields.Text(string='Ghi chú')

    _uniq_plant = models.Constraint(
        'UNIQUE(plant_id, name)',
        'Một nhà máy không có hai chuỗi trùng tên.')

    @api.depends('node_ids', 'node_ids.day_ids')
    def _compute_counts(self):
        for rec in self:
            rec.node_count = len(rec.node_ids)
            rec.day_count = len(set(rec.node_ids.mapped('day_ids.date')))


    def action_sinh_ngay(self):
        """Dựng dòng sản lượng ngày cho mọi bậc, từ số đọc công-tơ."""
        tao = 0
        for rec in self:
            for node in rec.node_ids:
                tao += node._sinh_ngay_tu_cong_to()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success' if tao else 'info',
                'title': _('Đã dựng %s dòng ngày', tao),
                'message': _('Chỉ dựng cho bậc có gắn công-tơ. Bậc lấy số '
                             'từ SCADA hoặc nhập tay thì điền riêng.'),
                'sticky': False,
            },
        }


class EamChainNode(models.Model):
    _name = 'eam.chain.node'
    _description = 'Bậc trong chuỗi điểm đo'
    _order = 'chain_id, sequence, id'

    chain_id = fields.Many2one(
        'eam.chain', string='Chuỗi', required=True, ondelete='cascade',
        index=True)
    plant_id = fields.Many2one(
        related='chain_id.plant_id', store=True, index=True)
    company_id = fields.Many2one(related='chain_id.company_id', store=True)
    sequence = fields.Integer(
        string='Thứ tự', default=10,
        help='Thứ tự theo đường đi của điện, từ thiết bị phát ra lưới. '
             'Tổn thất tính giữa bậc này và bậc ĐỨNG NGAY TRƯỚC nó.')
    name = fields.Char(string='Tên bậc', required=True)
    code = fields.Char(string='Mã bậc')

    node_type = fields.Selection(
        [('san_luong', 'Bậc sản lượng'),
         ('tu_dung', 'Điện tự dùng'),
         ('ban_dem', 'Tiêu thụ ban đêm'),
         ('do_rieng', 'Điểm đo riêng — ngoài chuỗi tổn thất')],
        string='Loại bậc', required=True, default='san_luong',
        help='Chỉ bậc SẢN LƯỢNG mới tham gia tính tổn thất theo bậc.\n\n'
             'Tự dùng và ban đêm là tiêu thụ có chủ đích — gộp vào tổn '
             'thất thì con số phồng lên mà không ai truy được tại sao.\n\n'
             'Điểm đo riêng là chỗ đo cho mục đích khác, không nằm trên '
             'đường điện đi — ví dụ điện năng dùng làm tử số tỷ số hiệu '
             'suất, vốn đo trong khoảng giờ riêng. Để nó trong chuỗi thì '
             'nó ăn vào phép trừ và sinh ra một con số tổn thất vô nghĩa.')
    is_billing = fields.Boolean(
        string='Công-tơ bán điện',
        help='Bậc ra doanh thu. Mỗi chuỗi chỉ một bậc được đánh dấu.')
    is_pr_source = fields.Boolean(
        string='Tử số tỷ số hiệu suất',
        help='Bậc dùng làm điện năng AC khi tính tỷ số hiệu suất.\n\n'
             'KHÁC bậc bán điện, và phải khai riêng. Đối chiếu báo cáo '
             'thật của một nhà máy đang vận hành: tử số PR của họ thấp '
             'hơn sản lượng tại công-tơ bán điện 3% — vì PR đo trong '
             'khoảng giờ vận hành riêng, ngắn hơn cả ngày. Gán cứng hai '
             'thứ làm một là sai 3% mà nhìn vẫn hợp lý.')

    # ----- Nguồn số liệu -------------------------------------------------
    meter_id = fields.Many2one(
        'eam.meter', string='Công-tơ',
        help='Lấy sản lượng ngày bằng hiệu hai số đọc liên tiếp. Đã xử lý '
             'sẵn trường hợp thay đồng hồ hoặc đồng hồ quay vòng.')
    tag_id = fields.Many2one(
        'eam.tag', string='Điểm đo SCADA',
        help='Khai thêm để ĐỐI CHIẾU với công-tơ. Khai một mình khi chưa '
             'có công-tơ ở bậc này.')
    doi_chieu_nguong = fields.Float(
        string='Ngưỡng báo lệch (%)', digits=(5, 2), default=2.0,
        help='Công-tơ và SCADA lệch quá mức này thì dòng ngày bị gắn cờ.')

    day_ids = fields.One2many('eam.chain.day', 'node_id', string='Theo ngày')
    note = fields.Char(string='Ghi chú')

    _uniq_seq = models.Constraint(
        'UNIQUE(chain_id, sequence)',
        'Hai bậc trong cùng một chuỗi không được trùng thứ tự — thứ tự là '
        'thứ quyết định tổn thất tính giữa bậc nào với bậc nào.')

    nhap_tay = fields.Boolean(
        string='Nhập tay', compute='_compute_nhap_tay', store=True,
        help='Bậc không gắn công-tơ lẫn điểm đo thì mỗi ngày phải có '
             'người điền. Chấp nhận được — điện tự dùng thường không có '
             'công-tơ riêng — nhưng nên thấy rõ bậc nào đang như vậy.')

    @api.constrains('is_billing', 'is_pr_source', 'chain_id')
    def _check_mot_bac(self):
        """Mỗi chuỗi chỉ một bậc bán điện và một bậc tử số PR.

        Đặt ràng buộc ở BẬC chứ không ở chuỗi: ``@api.constrains`` trên
        một2nhiều CHỈ chạy khi ghi vào trường đó từ bản ghi cha. Sửa
        thẳng một bậc — đúng cách người dùng hay làm nhất — thì nó không
        chạy, và ràng buộc trở thành thứ trang trí. Đã dính đúng lần đầu.
        """
        for rec in self:
            for truong, nhan in (('is_billing', 'công-tơ bán điện'),
                                 ('is_pr_source', 'tử số tỷ số hiệu suất')):
                if not rec[truong]:
                    continue
                khac = self.search_count([
                    ('chain_id', '=', rec.chain_id.id),
                    ('id', '!=', rec.id), (truong, '=', True)])
                if khac:
                    raise ValidationError(_(
                        'Chuỗi "%(c)s" đã có bậc khác đánh dấu là %(t)s. '
                        'Chỉ được MỘT — hai mốc thì không biết lấy cái nào.',
                        c=rec.chain_id.name, t=nhan))

    @api.depends('meter_id', 'tag_id')
    def _compute_nhap_tay(self):
        for rec in self:
            rec.nhap_tay = not rec.meter_id and not rec.tag_id

    def _tinh_lai_ngay(self):
        """Buộc tính lại tổn thất cho mọi dòng ngày của cả chuỗi.

        ``loss_kwh`` là trường tính CÓ LƯU, phụ thuộc vào bậc đứng trước
        — mà quan hệ đó Odoo không theo dõi được. Thêm, xoá hay đổi thứ
        tự một bậc là mọi dòng phía sau thành số cũ, và số cũ trông y hệt
        số mới. Nên phải gọi tay.
        """
        D = self.env['eam.chain.day']
        rows = D.search([('chain_id', 'in', self.mapped('chain_id').ids)])
        if rows:
            rows._compute_ton_that()
            rows.flush_recordset()

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs._tinh_lai_ngay()
        return recs

    def write(self, vals):
        res = super().write(vals)
        if {'sequence', 'node_type', 'chain_id'} & set(vals):
            self._tinh_lai_ngay()
        return res

    def unlink(self):
        chuoi = self.mapped('chain_id')
        res = super().unlink()
        chuoi.node_ids._tinh_lai_ngay()
        return res

    def _bac_truoc(self):
        """Bậc sản lượng đứng ngay trước bậc này trong cùng chuỗi."""
        self.ensure_one()
        if self.node_type != 'san_luong':
            return self.browse()
        return self.search([
            ('chain_id', '=', self.chain_id.id),
            ('node_type', '=', 'san_luong'),
            ('sequence', '<', self.sequence)], order='sequence desc', limit=1)

    def _sinh_ngay_tu_cong_to(self):
        """Dựng dòng ngày từ hiệu hai số đọc công-tơ liên tiếp."""
        self.ensure_one()
        if not self.meter_id:
            return 0
        D = self.env['eam.chain.day']
        ds = self.meter_id.reading_ids.sorted(lambda r: (r.date, r.id))
        tao = 0
        truoc = None
        for r in ds:
            if truoc is not None and r.date != truoc.date:
                sl = (r.effective_value or 0) - (truoc.effective_value or 0)
                if not D.search_count([('node_id', '=', self.id),
                                       ('date', '=', r.date)]):
                    D.create({'node_id': self.id, 'date': r.date,
                              'energy': sl, 'nguon': 'cong_to'})
                    tao += 1
            truoc = r
        return tao
