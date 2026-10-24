# -*- coding: utf-8 -*-
"""Yêu cầu bảo hành: còn hạn hay không quyết định AI TRẢ TIỀN.

Vì sao phải CHỤP LẠI tình trạng bảo hành
-----------------------------------------
Một phiếu gửi hàng đi sửa chỉ khác nhau một điều: lúc gửi, con máy còn
bảo hành hay đã hết. Còn hạn thì hãng chịu; hết hạn thì nhà máy trả.

Tình trạng ấy đổi theo ngày. Phiếu lập hôm nay còn hạn, ba tháng sau mở
lại thì hệ tính ra "đã hết" — và biên bản tự lật ngược kết luận của
chính nó. Nên tình trạng được **chụp lại lúc lập phiếu** và không đổi
nữa, đúng như hằng số hiệu suất và như kỳ hợp đồng đã chốt.

Phiếu bảo hành mà máy đã hết hạn thì NÓI RA
--------------------------------------------
Người lập hay chọn loại "bảo hành" theo thói quen. Nếu lúc đó máy đã hết
hạn, phiếu vẫn gửi đi được — nhưng bên kia sẽ từ chối, và cả quãng thời
gian chờ đó là thời gian chết. Nên hệ cắm cờ ngay lúc lập, chứ không để
phát hiện sau ba tuần.
"""
from odoo import _, api, fields, models


class EamRma(models.Model):
    _inherit = 'eam.rma'

    bao_hanh_luc_lap = fields.Selection(
        [('none', 'Không khai hạn'), ('valid', 'Còn hạn'),
         ('expiring', 'Sắp hết'), ('expired', 'Hết hạn')],
        string='Bảo hành lúc lập phiếu', readonly=True, copy=False,
        help='CHỤP LẠI lúc lập, không tính lại về sau. Tình trạng bảo '
             'hành đổi theo ngày; tính lại thì ba tháng sau biên bản tự '
             'lật ngược kết luận của chính nó.')
    han_bao_hanh_luc_lap = fields.Date(
        string='Hạn bảo hành lúc lập', readonly=True, copy=False)
    ngay_con_lai_luc_lap = fields.Integer(
        string='Còn (ngày) lúc lập', readonly=True, copy=False,
        aggregator=False)
    doi_bao_hanh_nhung_het_han = fields.Boolean(
        string='Đòi bảo hành nhưng đã hết hạn',
        compute='_compute_canh_bao', store=True,
        help='Phiếu khai loại bảo hành trong khi máy đã hết hạn. Vẫn gửi '
             'đi được, nhưng bên kia sẽ từ chối — và cả quãng chờ đó là '
             'thời gian chết.')
    supplier_goc_id = fields.Many2one(
        'res.partner', string='Nhà cung cấp gốc của máy',
        related='asset_id.supplier_partner_id', store=True, readonly=True,
        help='Bảo hành đòi ở bên CẤP. Khác bên nhận phiếu thì phải có lý '
             'do, nếu không là đòi nhầm cửa.')

    @api.depends('rma_type', 'bao_hanh_luc_lap')
    def _compute_canh_bao(self):
        for r in self:
            r.doi_bao_hanh_nhung_het_han = bool(
                r.rma_type == 'warranty'
                and r.bao_hanh_luc_lap == 'expired')

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs._chup_bao_hanh()
        return recs

    def write(self, vals):
        """Chụp khi con máy LỘ DIỆN, không phải cứng nhắc lúc tạo.

        ``asset_id`` suy ra từ lô, và người lập thường chọn lô ở bước
        sau — phiếu tạo ra lúc đầu chưa biết con máy nào, nên chụp ở
        ``create`` thôi thì phần lớn phiếu không có ảnh nào. Chụp vào
        thời điểm biết là con máy nào: đó mới đúng là "lúc lập phiếu".

        Đã có ảnh rồi thì KHÔNG chụp lại — đổi lô trên phiếu cũ không
        được phép viết lại tình trạng đã ghi.
        """
        res = super().write(vals)
        if 'lot_id' in vals or 'asset_id' in vals:
            self.filtered(
                lambda r: r.asset_id and not r.bao_hanh_luc_lap
            )._chup_bao_hanh()
        return res

    def _chup_bao_hanh(self, ghi_de=False):
        for r in self:
            a = r.asset_id
            if not a or (r.bao_hanh_luc_lap and not ghi_de):
                continue
            # Ghi qua super().write để không chạy lại móc write ở trên.
            super(EamRma, r).write({
                'bao_hanh_luc_lap': a.warranty_state,
                'han_bao_hanh_luc_lap': a.warranty_end,
                'ngay_con_lai_luc_lap': a.warranty_days_left,
            })

    def action_chup_lai_bao_hanh(self):
        """Chụp lại tình trạng — của HÔM NAY, không phải của ngày lập.

        Dùng cho phiếu lập trước khi có phần theo dõi bảo hành: không có
        ảnh cũ nào để phục hồi, nên đây là lấy con số hiện tại và người
        bấm phải biết đúng điều đó.
        """
        self._chup_bao_hanh(ghi_de=True)
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {
                'type': 'warning',
                'message': _('Đã chụp tình trạng bảo hành của HÔM NAY. Đây '
                             'không phải tình trạng ở ngày lập phiếu — '
                             'không có ảnh cũ nào để phục hồi.'),
                'sticky': False,
            },
        }
