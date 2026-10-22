# -*- coding: utf-8 -*-
"""Sổ nghĩa vụ hợp đồng (rp.obligation) — SỔ CÁI, không phải sổ thứ năm.

Vấn đề
------
EPCOne đã có bốn sổ nghĩa vụ chạy tốt, mỗi sổ neo vào một điều khoản:
hồ sơ phải trình (đ. 5.2), phát sinh (đ. 13), khiếu nại, bảo lãnh — cộng
lịch thanh toán trên chính hợp đồng. Thứ **không** có là một chỗ trả lời
được câu hỏi đơn giản nhất: *hợp đồng này buộc ai làm gì, hạn nào?*
Muốn biết thì phải mở năm màn, và phải biết trước là có năm cái đồng hồ
đó — tức là phải đã biết câu trả lời.

Cách KHÔNG làm
--------------
Chép hạn và trạng thái sang sổ mới. Chép là có hai sổ cho một việc, và
hai sổ thì sớm muộn lệch nhau — lúc đó không ai biết sổ nào đúng, mà cả
hai đều trông như đúng. Đây là cái bẫy đã tránh được ở mọi chỗ khác
trong hệ thống; không đáng đánh đổi lấy một màn hình đẹp.

Cách làm
--------
Mỗi dòng ở đây là **chỉ mục**, không phải bản sao:

* Loại đã có sổ chuyên → dòng nghĩa vụ **trỏ** tới bản ghi đó. ``han``
  và ``trang_thai`` là trường **tính**, đọc thẳng từ bản ghi gốc. Không
  có đường nào gõ tay đè lên được.
* Loại chưa có sổ (bảo hiểm, bảo hành, báo cáo định kỳ, giấy phép) →
  dòng nghĩa vụ **chính là** bản ghi, dùng ``han_tu_quan``.

Một bản ghi có thể sinh HAI nghĩa vụ
-------------------------------------
Một hồ sơ phải trình mang hai nghĩa vụ của **hai bên khác nhau**: nhà
thầu phải nộp trước ``date_required``, rồi bên xem xét phải trả lời
trong ``review_days``. Gộp thành một dòng là giấu mất một bên. Nên khoá
của sổ là **(bản ghi, vai)** chứ không phải chỉ bản ghi.

Đồng bộ lại nhiều lần phải ra cùng một kết quả
-----------------------------------------------
``khoa`` là chuỗi duy nhất dựng từ (bản ghi, vai), có ràng buộc UNIQUE ở
tầng CSDL. Chạy ``dong_bo`` mười lần cũng chỉ ra một dòng — bấm nhầm nút
không đẻ ra sổ rác.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

#: Ngưỡng "sắp đến hạn" (ngày). Ít hơn thì cảnh báo đến quá muộn để xoay,
#: nhiều hơn thì màn hình lúc nào cũng vàng và người ta thôi nhìn.
SAP_DEN_HAN = 14


def _ngay(v):
    """Ép Date/Datetime/False về Date. Trường ngày trong Odoo không nhất
    quán giữa các module, mà so Datetime với Date thì nổ TypeError lúc
    chạy chứ không lúc nạp — tức nổ trước mặt người dùng."""
    if not v:
        return False
    return v.date() if hasattr(v, 'hour') else v


class RpObligation(models.Model):
    _name = 'rp.obligation'
    _description = 'Nghĩa vụ hợp đồng'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'han asc, id desc'

    # ----- Định danh ------------------------------------------------------
    name = fields.Char(string='Nghĩa vụ', required=True, tracking=True)
    code = fields.Char(string='Mã', copy=False, readonly=True, index=True)

    contract_id = fields.Many2one(
        'rp.contract', string='Hợp đồng', required=True,
        ondelete='cascade', index=True, tracking=True)
    project_id = fields.Many2one(
        related='contract_id.project_id', string='Dự án', store=True)
    contractor_id = fields.Many2one(
        related='contract_id.contractor_id', string='Nhà thầu', store=True)
    company_id = fields.Many2one(
        related='contract_id.company_id', store=True)

    clause_id = fields.Many2one(
        'rp.contract.clause', string='Theo điều', tracking=True,
        domain="[('contract_id', '=', contract_id), ('is_current', '=', True)]",
        help='Neo vào điều khoản để thư gửi nhà thầu trích được đúng điều, '
             'đúng trang, đúng bản ký.')
    clause_number = fields.Char(
        related='clause_id.number', string='Số điều', store=True)

    # ----- Phân loại ------------------------------------------------------
    ben = fields.Selection(
        [('nha_thau', 'Nhà thầu'),
         ('chu_dau_tu', 'Chủ đầu tư / Chúng ta'),
         ('hai_ben', 'Cả hai bên')],
        string='Bên gánh nghĩa vụ', required=True, default='nha_thau',
        tracking=True, index=True)

    loai = fields.Selection(
        [('moc_tien_do', 'Mốc tiến độ hợp đồng'),
         ('ranh_gioi', 'Bàn giao ranh giới gói thầu'),
         ('rfi', 'Trả lời RFI'),
         ('ho_so', 'Hồ sơ phải trình'),
         ('xem_xet', 'Xem xét / phê duyệt hồ sơ'),
         ('phat_sinh', 'Phát sinh — báo giá'),
         ('khieu_nai', 'Khiếu nại — thông báo'),
         ('bao_lanh', 'Bảo lãnh — duy trì hiệu lực'),
         ('thanh_toan', 'Thanh toán theo mốc'),
         ('bao_hiem', 'Bảo hiểm'),
         ('bao_hanh', 'Bảo hành'),
         ('bao_cao', 'Báo cáo định kỳ'),
         ('giay_phep', 'Giấy phép / chấp thuận'),
         ('hieu_suat', 'Cam kết hiệu suất'),
         ('khac', 'Khác')],
        string='Loại nghĩa vụ', required=True, default='khac',
        tracking=True, index=True)

    vai = fields.Selection(
        [('dat_moc', 'Đạt mốc tiến độ'),
         ('ban_giao', 'Bàn giao ranh giới'),
         ('tra_loi_rfi', 'Trả lời RFI'),
         ('trinh', 'Nộp hồ sơ'),
         ('xem_xet', 'Trả lời hồ sơ'),
         ('bao_gia', 'Nộp báo giá'),
         ('thong_bao', 'Gửi thông báo'),
         ('duy_tri', 'Duy trì hiệu lực'),
         ('thanh_toan', 'Trả tiền'),
         ('tu_quan', 'Tự quản — sổ này là bản ghi')],
        string='Vai', required=True, default='tu_quan',
        help='Một bản ghi gốc có thể sinh hai nghĩa vụ của hai bên khác '
             'nhau; "vai" là thứ tách chúng ra.')

    # ----- Trỏ tới sổ chuyên ----------------------------------------------
    document_id = fields.Many2one(
        'rp.document', string='Hồ sơ kỹ thuật', ondelete='cascade',
        index=True)
    variation_id = fields.Many2one(
        'rp.variation', string='Phát sinh', ondelete='cascade', index=True)
    claim_id = fields.Many2one(
        'rp.claim', string='Khiếu nại', ondelete='cascade', index=True)
    guarantee_id = fields.Many2one(
        'rp.contract.guarantee', string='Bảo lãnh', ondelete='cascade',
        index=True)
    milestone_id = fields.Many2one(
        'rp.contract.payment.milestone', string='Mốc thanh toán',
        ondelete='cascade', index=True)
    # Ba sổ dưới đây là phần RIÊNG của hợp đồng EPC — O&M không có khái
    # niệm tương đương. Thiếu chúng thì sổ nghĩa vụ chỉ còn phần hành
    # chính thường kỳ, và đọc ra giống hợp đồng vận hành.
    task_id = fields.Many2one(
        'project.task', string='Mốc tiến độ', ondelete='cascade',
        index=True)
    interface_id = fields.Many2one(
        'rp.interface', string='Ranh giới gói thầu', ondelete='cascade',
        index=True)
    rfi_id = fields.Many2one(
        'rp.rfi', string='RFI', ondelete='cascade', index=True)

    nguon = fields.Selection(
        [('so_rieng', 'Có sổ chuyên — dòng này là chỉ mục'),
         ('tai_cho', 'Sổ này là bản ghi')],
        string='Nguồn', compute='_compute_nguon', store=True)

    khoa = fields.Char(
        string='Khoá đồng bộ', compute='_compute_khoa', store=True,
        index=True, copy=False)

    # ----- Hạn và trạng thái ---------------------------------------------
    han_tu_quan = fields.Date(
        string='Hạn (tự quản)',
        help='Chỉ dùng cho nghĩa vụ không có sổ chuyên. Dòng chỉ mục thì '
             'ô này để trống — hạn đọc thẳng từ bản ghi gốc.')
    ngay_xong_tu_quan = fields.Date(string='Ngày hoàn thành (tự quản)')

    han = fields.Date(
        string='Hạn', compute='_compute_tinh_trang', store=True, index=True,
        help='Dòng chỉ mục: đọc từ bản ghi gốc, không gõ tay được. Sửa hạn '
             'thì sửa ở sổ gốc — một việc một chỗ.')
    ngay_xong = fields.Date(
        string='Ngày hoàn thành', compute='_compute_tinh_trang', store=True)
    trang_thai = fields.Selection(
        [('xong', 'Đã xong'),
         ('qua_han', 'Quá hạn'),
         ('sap_den', 'Sắp đến hạn'),
         ('con_han', 'Còn hạn'),
         ('khong_han', 'Không đặt hạn')],
        string='Tình trạng', compute='_compute_tinh_trang', store=True,
        index=True)
    so_ngay_con = fields.Integer(
        string='Còn (ngày)', compute='_compute_tinh_trang', store=True,
        aggregator=False,
        help='Âm là đã quá hạn bấy nhiêu ngày.\n\n'
             'Không cộng dồn theo nhóm: tổng "số ngày còn lại" của 36 '
             'nghĩa vụ là một con số không mang nghĩa gì, mà lại nằm đúng '
             'chỗ mắt người đọc tìm số tổng.')

    nguoi_phu_trach_id = fields.Many2one(
        'res.users', string='Người theo dõi', tracking=True)
    ghi_chu = fields.Text(string='Ghi chú')
    active = fields.Boolean(default=True)

    _uniq_khoa = models.Constraint(
        'UNIQUE(khoa)',
        'Mỗi bản ghi gốc chỉ sinh một dòng nghĩa vụ cho mỗi vai.')

    # ======================================================================
    # Compute
    # ======================================================================
    @api.depends('document_id', 'variation_id', 'claim_id', 'guarantee_id',
                 'milestone_id', 'task_id', 'interface_id', 'rfi_id')
    def _compute_nguon(self):
        for rec in self:
            rec.nguon = 'so_rieng' if rec._ban_ghi_goc() else 'tai_cho'

    @api.depends('document_id', 'variation_id', 'claim_id', 'guarantee_id',
                 'milestone_id', 'task_id', 'interface_id', 'rfi_id', 'vai')
    def _compute_khoa(self):
        for rec in self:
            goc = rec._ban_ghi_goc()
            if goc:
                rec.khoa = '%s-%s-%s' % (goc._name, goc.id, rec.vai or '')
            else:
                # Dòng tự quản không tham gia đồng bộ nên không cần khoá;
                # để trống thay vì bịa một khoá, vì UNIQUE trong PostgreSQL
                # bỏ qua NULL — nhiều dòng tự quản cùng tồn tại được.
                rec.khoa = False

    @api.depends(
        'han_tu_quan', 'ngay_xong_tu_quan', 'vai',
        'document_id.date_required', 'document_id.date_submitted',
        'document_id.review_deadline', 'document_id.date_reviewed',
        'variation_id.quote_due_date', 'variation_id.date_quote',
        'claim_id.notice_deadline', 'claim_id.date_notice',
        'guarantee_id.date_expiry', 'guarantee_id.state',
        'guarantee_id.date_released',
        'milestone_id.due_date', 'milestone_id.paid_date',
        'milestone_id.state',
        'task_id.planned_end', 'task_id.date_end', 'task_id.state',
        'interface_id.date_required', 'interface_id.schedule_need_date',
        'interface_id.date_actual',
        'rfi_id.deadline', 'rfi_id.answered_date')
    def _compute_tinh_trang(self):
        hom_nay = fields.Date.context_today(self)
        for rec in self:
            han, xong = rec._doc_han_va_ngay_xong()
            rec.han = han
            rec.ngay_xong = xong
            if xong:
                rec.trang_thai = 'xong'
                rec.so_ngay_con = 0
            elif not han:
                rec.trang_thai = 'khong_han'
                rec.so_ngay_con = 0
            else:
                con = (han - hom_nay).days
                rec.so_ngay_con = con
                if con < 0:
                    rec.trang_thai = 'qua_han'
                elif con <= SAP_DEN_HAN:
                    rec.trang_thai = 'sap_den'
                else:
                    rec.trang_thai = 'con_han'

    # ======================================================================
    # Đọc từ bản ghi gốc
    # ======================================================================
    def _ban_ghi_goc(self):
        """Bản ghi ở sổ chuyên mà dòng này trỏ tới, hoặc ``False``."""
        self.ensure_one()
        return (self.document_id or self.variation_id or self.claim_id
                or self.guarantee_id or self.milestone_id or self.task_id
                or self.interface_id or self.rfi_id or False)

    def _doc_han_va_ngay_xong(self):
        """(hạn, ngày hoàn thành) đọc từ bản ghi gốc — KHÔNG chép, KHÔNG lưu.

        Sửa hạn ở sổ gốc là dòng chỉ mục đổi theo ngay. Đó là cả lý do
        tồn tại của cách làm này.
        """
        self.ensure_one()
        if self.document_id:
            d = self.document_id
            if self.vai == 'xem_xet':
                return d.review_deadline, d.date_reviewed
            return d.date_required, d.date_submitted
        if self.variation_id:
            v = self.variation_id
            return v.quote_due_date, v.date_quote
        if self.claim_id:
            c = self.claim_id
            return c.notice_deadline, c.date_notice
        if self.guarantee_id:
            g = self.guarantee_id
            # Bảo lãnh "xong" khi đã hoàn trả hoặc hết vai trò; còn hiệu
            # lực thì ngày hết hạn chính là hạn phải gia hạn.
            if g.state in ('released', 'claimed', 'cancelled'):
                return g.date_expiry, (g.date_released or g.date_expiry)
            return g.date_expiry, False
        if self.milestone_id:
            m = self.milestone_id
            xong = m.paid_date or (m.due_date if m.state == 'paid' else False)
            return m.due_date, xong
        if self.task_id:
            t = self.task_id
            # planned_end/date_end có thể là Date hoặc Datetime tuỳ module
            # nào khai; ép về Date để so sánh với hôm nay không vỡ.
            return _ngay(t.planned_end), (_ngay(t.date_end)
                                          if t.state == '1_done' else False)
        if self.interface_id:
            i = self.interface_id
            # Hai nguồn ngày, và thứ tự ưu tiên có lý do: date_required là
            # ngày bên nhận NHẬP TAY, schedule_need_date là ngày LỊCH suy
            # ra. Nhập tay thắng vì nó là thoả thuận giữa hai bên; thiếu
            # nó thì lịch vẫn trả lời được. Chỉ đọc date_required thì 9/9
            # ranh giới trên bản demo đều "không đặt hạn" — đúng mã, vô
            # dụng với người dùng.
            return (i.date_required or i.schedule_need_date), i.date_actual
        if self.rfi_id:
            r = self.rfi_id
            return r.deadline, r.answered_date
        return self.han_tu_quan, self.ngay_xong_tu_quan

    # ======================================================================
    # Chặn gõ tay đè lên dòng chỉ mục
    # ======================================================================
    @api.constrains('han_tu_quan', 'ngay_xong_tu_quan', 'nguon')
    def _check_tu_quan(self):
        for rec in self:
            if rec.nguon == 'so_rieng' and (rec.han_tu_quan
                                            or rec.ngay_xong_tu_quan):
                raise UserError(_(
                    'Nghĩa vụ "%(ten)s" là chỉ mục của %(so)s, nên hạn phải '
                    'sửa ở sổ gốc chứ không gõ vào đây. Gõ hai nơi thì sớm '
                    'muộn hai nơi lệch nhau, mà cả hai đều trông như đúng.',
                    ten=rec.name,
                    so=rec._ban_ghi_goc()._description))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code'):
                vals['code'] = self.env['ir.sequence'].next_by_code(
                    'rp.obligation') or '/'
        return super().create(vals_list)

    def action_mo_ban_ghi_goc(self):
        self.ensure_one()
        goc = self._ban_ghi_goc()
        if not goc:
            raise UserError(_('Nghĩa vụ này không trỏ tới sổ nào — nó tự '
                              'quản, sửa thẳng ở đây.'))
        return {
            'type': 'ir.actions.act_window',
            'res_model': goc._name,
            'res_id': goc.id,
            'view_mode': 'form',
            'target': 'current',
        }
