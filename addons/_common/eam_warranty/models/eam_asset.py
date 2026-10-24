# -*- coding: utf-8 -*-
"""Nguồn gốc và đồng hồ bảo hành của từng máy.

Câu hỏi ba năm sau
-------------------
Hộp số hỏng. Câu đầu tiên luôn là: *con này do ai cấp, theo hợp đồng
nào, còn bảo hành không*. Trả lời được hay không quyết định ai trả tiền
cho lần sửa đó.

Thông tin ấy **đã tồn tại** trong hệ, nhưng nằm rải: dòng bàn giao từ
phần dự án mang nhà cung cấp và hợp đồng; lô hàng trong kho mang hạn
bảo hành tính từ ngày nhận. Rải ra thì mỗi lần hỏi lại phải đi lục, và
máy đến bằng đường khác thì không lục được ở đâu.

Nên module này đưa câu trả lời về **một chỗ: chính con máy** — và ghi
luôn nó được kéo từ nguồn nào.

Hai đồng hồ bảo hành, và luật phân xử
--------------------------------------
Một con phụ tùng quay vòng có **hai** hạn bảo hành khác nhau về bản chất:

* trên **lô hàng**: tính từ ngày NHẬN HÀNG — hàng nằm kho hai năm thì
  hết bảo hành trước khi kịp lắp;
* trên **tài sản**: hạn bảo hành khi đã vận hành.

Cả hai đều đúng, nhưng chỉ một cái trả lời được câu *"lần sửa này ai
trả tiền"*. Luật ở đây: **lấy hạn trên tài sản**, và khi hai hạn lệch
nhau thì **cắm cờ** chứ không tự chọn — lệch là dấu hiệu có người khai
nhầm một trong hai, và tự chọn hộ là giấu mất chuyện đó.

Vì sao `warranty_state` cần hàm tìm kiếm
-----------------------------------------
Nó là trường tính KHÔNG lưu — đúng, vì "còn bao nhiêu ngày" đổi theo
từng ngày và lưu lại thì đứng yên. Nhưng không lưu thì **không lọc
được**: màn "sắp hết bảo hành" không dựng nổi, và cảnh báo không có gì
để quét. Nên bổ sung hàm tìm kiếm tự dựng điều kiện trên ``warranty_end``
— lọc được mà vẫn không lưu con số sẽ cũ đi.
"""
from datetime import timedelta

from odoo import _, api, fields, models

#: Ngưỡng "sắp hết hạn" mặc định, tính bằng ngày.
SAP_HET = 90


class EamAsset(models.Model):
    _inherit = 'eam.asset'

    # Khai lại CHỈ để gắn hàm tìm kiếm. Giữ nguyên compute và không
    # lưu — con số "còn bao nhiêu ngày" đổi theo từng ngày, lưu lại là
    # đứng yên.
    warranty_state = fields.Selection(
        compute='_compute_warranty', search='_search_warranty_state')

    # ----- Nguồn gốc (A26.2) ------------------------------------------
    supplier_partner_id = fields.Many2one(
        'res.partner', string='Nhà cung cấp', tracking=True, index=True,
        help='Ai CẤP con máy này — khác với nhà sản xuất là ai LÀM ra nó. '
             'Bảo hành đòi ở bên cấp, không đòi ở bên làm.')
    nguon_goc = fields.Selection(
        [('ban_giao', 'Bàn giao từ dự án'),
         ('mua_sam', 'Mua sắm / phụ tùng'),
         ('khac', 'Khác'),
         ('khong_ro', 'Chưa rõ')],
        string='Đến từ đâu', default='khong_ro', required=True,
        tracking=True)
    nguon_tham_chieu = fields.Char(
        string='Số hợp đồng / đơn mua', tracking=True,
        help='Ghi số để ba năm sau lần ngược được tới bộ hồ sơ gốc. Một '
             'dòng chữ, nhưng là dòng cứu được một cuộc tranh cãi.')
    nguon_ghi_chu = fields.Char(
        string='Nguồn gốc lấy từ đâu', readonly=True,
        help='Vết của việc kéo tự động: kéo từ bản ghi nào, lúc nào.')

    # ----- Hai đồng hồ bảo hành ---------------------------------------
    warranty_lot_end = fields.Date(
        string='Bảo hành theo lô (từ ngày nhận)',
        compute='_compute_lot_warranty', store=True,
        help='Hạn ghi trên lô hàng trong kho, tính từ ngày NHẬN. Để đối '
             'chiếu, không dùng để quyết ai trả tiền.')
    lech_bao_hanh = fields.Boolean(
        string='Hai hạn bảo hành LỆCH nhau',
        compute='_compute_lot_warranty', store=True,
        help='Hạn trên tài sản khác hạn trên lô hàng. Hệ KHÔNG tự chọn — '
             'lệch là dấu hiệu có người khai nhầm một trong hai, và chọn '
             'hộ là giấu mất chuyện đó.')

    nguoi_theo_doi_id = fields.Many2one(
        'res.users', string='Người theo dõi bảo hành', index=True,
        help='Nhận cảnh báo khi bảo hành sắp hết. Không khai thì máy vẫn '
             'được đếm vào mục "chưa ai theo dõi" — im lặng bỏ qua mới '
             'là cách làm mất hạn.')
    canh_bao_het_han = fields.Date(
        string='Đã cảnh báo hết hạn ngày', readonly=True, copy=False,
        help='Chặn nhắc lại mỗi ngày về cùng một con máy.')

    # ==================================================================
    # Đi qua one2many `lot_id` (eam_stock khai sẵn), KHÔNG dùng search.
    # Một trường tính có lưu mà thân hàm đi search thì Odoo không có cách
    # nào biết phải tính lại khi bản ghi BÊN KIA đổi: gắn lô mới hay sửa
    # hạn trên lô đều không kích hoạt gì, và con số nằm đó sai vĩnh viễn
    # mà màn hình không báo. Khai phụ thuộc đúng đường quan hệ thì Odoo
    # tự lo việc đó.
    @api.depends('lot_id.eam_warranty_end', 'warranty_end')
    def _compute_lot_warranty(self):
        for a in self:
            ngay = [l.eam_warranty_end for l in a.lot_id
                    if l.eam_warranty_end]
            # Nhiều lô cùng trỏ về một tài sản là chuyện không nên có,
            # nhưng nếu có thì lấy ngày SỚM NHẤT: nhận ngày muộn hơn là
            # tự tuyên bố một phạm vi bảo hành có thể không tồn tại.
            a.warranty_lot_end = min(ngay) if ngay else False
            a.lech_bao_hanh = bool(
                a.warranty_end and ngay
                and any(d != a.warranty_end for d in ngay))

    # ------------------------------------------------------------------
    @api.model
    def _search_warranty_state(self, operator, value):
        """Lọc theo tình trạng bảo hành mà KHÔNG phải lưu con số sẽ cũ đi.

        ``warranty_state`` tính lúc đọc nên không lưu — đúng, vì "còn bao
        nhiêu ngày" đổi theo từng ngày. Nhưng không lưu thì không lọc
        được, và màn "sắp hết bảo hành" không dựng nổi. Hàm này dựng
        điều kiện thẳng trên ``warranty_end``.
        """
        if operator in ('=', '!='):
            # Odoo 19 thường đã đổi '=' thành 'in' trước khi gọi tới đây,
            # nhưng mã khác vẫn gọi trực tiếp được nên vẫn phải đỡ.
            gia_tri = [value]
        elif operator in ('in', 'not in'):
            # KHÔNG phải list: Odoo 19 truyền OrderedSet, và
            # isinstance(value, (list, tuple)) trả False cho nó — cả tập
            # bị coi là MỘT giá trị, rồi vỡ ở dict.get vì set không băm
            # được. Nhận mọi thứ lặp được.
            gia_tri = list(value)
        else:
            raise ValueError(_('Chỉ so sánh bằng, khác, in hoặc not in được.'))
        phu_dinh = operator in ('!=', 'not in')

        hn = fields.Date.context_today(self)
        gioi = hn + timedelta(days=SAP_HET)
        # Nhánh nào có HAI lá thì phải ghi '&' TƯỜNG MINH. Ghép kiểu
        # ['|'] + A + B mà A là hai lá ngầm-AND thì bộ đọc tiền tố lấy
        # đúng hai toán hạng đầu cho '|' rồi để lá thứ ba lủng lẳng —
        # ra một domain hợp lệ nhưng SAI NGHĨA, và không có gì báo.
        dk = {
            'none': [('warranty_end', '=', False)],
            # NULL < ngày là NULL trong Postgres, nên một lá là đủ loại
            # được máy chưa khai hạn.
            'expired': [('warranty_end', '<', hn)],
            'expiring': ['&', ('warranty_end', '>=', hn),
                         ('warranty_end', '<=', gioi)],
            'valid': [('warranty_end', '>', gioi)],
        }
        gom = []
        for v in gia_tri:
            d = dk.get(v)
            if d:
                gom = d if not gom else ['|'] + gom + d
        if not gom:
            gom = [('id', '=', False)]
        return (['!'] + gom) if phu_dinh else gom

    # ==================================================================
    def action_keo_nguon_goc(self):
        """Kéo nhà cung cấp và hợp đồng từ dòng bàn giao, nếu có.

        Hai đường tìm, theo đúng thứ tự chắc chắn giảm dần:

        1. dòng bàn giao **liệt kê chính con máy này** — đích danh, không
           suy đoán;
        2. dòng bàn giao của **vị trí nó đang lắp** — suy ra, nên ghi rõ
           trong vết là "suy từ vị trí" để người đọc sau biết mức tin cậy.

        Không có đường nào thì nói thẳng, chứ không im lặng để người dùng
        tưởng đã kéo.
        """
        if 'rp.handover.line' not in self.env:
            return self._bao(_(
                'Phần bàn giao dự án không có trên bản cài này, nên không '
                'có nguồn nào để kéo. Khai tay nhà cung cấp và số hợp '
                'đồng.'))
        H = self.env['rp.handover.line'].sudo()
        keo = suy = co_ncc = 0
        for a in self:
            d = H.search([('asset_ids', 'in', a.id)], limit=1)
            dich_danh = bool(d)
            if not d:
                vt = a.installation_ids.filtered(
                    lambda i: not i.date_remove)[:1].location_id
                if not vt:
                    continue
                d = H.search([('location_id', '=', vt.id),
                              ('state', '=', 'done')], limit=1)
            if not d:
                continue
            a.write({
                'supplier_partner_id': d.supplier_id.id or False,
                'nguon_goc': 'ban_giao',
                'nguon_tham_chieu': d.contract_id.name or '',
                'nguon_ghi_chu': _(
                    'kéo từ biên bản bàn giao %(bb)s, vị trí %(vt)s (%(c)s)',
                    bb=d.handover_id.name, vt=d.location_code or '—',
                    c=_('liệt kê đích danh máy này') if dich_danh
                    else _('SUY từ vị trí đang lắp')),
            })
            keo += 1
            suy += 0 if dich_danh else 1
            co_ncc += 1 if d.supplier_id else 0

        # Nói rõ bao nhiêu máy thực sự có TÊN NHÀ CUNG CẤP. "Kéo được
        # nguồn gốc" mà ô nhà cung cấp vẫn trống là nửa câu: biên bản
        # bàn giao không bắt buộc khai bên cấp, nên nhiều dòng chỉ mang
        # được số hợp đồng. Số hợp đồng lần ngược được tới hồ sơ, nhưng
        # không phải cái tên để gọi khi cần đòi bảo hành.
        thieu = keo - co_ncc
        phan = [_('Kéo được cho %(a)d trên %(b)d máy, %(c)d máy có tên nhà '
                  'cung cấp.', a=keo, b=len(self), c=co_ncc)]
        if thieu:
            phan.append(_('%(d)d máy chỉ có số hợp đồng — biên bản bàn giao '
                          'không khai bên cấp. Khai tay vào đó, vì số hợp '
                          'đồng không phải cái tên để gọi khi đòi bảo hành.',
                          d=thieu))
        if suy:
            phan.append(_('%(c)d máy là SUY từ vị trí đang lắp, không phải '
                          'biên bản liệt kê đích danh — soi lại trước khi '
                          'dùng để đòi bảo hành.', c=suy))
        return self._bao(' '.join(phan))

    def _bao(self, loi_nhan):
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {'type': 'info', 'message': loi_nhan, 'sticky': False},
        }

    # ==================================================================
    @api.model
    def _cron_canh_bao_bao_hanh(self):
        """Đẩy cảnh báo cho máy sắp hết bảo hành.

        Hai điều cố ý:

        * **Không nhắc lại** cùng một máy trong vòng ba mươi ngày — bảo
          hành hết dần suốt ba tháng, nhắc mỗi ngày thì chín mươi thông
          báo cho một việc.
        * Máy **chưa ai theo dõi** vẫn được đếm và trả về, chứ không bị
          bỏ qua trong im lặng. Không có người nhận là một vấn đề cần
          thấy, không phải lý do để thôi báo.
        """
        hn = fields.Date.context_today(self)
        gioi = hn + timedelta(days=SAP_HET)
        sap = self.search([
            ('warranty_end', '>=', hn), ('warranty_end', '<=', gioi),
            ('state', '!=', 'scrapped'),
        ])
        day = 0
        khong_nguoi = self.browse()
        for a in sap:
            if a.canh_bao_het_han and (hn - a.canh_bao_het_han).days < 30:
                continue
            if not a.nguoi_theo_doi_id:
                khong_nguoi |= a
                continue
            a.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=a.nguoi_theo_doi_id.id,
                summary=_('Bảo hành sắp hết — còn %d ngày',
                          a.warranty_days_left),
                note=_('Máy %(m)s hết bảo hành ngày %(d)s. Nhà cung cấp: '
                       '%(n)s. Hồ sơ gốc: %(h)s.',
                       m=a.display_name, d=a.warranty_end,
                       n=a.supplier_partner_id.name or _('chưa khai'),
                       h=a.nguon_tham_chieu or _('chưa khai')))
            a.canh_bao_het_han = hn
            day += 1
        return {'sap_het': len(sap), 'da_day': day,
                'chua_ai_theo_doi': len(khong_nguoi)}

    def action_quet_bao_hanh(self):
        kq = self._cron_canh_bao_bao_hanh()
        return self._bao(_(
            '%(a)d máy sắp hết bảo hành · đẩy %(b)d thông báo · '
            '%(c)d máy CHƯA AI THEO DÕI.',
            a=kq['sap_het'], b=kq['da_day'], c=kq['chua_ai_theo_doi']))
