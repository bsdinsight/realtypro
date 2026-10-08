# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class EamWorkOrder(models.Model):
    """Lệnh công việc — chứng từ CHO PHÉP tiêu giờ công, vật tư và thời gian.

    Tên gọi
    -------
    Maximo và ISO 14224 gọi *work order*; SAP PM gọi *maintenance order*.
    Hai cái là một thứ. Tiếng Việt dùng "lệnh công việc".

    **Đừng gọi là "lệnh công tác".** Trong ngành điện Việt Nam, *phiếu
    công tác* và *lệnh công tác* là hai chứng từ AN TOÀN do quy chuẩn
    định nghĩa (mục 3.8 QCVN 25:2025/BCT, hiệu lực 08/08/2025, thay
    QCVN 01:2020/BCT) — giấy cho phép làm việc trên thiết bị điện, do
    người có thẩm quyền cấp. Lệnh công việc ở đây là chứng từ QUẢN LÝ
    BẢO TRÌ, nó **trỏ tới** phiếu công tác chứ không đóng vai phiếu đó.
    Gộp hai thứ là vừa làm hỏng hồ sơ an toàn vừa làm hỏng hồ sơ bảo trì.

    Bốn quyết định thiết kế, cả bốn đều ngược trực giác
    ---------------------------------------------------

    **① Dừng máy ≠ hỏng ≠ lệnh công việc.** Ba thực thể liên kết nhưng
    độc lập. Rất nhiều lần dừng chỉ cần khởi động lại từ xa: có khoảng
    dừng, không có hỏng, không có lệnh công việc. Ngược lại bảo trì theo
    kế hoạch có lệnh công việc mà không có hỏng. Nên ``is_failure`` là
    một ô KHAI TAY, không suy từ việc có lệnh công việc hay không — suy
    kiểu đó thì MTBF sai hoàn toàn, và sai theo hướng đẹp hơn thực tế.

    **② Người LÀM khác người TRẢ TIỀN.** Hãng chế tạo có thể tự cử người
    tới sửa mà chủ đầu tư vẫn phải trả, vì đã hết bảo hành. Ngược lại tổ
    của chủ đầu tư làm một việc mà chi phí đòi được từ nhà thầu O&M. Nên
    ``executor`` và ``cost_bearer`` là HAI trường. Gộp lại là mất dấu
    tiền đòi được — và đó là phần lớn giá trị của cả module này.

    **③ "Đang làm" lâu ngày thường là ĐANG CHỜ, không phải đang làm.**
    Một lệnh mở 14 ngày hiếm khi có người làm suốt 14 ngày. Không ghi lý
    do chờ thì không phân biệt được *sửa chậm* với *chờ một cái cẩu bánh
    xích phải huy động cả tuần*. Và lý do chờ đúng là chỗ chế tài hợp
    đồng O&M cắn vào. Nên trạng thái vẫn là "đang làm", còn việc chờ là
    một cờ riêng đo được.

    **④ Tổng chi phí thật = chi phí can thiệp + SẢN LƯỢNG MẤT.** Vật tư
    và giờ công là phần nhìn thấy; phần lớn tiền nằm ở sản lượng không
    phát được trong lúc máy dừng. Chỉ nhìn chi phí can thiệp thì bảo trì
    phòng ngừa luôn trông như một khoản chi vô ích. ``cost_full`` ghép cả
    hai, và đó là con số dùng để biện minh đầu tư phòng ngừa.
    """
    _name = 'eam.work.order'
    _description = 'Lệnh công việc'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'priority desc, date_planned_start, id desc'

    name = fields.Char(string='Số hiệu', copy=False, index=True,
                       default=lambda s: _('Mới'), tracking=True)
    title = fields.Char(string='Nội dung công việc', required=True,
                        tracking=True)
    description = fields.Text(string='Diễn giải')

    # ------------------------------------------------------------------
    # Phân loại
    # ------------------------------------------------------------------
    work_type = fields.Selection(
        [('corrective', 'Sửa chữa khắc phục'),
         ('preventive', 'Bảo trì phòng ngừa'),
         ('predictive', 'Bảo trì theo trạng thái'),
         ('inspection', 'Kiểm tra, xem xét'),
         ('statutory', 'Kiểm định bắt buộc'),
         ('modification', 'Cải tạo, nâng cấp'),
         ('commissioning', 'Chạy thử, nghiệm thu'),
         ('other', 'Khác')],
        string='Loại công việc', required=True, default='corrective',
        tracking=True,
        help='"Kiểm định bắt buộc" tách riêng vì nó có thời hạn do pháp '
             'luật đặt, không phải do mình chọn — quá hạn là phải dừng '
             'thiết bị, không phải chỉ số xấu đi.')
    priority = fields.Selection(
        [('0', 'Thấp'), ('1', 'Bình thường'),
         ('2', 'Cao'), ('3', 'Khẩn cấp')],
        string='Mức ưu tiên', default='1', required=True, tracking=True)

    location_id = fields.Many2one(
        'eam.location', string='Vị trí', required=True, ondelete='restrict',
        index=True, tracking=True,
        help='Công việc làm ở một CHỖ. Thiết bị đang nằm ở đó suy ra từ '
             'lịch sử lắp đặt.')
    asset_id = fields.Many2one(
        'eam.asset', string='Thiết bị', compute='_compute_asset',
        store=True, readonly=False, index=True, tracking=True,
        help='Tự suy từ vị trí và ngày dự kiến. Sửa được khi cần chỉ '
             'đích danh một cấu phần khác.')
    category_id = fields.Many2one(
        related='asset_id.category_id', store=True, string='Loại cấu phần')

    # Chiến dịch: thay cả 30 hộp số thì mỗi máy một lệnh, gom về một lệnh
    # cha. Không nhân bản nội dung, và không gộp 30 máy vào một lệnh —
    # gộp thì mất lịch sử riêng của từng máy.
    parent_id = fields.Many2one(
        'eam.work.order', string='Thuộc chiến dịch', ondelete='set null',
        index=True,
        help='Công việc lặp trên nhiều máy (thay cả đội hộp số, hiệu '
             'chỉnh góc cánh toàn nhà máy): mỗi máy một lệnh riêng, gom '
             'về một lệnh cha. Mỗi máy có lịch, chi phí và lịch sử hỏng '
             'riêng nên không được gộp.')
    child_ids = fields.One2many(
        'eam.work.order', 'parent_id', string='Lệnh trong chiến dịch')
    child_count = fields.Integer(
        string='Số lệnh con', compute='_compute_child_count', store=True)

    outage_id = fields.Many2one(
        'eam.outage', string='Khoảng dừng', ondelete='set null', index=True,
        tracking=True,
        help='Khoảng dừng mà công việc này xử lý. Để trống khi làm được '
             'mà không phải dừng máy — và nhiều việc đúng là như vậy.')

    # ------------------------------------------------------------------
    # Ai làm, ai trả tiền — HAI chuyện khác nhau
    # ------------------------------------------------------------------
    executor = fields.Selection(
        [('own_team', 'Tổ của chủ đầu tư'),
         ('om_contractor', 'Nhà thầu O&M'),
         ('oem', 'Hãng chế tạo'),
         ('third_party', 'Đơn vị bên ngoài khác')],
        string='Bên thực hiện', default='own_team', required=True,
        tracking=True)
    contractor_id = fields.Many2one(
        'res.partner', string='Đơn vị thực hiện', tracking=True,
        help='Khai khi bên thực hiện không phải tổ của mình.')
    cost_bearer = fields.Selection(
        [('owner', 'Chủ đầu tư tự chịu'),
         ('warranty', 'Bảo hành thiết bị'),
         ('om_contract', 'Trong giá hợp đồng O&M'),
         ('om_chargeable', 'Đòi lại nhà thầu O&M'),
         ('insurance', 'Bảo hiểm'),
         ('undetermined', 'Chưa quy')],
        # Hai cái bẫy ở đây đánh nhau, và lối ra là bỏ cả hai:
        #
        # ① KHÔNG khai ``default``. Trường vừa tính vừa cho sửa mà có
        #    default thì Odoo đưa default vào vals lúc tạo, hàm tính coi
        #    như giá trị "đã được cung cấp" nên KHÔNG chạy — mọi lệnh mới
        #    ra "Chưa quy" dù khoảng dừng đã quy trách nhiệm rõ ràng. Im
        #    lặng, không lỗi.
        # ② KHÔNG khai ``required=True``. Odoo CHÈN giá trị rỗng trước
        #    rồi mới tính trường lưu, nên ràng buộc NOT NULL nổ ngay lúc
        #    chèn: "null value in column cost_bearer violates not-null".
        #
        # Nên bắt buộc được bảo đảm bằng chính hàm tính (luôn trả về một
        # giá trị, cùng lắm là 'undetermined') và bằng cổng đóng lệnh.
        string='Bên chịu chi phí',
        compute='_compute_cost_bearer', store=True, readonly=False,
        tracking=True,
        help='KHÁC bên thực hiện. Hãng chế tạo tự cử người tới sửa mà '
             'chủ đầu tư vẫn trả nếu đã hết bảo hành; tổ của mình làm mà '
             'chi phí đòi lại được nhà thầu. Suy sẵn từ khoảng dừng nếu '
             'có, và sửa được.')
    user_id = fields.Many2one(
        'res.users', string='Người phụ trách', tracking=True,
        default=lambda s: s.env.user)

    # ------------------------------------------------------------------
    # Lịch và trạng thái
    # ------------------------------------------------------------------
    date_request = fields.Datetime(
        string='Ngày đề nghị', default=fields.Datetime.now, required=True,
        tracking=True)
    date_planned_start = fields.Datetime(string='Dự kiến bắt đầu',
                                         tracking=True)
    date_planned_end = fields.Datetime(string='Dự kiến xong', tracking=True)
    date_start = fields.Datetime(string='Thực tế bắt đầu', readonly=True,
                                 copy=False, tracking=True)
    date_end = fields.Datetime(string='Thực tế xong', readonly=True,
                               copy=False, tracking=True)
    duration_hours = fields.Float(
        string='Số giờ thực tế', compute='_compute_duration', store=True,
        digits=(16, 2), aggregator='sum')
    # Trễ so với kế hoạch là một con số, không phải một cảm giác.
    delay_days = fields.Integer(
        string='Trễ so kế hoạch (ngày)', compute='_compute_duration',
        store=True, aggregator=False,
        help='Tính từ ngày dự kiến xong. Lệnh chưa xong thì tính tới hôm '
             'nay — để nó không đứng im và trông như vẫn còn hạn.')

    state = fields.Selection(
        [('draft', 'Nháp'),
         ('approved', 'Đã duyệt'),
         ('planned', 'Đã lên lịch'),
         ('in_progress', 'Đang làm'),
         ('done', 'Đã xong'),
         ('closed', 'Đã đóng'),
         ('cancelled', 'Đã huỷ')],
        string='Trạng thái', default='draft', required=True, tracking=True,
        copy=False, index=True)

    is_on_hold = fields.Boolean(
        string='Đang chờ', copy=False, tracking=True,
        help='Vẫn ở trạng thái "đang làm" nhưng thực tế không ai làm. '
             'Tách ra mới đo được: một lệnh mở 14 ngày hiếm khi có người '
             'làm suốt 14 ngày.')
    hold_reason = fields.Selection(
        [('parts', 'Chờ vật tư, phụ tùng'),
         ('crane', 'Chờ thiết bị nâng hạ'),
         ('weather', 'Chờ điều kiện thời tiết'),
         ('permit', 'Chờ phiếu công tác, cho phép an toàn'),
         ('grid', 'Chờ lưới cho cắt điện'),
         ('contractor', 'Chờ nhà thầu'),
         ('access', 'Chờ đường vào, mặt bằng'),
         ('decision', 'Chờ quyết định, phê duyệt'),
         ('other', 'Lý do khác')],
        string='Chờ vì', tracking=True,
        help='Chờ cẩu và chờ thời tiết là lý do THẬT của điện gió, không '
             'phải cái cớ: thay cánh cần cẩu bánh xích huy động cả tuần '
             'và gió phải dưới ngưỡng cho phép.')
    date_hold_start = fields.Datetime(string='Chờ từ', copy=False)
    hold_hours = fields.Float(
        string='Số giờ đang chờ', compute='_compute_hold', digits=(16, 2),
        help='Chỉ tính lần chờ ĐANG MỞ. Tổng thời gian chờ qua nhiều lần '
             'cần một sổ ghi từng lần — chưa làm.')

    # ------------------------------------------------------------------
    # An toàn — phần của quy chuẩn Việt Nam
    # ------------------------------------------------------------------
    requires_permit = fields.Boolean(
        string='Cần phiếu, lệnh công tác', tracking=True,
        help='Làm việc trên thiết bị điện phải có phiếu công tác hoặc '
             'lệnh công tác theo quy chuẩn an toàn điện. Đây là chứng từ '
             'KHÁC lệnh công việc này; ô dưới chỉ ghi số hiệu để tra '
             'ngược.')
    permit_kind = fields.Selection(
        [('phieu_cong_tac', 'Phiếu công tác'),
         ('lenh_cong_tac', 'Lệnh công tác')],
        string='Loại chứng từ an toàn')
    permit_ref = fields.Char(string='Số phiếu, lệnh công tác', copy=False,
                             tracking=True)
    permit_date = fields.Date(string='Ngày cấp')
    permit_issuer_id = fields.Many2one(
        'res.users', string='Người cấp phiếu',
        help='Quy chuẩn yêu cầu người cấp phải nắm rõ nội dung công việc '
             'và các điều kiện bảo đảm an toàn điện.')
    requires_isolation = fields.Boolean(
        string='Phải cắt điện, cô lập',
        help='Cắt điện, treo thẻ, khoá và thử không điện trước khi vào.')
    work_at_height = fields.Boolean(
        string='Làm việc trên cao',
        help='Trong nacelle và trên tháp. Có hồ sơ riêng về huấn luyện, '
             'dây đai và cứu hộ treo cao.')
    safety_note = fields.Text(string='Ghi chú an toàn')

    # ------------------------------------------------------------------
    # Hỏng hóc — nơi sinh ra dữ liệu độ tin cậy
    # ------------------------------------------------------------------
    is_failure = fields.Boolean(
        string='Có hỏng hóc', tracking=True,
        help='KHAI TAY, không suy từ việc có lệnh công việc. Nhiều lần '
             'dừng chỉ cần khởi động lại từ xa: có dừng, không có hỏng. '
             'Bảo trì theo kế hoạch thì ngược lại. Suy sai ô này là MTBF '
             'sai hoàn toàn, và sai theo hướng đẹp hơn thực tế.')
    failure_mode_id = fields.Many2one(
        'eam.failure.mode', string='Dạng hỏng', ondelete='restrict',
        tracking=True)
    # Khai lại danh sách thay vì trỏ sang selection của eam.failure.mode:
    # trỏ sang thì thứ tự nạp model quyết định có chạy hay không, và lỗi
    # kiểu đó chỉ lộ ra ở một thứ tự cài đặt nhất định.
    failure_mechanism = fields.Selection(
        [('fatigue', 'Mỏi'),
         ('wear', 'Mài mòn'),
         ('corrosion', 'Ăn mòn'),
         ('overload', 'Quá tải'),
         ('insulation', 'Lão hoá cách điện'),
         ('contamination', 'Nhiễm bẩn, lẫn tạp'),
         ('lubrication', 'Bôi trơn không đủ'),
         ('loosening', 'Lỏng liên kết'),
         ('software', 'Lỗi điều khiển, phần mềm'),
         ('external', 'Tác động bên ngoài'),
         ('unknown', 'Chưa xác định')],
        string='Cơ chế hỏng',
        help='Cơ chế THẬT của lần này. Dạng hỏng có gợi ý cơ chế thường '
             'gặp, nhưng cùng một dạng hỏng có thể do nhiều cơ chế.')
    detection_method = fields.Selection(
        [('scada', 'Báo động từ hệ giám sát'),
         ('condition', 'Giám sát trạng thái, đo rung'),
         ('inspection', 'Kiểm tra định kỳ'),
         ('operator', 'Người vận hành phát hiện'),
         ('production', 'Phát hiện qua sụt sản lượng'),
         ('casual', 'Tình cờ phát hiện'),
         ('other', 'Cách khác')],
        string='Phát hiện bằng', tracking=True,
        help='Cột này trả lời câu đắt tiền nhất: bao nhiêu phần trăm hỏng '
             'hóc được bắt TRƯỚC khi mất sản lượng. Giám sát trạng thái '
             'chỉ đáng tiền khi tỷ lệ đó cao hơn hẳn.')
    root_cause = fields.Text(
        string='Nguyên nhân gốc',
        help='Vì sao cơ chế đó xảy ra: lắp sai lực siết, bôi trơn thiếu, '
             'lỗi thiết kế, lỗi lô hàng. Khác dạng hỏng và cơ chế hỏng.')
    corrective_action = fields.Text(string='Việc đã làm')

    # ------------------------------------------------------------------
    # Chi phí
    # ------------------------------------------------------------------
    labour_line_ids = fields.One2many(
        'eam.work.order.labour', 'order_id', string='Giờ công')
    part_line_ids = fields.One2many(
        'eam.work.order.part', 'order_id', string='Vật tư, phụ tùng')
    cost_labour = fields.Monetary(
        string='Chi phí giờ công', compute='_compute_cost', store=True)
    cost_parts = fields.Monetary(
        string='Chi phí vật tư', compute='_compute_cost', store=True)
    cost_service = fields.Monetary(
        string='Chi phí thuê ngoài', tracking=True,
        help='Thuê cẩu, thuê chuyên gia, vận chuyển. Khai gộp vì các '
             'khoản này thường về theo một hoá đơn.')
    cost_service_note = fields.Char(string='Diễn giải thuê ngoài')
    cost_total = fields.Monetary(
        string='Chi phí can thiệp', compute='_compute_cost', store=True,
        help='Giờ công + vật tư + thuê ngoài. CHƯA tính sản lượng mất.')
    cost_downtime = fields.Monetary(
        string='Sản lượng mất quy tiền', compute='_compute_cost', store=True,
        help='Lấy từ khoảng dừng gắn vào lệnh này. Với nhà máy điện, phần '
             'này thường lớn hơn hẳn chi phí can thiệp.')
    cost_full = fields.Monetary(
        string='Tổng chi phí thật', compute='_compute_cost', store=True,
        help='Can thiệp + sản lượng mất. Đây là con số dùng để biện minh '
             'đầu tư bảo trì phòng ngừa — chỉ nhìn chi phí can thiệp thì '
             'phòng ngừa luôn trông như một khoản chi vô ích.')
    amount_chargeable = fields.Monetary(
        string='Chi phí đòi lại được', compute='_compute_cost', store=True,
        help='Phần chi phí can thiệp quy cho bảo hành hoặc đòi lại nhà '
             'thầu O&M. KHÔNG gồm sản lượng mất — phần đó đi theo chế '
             'tài khả dụng của hợp đồng, có công thức và trần riêng.')
    currency_id = fields.Many2one(
        'res.currency', string='Tiền tệ',
        default=lambda s: s.env.company.currency_id, required=True)
    company_id = fields.Many2one(
        'res.company', string='Công ty', required=True,
        default=lambda self: self.env.company, index=True)

    _uniq_name = models.Constraint(
        'UNIQUE(company_id, name)',
        'Số hiệu lệnh công việc không được trùng.')

    # ------------------------------------------------------------------
    # Tính toán
    # ------------------------------------------------------------------
    @api.depends('location_id', 'date_planned_start', 'date_request')
    def _compute_asset(self):
        I = self.env['eam.installation']
        for o in self:
            if not o.location_id:
                continue
            moc = o.date_planned_start or o.date_request
            d = moc.date() if moc else fields.Date.context_today(o)
            lap = I.search([('location_id', '=', o.location_id.id),
                            ('date_install', '<=', d)])
            hop = lap.filtered(
                lambda x: not x.date_remove or x.date_remove >= d)
            o.asset_id = hop[:1].asset_id

    @api.depends('outage_id.liability')
    def _compute_cost_bearer(self):
        """Suy bên chịu chi phí từ trách nhiệm của khoảng dừng.

        Chỉ là GỢI Ý ban đầu và sửa được, vì hai câu hỏi khác nhau: ai
        làm mất sản lượng, và ai trả tiền sửa. Trùng nhau phần lớn
        trường hợp, nhưng không phải luôn luôn.
        """
        anh_xa = {
            'warranty': 'warranty',
            'om_contract': 'om_chargeable',
            'owner': 'owner',
            'grid': 'owner',
            'force_majeure': 'insurance',
        }
        for o in self:
            if o.cost_bearer and o.cost_bearer != 'undetermined':
                continue
            o.cost_bearer = anh_xa.get(
                o.outage_id.liability, 'undetermined')

    @api.depends('child_ids')
    def _compute_child_count(self):
        for o in self:
            o.child_count = len(o.child_ids)

    @api.depends('date_start', 'date_end', 'date_planned_end')
    def _compute_duration(self):
        bg = fields.Datetime.now()
        for o in self:
            o.duration_hours = (
                ((o.date_end or bg) - o.date_start).total_seconds() / 3600.0
                if o.date_start else 0.0)
            if o.date_planned_end:
                moc = o.date_end or bg
                o.delay_days = max((moc - o.date_planned_end).days, 0)
            else:
                o.delay_days = 0

    @api.depends('is_on_hold', 'date_hold_start')
    def _compute_hold(self):
        bg = fields.Datetime.now()
        for o in self:
            if not (o.is_on_hold and o.date_hold_start):
                o.hold_hours = 0.0
                continue
            # Chặn số âm. "Chờ từ" ở tương lai là dữ liệu sai, nhưng
            # hiện ra "đã chờ −17.724 giờ" thì người dùng mất tin vào cả
            # màn hình, không chỉ một ô.
            o.hold_hours = max(
                (bg - o.date_hold_start).total_seconds() / 3600.0, 0.0)

    @api.depends('labour_line_ids.amount', 'part_line_ids.amount',
                 'cost_service', 'cost_bearer',
                 'outage_id.lost_revenue')
    def _compute_cost(self):
        for o in self:
            o.cost_labour = sum(o.labour_line_ids.mapped('amount'))
            o.cost_parts = sum(o.part_line_ids.mapped('amount'))
            o.cost_total = o.cost_labour + o.cost_parts + (o.cost_service or 0)
            o.cost_downtime = o.outage_id.lost_revenue or 0.0
            o.cost_full = o.cost_total + o.cost_downtime
            o.amount_chargeable = (
                o.cost_total
                if o.cost_bearer in ('warranty', 'om_chargeable')
                else 0.0)

    @api.depends('name', 'title')
    def _compute_display_name(self):
        for o in self:
            o.display_name = '%s — %s' % (o.name or '/', o.title or '')

    # ------------------------------------------------------------------
    # Ràng buộc
    # ------------------------------------------------------------------
    @api.constrains('date_planned_start', 'date_planned_end')
    def _check_lich(self):
        for o in self:
            if (o.date_planned_start and o.date_planned_end
                    and o.date_planned_end < o.date_planned_start):
                raise ValidationError(_(
                    'Lệnh "%s": ngày dự kiến xong trước ngày dự kiến bắt '
                    'đầu.', o.name or '/'))

    @api.constrains('parent_id')
    def _check_vong(self):
        if self._has_cycle('parent_id'):
            raise ValidationError(_(
                'Chiến dịch không được lồng vòng vào chính nó.'))

    @api.constrains('is_on_hold', 'hold_reason')
    def _check_ly_do_cho(self):
        for o in self:
            if o.is_on_hold and not o.hold_reason:
                raise ValidationError(_(
                    'Lệnh "%s" đang chờ mà không ghi chờ vì gì. Ô này là '
                    'chỗ duy nhất phân biệt được sửa chậm với chờ một '
                    'nguồn lực bên ngoài — bỏ trống thì mọi lệnh quá hạn '
                    'trông giống nhau.', o.name or '/'))

    # ------------------------------------------------------------------
    # Chuyển trạng thái
    # ------------------------------------------------------------------
    def action_duyet(self):
        for o in self:
            if o.state != 'draft':
                raise UserError(_('Lệnh "%s" không còn ở trạng thái nháp.',
                                  o.name))
        self.state = 'approved'
        return True

    def action_len_lich(self):
        for o in self:
            if not o.date_planned_start:
                raise UserError(_(
                    'Lệnh "%s" chưa có ngày dự kiến bắt đầu.', o.name))
        self.state = 'planned'
        return True

    def action_bat_dau(self):
        for o in self:
            if o.state not in ('approved', 'planned'):
                raise UserError(_(
                    'Lệnh "%s" phải được duyệt trước khi bắt đầu.', o.name))
            # Cổng an toàn. Chặn ở đây là chặn đúng chỗ: sau khi bắt đầu
            # thì giấy tờ an toàn không còn ý nghĩa gì nữa.
            if o.requires_permit and not o.permit_ref:
                raise UserError(_(
                    'Lệnh "%(ten)s" khai là cần phiếu, lệnh công tác '
                    'nhưng chưa có số hiệu.\n\n'
                    'Theo quy chuẩn an toàn điện, làm việc trên thiết bị '
                    'điện phải có phiếu công tác hoặc lệnh công tác do '
                    'người có thẩm quyền cấp. Lệnh công việc này KHÔNG '
                    'thay thế chứng từ đó — hãy ghi số hiệu phiếu vào, '
                    'hoặc bỏ dấu ô "cần phiếu, lệnh công tác" nếu công '
                    'việc không chạm vào thiết bị điện.', ten=o.name))
            o.write({'state': 'in_progress',
                     'date_start': o.date_start or fields.Datetime.now()})
        return True

    def action_cho(self):
        for o in self:
            if o.state != 'in_progress':
                raise UserError(_(
                    'Chỉ lệnh đang làm mới chuyển sang chờ được.'))
            o.write({'is_on_hold': True,
                     'date_hold_start': fields.Datetime.now()})
        return True

    def action_lam_tiep(self):
        self.write({'is_on_hold': False, 'date_hold_start': False,
                    'hold_reason': False})
        return True

    def action_xong(self):
        for o in self:
            if o.state != 'in_progress':
                raise UserError(_(
                    'Lệnh "%s" chưa ở trạng thái đang làm.', o.name))
            if o.is_failure and not o.failure_mode_id:
                raise UserError(_(
                    'Lệnh "%(ten)s" khai là có hỏng hóc nhưng chưa chọn '
                    'dạng hỏng.\n\n'
                    'Đóng lệnh mà bỏ trống ô này thì lần hỏng đó không '
                    'bao giờ vào được thống kê độ tin cậy — và không có '
                    'cách nào lấy lại, vì người biết đã đi làm việc '
                    'khác.', ten=o.name))
            o.write({'state': 'done', 'is_on_hold': False,
                     'date_hold_start': False, 'hold_reason': False,
                     'date_end': o.date_end or fields.Datetime.now()})
        return True

    def action_dong_lenh(self):
        """Đóng hồ sơ — chốt chi phí và quy trách nhiệm."""
        for o in self:
            if o.state != 'done':
                raise UserError(_('Lệnh "%s" chưa xong.', o.name))
            # Bỏ trống và "Chưa quy" là cùng một chuyện: trường không khai
            # required ở tầng cơ sở dữ liệu nên phải chặn cả hai ở đây.
            if o.cost_bearer in (False, 'undetermined'):
                raise UserError(_(
                    'Lệnh "%s" chưa quy bên chịu chi phí. Đóng lệnh mà bỏ '
                    'trống thì khoản này không vào được hồ sơ đòi bảo '
                    'hành hay đòi nhà thầu.', o.name))
        self.state = 'closed'
        return True

    def action_huy(self):
        for o in self:
            if o.state == 'closed':
                raise UserError(_('Lệnh "%s" đã đóng, không huỷ được.',
                                  o.name))
        self.state = 'cancelled'
        return True

    def action_ve_nhap(self):
        self.write({'state': 'draft', 'date_start': False,
                    'date_end': False, 'is_on_hold': False,
                    'date_hold_start': False, 'hold_reason': False})
        return True

    def action_mo_khoang_dung(self):
        self.ensure_one()
        if not self.outage_id:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Ghi khoảng dừng'),
                'res_model': 'eam.outage',
                'view_mode': 'form',
                'target': 'new',
                'context': {'default_location_id': self.location_id.id},
            }
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'eam.outage',
            'view_mode': 'form',
            'res_id': self.outage_id.id,
        }

    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for v in vals_list:
            if not v.get('name') or v['name'] == _('Mới'):
                v['name'] = self.env['ir.sequence'].next_by_code(
                    'eam.work.order') or '/'
        return super().create(vals_list)


class EamWorkOrderLabour(models.Model):
    """Giờ công trên một lệnh — ai làm, bao lâu, đơn giá nào.

    Đơn giá khai trên TỪNG DÒNG, không lấy từ một bảng giá chung. Giờ
    của tổ mình, giờ của nhà thầu O&M trong giá hợp đồng, và giờ của
    chuyên gia hãng tính theo ngày có ba mức hoàn toàn khác nhau — mà
    cùng xuất hiện trên một lệnh.
    """
    _name = 'eam.work.order.labour'
    _description = 'Giờ công trên lệnh công việc'
    _order = 'order_id, id'

    order_id = fields.Many2one(
        'eam.work.order', string='Lệnh công việc', required=True,
        ondelete='cascade', index=True)
    user_id = fields.Many2one('res.users', string='Người thực hiện')
    worker_name = fields.Char(
        string='Tên người thực hiện',
        help='Dùng khi người làm không có tài khoản trong hệ thống — '
             'nhân sự nhà thầu phần lớn là như vậy.')
    trade = fields.Selection(
        [('mechanical', 'Cơ khí'),
         ('electrical', 'Điện'),
         ('control', 'Điều khiển, tự động'),
         ('blade', 'Cánh quạt, composite'),
         ('civil', 'Xây dựng, nền móng'),
         ('hv', 'Điện cao áp'),
         ('rope', 'Tiếp cận bằng dây'),
         ('other', 'Khác')],
        string='Nghề')
    date_work = fields.Date(string='Ngày làm',
                            default=lambda s: fields.Date.context_today(s))
    hours = fields.Float(string='Số giờ', digits=(16, 2), required=True)
    rate = fields.Monetary(string='Đơn giá giờ')
    amount = fields.Monetary(string='Thành tiền', compute='_compute_amount',
                             store=True)
    currency_id = fields.Many2one(
        related='order_id.currency_id', store=True, string='Tiền tệ')
    company_id = fields.Many2one(related='order_id.company_id', store=True)
    note = fields.Char(string='Ghi chú')

    @api.depends('hours', 'rate')
    def _compute_amount(self):
        for l in self:
            l.amount = (l.hours or 0.0) * (l.rate or 0.0)


class EamWorkOrderPart(models.Model):
    """Vật tư, phụ tùng dùng trên một lệnh.

    ``asset_out_id`` và ``asset_in_id`` là chỗ nối sang lịch sử lắp đặt:
    thay một con hộp số là THÁO con cũ ra và LẮP con mới vào, cả hai đều
    mang sê-ri riêng. Ghi mỗi số lượng thì vài năm sau không biết trong
    máy đang có con nào — và đó đúng là câu cần trả lời khi đi đòi bảo
    hành.
    """
    _name = 'eam.work.order.part'
    _description = 'Vật tư trên lệnh công việc'
    _order = 'order_id, id'

    order_id = fields.Many2one(
        'eam.work.order', string='Lệnh công việc', required=True,
        ondelete='cascade', index=True)
    product_id = fields.Many2one('product.product', string='Vật tư')
    part_name = fields.Char(
        string='Tên vật tư',
        help='Dùng khi vật tư chưa có trong danh mục. Mua gấp một lần '
             'thì thường là như vậy.')
    qty = fields.Float(string='Số lượng', digits='Product Unit of Measure',
                       default=1.0, required=True)
    uom_id = fields.Many2one('uom.uom', string='Đơn vị')
    unit_cost = fields.Monetary(string='Đơn giá')
    amount = fields.Monetary(string='Thành tiền', compute='_compute_amount',
                             store=True)
    currency_id = fields.Many2one(
        related='order_id.currency_id', store=True, string='Tiền tệ')
    company_id = fields.Many2one(related='order_id.company_id', store=True)

    is_rotable = fields.Boolean(
        string='Vật tư quay vòng',
        help='Tháo ra đem đại tu rồi lắp lại, giữ nguyên lịch sử theo '
             'sê-ri. Hộp số, máy phát, cánh, bộ biến đổi thuộc loại này.')
    asset_out_id = fields.Many2one(
        'eam.asset', string='Thiết bị tháo ra',
        help='Con cũ tháo khỏi máy. Ghi vào đây rồi đóng quãng lắp đặt '
             'của nó — không ghi thì mất dấu một tài sản mang sê-ri.')
    asset_in_id = fields.Many2one(
        'eam.asset', string='Thiết bị lắp vào',
        help='Con mới lắp lên máy. Ghi vào đây rồi mở quãng lắp đặt mới.')
    is_warranty_part = fields.Boolean(
        string='Phụ tùng bảo hành',
        help='Hãng cấp không thu tiền. Vẫn phải ghi số lượng và sê-ri, '
             'vì đó là bằng chứng cho lần đòi bảo hành tiếp theo.')
    note = fields.Char(string='Ghi chú')

    @api.depends('qty', 'unit_cost', 'is_warranty_part')
    def _compute_amount(self):
        for l in self:
            l.amount = (0.0 if l.is_warranty_part
                        else (l.qty or 0.0) * (l.unit_cost or 0.0))

    @api.onchange('product_id')
    def _onchange_product(self):
        for l in self:
            if l.product_id:
                l.uom_id = l.product_id.uom_id
                if not l.unit_cost:
                    l.unit_cost = l.product_id.standard_price
