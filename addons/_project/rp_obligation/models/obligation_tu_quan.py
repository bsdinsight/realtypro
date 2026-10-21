# -*- coding: utf-8 -*-
"""Nghĩa vụ chưa có sổ chuyên: bảo hiểm · bảo hành · báo cáo định kỳ · giấy phép.

Bốn loại này trước nay không nằm ở đâu cả. Người ta nhớ bằng đầu, hoặc
bằng một file Excel của riêng ai đó — tới lúc bảo hiểm hết hạn giữa kỳ
thi công thì mới biết. Đây là chỗ ``rp.obligation`` thôi làm chỉ mục và
**chính nó là bản ghi**.

Ba loại một hạn, một loại nhiều hạn
------------------------------------
Bảo hiểm, bảo hành, giấy phép đều là *một tờ giấy do bên thứ ba cấp, có
số hiệu, có hiệu lực từ ngày này tới ngày kia* — cùng một hình dạng, nên
dùng chung một bộ trường. Gộp được thì gộp; đẻ ba model gần giống nhau
chỉ tạo ba chỗ để quên đồng bộ.

Báo cáo định kỳ thì khác hẳn. Hợp đồng 24 tháng với nghĩa vụ báo cáo
tháng không phải **một** hạn — nó là **24** hạn, và *"báo cáo tháng 3
nộp muộn 5 ngày"* là một dữ kiện phải giữ được. Một dòng mang ô "chu kỳ
= hàng tháng" trông thì gọn nhưng không trả lời nổi câu hỏi duy nhất
đáng hỏi: **tháng nào đã nộp, tháng nào chưa.**

Nên lịch là lịch, kỳ là kỳ: dòng cha giữ *luật* (từ ngày nào, tới ngày
nào, mấy ngày sau khi hết kỳ thì phải nộp), mỗi kỳ là một dòng con có
hạn riêng và ngày hoàn thành riêng.

Sinh kỳ chạy lại không đẻ thêm
-------------------------------
Mỗi kỳ mang ``khoa`` dựng từ (dòng cha, ngày bắt đầu kỳ) — cùng ràng
buộc UNIQUE ở tầng CSDL với các dòng chỉ mục. Bấm sinh mười lần vẫn ra
đúng ngần ấy kỳ.

Không sinh tới vô tận
----------------------
Chỉ sinh tới ngày kết thúc lịch, hoặc ngày hoàn thành hợp đồng, hoặc 12
tháng tới — cái nào đến trước. Hợp đồng chưa biết ngày kết thúc mà sinh
thẳng 10 năm thì sổ ngập kỳ mà không kỳ nào có người đọc.
"""
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

#: Chu kỳ → số tháng một kỳ.
THANG_MOI_KY = {'thang': 1, 'quy': 3, 'nua_nam': 6, 'nam': 12}

#: Loại nghĩa vụ mang hình dạng "giấy tờ do bên thứ ba cấp".
LOAI_GIAY_TO = ('bao_hiem', 'bao_hanh', 'giay_phep')

#: Không sinh kỳ xa hơn ngần này tháng khi lịch chưa khai ngày kết thúc.
CHAN_TRUOC_THANG = 12


class RpObligationTuQuan(models.Model):
    _inherit = 'rp.obligation'

    # ----- Giấy tờ bên thứ ba cấp (bảo hiểm / bảo hành / giấy phép) -----
    ben_thu_ba_id = fields.Many2one(
        'res.partner', string='Bên cấp',
        help='Công ty bảo hiểm, cơ quan cấp phép, hoặc bên bảo hành.')
    so_hieu = fields.Char(
        string='Số hiệu',
        help='Số đơn bảo hiểm / số giấy phép / số chứng nhận bảo hành.')
    gia_tri = fields.Monetary(
        string='Giá trị', currency_field='currency_id',
        help='Số tiền bảo hiểm, hoặc giá trị cam kết. Để trống nếu không '
             'quy ra tiền được.')
    currency_id = fields.Many2one(
        related='contract_id.currency_id', string='Tiền tệ')
    hieu_luc_tu = fields.Date(string='Hiệu lực từ')
    hieu_luc_den = fields.Date(string='Hiệu lực đến')

    # ----- Lịch định kỳ --------------------------------------------------
    la_dinh_ky = fields.Boolean(
        string='Là lịch định kỳ', tracking=True,
        help='Bật thì dòng này giữ LUẬT, còn từng kỳ là các dòng con có '
             'hạn riêng. Bản thân nó không có hạn — một cái lịch thì '
             'không quá hạn được.')
    chu_ky = fields.Selection(
        [('thang', 'Hàng tháng'),
         ('quy', 'Hàng quý'),
         ('nua_nam', 'Nửa năm'),
         ('nam', 'Hàng năm')],
        string='Chu kỳ')
    ky_tu = fields.Date(string='Bắt đầu từ')
    ky_den = fields.Date(
        string='Kết thúc', help='Để trống thì lấy ngày hoàn thành hợp '
                                'đồng, hoặc 12 tháng tới.')
    han_sau_ky = fields.Integer(
        string='Nộp trong (ngày sau khi hết kỳ)', default=7,
        help='Báo cáo tháng 3 hạn nộp ngày 7/4 thì điền 7. Để 0 nghĩa là '
             'hạn rơi đúng ngày cuối kỳ.')

    parent_id = fields.Many2one(
        'rp.obligation', string='Thuộc lịch', ondelete='cascade', index=True)
    child_ids = fields.One2many(
        'rp.obligation', 'parent_id', string='Các kỳ')
    ky_bat_dau = fields.Date(string='Kỳ bắt đầu', readonly=True)

    so_ky = fields.Integer(string='Số kỳ', compute='_compute_thong_ke_ky')
    so_ky_qua_han = fields.Integer(
        string='Kỳ quá hạn', compute='_compute_thong_ke_ky')
    so_ky_xong = fields.Integer(
        string='Kỳ đã nộp', compute='_compute_thong_ke_ky')

    # ======================================================================
    # Compute
    # ======================================================================
    @api.depends('child_ids.trang_thai')
    def _compute_thong_ke_ky(self):
        for rec in self:
            con = rec.child_ids
            rec.so_ky = len(con)
            rec.so_ky_qua_han = len(
                con.filtered(lambda c: c.trang_thai == 'qua_han'))
            rec.so_ky_xong = len(
                con.filtered(lambda c: c.trang_thai == 'xong'))

    @api.depends('document_id', 'variation_id', 'claim_id', 'guarantee_id',
                 'milestone_id', 'vai', 'parent_id', 'ky_bat_dau')
    def _compute_khoa(self):
        """Mở rộng khoá đồng bộ sang các kỳ của lịch định kỳ."""
        super()._compute_khoa()
        for rec in self:
            if not rec.khoa and rec.parent_id and rec.ky_bat_dau:
                rec.khoa = 'ky-%s-%s' % (rec.parent_id.id, rec.ky_bat_dau)

    # ======================================================================
    # Nhập liệu
    # ======================================================================
    @api.onchange('hieu_luc_den', 'loai')
    def _onchange_hieu_luc_den(self):
        """Ngày hết hiệu lực CHÍNH LÀ hạn phải gia hạn — điền sẵn hộ.

        Vẫn sửa đè được: có hợp đồng buộc gia hạn trước 30 ngày, lúc đó
        hạn thật sớm hơn ngày hết hiệu lực.
        """
        for rec in self:
            if (rec.loai in LOAI_GIAY_TO and rec.hieu_luc_den
                    and not rec.han_tu_quan):
                rec.han_tu_quan = rec.hieu_luc_den

    @api.onchange('la_dinh_ky')
    def _onchange_la_dinh_ky(self):
        for rec in self:
            if rec.la_dinh_ky:
                rec.vai = 'tu_quan'
                rec.han_tu_quan = False
                if not rec.chu_ky:
                    rec.chu_ky = 'thang'
                if not rec.ky_tu:
                    rec.ky_tu = (rec.contract_id.date_start
                                 or fields.Date.context_today(rec))

    @api.constrains('la_dinh_ky', 'parent_id', 'nguon', 'han_tu_quan')
    def _check_dinh_ky(self):
        for rec in self:
            if rec.la_dinh_ky and rec.han_tu_quan:
                raise ValidationError(_(
                    'Lịch "%s" không mang hạn của riêng nó — hạn nằm ở '
                    'từng kỳ. Để hạn trên lịch thì nó vừa là cái lịch vừa '
                    'là một việc, và không ai biết dòng nào mới là việc.',
                    rec.name))
            if rec.la_dinh_ky and rec.nguon == 'so_rieng':
                raise ValidationError(_(
                    'Dòng chỉ mục của sổ chuyên không làm lịch định kỳ '
                    'được — hạn của nó thuộc về sổ gốc.'))
            if rec.la_dinh_ky and rec.parent_id:
                raise ValidationError(_(
                    'Một kỳ không chứa lịch khác bên trong. Lồng hai tầng '
                    'thì "kỳ nào chưa nộp" không còn trả lời được.'))

    # ======================================================================
    # Sinh kỳ
    # ======================================================================
    def _chan_sinh_ky(self):
        """Ngày xa nhất được phép sinh tới."""
        self.ensure_one()
        hn = fields.Date.context_today(self)
        ung_vien = [
            self.ky_den,
            self.contract_id.date_end,
            hn + relativedelta(months=CHAN_TRUOC_THANG),
        ]
        return min(d for d in ung_vien if d)

    def sinh_ky(self):
        """Dựng các kỳ còn thiếu. Chạy lại không đẻ thêm."""
        tao = 0
        for lich in self:
            if not lich.la_dinh_ky:
                continue
            if not lich.chu_ky or not lich.ky_tu:
                raise UserError(_(
                    'Lịch "%s" chưa khai chu kỳ hoặc ngày bắt đầu.',
                    lich.name))
            buoc = THANG_MOI_KY[lich.chu_ky]
            chan = lich._chan_sinh_ky()
            da_co = set(lich.child_ids.mapped('ky_bat_dau'))
            moi, dau = [], lich.ky_tu
            while dau <= chan:
                cuoi = dau + relativedelta(months=buoc, days=-1)
                if dau not in da_co:
                    moi.append({
                        'name': '%s — %s' % (
                            lich.name, lich._nhan_ky(dau, cuoi)),
                        'contract_id': lich.contract_id.id,
                        'parent_id': lich.id,
                        'ky_bat_dau': dau,
                        'han_tu_quan': cuoi + relativedelta(
                            days=lich.han_sau_ky or 0),
                        'ben': lich.ben,
                        'loai': lich.loai,
                        'vai': 'tu_quan',
                        'clause_id': lich.clause_id.id or False,
                        'nguoi_phu_trach_id':
                            lich.nguoi_phu_trach_id.id or False,
                    })
                dau += relativedelta(months=buoc)
            if moi:
                self.create(moi)
                tao += len(moi)
        return tao

    def _nhan_ky(self, dau, cuoi):
        """Tên kỳ đọc được: "tháng 3/2027", "quý 2/2027", "năm 2027"."""
        self.ensure_one()
        if self.chu_ky == 'thang':
            return _('tháng %(m)s/%(y)s', m=dau.month, y=dau.year)
        if self.chu_ky == 'quy':
            return _('quý %(q)s/%(y)s', q=(dau.month - 1) // 3 + 1, y=dau.year)
        if self.chu_ky == 'nua_nam':
            return _('nửa %(n)s/%(y)s', n=1 if dau.month <= 6 else 2,
                     y=dau.year)
        return _('năm %s', dau.year)

    def action_sinh_ky(self):
        tao = self.sinh_ky()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success' if tao else 'info',
                'title': _('Đã sinh %s kỳ', tao),
                'message': _('Chỉ sinh tới ngày kết thúc lịch, ngày hoàn '
                             'thành hợp đồng, hoặc %s tháng tới — cái nào '
                             'đến trước.', CHAN_TRUOC_THANG),
                'sticky': False,
            },
        }

    def action_xem_ky(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Các kỳ — %s', self.name),
            'res_model': 'rp.obligation',
            'view_mode': 'list,form',
            'domain': [('parent_id', '=', self.id)],
            'context': {'default_parent_id': self.id},
        }

    @api.model
    def cron_sinh_ky(self):
        """Lịch đêm: đẩy chân trời sinh kỳ tiến lên theo thời gian."""
        lich = self.search([('la_dinh_ky', '=', True),
                            ('active', '=', True)])
        return lich.sinh_ky()
