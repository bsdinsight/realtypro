# -*- coding: utf-8 -*-
import re

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class RpHandover(models.Model):
    """Biên bản bàn giao từ dự án sang vận hành.

    Khúc không ai sở hữu
    --------------------
    Phần mềm quản lý dự án dừng ở ngày vận hành thương mại. Phần mềm quản
    lý tài sản bắt đầu từ đó. Giữa hai bên là một cuộc **gõ lại bằng tay
    vài trăm bản ghi** — và mọi cuộc bàn giao EPC sang O&M trên đời đều
    mất dữ liệu ở đúng khúc này. Thứ mất đi đắt nhất là **đồng hồ bảo
    hành**: ba năm sau hộp số hỏng, không ai trả lời nổi *con này do ai
    cấp, theo hợp đồng nào, bảo hành tới khi nào*.

    Năm quyết định thiết kế
    -----------------------

    **① Bàn giao theo TỪNG VỊ TRÍ, không theo cả dự án.** Nhà máy điện
    gió bàn giao từng trụ một: trụ số 1 xong trước trụ số 30 có khi tám
    tháng. Gộp thành một mốc "COD" duy nhất là **xoá mất đồng hồ bảo
    hành riêng của từng trụ** — thứ đắt nhất trong cả cuộc bàn giao.

    **② Bảo hành chạy từ ngày nghiệm thu của CHÍNH trụ đó**, lấy từ cổng
    nghiệm thu trong sổ dựng máy. Trước bàn giao, cả đội máy dùng chung
    một ngày hết hạn; sau bàn giao, mỗi trụ một ngày.

    **③ Bàn giao là NỐI DẤU VẾT, không phải chép dữ liệu.** Tài sản phải
    giữ đường về: lô thiết bị nào, hợp đồng nào, nhà cung cấp nào, biên
    bản nào chuyển. Chép xong mà không nối thì vẫn phải đi khảo cổ.

    **④ Được phép bàn giao khi còn THIẾU, nhưng phải nói ra thiếu gì.**
    Sê-ri thường chưa có lúc bàn giao vì nhà thầu chưa nộp hồ sơ hoàn
    công. Chặn tới khi đủ thì bàn giao không bao giờ xảy ra; cho qua im
    lặng thì chỗ thiếu không bao giờ được điền. Nên có **độ đầy đủ** và
    danh sách thiếu gì.

    **⑤ Mã không khớp phải BÁO.** Sổ lô thiết bị ghi ``WTG-01``, vị trí
    chức năng ghi ``T01`` — hai hệ đặt tên khác nhau là chuyện thường.
    Khớp theo quy ước, nhưng cái nào không khớp thì liệt kê ra chứ không
    lặng lẽ bỏ qua.
    """
    _name = 'rp.handover'
    _description = 'Biên bản bàn giao sang vận hành'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_handover desc, id desc'

    name = fields.Char(string='Số hiệu', copy=False, index=True,
                       default=lambda s: _('Mới'), tracking=True)
    project_id = fields.Many2one(
        're.project', string='Dự án', required=True, ondelete='restrict',
        index=True, tracking=True)
    plant_id = fields.Many2one(
        'eam.location', string='Nhà máy', required=True,
        domain="[('location_type', '=', 'plant')]", tracking=True)
    date_handover = fields.Date(
        string='Ngày lập', required=True, tracking=True,
        default=lambda s: fields.Date.context_today(s))
    gate_id = fields.Many2one(
        'rp.erection.gate', string='Cổng đánh dấu bàn giao',
        help='Vị trí nào đã qua cổng này thì sẵn sàng bàn giao. Thường là '
             'cổng nghiệm thu bàn giao trong sổ dựng máy — và ngày qua '
             'cổng chính là ngày bắt đầu chạy bảo hành của trụ đó.')
    contract_id = fields.Many2one(
        'rp.contract', string='Hợp đồng cấp bảo hành',
        domain="[('project_id', '=', project_id)]", tracking=True)
    warranty_months = fields.Integer(
        string='Bảo hành (tháng)', default=60, required=True, tracking=True)

    state = fields.Selection(
        [('draft', 'Nháp'), ('confirmed', 'Đã chốt danh sách'),
         ('done', 'Đã bàn giao')],
        string='Trạng thái', default='draft', required=True, tracking=True,
        copy=False)
    line_ids = fields.One2many(
        'rp.handover.line', 'handover_id', string='Chi tiết theo vị trí')

    # LƯU cả bốn: trường tính KHÔNG lưu thì không đưa vào bộ lọc được,
    # mà "hồ sơ còn khuyết" đúng là bộ lọc người ta cần nhất ở màn này.
    line_count = fields.Integer(string='Số vị trí', store=True,
                                compute='_compute_thong_ke')
    done_count = fields.Integer(string='Đã bàn giao', store=True,
                                compute='_compute_thong_ke')
    completeness = fields.Float(
        string='Độ đầy đủ hồ sơ (%)', compute='_compute_thong_ke',
        store=True, digits=(16, 1), aggregator=False,
        help='Trung bình độ đầy đủ của các dòng. Dưới 100% nghĩa là bàn '
             'giao được nhưng hồ sơ còn khuyết — xem cột thiếu gì.')
    missing_serial = fields.Integer(string='Thiếu sê-ri', store=True,
                                    compute='_compute_thong_ke')
    missing_lot = fields.Integer(string='Không khớp lô thiết bị',
                                 store=True, compute='_compute_thong_ke')
    unmatched_note = fields.Text(
        string='Lô thiết bị không khớp vị trí nào', readonly=True,
        help='Khớp theo quy ước đặt tên. Cái nào không khớp thì liệt kê '
             'ra đây chứ không lặng lẽ bỏ qua.')
    note = fields.Text(string='Ghi chú')
    company_id = fields.Many2one(
        'res.company', string='Công ty', required=True,
        default=lambda self: self.env.company, index=True)

    @api.depends('line_ids.state', 'line_ids.completeness',
                 'line_ids.has_serial', 'line_ids.lot_count')
    def _compute_thong_ke(self):
        for h in self:
            ds = h.line_ids
            h.line_count = len(ds)
            h.done_count = len(ds.filtered(lambda l: l.state == 'done'))
            h.completeness = (sum(ds.mapped('completeness')) / len(ds)
                              if ds else 0.0)
            h.missing_serial = len(ds.filtered(lambda l: not l.has_serial))
            h.missing_lot = len(ds.filtered(lambda l: not l.lot_count))

    @api.model_create_multi
    def create(self, vals_list):
        for v in vals_list:
            if not v.get('name') or v['name'] == _('Mới'):
                v['name'] = self.env['ir.sequence'].next_by_code(
                    'rp.handover') or '/'
        return super().create(vals_list)

    @api.onchange('project_id')
    def _onchange_project(self):
        if self.project_id and 'plant_location_id' in self.project_id._fields:
            self.plant_id = self.project_id.plant_location_id

    # ------------------------------------------------------------------
    # Khớp mã lô thiết bị với mã vị trí
    # ------------------------------------------------------------------
    @staticmethod
    def _chuan_ma(s):
        """Rút phần SỐ của mã để khớp hai hệ đặt tên.

        Sổ lô thiết bị ghi ``WTG-01``, vị trí chức năng ghi ``T01``. Hai
        hệ đặt tên khác nhau là chuyện thường — cái đứng sau cùng và là
        số mới là thứ thật sự chỉ ra trụ nào.
        """
        if not s:
            return None
        m = re.findall(r'(\d+)', str(s))
        return int(m[-1]) if m else None

    def action_quet(self):
        """Quét: vị trí nào đã qua cổng, lô thiết bị nào khớp vào đó."""
        self.ensure_one()
        if self.state == 'done':
            raise UserError(_('Biên bản đã bàn giao, không quét lại được.'))
        L = self.env['eam.location']
        S = self.env['rp.erection.step']
        Lot = self.env['rp.equipment.lot']
        A = self.env['eam.asset']

        vt = L.search([('id', 'child_of', self.plant_id.id),
                       ('location_type', '=', 'position')])
        # Cổng nghiệm thu: chỉ lấy vị trí ĐÃ QUA cổng. Không có cổng thì
        # lấy hết — nhưng khi đó không có ngày bắt đầu bảo hành, và dòng
        # sẽ tự báo thiếu.
        ngay_toc = {}
        if self.gate_id:
            for s in S.search([('gate_id', '=', self.gate_id.id),
                               ('location_id', 'in', vt.ids),
                               ('state', '=', 'done')]):
                ngay_toc[s.location_id.id] = s.date_done
            vt = vt.filtered(lambda l: l.id in ngay_toc)

        lots = Lot.search([('project_id', '=', self.project_id.id)])
        theo_so = {}
        for lo in lots:
            k = self._chuan_ma(lo.turbine_no)
            if k is not None:
                theo_so.setdefault(k, []).append(lo.id)

        self.line_ids.filtered(lambda l: l.state != 'done').unlink()
        da_co = self.line_ids.mapped('location_id')
        moi = []
        dung = set()
        for l in vt - da_co:
            k = self._chuan_ma(l.code)
            ids = theo_so.get(k, [])
            dung.update(ids)
            ts = A.search([('current_location_id', 'child_of', l.id)])
            moi.append({
                'handover_id': self.id,
                'location_id': l.id,
                'date_toc': ngay_toc.get(l.id) or False,
                'lot_ids': [(6, 0, ids)],
                'asset_ids': [(6, 0, ts.ids)],
            })
        self.env['rp.handover.line'].create(moi)

        # Lô không khớp vị trí nào — nói ra, đừng bỏ qua
        thua = lots.filtered(lambda x: x.id not in dung)
        if thua:
            self.unmatched_note = '\n'.join(
                '· %s — %s (trụ ghi: %s)'
                % (x.name or '', dict(Lot._fields['equip_type'].selection)
                   .get(x.equip_type, ''), x.turbine_no or '— trống —')
                for x in thua[:40])
        else:
            self.unmatched_note = False
        self.state = 'confirmed'
        return True

    # ------------------------------------------------------------------
    def action_ban_giao(self):
        """Thực hiện bàn giao: nối tài sản, đặt bảo hành, dựng đồng hồ, lịch."""
        for h in self:
            if h.state == 'draft':
                raise UserError(_('Chốt danh sách trước khi bàn giao.'))
            cho = h.line_ids.filtered(lambda l: l.state != 'done')
            if not cho:
                raise UserError(_('Không còn vị trí nào chờ bàn giao.'))
            for l in cho:
                l._ban_giao()
            h.state = 'done'
        return True

    def action_ve_nhap(self):
        for h in self:
            if h.line_ids.filtered(lambda l: l.state == 'done'):
                raise UserError(_(
                    'Đã có vị trí bàn giao xong — không quay về nháp được. '
                    'Bàn giao là mốc pháp lý: quay lui sẽ làm đồng hồ bảo '
                    'hành đã chạy biến mất mà không ai biết.'))
            h.state = 'draft'
        return True

    def action_mo_tai_san(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Tài sản đã bàn giao — %s', self.name),
            'res_model': 'eam.asset',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.line_ids.mapped('asset_ids').ids)],
        }
