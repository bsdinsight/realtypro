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
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models

from .thu_vien_fidic import DIEU_DUNG_DUOC, MOC, THEO_SO


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
        """Khai thư viện điều khoản FIDIC cho hợp đồng này.

        Không đụng điều khoản đã có — chỉ thêm số điều còn thiếu. Mọi
        dòng mang nhãn "mẫu — chưa đối chiếu hợp đồng", vì Điều kiện
        Riêng của từng hợp đồng gần như luôn sửa một vài con số.
        """
        Clause = self.env['rp.contract.clause']
        them = 0
        for hd in self:
            da_co = set(Clause.search(
                [('contract_id', '=', hd.id)]).mapped('number'))
            moi = [{
                'contract_id': hd.id,
                'number': d['so'],
                'name': d['ten'],
                'notice_days': d['ngay'],
                'mo_ta': '%s%s' % (
                    d['mo_ta'],
                    _('\n\nĐồng hồ chạy từ: %s.', MOC[d['moc']])
                    if d['ngay'] else ''),
                'source': 'mau',
                'sequence': i * 10,
            } for i, d in enumerate(DIEU_DUNG_DUOC) if d['so'] not in da_co]
            if moi:
                Clause.create(moi)
                them += len(moi)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'warning' if them else 'info',
                'title': _('Đã khai %s điều khoản từ thư viện FIDIC', them),
                'message': _(
                    'Đây là Điều kiện CHUNG. Điều kiện Riêng của hợp đồng '
                    'gần như luôn sửa một vài con số — đó là chỗ các bên '
                    'mặc cả thật. Mở từng điều, đối chiếu bản giấy, điền '
                    'trang và trích đoạn, rồi mới gỡ nhãn "chưa đối chiếu".'),
                'sticky': True,
            },
        }

    def action_dung_nghia_vu_chuan(self):
        """Dựng các nghĩa vụ đứng sẵn mà thư viện nói là hợp đồng nào cũng có.

        Bảo hiểm, bảo lãnh, báo cáo định kỳ, giấy phép, hồ sơ phải nộp
        một lần — những thứ không sinh ra từ một chứng từ nào nên không
        sổ chuyên nào bắt được.

        Hạn chỉ tính được khi biết MỐC khởi đồng hồ. Hợp đồng mới ký thì
        ta mới có ngày ký và ngày khởi công; các mốc còn lại (Thư chấp
        thuận, Chứng chỉ nghiệm thu) nằm ở chứng từ ngoài. Mốc nào chưa
        có thì để trống hạn và ghi rõ luật tính — thà "chưa đặt hạn" còn
        hơn một cái hạn bịa trông như thật.
        """
        Ob = self.env['rp.obligation']
        them = 0
        for hd in self:
            trong_hd = Ob.search([('contract_id', '=', hd.id),
                                  ('clause_id', '!=', False)])
            # Luật 1 — bất biến: đã dựng rồi thì không dựng lại.
            da_dung = {(o.clause_id.id, o.loai) for o in trong_hd
                       if o.vai == 'tu_quan' and not o.parent_id}
            # Luật 2 — có hàng thật thì thôi dòng chung chung: hợp đồng
            # đã có bảo lãnh/hồ sơ thật ghi ở sổ chuyên, neo cùng điều
            # khoản ấy, thì một dòng "phải có bảo lãnh" không mang thêm
            # thông tin nào — nó chỉ làm sổ dài ra. Dòng thật có số hiệu,
            # có ngày hết hạn; dòng chung chung không có gì.
            da_co_that = {(o.clause_id.id, o.loai) for o in trong_hd
                          if o.nguon == 'so_rieng'}
            for dieu in hd.clause_ids.filtered('is_current'):
                d = THEO_SO.get(dieu.number)
                if not d or not d['sinh']:
                    continue
                if (dieu.id, d['loai']) in da_dung:
                    continue
                if (dieu.id, d['loai']) in da_co_that:
                    continue
                vals = {
                    'name': d['ten'].split(' — ')[-1].capitalize(),
                    'contract_id': hd.id,
                    'clause_id': dieu.id,
                    'loai': d['loai'],
                    'ben': d['ben'],
                    'vai': 'tu_quan',
                    'ghi_chu': d['mo_ta'],
                }
                if d['chu_ky']:
                    vals.update({
                        'la_dinh_ky': True,
                        'chu_ky': d['chu_ky'],
                        'ky_tu': hd.date_start or hd.contract_date,
                        'han_sau_ky': d['ngay'] or 0,
                    })
                else:
                    moc, ngay = hd._moc_khoi_dong_ho(d['moc'])
                    if moc and d['ngay']:
                        vals['han_tu_quan'] = moc + relativedelta(
                            days=d['ngay'])
                        vals['ghi_chu'] += _(
                            '\n\nHạn tính từ %(ten)s (%(ngay)s) + %(n)s '
                            'ngày.%(luu_y)s',
                            ten=MOC[d['moc']], ngay=moc, n=d['ngay'],
                            luu_y=ngay or '')
                    elif not d['ngay']:
                        vals['ghi_chu'] += _(
                            '\n\nCHƯA ĐẶT HẠN: Điều kiện Chung KHÔNG đặt '
                            'số ngày cứng cho nghĩa vụ này — hạn theo thực '
                            'tế dự án và Điều kiện Riêng. Điền bằng tay.')
                    else:
                        vals['ghi_chu'] += _(
                            '\n\nCHƯA ĐẶT HẠN: luật là %(n)s ngày kể từ '
                            '%(ten)s, nhưng hệ thống chưa biết ngày mốc đó. '
                            'Điền hạn bằng tay khi có.',
                            n=d['ngay'], ten=MOC[d['moc']])
                Ob.create(vals)
                them += 1
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success' if them else 'info',
                'title': _('Đã dựng %s nghĩa vụ chuẩn', them),
                'message': _('Nghĩa vụ định kỳ còn phải bấm "Sinh các kỳ" '
                             'để ra từng kỳ. Dòng nào ghi "CHƯA ĐẶT HẠN" '
                             'là hệ thống chưa biết ngày mốc — điền tay.'),
                'sticky': False,
            },
        }

    def _moc_khoi_dong_ho(self, ma_moc):
        """(ngày mốc, lưu ý) — CHỈ những mốc hợp đồng thật sự biết.

        Cố ý KHÔNG lấy ngày ký làm xấp xỉ cho Thư chấp thuận. Hai thứ
        khác nhau, và một cái hạn suy từ ngày sai thì hiện lên màn hình
        y hệt một cái hạn thật — người xem không có cách nào phân biệt.
        Thà để "chưa đặt hạn" kèm luật tính, rồi ai biết ngày mốc thì
        điền. Đã dính 2026-10-22: sáu dòng bảo lãnh/bảo hiểm báo "sắp
        đến hạn 31/10" suy từ ngày seed dữ liệu demo.
        """
        self.ensure_one()
        if ma_moc == 'khoi_cong':
            return self.date_start, ''
        return False, ''


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
