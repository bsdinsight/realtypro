# -*- coding: utf-8 -*-
"""Đồng hồ hạn đọc số ngày từ ĐIỀU KHOẢN, thay vì hằng số trong mã.

Vấn đề
------
Các con số 14 / 21 / 28 nằm rải trong mã nguồn như giá trị mặc định. Đó
là giả định FIDIC, và với phần lớn hợp đồng thì đúng. Nhưng khi hợp đồng
quy định khác, hệ thống **âm thầm tính sai hạn** — trên màn hình chỉ
hiện ra một cái ngày, trông y hệt lúc đúng. Không ai phát hiện được, kể
cả người đọc kỹ.

Nguyên tắc: không ghi đè im lặng, không lệch im lặng
-----------------------------------------------------
Hai cách xử dễ nghĩ ra đều sai:

* **Tính lại liên tục theo điều khoản.** Nuốt mất trường hợp hợp lệ —
  Engineer gia hạn bằng văn bản cho riêng một hồ sơ. Sửa xong lần sau mở
  ra lại bị đè về, và không ai hiểu vì sao.
* **Chỉ đặt mặc định lúc tạo.** Bản ghi cũ giữ số cũ mãi mãi; khai đúng
  điều khoản về sau không chữa được gì, mà màn hình thì trông như đã
  chữa.

Cách ở đây lấy cả hai nửa đúng: **lấy mặc định từ điều khoản lúc tạo**,
rồi **hiện cờ lệch** ở mọi bản ghi có số khác điều khoản, kèm nút áp
lại do người bấm. Không bản ghi nào bị sửa sau lưng, mà cũng không chỗ
lệch nào ẩn đi.

Vì sao điều khoản "mẫu FIDIC" vẫn đáng khai
--------------------------------------------
Dòng điều khoản khai theo mẫu mang đúng con số mà mã nguồn vẫn ngầm
dùng. Nó không thêm giả định nào — nó **mang giả định sẵn có ra chỗ
người ta nhìn thấy và sửa được**. Đó là toàn bộ giá trị của nó, và là lý
do nó cố ý để trống trang và trích đoạn: nhìn là biết chưa đối chiếu bản
giấy.

Vì sao không gom vào một mixin
-------------------------------
Đã thử. ``@api.depends`` cần tên trường viết sẵn lúc nạp lớp, mà mỗi
model lại đặt tên trường số ngày một kiểu (``review_days``,
``quote_days``, ``notice_days``). Gom lại thì phải khai phụ thuộc động —
Odoo không nhận, và cái giá là trường tính không tự làm mới khi người
dùng sửa số ngày. Viết thẳng ra bốn lần dài hơn nhưng đúng, và đọc một
lượt là hiểu.
"""
from odoo import _, api, fields, models

#: Bộ điều khoản mẫu để khai nhanh — tiêu đề và số ngày đúng bằng mặc
#: định mà mã nguồn vẫn dùng. Trang và trích đoạn cố ý để trống.
DIEU_KHOAN_MAU = [
    ('5.2', 'Xem xét hồ sơ của Nhà thầu', 21),
    ('13.1', 'Quyền thay đổi — thời hạn phản đối chỉ thị', 14),
    ('13.3', 'Thủ tục thay đổi — thời hạn nộp báo giá', 14),
    ('20.1', 'Khiếu nại của Nhà thầu — thời hạn thông báo', 28),
]

DIEU_HO_SO = '5.2'
DIEU_BAO_GIA = '13.3'
DIEU_PHAN_DOI = '13.1'
DIEU_KHIEU_NAI = '20.1'


class RpContractClause(models.Model):
    _inherit = 'rp.contract.clause'

    @api.model
    def so_ngay_theo_hop_dong(self, hop_dong, so_dieu):
        """{id hợp đồng: số ngày} cho một số điều — một truy vấn cho cả lô."""
        if not hop_dong or not so_dieu:
            return {}
        ra = {}
        for c in self.search([
                ('contract_id', 'in', hop_dong.ids),
                ('number', '=', so_dieu),
                ('is_current', '=', True),
                ('notice_days', '>', 0)]):
            ra.setdefault(c.contract_id.id, c.notice_days)
        return ra

    @api.model
    def mac_dinh_khi_tao(self, vals_list, truong, so_dieu):
        """Điền số ngày từ điều khoản cho những vals CHƯA khai số nào."""
        can = [v for v in vals_list
               if not v.get(truong) and v.get('contract_id')]
        if not can:
            return
        hd = self.env['rp.contract'].browse(
            list({v['contract_id'] for v in can}))
        ban_do = self.so_ngay_theo_hop_dong(hd, so_dieu)
        for v in can:
            n = ban_do.get(v['contract_id'])
            if n:
                v[truong] = n


class RpContract(models.Model):
    _inherit = 'rp.contract'

    doc_review_theo_dieu = fields.Integer(
        string='Điều %s quy định (ngày)' % DIEU_HO_SO,
        compute='_compute_doc_review_theo_dieu')
    doc_review_lech = fields.Boolean(
        string='Hạn xem xét lệch điều khoản',
        compute='_compute_doc_review_theo_dieu')

    @api.depends('doc_review_days', 'clause_ids.notice_days',
                 'clause_ids.number', 'clause_ids.is_current')
    def _compute_doc_review_theo_dieu(self):
        ban_do = self.env['rp.contract.clause'].so_ngay_theo_hop_dong(
            self, DIEU_HO_SO)
        for rec in self:
            theo = ban_do.get(rec.id, 0)
            rec.doc_review_theo_dieu = theo
            rec.doc_review_lech = bool(theo) and rec.doc_review_days != theo

    def action_ap_han_xem_xet_tu_dieu(self):
        for rec in self:
            if rec.doc_review_theo_dieu:
                rec.doc_review_days = rec.doc_review_theo_dieu
        return True

    def action_khai_dieu_khoan_mau(self):
        """Khai bộ điều khoản mẫu để sửa lại theo bản giấy.

        Không đụng điều khoản đã có — chỉ thêm số điều còn thiếu.
        """
        Clause = self.env['rp.contract.clause']
        them = 0
        for hd in self:
            da_co = set(Clause.search(
                [('contract_id', '=', hd.id)]).mapped('number'))
            moi = [{
                'contract_id': hd.id,
                'number': so,
                'name': ten,
                'notice_days': ngay,
                'source': 'mau',
            } for so, ten, ngay in DIEU_KHOAN_MAU if so not in da_co]
            if moi:
                Clause.create(moi)
                them += len(moi)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'warning' if them else 'info',
                'title': _('Đã khai %s điều khoản mẫu', them),
                'message': _(
                    'Đây là số ngày phần mềm vẫn ngầm dùng, nay đưa ra chỗ '
                    'sửa được — CHƯA đối chiếu bản giấy. Mở từng điều, điền '
                    'trang và trích đoạn, sửa số ngày cho đúng hợp đồng.'),
                'sticky': True,
            },
        }


class RpDocument(models.Model):
    _inherit = 'rp.document'

    review_theo_dieu = fields.Integer(
        string='Điều %s quy định (ngày)' % DIEU_HO_SO,
        compute='_compute_review_theo_dieu')
    review_lech = fields.Boolean(
        string='Lệch điều khoản', compute='_compute_review_theo_dieu',
        help='Số ngày trên hồ sơ này khác điều khoản hợp đồng. Có thể hợp '
             'lệ — được gia hạn bằng văn bản chẳng hạn — nhưng phải nhìn '
             'thấy, không được ẩn đi.')

    @api.depends('review_days', 'contract_id.clause_ids.notice_days',
                 'contract_id.clause_ids.number',
                 'contract_id.clause_ids.is_current')
    def _compute_review_theo_dieu(self):
        ban_do = self.env['rp.contract.clause'].so_ngay_theo_hop_dong(
            self.contract_id, DIEU_HO_SO)
        for rec in self:
            theo = ban_do.get(rec.contract_id.id, 0)
            rec.review_theo_dieu = theo
            rec.review_lech = bool(theo) and rec.review_days != theo

    def action_ap_so_ngay_tu_dieu(self):
        for rec in self:
            if rec.review_theo_dieu:
                rec.review_days = rec.review_theo_dieu
        return True

    @api.model_create_multi
    def create(self, vals_list):
        self.env['rp.contract.clause'].mac_dinh_khi_tao(
            vals_list, 'review_days', DIEU_HO_SO)
        return super().create(vals_list)


class RpVariation(models.Model):
    _inherit = 'rp.variation'

    quote_theo_dieu = fields.Integer(
        string='Điều %s quy định (ngày)' % DIEU_BAO_GIA,
        compute='_compute_theo_dieu')
    quote_lech = fields.Boolean(
        string='Hạn báo giá lệch điều khoản', compute='_compute_theo_dieu')
    objection_theo_dieu = fields.Integer(
        string='Điều %s quy định (ngày)' % DIEU_PHAN_DOI,
        compute='_compute_theo_dieu')
    objection_lech = fields.Boolean(
        string='Hạn phản đối lệch điều khoản', compute='_compute_theo_dieu')

    @api.depends('quote_days', 'objection_days',
                 'contract_id.clause_ids.notice_days',
                 'contract_id.clause_ids.number',
                 'contract_id.clause_ids.is_current')
    def _compute_theo_dieu(self):
        Clause = self.env['rp.contract.clause']
        bg = Clause.so_ngay_theo_hop_dong(self.contract_id, DIEU_BAO_GIA)
        pd = Clause.so_ngay_theo_hop_dong(self.contract_id, DIEU_PHAN_DOI)
        for rec in self:
            hd = rec.contract_id.id
            rec.quote_theo_dieu = bg.get(hd, 0)
            rec.quote_lech = (bool(rec.quote_theo_dieu)
                              and rec.quote_days != rec.quote_theo_dieu)
            rec.objection_theo_dieu = pd.get(hd, 0)
            rec.objection_lech = (
                bool(rec.objection_theo_dieu)
                and rec.objection_days != rec.objection_theo_dieu)

    def action_ap_so_ngay_tu_dieu(self):
        for rec in self:
            if rec.quote_theo_dieu:
                rec.quote_days = rec.quote_theo_dieu
            if rec.objection_theo_dieu:
                rec.objection_days = rec.objection_theo_dieu
        return True

    @api.model_create_multi
    def create(self, vals_list):
        Clause = self.env['rp.contract.clause']
        Clause.mac_dinh_khi_tao(vals_list, 'quote_days', DIEU_BAO_GIA)
        Clause.mac_dinh_khi_tao(vals_list, 'objection_days', DIEU_PHAN_DOI)
        return super().create(vals_list)


class RpClaim(models.Model):
    _inherit = 'rp.claim'

    notice_theo_dieu = fields.Integer(
        string='Điều %s quy định (ngày)' % DIEU_KHIEU_NAI,
        compute='_compute_notice_theo_dieu')
    notice_lech = fields.Boolean(
        string='Lệch điều khoản', compute='_compute_notice_theo_dieu')

    @api.depends('notice_days', 'contract_id.clause_ids.notice_days',
                 'contract_id.clause_ids.number',
                 'contract_id.clause_ids.is_current')
    def _compute_notice_theo_dieu(self):
        ban_do = self.env['rp.contract.clause'].so_ngay_theo_hop_dong(
            self.contract_id, DIEU_KHIEU_NAI)
        for rec in self:
            theo = ban_do.get(rec.contract_id.id, 0)
            rec.notice_theo_dieu = theo
            rec.notice_lech = bool(theo) and rec.notice_days != theo

    def action_ap_so_ngay_tu_dieu(self):
        for rec in self:
            if rec.notice_theo_dieu:
                rec.notice_days = rec.notice_theo_dieu
        return True

    @api.model_create_multi
    def create(self, vals_list):
        self.env['rp.contract.clause'].mac_dinh_khi_tao(
            vals_list, 'notice_days', DIEU_KHIEU_NAI)
        return super().create(vals_list)
