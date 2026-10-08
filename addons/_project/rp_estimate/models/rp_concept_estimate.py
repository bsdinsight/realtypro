# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class RpConceptEstimate(models.Model):
    """Khái toán — con số mang đi xin chủ trương, lập khi chưa có thiết kế.

    Khác dự toán ở chỗ căn bản: dự toán cộng từ khối lượng bóc ra được,
    khái toán thì chưa có khối lượng nào để bóc. Nó suy ra tiền từ một
    CHỈ TIÊU duy nhất mà dự án đã biết — công suất đặt, diện tích sàn,
    chiều dài tuyến — nhân với một suất đầu tư lấy ở đâu đó.

    Vì vậy hai thứ sau đây mới là nội dung thật của khái toán, chứ không
    phải con số:

    * **Suất ấy lấy ở đâu.** Khái toán không ai kiểm chứng được bằng
      khối lượng, nên thứ duy nhất bảo vệ được nó trước hội đồng là
      nguồn: suất vốn đầu tư công bố, dự án tương tự đã quyết toán, hay
      báo giá sơ bộ. Không ghi nguồn thì nó là con số đoán.
    * **Giá mặt bằng năm nào.** Khái toán lập một năm, giải ngân trải
      hai ba năm. Gộp trượt giá vào giá gốc là về sau không tách ra
      được nữa, nên mọi dòng ở đây giữ nguyên mặt bằng giá ``price_year``
      và trượt giá đứng riêng thành một dòng tỷ lệ.

    Khái toán còn là chỗ DUY NHẤT trong hệ thống đếm đủ tổng mức đầu tư.
    BOQ chỉ chứa xây lắp và thiết bị; tiền đất, tư vấn, quản lý dự án,
    lãi vay vốn hoá và dự phòng không bao giờ có dòng BOQ nào — thiếu
    khái toán là thiếu luôn khoảng một phần tư tổng mức.

    Duyệt xong thì ĐÓNG BĂNG, cùng lý do với bản chụp lịch: mốc so sánh
    mà sửa được thì mọi báo cáo "so với khái toán duyệt" đều vô nghĩa.
    Kế hoạch đổi thì lập phiên bản mới, không sửa bản cũ.
    """
    _name = 'rp.concept.estimate'
    _description = 'Khái toán / Sơ bộ tổng mức đầu tư'
    _order = 'project_id, version desc, id desc'

    name = fields.Char(string='Phiên bản', required=True, copy=False)
    project_id = fields.Many2one(
        're.project', string='Dự án', required=True,
        ondelete='cascade', index=True)
    version = fields.Integer(string='Số hiệu', default=1)
    date_made = fields.Date(
        string='Ngày lập', required=True,
        default=lambda self: fields.Date.context_today(self))
    price_year = fields.Integer(
        string='Mặt bằng giá năm', required=True,
        default=lambda self: fields.Date.context_today(self).year,
        help='Mọi dòng trong bảng giữ nguyên giá của năm này. Phần tăng '
             'giá tới lúc giải ngân khai riêng ở dòng dự phòng trượt giá.')
    state = fields.Selection(
        [('draft', 'Nháp'), ('approved', 'Đã duyệt')],
        string='Trạng thái', default='draft', required=True, index=True)
    date_approved = fields.Date(string='Ngày duyệt', readonly=True)
    user_approved_id = fields.Many2one(
        'res.users', string='Người duyệt', readonly=True)
    currency_id = fields.Many2one(
        'res.currency', string='Tiền tệ', required=True,
        default=lambda self: self.env.company.currency_id)
    note = fields.Text(string='Căn cứ lập / lý do lập phiên bản')
    line_ids = fields.One2many(
        'rp.concept.estimate.line', 'estimate_id', string='Dòng khái toán')

    amount_build = fields.Monetary(
        string='Xây lắp & thiết bị', compute='_compute_tong', store=True)
    amount_soft = fields.Monetary(
        string='Chi phí mềm', compute='_compute_tong', store=True,
        help='Đất, tư vấn, quản lý dự án và các khoản không có dòng BOQ.')
    amount_finance = fields.Monetary(
        string='Chi phí tài chính', compute='_compute_tong', store=True)
    amount_contingency = fields.Monetary(
        string='Dự phòng', compute='_compute_tong', store=True)
    amount_total = fields.Monetary(
        string='Tổng mức đầu tư', compute='_compute_tong', store=True)
    line_count = fields.Integer(compute='_compute_tong', store=True)

    _uniq_ten = models.Constraint(
        'UNIQUE(project_id, name)',
        'Mỗi dự án không được có hai khái toán trùng tên phiên bản.')

    @api.depends('line_ids.amount_total', 'line_ids.category_id')
    def _compute_tong(self):
        for kt in self:
            xl = mem = tc = dp = 0.0
            for d in kt.line_ids:
                c = d.category_id
                if c.is_contingency:
                    dp += d.amount_total
                elif c.is_finance_cost:
                    tc += d.amount_total
                elif d.is_build:
                    xl += d.amount_total
                else:
                    mem += d.amount_total
            kt.amount_build = xl
            kt.amount_soft = mem
            kt.amount_finance = tc
            kt.amount_contingency = dp
            kt.amount_total = xl + mem + tc + dp
            kt.line_count = len(kt.line_ids)

    # ------------------------------------------------------------------
    # Đóng băng
    # ------------------------------------------------------------------
    def action_duyet(self):
        for kt in self:
            if kt.state == 'approved':
                raise UserError(_('"%s" đã duyệt rồi.', kt.display_name))
            if not kt.line_ids:
                raise UserError(_('Khái toán rỗng thì không duyệt được.'))
            # Kiểm ở đây chứ không đặt thành ràng buộc: bản nháp đang
            # dựng dở thì dòng tỷ lệ chưa trỏ vào đâu là bình thường —
            # chặn ngay lúc tạo thì không chép được phiên bản mới.
            treo = kt.line_ids.filtered(
                lambda d: d.method == 'percent' and not d.base_line_ids)
            if treo:
                raise UserError(_(
                    '%s dòng tính theo tỷ lệ nhưng chưa chỉ ra tính trên '
                    'dòng nào (%s) — các dòng này đang bằng 0.',
                    len(treo), ', '.join(treo[:3].mapped('category_id.name'))))
            thieu = kt.line_ids.filtered(lambda d: not d.source)
            if thieu:
                raise UserError(_(
                    'Còn %s dòng chưa ghi nguồn của suất (%s). Khái toán '
                    'không ai kiểm chứng được bằng khối lượng — bỏ trống '
                    'nguồn là duyệt một con số đoán.',
                    len(thieu),
                    ', '.join(thieu[:3].mapped('category_id.name'))))
            kt.write({'state': 'approved',
                      'date_approved': fields.Date.context_today(kt),
                      'user_approved_id': self.env.uid})
        return True

    def write(self, vals):
        KHOA = {'project_id', 'price_year', 'date_made', 'currency_id',
                'line_ids', 'version'}
        if KHOA & set(vals):
            xong = self.filtered(lambda k: k.state == 'approved')
            if xong:
                raise UserError(_(
                    'Khái toán "%s" đã duyệt nên không sửa được nữa. Số '
                    'liệu đổi thì bấm "Lập phiên bản mới" — giữ bản cũ '
                    'lại mới so sánh được về sau.', xong[0].display_name))
        return super().write(vals)

    def unlink(self):
        xong = self.filtered(lambda k: k.state == 'approved')
        if xong:
            raise UserError(_(
                'Không xoá được khái toán đã duyệt ("%s").',
                xong[0].display_name))
        return super().unlink()

    def action_phien_ban_moi(self):
        """Nhân bản sang bản nháp mới, giữ nguyên cách tính từng dòng."""
        self.ensure_one()
        n = max(self.search(
            [('project_id', '=', self.project_id.id)]).mapped('version')) + 1
        moi = self.copy({
            'name': 'KT-V%d' % n,
            'version': n,
            'state': 'draft',
            'date_made': fields.Date.context_today(self),
            'date_approved': False,
            'user_approved_id': False,
        })
        # One2many mặc định copy=False nên bản mới ra rỗng — phải tự
        # chép từng dòng. Chép tay luôn tiện: giữ được bản đồ cũ→mới để
        # đấu lại các dòng tính theo tỷ lệ, thay vì tin vào thứ tự.
        cu_moi = {}
        for d in self.line_ids.sorted(lambda x: (x.sequence, x.id)):
            cu_moi[d.id] = d.copy({'estimate_id': moi.id,
                                   'base_line_ids': [(5, 0, 0)]}).id
        # Dòng tỷ lệ chép sang vẫn trỏ về dòng của bản CŨ. Không đấu lại
        # thì sửa bản cũ là bản mới nhảy theo — mà bản cũ đã đóng băng,
        # nên bản mới sẽ vĩnh viễn tính trên số của bản cũ.
        for d in self.line_ids.filtered('base_line_ids'):
            self.env['rp.concept.estimate.line'].browse(
                cu_moi[d.id]).base_line_ids = [
                    (6, 0, [cu_moi[b.id] for b in d.base_line_ids
                            if b.id in cu_moi])]
        return {
            'type': 'ir.actions.act_window',
            'name': _('Khái toán'),
            'res_model': 'rp.concept.estimate',
            'res_id': moi.id,
            'view_mode': 'form',
        }


class RpConceptEstimateLine(models.Model):
    """Một dòng khái toán = một CÁCH TÍNH, không phải một con số gõ tay.

    Ba cách, vì thực tế chỉ có ba kiểu ước:

    * **Theo suất đầu tư** — chỉ tiêu × suất. Dùng cho phần xây lắp và
      thiết bị, nơi đã có suất công bố hay dự án tương tự để dựa.
    * **Theo tỷ lệ của nhóm khác** — tư vấn, quản lý dự án, dự phòng
      luôn tính bằng phần trăm của phần xây lắp. Khai thành tỷ lệ thì
      sửa phần xây lắp một chỗ là cả bảng chạy theo; khai thành số thì
      mỗi lần sửa phải gõ lại hết và chắc chắn có chỗ quên.
    * **Nhập thẳng số tiền** — tiền thuê đất, phí thu xếp vốn: đã có
      hợp đồng hoặc thông báo, không việc gì phải ước.
    """
    _name = 'rp.concept.estimate.line'
    _description = 'Dòng khái toán'
    _order = 'estimate_id, sequence, id'

    estimate_id = fields.Many2one(
        'rp.concept.estimate', string='Khái toán', required=True,
        ondelete='cascade', index=True)
    sequence = fields.Integer(string='Thứ tự', default=10)
    project_id = fields.Many2one(
        related='estimate_id.project_id', store=True, index=True)
    currency_id = fields.Many2one(
        related='estimate_id.currency_id', store=True)
    state = fields.Selection(related='estimate_id.state', store=True)
    category_id = fields.Many2one(
        'rp.cost.category', string='Nhóm chi phí', required=True,
        ondelete='restrict', index=True,
        help='Dùng chung cây nhóm chi phí với dự toán và BOQ — nhờ vậy '
             'về sau đối chiếu khái toán với dự toán chỉ là một phép '
             'ghép, không phải ánh xạ tay.')
    name = fields.Char(string='Diễn giải')

    method = fields.Selection(
        [('rate', 'Theo suất đầu tư'),
         ('percent', 'Theo tỷ lệ của nhóm khác'),
         ('amount', 'Nhập thẳng số tiền')],
        string='Cách tính', default='rate', required=True)

    # --- cách 1: chỉ tiêu × suất
    driver_qty = fields.Float(string='Chỉ tiêu', digits=(16, 2))
    driver_uom = fields.Selection(
        [('mw', 'MW công suất'), ('gfa', 'm² sàn'), ('m2', 'm² đất'),
         ('km', 'km tuyến'), ('unit', 'căn / vị trí'), ('other', 'khác')],
        string='Đơn vị chỉ tiêu', default='mw')
    rate = fields.Monetary(
        string='Suất đầu tư', help='Tiền trên một đơn vị chỉ tiêu.')

    # --- cách 2: % của các dòng khác
    base_line_ids = fields.Many2many(
        'rp.concept.estimate.line', 'rp_concept_est_line_base_rel',
        'line_id', 'base_line_id', string='Tính trên các dòng',
        domain="[('estimate_id', '=', estimate_id), ('id', '!=', id)]")
    percent = fields.Float(string='Tỷ lệ %', digits=(16, 3))
    base_amount = fields.Monetary(
        string='Số gốc để tính tỷ lệ', compute='_compute_amount',
        store=True)

    # --- cách 3
    amount_input = fields.Monetary(string='Số tiền khai')

    amount_total = fields.Monetary(
        string='Thành tiền', compute='_compute_amount', store=True)
    is_build = fields.Boolean(
        string='Thuộc xây lắp & thiết bị', default=True,
        help='Bỏ dấu cho các khoản không bao giờ có dòng BOQ: đất, tư '
             'vấn, quản lý dự án. Chỉ dùng để tách nhóm khi báo cáo.')

    # --- nguồn: phần bắt buộc khi duyệt
    source = fields.Selection(
        [('norm', 'Suất vốn đầu tư công bố'),
         ('similar', 'Dự án tương tự đã làm'),
         ('quote', 'Báo giá sơ bộ nhà cung cấp'),
         ('contract', 'Đã có hợp đồng / thông báo'),
         ('rule', 'Thông lệ ngành / tỷ lệ chuẩn'),
         ('assumption', 'Giả định nội bộ')],
        string='Nguồn của suất', index=True)
    source_ref = fields.Char(
        string='Dẫn chứng',
        help='Số quyết định công bố suất, tên dự án tương tự, tên nhà '
             'cung cấp báo giá…')
    source_project_id = fields.Many2one(
        're.project', string='Dự án tham chiếu')
    note = fields.Text(string='Ghi chú')

    @api.depends('method', 'driver_qty', 'rate', 'percent', 'amount_input',
                 'base_line_ids', 'base_line_ids.amount_total')
    def _compute_amount(self):
        for d in self:
            goc = 0.0
            if d.method == 'rate':
                tien = (d.driver_qty or 0.0) * (d.rate or 0.0)
            elif d.method == 'percent':
                goc = sum(d.base_line_ids.mapped('amount_total'))
                tien = goc * (d.percent or 0.0) / 100.0
            else:
                tien = d.amount_input or 0.0
            d.base_amount = goc
            d.amount_total = tien

    @api.onchange('category_id')
    def _onchange_category(self):
        """Nhóm dự phòng và tài chính gần như luôn tính theo tỷ lệ."""
        for d in self:
            c = d.category_id
            if c and (c.is_contingency or c.is_finance_cost
                      or c.is_land_cost):
                d.is_build = False
            if c and c.is_contingency and d.method == 'rate':
                d.method = 'percent'

    @api.constrains('base_line_ids')
    def _check_vong_lap(self):
        """Chặn dòng tỷ lệ tính vòng về chính nó.

        Dự phòng tính trên tư vấn, tư vấn tính trên xây lắp — chuỗi tỷ
        lệ nhiều tầng là bình thường và phải cho phép. Nhưng để lọt một
        vòng kín thì compute chạy không bao giờ dừng.
        """
        for d in self:
            da_qua, hang_doi = set(), list(d.base_line_ids)
            while hang_doi:
                x = hang_doi.pop()
                if x.id == d.id:
                    raise ValidationError(_(
                        'Dòng "%s" đang tính vòng về chính nó.',
                        d.category_id.name or d.name or ''))
                if x.id in da_qua:
                    continue
                da_qua.add(x.id)
                hang_doi += list(x.base_line_ids)

    def _chan_khi_duyet(self):
        xong = self.filtered(lambda d: d.estimate_id.state == 'approved')
        if xong:
            raise UserError(_(
                'Khái toán "%s" đã duyệt — không thêm, sửa hay xoá dòng '
                'được nữa.', xong[0].estimate_id.display_name))

    @api.model_create_multi
    def create(self, vals_list):
        dong = super().create(vals_list)
        dong._chan_khi_duyet()
        return dong

    def write(self, vals):
        # Trường compute được ghi lại khi dòng gốc đổi — không chặn.
        if set(vals) - {'amount_total', 'base_amount'}:
            self._chan_khi_duyet()
        return super().write(vals)

    def unlink(self):
        self._chan_khi_duyet()
        return super().unlink()
