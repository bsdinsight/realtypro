# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class EamInstallation(models.Model):
    """Một quãng thời gian một TÀI SẢN nằm ở một VỊ TRÍ.

    Bảng này là chỗ duy nhất nối vật với chỗ, và nó nối theo THỜI GIAN
    chứ không phải theo trạng thái hiện tại. Nhờ vậy hỏi được cả hai
    chiều: vị trí này đã qua những con nào, và con này đã qua những vị
    trí nào.

    Ràng buộc chịu lực: **không chồng thời gian**, trên cả hai trục.

    * Một tài sản không thể cùng lúc nằm ở hai nơi — vô lý về vật lý.
    * Một vị trí đơn không thể cùng lúc chứa hai tài sản.

    Thiếu ràng buộc này thì lịch sử hỏng **mà không ai phát hiện**: mọi
    màn hình vẫn hiện số, chỉ là số sai. Vài năm sau mới lộ ra lúc cần
    tra cứu để đòi bảo hành, và khi đó đã muộn.

    Quãng đang mở (``date_remove`` để trống) nghĩa là ĐANG LẮP. Phải hỗ
    trợ quãng mở chứ không ép điền ngày tháo — ép thì người dùng sẽ bịa
    một ngày.
    """
    _name = 'eam.installation'
    _description = 'Lần lắp đặt'
    _inherit = ['mail.thread']
    _order = 'date_install desc, id desc'

    asset_id = fields.Many2one(
        'eam.asset', string='Tài sản', required=True, ondelete='cascade',
        index=True, tracking=True)
    location_id = fields.Many2one(
        'eam.location', string='Vị trí', required=True, ondelete='restrict',
        index=True, tracking=True)
    date_install = fields.Date(
        string='Ngày lắp', required=True, tracking=True,
        default=lambda self: fields.Date.context_today(self))
    date_remove = fields.Date(
        string='Ngày tháo', tracking=True,
        help='Để trống nghĩa là đang lắp. Không bịa ngày tháo cho thiết '
             'bị còn trên máy.')
    is_current = fields.Boolean(
        string='Đang lắp', compute='_compute_is_current', store=True,
        index=True)
    duration_days = fields.Integer(
        string='Số ngày tại vị trí', compute='_compute_is_current',
        store=True)

    reason_install = fields.Selection(
        [('new', 'Lắp mới'),
         ('replacement', 'Thay thế'),
         ('reinstall', 'Lắp lại sau đại tu'),
         ('relocation', 'Chuyển vị trí'),
         ('migration', 'Nhập dữ liệu lịch sử')],
        string='Lý do lắp', default='new', required=True)
    reason_remove = fields.Selection(
        [('failure', 'Hỏng'),
         ('preventive', 'Thay theo kế hoạch'),
         ('upgrade', 'Nâng cấp'),
         ('relocation', 'Chuyển vị trí'),
         ('scrap', 'Thanh lý'),
         ('other', 'Khác')],
        string='Lý do tháo')

    category_id = fields.Many2one(
        related='asset_id.category_id', store=True, string='Loại cấu phần')
    company_id = fields.Many2one(
        related='asset_id.company_id', store=True, index=True)
    note = fields.Text(string='Ghi chú')

    _ck_ngay = models.Constraint(
        'CHECK(date_remove IS NULL OR date_remove >= date_install)',
        'Ngày tháo không được trước ngày lắp.')

    @api.depends('date_install', 'date_remove')
    def _compute_is_current(self):
        hn = fields.Date.context_today(self)
        for r in self:
            r.is_current = bool(r.date_install and not r.date_remove)
            r.duration_days = (
                ((r.date_remove or hn) - r.date_install).days
                if r.date_install else 0)

    @api.depends('asset_id', 'location_id', 'date_install', 'date_remove')
    def _compute_display_name(self):
        for r in self:
            r.display_name = '%s @ %s (%s → %s)' % (
                r.asset_id.code or '?', r.location_id.complete_code or '?',
                r.date_install or '?', r.date_remove or 'nay')

    # ------------------------------------------------------------------
    # Ràng buộc chịu lực
    # ------------------------------------------------------------------
    @staticmethod
    def _chong_nhau(a1, a2, b1, b2):
        """Hai quãng có giao nhau không. Vế sau rỗng = vô hạn.

        Trường Date rỗng của Odoo trả về ``False``, KHÔNG phải ``None``
        — nên phải kiểm bằng ``not``, chứ ``is None`` sẽ lọt và vỡ ngay
        khi so sánh date với bool.
        """
        return (not a2 or b1 < a2) and (not b2 or a1 < b2)

    def _soat_chong(self, field, nhan):
        """Soát chồng thời gian trên một trục (tài sản hoặc vị trí)."""
        for r in self:
            muc = r[field]
            if not muc or not r.date_install:
                continue
            anh_em = self.search([
                (field, '=', muc.id), ('id', '!=', r.id or 0),
            ])
            for k in anh_em:
                if not k.date_install:
                    continue
                if self._chong_nhau(r.date_install, r.date_remove,
                                    k.date_install, k.date_remove):
                    raise ValidationError(_(
                        '%(nhan)s "%(ten)s" đã có một quãng lắp đặt chồng '
                        'thời gian: %(tu)s → %(den)s.\n\n'
                        'Hai quãng không được giao nhau. Thay thiết bị thì '
                        'phải ĐÓNG quãng cũ (điền ngày tháo) trước khi mở '
                        'quãng mới — nếu không, lịch sử sẽ sai mà không ai '
                        'phát hiện.',
                        nhan=nhan, ten=muc.display_name,
                        tu=k.date_install, den=k.date_remove or 'nay'))

    @api.constrains('asset_id', 'date_install', 'date_remove')
    def _check_chong_tai_san(self):
        """Một vật không thể cùng lúc nằm ở hai nơi."""
        self._soat_chong('asset_id', _('Tài sản'))

    @api.constrains('location_id', 'date_install', 'date_remove')
    def _check_chong_vi_tri(self):
        """Một vị trí đơn không thể cùng lúc chứa hai vật.

        Nhà máy và hệ thống thì chứa nhiều nên bỏ qua — ràng buộc chỉ áp
        cho vị trí thiết bị và vị trí cấu phần.
        """
        self.filtered(
            lambda r: r.location_id and not r.location_id.allow_multiple
        )._soat_chong('location_id', _('Vị trí'))

    @api.constrains('asset_id', 'location_id')
    def _check_dung_loai(self):
        """Cảnh báo lắp nhầm loại — chỉ khi vị trí có khai loại chấp nhận."""
        for r in self:
            mong = r.location_id.category_id
            if not mong:
                continue
            hop = self.env['eam.asset.category'].search(
                [('id', 'child_of', mong.id)])
            if r.asset_id.category_id not in hop:
                raise ValidationError(_(
                    'Vị trí "%(vt)s" nhận loại "%(mong)s", nhưng tài sản '
                    '"%(ts)s" thuộc loại "%(co)s".',
                    vt=r.location_id.display_name, mong=mong.complete_name,
                    ts=r.asset_id.display_name,
                    co=r.asset_id.category_id.complete_name))

    # ------------------------------------------------------------------
    def action_thao(self):
        """Đóng quãng đang mở — đặt ngày tháo là hôm nay."""
        for r in self:
            if r.date_remove:
                raise UserError(_('Quãng này đã đóng ngày %s.', r.date_remove))
            r.date_remove = fields.Date.context_today(r)
        return True

    @api.model_create_multi
    def create(self, vals_list):
        r = super().create(vals_list)
        # Lắp lên máy thì tài sản đang nháp phải chuyển sang đang dùng.
        r.asset_id.filtered(lambda a: a.state == 'draft').state = 'active'
        return r
