# -*- coding: utf-8 -*-
"""Mục tiêu sản lượng P50 / P75 / P90 — BA mức, không phải một.

Vì sao ba mức
--------------
Sản lượng một nhà máy gió hay mặt trời không phải con số, mà là một
phân phối: gió năm nay mạnh hơn năm ngoái thì sản lượng khác, và không
ai điều khiển được chuyện đó.

* **P50** — mức mà xác suất vượt qua là 50%. Đây là *kỳ vọng*, dùng để
  lập kế hoạch vận hành.
* **P75** — vượt qua 75% số năm. Thận trọng hơn.
* **P90** — vượt qua 90% số năm. Đây là mức **ngân hàng** dùng để tính
  khả năng trả nợ, vì họ cần con số gần như chắc chắn đạt.

Khai một mức rồi gọi nó là "kế hoạch" thì mọi câu hỏi về rủi ro sản
lượng đều mất chỗ trả lời — và câu hỏi ấy luôn được hỏi, chỉ là hỏi lúc
nào.

Thứ tự P50 > P75 > P90 là RÀNG BUỘC, không phải quy ước
--------------------------------------------------------
Càng chắc chắn đạt thì con số càng phải thấp. Người khai hay nhầm chiều
— nhầm thì mọi phân tích rủi ro sau đó lộn ngược mà vẫn chạy trơn tru.
Nên hệ chặn ngay lúc lưu.

Rải theo ngày là một QUY ƯỚC, và hệ nói rõ thế
-----------------------------------------------
Mục tiêu khai theo THÁNG. Muốn so luỹ kế giữa tháng thì phải rải nó ra
từng ngày, mà gió không thổi đều suốt tháng — chia đều là một phép xấp
xỉ. Hệ vẫn chia đều (không có gì tốt hơn khi chưa có hồ sơ mùa vụ),
nhưng **ghi rõ đó là chia đều** chứ không để người đọc tưởng đấy là mục
tiêu thật của riêng ngày hôm đó.
"""
import calendar

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

MUC = [('p50', 'P50'), ('p75', 'P75'), ('p90', 'P90')]


class EamEnergyTarget(models.Model):
    _name = 'eam.energy.target'
    _description = 'Mục tiêu sản lượng theo tháng'
    _order = 'plant_id, nam desc, thang'
    _rec_name = 'display_name'

    plant_id = fields.Many2one(
        'eam.location', string='Nhà máy', required=True, index=True,
        domain="[('location_type', '=', 'plant')]", ondelete='cascade')
    # Năm là CHUỖI bốn chữ số, không phải số nguyên: Odoo chấm phân
    # cách nghìn cho mọi Integer, nên năm 2026 hiện ra "2.026" trên mọi
    # màn hình. Lỗi nhỏ, nhưng nó nằm ngay cột đầu của một bảng mang đi
    # trình diễn.
    nam = fields.Char(
        string='Năm', required=True, index=True, size=4,
        default=lambda s: str(fields.Date.context_today(s).year))
    thang = fields.Selection(
        [(str(i), '%02d' % i) for i in range(1, 13)],
        string='Tháng', required=True, index=True)
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda s: s.env.company)

    p50 = fields.Float(string='P50 (kWh)', digits=(16, 1))
    p75 = fields.Float(string='P75 (kWh)', digits=(16, 1))
    p90 = fields.Float(string='P90 (kWh)', digits=(16, 1))

    nguon = fields.Char(
        string='Lấy từ đâu', required=True,
        help='Báo cáo mô phỏng gió/bức xạ, phụ lục hợp đồng vay, hay kế '
             'hoạch nội bộ — ghi rõ. Ba năm sau khi con số bị chất vấn, '
             'đây là thứ duy nhất trả lời được nó từ đâu ra.')
    cach_rai = fields.Selection(
        [('deu', 'Chia đều theo ngày'),
         ('khong', 'Không rải — chỉ so cả tháng')],
        string='Rải theo ngày', default='deu', required=True,
        help='Mục tiêu khai theo THÁNG. Chia đều là một phép xấp xỉ: gió '
             'không thổi đều suốt tháng. Chọn "không rải" nếu chỉ muốn '
             'đối chiếu vào cuối tháng.')
    ghi_chu = fields.Char(string='Ghi chú')
    display_name = fields.Char(compute='_compute_display_name', store=True)

    _uniq = models.Constraint(
        'unique(plant_id, nam, thang, company_id)',
        'Nhà máy này đã có mục tiêu cho tháng đó rồi.')

    # ==================================================================
    @api.depends('plant_id', 'nam', 'thang')
    def _compute_display_name(self):
        for r in self:
            r.display_name = '%s — %s/%s' % (
                r.plant_id.name or '', r.thang or '', r.nam or '')

    @api.constrains('p50', 'p75', 'p90')
    def _check_thu_tu(self):
        """Càng chắc chắn đạt thì con số càng THẤP."""
        for r in self:
            co = [(m, r[m]) for m, _n in MUC if r[m]]
            if len(co) < 2:
                continue
            gt = [v for _m, v in co]
            if gt != sorted(gt, reverse=True):
                raise ValidationError(_(
                    'Phải có P50 ≥ P75 ≥ P90. Đang khai %(ds)s.\n\n'
                    'P90 là mức vượt qua 90%% số năm nên nó là con số '
                    'THẤP NHẤT — ngân hàng dùng đúng mức ấy vì cần gần '
                    'như chắc chắn đạt. Khai ngược chiều thì mọi phân '
                    'tích rủi ro sau đó lộn ngược mà vẫn chạy trơn tru.',
                    ds=', '.join('%s=%s' % (m.upper(), '{:,.0f}'.format(v))
                                 for m, v in co)))

    @api.constrains('thang', 'nam')
    def _check_ky(self):
        for r in self:
            if r.thang and not 1 <= int(r.thang) <= 12:
                raise ValidationError(_('Tháng phải từ 1 tới 12.'))
            if not (r.nam or '').isdigit() or len(r.nam) != 4:
                raise ValidationError(_(
                    'Năm phải là bốn chữ số, đang khai "%s".', r.nam))

    # ==================================================================
    @api.model
    def cua_thang(self, plant, ngay):
        """Bản ghi mục tiêu của tháng chứa ngày này, nếu có."""
        return self.search([
            ('plant_id', '=', plant.id), ('nam', '=', str(ngay.year)),
            ('thang', '=', str(ngay.month))], limit=1)

    @api.model
    def luy_ke_den(self, plant, ngay):
        """Mục tiêu LUỸ KẾ tới hết ngày này, cho cả ba mức.

        Trả về dict kèm ``cach_rai`` và ``ghi_chu`` để nơi in ra nói
        được *con số này là chia đều*, chứ không trình bày nó như mục
        tiêu riêng của ngày hôm đó.

        Chưa khai mục tiêu thì trả ``do_duoc=False`` kèm lý do — KHÔNG
        trả 0. Mục tiêu bằng 0 đọc ra là "tháng này không cần phát gì",
        ngược hẳn sự thật là "chưa ai khai".
        """
        t = self.cua_thang(plant, ngay)
        if not t:
            return {'do_duoc': False, 'ly_do': _(
                'chưa khai mục tiêu cho tháng %(t)02d/%(n)d của nhà máy '
                'này', t=ngay.month, n=ngay.year)}
        so_ngay = calendar.monthrange(ngay.year, ngay.month)[1]
        if t.cach_rai == 'khong':
            # Chưa hết tháng thì KHÔNG có mục tiêu luỹ kế nào để so.
            if ngay.day < so_ngay:
                return {'do_duoc': False, 'target_id': t.id,
                        'cach_rai': 'khong', 'ly_do': _(
                            'mục tiêu tháng này khai là KHÔNG rải theo '
                            'ngày, nên chỉ đối chiếu vào ngày cuối tháng')}
            ty = 1.0
        else:
            ty = ngay.day / float(so_ngay)
        return {
            'do_duoc': True, 'target_id': t.id, 'ly_do': '',
            'cach_rai': t.cach_rai, 'ty_le': ty,
            'so_ngay_thang': so_ngay, 'ngay_thu': ngay.day,
            'p50': t.p50 * ty, 'p75': t.p75 * ty, 'p90': t.p90 * ty,
            'ca_thang': {'p50': t.p50, 'p75': t.p75, 'p90': t.p90},
            'nguon': t.nguon,
        }

    @api.model
    def dat_muc_nao(self, plant, ngay, san_luong_luy_ke):
        """Sản lượng luỹ kế này đang đạt tới mức nào.

        Trả về mã mức CAO NHẤT đã vượt, hoặc ``None`` khi chưa đạt cả
        P90. Nói "đạt P90" khi mới vượt P90 chứ chưa tới P75 là đúng —
        và nói "chưa đạt P90" là tín hiệu đáng báo động, không phải lỗi
        hiển thị.
        """
        lk = self.luy_ke_den(plant, ngay)
        if not lk.get('do_duoc'):
            return dict(lk, muc=None)
        dat = None
        for m, _n in MUC:          # p50 trước: mức cao nhất
            if lk[m] and san_luong_luy_ke >= lk[m]:
                dat = m
                break
        return dict(lk, muc=dat, san_luong=san_luong_luy_ke,
                    ty_le_p50=(100.0 * san_luong_luy_ke / lk['p50'])
                    if lk['p50'] else None)

    # ==================================================================
    def action_nhan_ban_sang_nam(self):
        """Nhân bản cả năm sang năm sau — việc khai lại 12 dòng là chỗ
        người ta bỏ qua, rồi tháng 1 năm sau không có mục tiêu nào."""
        tao = self.browse()
        for r in self:
            if self.search_count([('plant_id', '=', r.plant_id.id),
                                  ('nam', '=', str(int(r.nam) + 1)),
                                  ('thang', '=', r.thang)]):
                continue
            tao |= r.copy({'nam': str(int(r.nam) + 1),
                           'ghi_chu': _('nhân bản từ năm %s', r.nam)})
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {'type': 'info', 'sticky': False, 'message': _(
                'Nhân bản %(a)d dòng sang năm sau. Nhớ soi lại: mục tiêu '
                'năm mới hiếm khi bằng y năm cũ.', a=len(tao))},
        }
