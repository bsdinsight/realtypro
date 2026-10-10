# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class EamAsset(models.Model):
    """Tài sản mang sê-ri — VẬT, không phải CHỖ.

    Một vật có danh tính riêng và mang theo lịch sử của chính nó qua mọi
    lần tháo ra, đại tu, lắp lại. Vị trí nó đang nằm là thuộc tính TẠM
    THỜI, suy ra từ lịch sử lắp đặt, không phải thuộc tính của vật.

    Vì vậy ``current_location_id`` ở đây là trường TÍNH, không cho sửa
    tay. Muốn đổi chỗ thì ghi một bản ghi lắp đặt — đó là cách duy nhất
    giữ được lịch sử. Cho sửa tay là mở cửa cho việc dời chỗ không để
    lại dấu vết.

    Nguồn gốc (từ hợp đồng nào, dòng BOQ nào, nghiệm thu ngày nào) KHÔNG
    khai ở lõi — lõi không được biết tới EPCOne. Cầu bàn giao kế
    thừa model này và thêm các trường đó.
    """
    _name = 'eam.asset'
    _description = 'Tài sản mang sê-ri'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'code, id'

    name = fields.Char(string='Tên tài sản', required=True, tracking=True)
    code = fields.Char(string='Mã tài sản', required=True, index=True,
                       copy=False, tracking=True)
    serial_no = fields.Char(string='Số sê-ri', index=True, copy=False,
                            tracking=True)
    category_id = fields.Many2one(
        'eam.asset.category', string='Loại cấu phần', required=True,
        ondelete='restrict', index=True, tracking=True)
    manufacturer_id = fields.Many2one(
        'res.partner', string='Nhà sản xuất', tracking=True)
    model_ref = fields.Char(string='Model / nền tảng', tracking=True)

    # Vòng đời là trạng thái KHAI TAY. Việc đang nằm ở đâu thì suy ra từ
    # lịch sử lắp đặt — hai thứ khác nhau, đừng gộp thành một trường.
    state = fields.Selection(
        [('draft', 'Nháp'),
         ('active', 'Đang dùng'),
         ('repair', 'Đang sửa chữa'),
         ('scrapped', 'Đã thanh lý')],
        string='Vòng đời', default='draft', required=True, tracking=True)
    is_rotable = fields.Boolean(
        string='Vật tư quay vòng', tracking=True,
        help='Tháo ra, đem đi đại tu, rồi lắp lại — giữ nguyên lịch sử '
             'theo sê-ri. Hộp số, máy phát, cánh, bộ biến đổi thuộc loại '
             'này. Khác hẳn vật tư tiêu hao.')
    is_refurbished = fields.Boolean(
        string='Hàng đã tân trang', tracking=True,
        help='Nhà thầu OEM thường đòi quyền lắp phụ tùng đã tân trang. '
             'Không ghi lại thì vài năm sau không ai biết trong máy đang '
             'có những gì.')
    owner_partner_id = fields.Many2one(
        'res.partner', string='Thuộc sở hữu của',
        help='Để trống nghĩa là của chính mình. Khai khi cấu phần đã '
             'tháo ra thuộc về nhà thầu theo hợp đồng dịch vụ — đây là '
             'điều khoản phải thương lượng, và không ghi thì mất dấu '
             'tài sản.')

    criticality = fields.Selection(
        [('low', 'Thấp'), ('medium', 'Trung bình'),
         ('high', 'Cao'), ('critical', 'Trọng yếu')],
        string='Mức quan trọng', default='medium', tracking=True,
        help='Suy ra từ lịch sử hỏng hóc của CHÍNH đội máy này, không '
             'lấy bảng xếp hạng chung. Dữ liệu nhiều nguồn cho thấy thứ '
             'tự này khác nhau rất xa giữa các đội máy.')

    date_manufacture = fields.Date(string='Ngày sản xuất')
    date_commissioned = fields.Date(string='Ngày đưa vào vận hành',
                                    tracking=True)
    warranty_end = fields.Date(string='Bảo hành đến ngày', tracking=True)
    warranty_note = fields.Text(string='Điều kiện bảo hành')
    warranty_days_left = fields.Integer(
        string='Bảo hành còn (ngày)', compute='_compute_warranty')
    warranty_state = fields.Selection(
        [('none', 'Không khai'), ('valid', 'Còn hạn'),
         ('expiring', 'Sắp hết'), ('expired', 'Hết hạn')],
        string='Tình trạng bảo hành', compute='_compute_warranty')

    # ── Cây LẮP RÁP: vật nằm trong vật, ĐI THEO VẬT.
    #
    # Khác hẳn cây vị trí chức năng. Cây vị trí trả lời "vị trí 7 hỏng
    # hộp số mấy lần" — lỗi nền móng, dòng gió hay lắp đặt. Cây lắp ráp
    # trả lời câu NGƯỢC LẠI: "con hộp số này đã hỏng ở mấy vị trí" —
    # lỗi lô hàng. Tháo hộp số đem đi đại tu thì ổ trục bên trong đi
    # theo nó, chứ không ở lại chỗ cũ. Trộn hai cây làm một là mất một
    # trong hai câu hỏi.
    parent_id = fields.Many2one(
        'eam.asset', string='Lắp trong tài sản', ondelete='restrict',
        index=True, tracking=True,
        help='Cấu phần nằm BÊN TRONG một tài sản khác và đi theo nó khi '
             'tháo ra. Khác với vị trí chức năng — chỗ thì ở lại.')
    child_ids = fields.One2many(
        'eam.asset', 'parent_id', string='Cấu phần bên trong')
    child_count = fields.Integer(
        string='Số cấu phần bên trong', compute='_compute_child_count',
        store=True)
    # Cấp tài sản — thứ cứu sổ tài sản khỏi chết chìm.
    #
    # Một nhà máy 30 trụ × 22 cấu phần là gần bảy trăm dòng, trong đó
    # chỉ 30 dòng là CÁI MÁY. Mở danh sách ra mà không tách cấp thì hai
    # mươi dòng đầu toàn cánh quạt, và người dùng tưởng mất máy. Mặc
    # định màn hình chỉ hiện thiết bị chính; muốn xem cấu phần thì bấm
    # vào máy, hoặc đổi ô lọc.
    asset_level = fields.Selection(
        [('main', 'Thiết bị chính'), ('component', 'Cấu phần')],
        string='Cấp tài sản', compute='_compute_child_count', store=True,
        index=True)
    installation_ids = fields.One2many(
        'eam.installation', 'asset_id', string='Lịch sử lắp đặt')
    current_installation_id = fields.Many2one(
        'eam.installation', string='Lần lắp hiện tại',
        compute='_compute_current', store=True)
    current_location_id = fields.Many2one(
        'eam.location', string='Đang lắp tại', compute='_compute_current',
        store=True, index=True)
    is_installed = fields.Boolean(
        string='Đang lắp trên máy', compute='_compute_current', store=True)
    install_count = fields.Integer(
        string='Số lần lắp', compute='_compute_current', store=True)
    plant_id = fields.Many2one(
        'eam.location', string='Thuộc nhà máy',
        related='current_location_id.plant_id', store=True, index=True)

    origin = fields.Char(
        string='Nguồn gốc',
        help='Tham chiếu tự do tới nguồn bàn giao. Cầu bàn giao thay '
             'trường này bằng liên kết thật tới hợp đồng và dòng BOQ.')
    company_id = fields.Many2one(
        'res.company', string='Công ty', required=True,
        default=lambda self: self.env.company, index=True)
    note = fields.Text(string='Ghi chú')
    active = fields.Boolean(default=True)

    _uniq_code = models.Constraint(
        'UNIQUE(company_id, code)',
        'Mã tài sản không được trùng trong cùng một công ty.')
    # Sê-ri trùng là dấu hiệu nhập trùng — chặn ở tầng cơ sở dữ liệu chứ
    # không chỉ cảnh báo, vì một khi đã có hai bản ghi cho cùng một vật
    # thì lịch sử bị chẻ đôi và ghép lại rất tốn công.
    _uniq_serial = models.Constraint(
        'UNIQUE(company_id, category_id, serial_no)',
        'Số sê-ri đã tồn tại cho loại cấu phần này.')

    @api.depends('child_ids', 'parent_id')
    def _compute_child_count(self):
        for a in self:
            a.child_count = len(a.child_ids)
            a.asset_level = 'component' if a.parent_id else 'main'

    @api.constrains('parent_id')
    def _check_vong_lap_rap(self):
        if self._has_cycle('parent_id'):
            raise ValidationError(_(
                'Cấu phần không được lắp lồng vòng vào chính nó.'))

    @api.constrains('parent_id', 'current_location_id')
    def _check_cay_khop_vi_tri(self):
        """Không được NHẢY CÓC qua cụm trung gian trong cây lắp ráp.

        Cha phải là tài sản ở vị trí tổ tiên GẦN NHẤT có tài sản, chứ
        không phải một tổ tiên bất kỳ. Soát lỏng kiểu "miễn là tổ tiên"
        thì gán cánh thẳng lên tua-bin vẫn lọt — vị trí tua-bin đúng là
        tổ tiên của vị trí cánh — và hai cây vẫn đá nhau: cây vị trí nói
        cánh nằm trong cụm rotor, cây lắp ráp nói cánh đứng NGANG HÀNG
        với chính cụm chứa nó.

        Đã xảy ra thật: 462 cấu phần bị gán cha là con tua-bin ở gốc
        thay vì cụm trung gian, và không màn hình nào chặn.

        Chỉ soát khi cả hai đang lắp trên máy. Cấu phần tháo ra đem đại
        tu vẫn thuộc cụm cũ nhưng không còn ở vị trí nào — ép khớp là
        buộc người dùng gỡ quan hệ lắp ráp mỗi lần tháo, tức xoá mất
        đúng thứ cần giữ.
        """
        for a in self:
            cha = a.parent_id
            if not (cha and a.current_location_id
                    and cha.current_location_id):
                continue
            # Leo ngược từ vị trí con, dừng ở tổ tiên ĐẦU TIÊN có tài sản
            p = a.current_location_id.parent_id
            dung = None
            while p:
                c = self.search([('current_location_id', '=', p.id)],
                                limit=1)
                if c:
                    dung = c
                    break
                p = p.parent_id
            if dung and dung != cha:
                raise ValidationError(_(
                    'Tài sản "%(con)s" lắp tại %(vtc)s thì cụm chứa nó '
                    'phải là "%(dung)s" (ở %(vtd)s), không phải '
                    '"%(cha)s".\n\n'
                    'Gán vượt cấp là để con đứng NGANG HÀNG với chính '
                    'cụm chứa nó — cây vị trí nói một đằng, cây lắp ráp '
                    'nói một nẻo, và người xem thấy ngay.',
                    con=a.display_name,
                    vtc=a.current_location_id.complete_code,
                    dung=dung.display_name,
                    vtd=dung.current_location_id.complete_code,
                    cha=cha.display_name))

    @api.depends('installation_ids.is_current',
                 'installation_ids.location_id')
    def _compute_current(self):
        for a in self:
            mo = a.installation_ids.filtered('is_current')[:1]
            a.current_installation_id = mo
            a.current_location_id = mo.location_id
            a.is_installed = bool(mo)
            a.install_count = len(a.installation_ids)

    @api.depends('warranty_end')
    def _compute_warranty(self):
        hn = fields.Date.context_today(self)
        for a in self:
            if not a.warranty_end:
                a.warranty_days_left = 0
                a.warranty_state = 'none'
                continue
            con = (a.warranty_end - hn).days
            a.warranty_days_left = con
            a.warranty_state = ('expired' if con < 0
                                else 'expiring' if con <= 90 else 'valid')

    @api.depends('code', 'name', 'serial_no')
    def _compute_display_name(self):
        for a in self:
            sn = ' · SN %s' % a.serial_no if a.serial_no else ''
            a.display_name = '[%s] %s%s' % (a.code or '', a.name or '', sn)

    # ------------------------------------------------------------------
    def action_lap_dat(self):
        """Mở form ghi một lần lắp mới cho tài sản này."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Lắp đặt — %s' % self.display_name,
            'res_model': 'eam.installation',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_asset_id': self.id},
        }

    def action_xem_cay(self):
        """Mở kiểu xem CÂY, neo vào chính con này và các cấu phần dưới nó.

        Trên form chỉ thấy được MỘT tầng con. Muốn nhìn cả cụm rotor rồi
        xuống ba cánh thì phải có cây — mà nút chuyển kiểu xem của Odoo
        chỉ hiện ở màn danh sách, nên từ form không có đường nào tới.
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Cây lắp ráp — %s', self.display_name),
            'res_model': 'eam.asset',
            'view_mode': 'hierarchy,list,form',
            'domain': [('id', 'child_of', self.id)],
        }

    def action_mo_lich_su(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Lịch sử lắp đặt — %s' % self.display_name,
            'res_model': 'eam.installation',
            'view_mode': 'list,form',
            'domain': [('asset_id', '=', self.id)],
            'context': {'default_asset_id': self.id},
        }

    @api.model
    def _cron_tinh_bao_hanh(self):
        """Đánh thức các trường phụ thuộc NGÀY HÔM NAY.

        ``warranty_days_left`` và ``warranty_state`` tính từ ngày hôm
        nay. Chúng không lưu nên không bị đứng im, nhưng cron này tồn tại
        để chỗ nào về sau cần lưu thì đã có sẵn chỗ gọi — bài học từ
        trường đếm ngày bảo lãnh từng đứng im vì không ai đánh thức.
        """
        self.search([])._compute_warranty()
        return True
