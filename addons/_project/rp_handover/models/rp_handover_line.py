# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models


class RpHandoverLine(models.Model):
    """Một vị trí trong biên bản bàn giao.

    Đây là chỗ đồng hồ bảo hành của TRỤ ĐÓ bắt đầu chạy.
    """
    _name = 'rp.handover.line'
    _description = 'Dòng bàn giao theo vị trí'
    _order = 'location_code, id'
    _rec_name = 'location_code'

    handover_id = fields.Many2one(
        'rp.handover', string='Biên bản', required=True, ondelete='cascade',
        index=True)
    location_id = fields.Many2one(
        'eam.location', string='Vị trí', required=True, ondelete='restrict',
        index=True)
    location_code = fields.Char(
        related='location_id.code', store=True, string='Mã vị trí')
    date_toc = fields.Date(
        string='Ngày nghiệm thu (TOC)',
        help='Lấy từ cổng nghiệm thu trong sổ dựng máy. ĐÂY là mốc bảo '
             'hành bắt đầu chạy — của chính trụ này, không phải của dự án.')
    warranty_end = fields.Date(
        string='Bảo hành đến', compute='_compute_warranty', store=True,
        readonly=False)

    lot_ids = fields.Many2many(
        'rp.equipment.lot', string='Lô thiết bị khớp')
    lot_count = fields.Integer(string='Số lô', compute='_compute_kiem',
                               store=True)
    asset_ids = fields.Many2many('eam.asset', string='Tài sản')
    asset_count = fields.Integer(string='Số tài sản',
                                 compute='_compute_kiem', store=True)
    has_serial = fields.Boolean(
        string='Có sê-ri', compute='_compute_kiem', store=True)
    supplier_id = fields.Many2one(
        'res.partner', string='Nhà cung cấp', compute='_compute_kiem',
        store=True)
    contract_id = fields.Many2one(
        'rp.contract', string='Hợp đồng', compute='_compute_kiem',
        store=True)
    lot_value = fields.Monetary(
        string='Giá trị lô', compute='_compute_kiem', store=True)
    currency_id = fields.Many2one(
        related='handover_id.company_id.currency_id', string='Tiền tệ')

    completeness = fields.Float(
        string='Độ đầy đủ (%)', compute='_compute_kiem', store=True,
        digits=(16, 1), aggregator=False)
    missing = fields.Char(
        string='Còn thiếu', compute='_compute_kiem', store=True)
    kept_warranty = fields.Integer(
        string='Giữ bảo hành riêng', readonly=True,
        help='Số tài sản ĐÃ CÓ hạn bảo hành khác mặc định nên được giữ '
             'nguyên. Thường là cấu phần tân trang hoặc thay thế, có bảo '
             'hành riêng của nhà cung cấp.')
    state = fields.Selection(
        [('pending', 'Chờ bàn giao'), ('done', 'Đã bàn giao')],
        string='Trạng thái', default='pending', required=True, index=True)
    note = fields.Char(string='Ghi chú')
    company_id = fields.Many2one(related='handover_id.company_id',
                                 store=True)

    _uniq = models.Constraint(
        'UNIQUE(handover_id, location_id)',
        'Mỗi vị trí chỉ có một dòng trong một biên bản.')

    @api.depends('date_toc', 'handover_id.warranty_months')
    def _compute_warranty(self):
        for l in self:
            thang = l.handover_id.warranty_months or 0
            l.warranty_end = (l.date_toc + relativedelta(months=thang)
                              if l.date_toc and thang else False)

    @api.depends('lot_ids', 'asset_ids', 'asset_ids.serial_no', 'date_toc')
    def _compute_kiem(self):
        for l in self:
            l.lot_count = len(l.lot_ids)
            l.asset_count = len(l.asset_ids)
            l.has_serial = bool(l.asset_ids) and all(
                a.serial_no for a in l.asset_ids)
            l.supplier_id = l.lot_ids[:1].supplier_id
            l.contract_id = (l.lot_ids[:1].contract_id
                             or l.handover_id.contract_id)
            l.lot_value = sum(l.lot_ids.mapped('value'))
            # Độ đầy đủ: năm thứ phải có để ba năm sau còn trả lời được
            # câu "con này do ai cấp, theo hợp đồng nào, bảo hành tới bao
            # giờ". Thiếu cái nào thì ghi tên cái đó ra.
            kiem = [
                ('ngày nghiệm thu', bool(l.date_toc)),
                ('tài sản', bool(l.asset_ids)),
                ('sê-ri', l.has_serial),
                ('lô thiết bị', bool(l.lot_ids)),
                ('nhà cung cấp', bool(l.supplier_id)),
            ]
            dat = [x for x, ok in kiem if ok]
            thieu = [x for x, ok in kiem if not ok]
            l.completeness = len(dat) / len(kiem) * 100.0
            l.missing = ', '.join(thieu) or False

    # ------------------------------------------------------------------
    def _ban_giao(self):
        """Nối tài sản vào dây chuyền vận hành.

        Bốn việc, và việc nào thiếu cũng làm hỏng một câu hỏi về sau:

        * đặt **ngày vận hành và hạn bảo hành theo TOC của chính trụ này**
          — không có thì cả đội máy dùng chung một ngày hết hạn;
        * ghi **nguồn gốc** trỏ về lô thiết bị, hợp đồng, biên bản — không
          có thì ba năm sau phải đi khảo cổ;
        * dựng **đồng hồ giờ máy** bắt đầu từ 0 — không có thì mọi kế
          hoạch bảo trì theo giờ im lặng không bao giờ tới hạn;
        * **áp lịch bảo trì** với mốc tính từ ngày bàn giao — không có thì
          chu kỳ đầu tiên đếm từ ngày lắp, tức đã quá hạn ngay khi nhận.
        """
        self.ensure_one()
        h = self.handover_id
        goc = _('Bàn giao %(bb)s · %(hd)s%(lo)s',
                bb=h.name,
                hd=self.contract_id.name or _('(chưa rõ hợp đồng)'),
                lo=(' · lô: %s' % ', '.join(self.lot_ids.mapped('name')[:4]))
                if self.lot_ids else '')
        giu = 0
        for a in self.asset_ids:
            v = {'origin': goc, 'state': 'active'}
            if self.date_toc:
                v['date_commissioned'] = self.date_toc
            if self.warranty_end:
                # LUẬT: bàn giao KHÔNG BAO GIỜ KÉO DÀI bảo hành, chỉ
                # chỉnh về đúng ngày nghiệm thu của từng trụ.
                #
                # Cấu phần tân trang hay thay thế mang bảo hành riêng của
                # nhà cung cấp, thường NGẮN hơn. Áp mặc định dự án lên là
                # tuyên bố một thứ còn được bảo hành trong khi không —
                # đo trên dữ liệu thật: hai hộp số tân trang hết hạn sau
                # 62 ngày suýt bị kéo dài thêm 15 tháng, im lặng. Người
                # đọc tin vào đó rồi không đặt phụ tùng dự phòng.
                #
                # Nhưng chặn MỌI thay đổi thì quá tay: 22 tua-bin đang
                # dùng chung một ngày tính từ COD sẽ không bao giờ nhận
                # được ngày riêng của mình, tức mất đúng mục đích của cả
                # cuộc bàn giao. Nên chỉ giữ khi ngày tính ra DÀI HƠN —
                # rút ngắn về đúng ngày nghiệm thu của trụ là việc cần
                # làm, kéo dài mới là bịa ra phạm vi bảo hành.
                if a.warranty_end and self.warranty_end > a.warranty_end:
                    giu += 1
                else:
                    v['warranty_end'] = self.warranty_end
                    v['warranty_note'] = _(
                        'Bảo hành %(n)d tháng kể từ ngày nghiệm thu bàn '
                        'giao %(d)s của chính vị trí này.',
                        n=h.warranty_months, d=self.date_toc or '')
            if self.supplier_id and not a.manufacturer_id:
                v['manufacturer_id'] = self.supplier_id.id
            a.write(v)

        # Đồng hồ giờ máy — bắt đầu từ 0 tại ngày bàn giao
        M = self.env['eam.meter']
        dh = M._lay_hoac_tao(self.location_id, 'operating_hours')
        if not dh.reading_ids and self.date_toc:
            self.env['eam.meter.reading'].create({
                'meter_id': dh.id, 'date': self.date_toc, 'value': 0.0,
                'source': 'migration',
                'note': _('Mốc 0 tại ngày bàn giao %s', h.name)})

        # Lịch bảo trì — mốc tính từ ngày bàn giao
        S = self.env['rp.erection.step']  # noqa: giữ import gọn
        PS = self.env['eam.pm.schedule']
        for p in self.env['eam.pm.plan'].search([]):
            if self.location_id not in p._vi_tri_ap_dung():
                continue
            d = PS.search([('plan_id', '=', p.id),
                           ('location_id', '=', self.location_id.id)],
                          limit=1)
            if not d:
                d = PS.create({'plan_id': p.id,
                               'location_id': self.location_id.id})
            if self.date_toc and not d.date_start:
                d.date_start = self.date_toc
        self.kept_warranty = giu
        self.state = 'done'
        return True
