# -*- coding: utf-8 -*-
"""Hiệu lực chứng chỉ — tính trên bảng kỹ năng CÓ SẴN của Odoo.

Vì sao KHÔNG dựng bảng năng lực riêng
-------------------------------------
``hr.employee.skill`` của Odoo 19 đã có ``valid_from``, ``valid_to`` và
cờ ``is_certification``. Dựng thêm một bảng chứng chỉ của EAMOne là có
**hai nguồn sự thật** về cùng một tờ giấy: phòng nhân sự cập nhật một
bên, đội bảo trì nhập một bên, rồi cổng chặn đọc bên nào cũng sai.

Nên ở đây chỉ **tính thêm** hai thứ mà Odoo không tính: tình trạng hiệu
lực và số ngày còn lại.

Phân biệt THIẾU và HẾT HẠN
--------------------------
Hai cái này trông giống nhau trên màn hình — cùng là "người này không
được làm việc đó" — nhưng là hai bài toán khác nhau về thời gian:

* **Hết hạn** là lỗi xếp lịch đào tạo. Sửa được trong tuần: đăng ký lớp
  gia hạn, thi lại.
* **Thiếu hẳn** là lỗi kế hoạch nhân lực. Mất hàng tháng: tuyển, hoặc
  đào tạo từ đầu, hoặc thuê ngoài.

Gộp hai cái thành một câu "không đủ năng lực" là mất đúng thông tin cần
để xử lý. Nên mã này tách riêng, và câu báo ở cổng chặn cũng tách riêng.
"""
from markupsafe import Markup

from odoo import _, api, fields, models

NGUONG_SAP_HET = 60


class HrEmployeeSkill(models.Model):
    _inherit = 'hr.employee.skill'

    eam_state = fields.Selection(
        [('no_expiry', 'Không có thời hạn'),
         ('valid', 'Còn hiệu lực'),
         ('expiring', 'Sắp hết hạn'),
         ('expired', 'ĐÃ HẾT HẠN'),
         ('future', 'Chưa tới hiệu lực')],
        string='Hiệu lực', compute='_compute_eam_state', store=True,
        index=True)
    eam_days_left = fields.Integer(
        string='Còn (ngày)', compute='_compute_eam_state', store=True,
        aggregator=False,
        help='Số ngày tới ngày hết hạn. Âm là đã quá hạn bao nhiêu ngày.')

    @api.depends('valid_from', 'valid_to')
    def _compute_eam_state(self):
        hn = fields.Date.context_today(self)
        for s in self:
            s.eam_days_left = 0
            if s.valid_from and s.valid_from > hn:
                s.eam_state = 'future'
                continue
            if not s.valid_to:
                # Không khai ngày hết hạn thì coi là vô thời hạn. Đây là
                # mặc định TỐT: đoán ra một ngày hết hạn không có trên
                # giấy rồi chặn người ta làm việc là tệ hơn.
                s.eam_state = 'no_expiry'
                continue
            con = (s.valid_to - hn).days
            s.eam_days_left = con
            if con < 0:
                s.eam_state = 'expired'
            elif con <= NGUONG_SAP_HET:
                s.eam_state = 'expiring'
            else:
                s.eam_state = 'valid'

    def _hieu_luc_ngay(self, d):
        """Chứng chỉ này có hiệu lực vào NGÀY d hay không.

        Kiểm theo ngày LÀM VIỆC, không theo hôm nay. Đây là cái bẫy thật:
        hôm nay chứng chỉ còn hạn, lệnh xếp làm ba tuần nữa, tới lúc làm
        thì đã quá hạn — mà cổng chặn đã cho qua từ hôm kiểm.
        """
        self.ensure_one()
        if self.valid_from and self.valid_from > d:
            return False
        if self.valid_to and self.valid_to < d:
            return False
        return True

    @api.model
    def _cron_nhac_het_han(self):
        """Nhắc chứng chỉ sắp hết hạn, gửi vào chính hồ sơ nhân viên.

        Nhắc trước là toàn bộ giá trị của việc theo dõi hiệu lực. Phát
        hiện hết hạn vào đúng buổi sáng đội đã lên tới chân trụ thì thông
        tin đó không còn dùng được để làm gì.
        """
        ds = self.search([('eam_state', '=', 'expiring')])
        for s in ds:
            nv = s.employee_id
            if not nv or not hasattr(nv, 'message_post'):
                continue
            # Dịch TRƯỚC, bọc Markup, rồi mới thay giá trị: như vậy thẻ
            # `<b>` là thẻ thật còn tên chứng chỉ do người dùng nhập vẫn
            # được escape. Gọi `_()` kèm tham số rồi mới bọc thì tên đã
            # nằm trong chuỗi và không còn được escape nữa.
            nv.message_post(body=Markup(_(
                'Chứng chỉ <b>%(ten)s</b> hết hạn ngày %(d)s — còn %(n)d '
                'ngày. Hết hạn là lỗi xếp lịch đào tạo, sửa được trong '
                'tuần; để quá hạn rồi mới biết thì mất cả buổi của một '
                'đội.')) % {'ten': s.skill_id.name or '',
                            'd': s.valid_to, 'n': s.eam_days_left})
        return True
