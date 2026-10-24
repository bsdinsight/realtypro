# -*- coding: utf-8 -*-
"""Ba việc người trực làm nhiều nhất với cảnh báo: hoãn, gom, xác nhận lô.

Hoãn phải CÓ HẠN
-----------------
Cảnh báo đã biết mà chưa sửa được ngay — chờ phụ tùng, chờ cửa sổ dừng
máy — thì người trực cần tắt nó đi, nếu không nó che mất cảnh báo mới.
Nhưng tắt **vĩnh viễn** là cách một nhà máy mất hẳn một lớp canh gác mà
không ai nhớ đã tắt gì.

Nên hoãn luôn kèm **hạn** và **lý do**, và tới hạn hệ tự bật lại. Người
hoãn không phải nhớ; hệ nhớ hộ.

Gom cùng gốc
-------------
Một sự cố đẻ ra cả chục cảnh báo: mất lưới làm mười hai tua-bin cùng
báo. Xử lý từng cái là mười hai lần gõ cùng một câu, và bản ghi sau đó
không cho biết chúng là MỘT chuyện.

Nên có cảnh báo GỐC: bình luận một lần, đóng một lần, và sổ giữ được
quan hệ cha–con để sau này đếm đúng *"sự cố"* chứ không đếm *"số dòng
cảnh báo"*.

Xác nhận hàng loạt KHÔNG được âm thầm
--------------------------------------
Chọn ba mươi dòng rồi xác nhận một lần là tiện. Nhưng mỗi dòng vẫn phải
ghi riêng ai xác nhận và lúc nào — nếu không, ba tháng sau không ai
truy được một cảnh báo cụ thể đã qua tay ai.
"""
import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class EamAlarm(models.Model):
    _inherit = 'eam.alarm'

    # ----- Hoãn có hạn -------------------------------------------------
    snooze_den = fields.Datetime(
        string='Hoãn tới', copy=False, index=True, tracking=True,
        help='Tới mốc này hệ TỰ BẬT LẠI. Hoãn không hạn là cách một nhà '
             'máy mất hẳn một lớp canh gác mà không ai nhớ đã tắt gì.')
    snooze_ly_do = fields.Char(string='Lý do hoãn', copy=False,
                               tracking=True)
    snooze_user_id = fields.Many2one('res.users', string='Người hoãn',
                                     readonly=True, copy=False)
    dang_hoan = fields.Boolean(
        string='Đang hoãn', compute='_compute_dang_hoan', search='_search_hoan')

    # ----- Gom cùng gốc ------------------------------------------------
    parent_alarm_id = fields.Many2one(
        'eam.alarm', string='Thuộc cảnh báo gốc', index=True,
        ondelete='set null', copy=False,
        help='Một sự cố đẻ ra cả chục cảnh báo. Gom lại để đếm đúng SỰ '
             'CỐ, chứ không đếm số dòng.')
    child_alarm_ids = fields.One2many('eam.alarm', 'parent_alarm_id',
                                      string='Cảnh báo cùng gốc')
    child_count = fields.Integer(compute='_compute_child', store=True)
    la_goc = fields.Boolean(compute='_compute_child', store=True,
                            string='Là cảnh báo gốc')

    # ==================================================================
    @api.depends('snooze_den')
    def _compute_dang_hoan(self):
        bg = fields.Datetime.now()
        for a in self:
            a.dang_hoan = bool(a.snooze_den and a.snooze_den > bg)

    @api.model
    def _search_hoan(self, operator, value):
        bg = fields.Datetime.now()
        dk = ['&', ('snooze_den', '!=', False), ('snooze_den', '>', bg)]
        co = (operator in ('=', 'in') and value) or \
             (operator in ('!=', 'not in') and not value)
        return dk if co else ['!'] + dk

    @api.depends('child_alarm_ids')
    def _compute_child(self):
        for a in self:
            a.child_count = len(a.child_alarm_ids)
            a.la_goc = bool(a.child_alarm_ids)

    # ==================================================================
    def action_hoan(self):
        """Mở hộp thoại hoãn — bắt khai CẢ hạn lẫn lý do."""
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'eam.alarm.snooze.wizard',
            'view_mode': 'form', 'target': 'new',
            'name': _('Hoãn cảnh báo'),
            'context': {'default_alarm_ids': self.ids},
        }

    def action_bo_hoan(self):
        self.write({'snooze_den': False, 'snooze_ly_do': False,
                    'snooze_user_id': False})
        for a in self:
            a.message_post(body=_('Bỏ hoãn, cảnh báo bật lại.'))
        return True

    @api.model
    def _cron_het_hoan(self):
        """Tới hạn thì bật lại — và NÓI RA, không bật lặng lẽ."""
        bg = fields.Datetime.now()
        het = self.search([('snooze_den', '!=', False),
                           ('snooze_den', '<=', bg),
                           ('state', 'not in', ('cleared', 'ignored'))])
        for a in het:
            a.message_post(body=_(
                'Hết hạn hoãn (%(d)s). Cảnh báo bật lại. Lý do hoãn trước '
                'đó: %(l)s', d=a.snooze_den, l=a.snooze_ly_do or '—'))
            a.write({'snooze_den': False, 'snooze_ly_do': False,
                     'snooze_user_id': False})
        return {'da_bat_lai': len(het)}

    # ==================================================================
    def action_ack_lo(self):
        """Xác nhận hàng loạt — mỗi dòng vẫn ghi riêng ai và lúc nào."""
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'eam.alarm.ack.wizard',
            'view_mode': 'form', 'target': 'new',
            'name': _('Xác nhận %d cảnh báo', len(self)),
            'context': {'default_alarm_ids': self.ids},
        }

    def action_gom_cung_goc(self):
        """Lấy cảnh báo NỔ SỚM NHẤT làm gốc, các cái còn lại thành con."""
        if len(self) < 2:
            raise UserError(_('Chọn từ hai cảnh báo trở lên để gom.'))
        goc = min(self, key=lambda a: a.date_raised)
        con = self - goc
        if any(a.parent_alarm_id and a.parent_alarm_id != goc for a in con):
            raise UserError(_(
                'Trong số đã chọn có cảnh báo đang thuộc một gốc KHÁC. '
                'Gỡ nó ra trước — một cảnh báo chỉ thuộc một sự cố.'))
        con.write({'parent_alarm_id': goc.id})
        goc.message_post(body=_(
            'Gom %(n)d cảnh báo về đây làm một sự cố: %(ds)s',
            n=len(con), ds=', '.join(con.mapped('display_name')[:10])))
        return {
            'type': 'ir.actions.act_window', 'res_model': 'eam.alarm',
            'res_id': goc.id, 'view_mode': 'form',
        }

    def action_go_khoi_goc(self):
        self.write({'parent_alarm_id': False})
        return True


class EamAlarmSnoozeWizard(models.TransientModel):
    _name = 'eam.alarm.snooze.wizard'
    _description = 'Hoãn cảnh báo'

    alarm_ids = fields.Many2many('eam.alarm', required=True)
    so_gio = fields.Integer(
        string='Hoãn bao nhiêu giờ', default=24, required=True,
        help='Tới hạn hệ tự bật lại và ghi vào trao đổi của cảnh báo.')
    ly_do = fields.Char(
        string='Lý do', required=True,
        help='Ba tháng sau, đây là thứ duy nhất giải thích vì sao một '
             'cảnh báo nghiêm trọng từng bị tắt tiếng.')

    def action_hoan(self):
        self.ensure_one()
        if self.so_gio <= 0:
            raise UserError(_('Số giờ hoãn phải lớn hơn 0.'))
        den = fields.Datetime.now() + timedelta(hours=self.so_gio)
        self.alarm_ids.write({
            'snooze_den': den, 'snooze_ly_do': self.ly_do,
            'snooze_user_id': self.env.user.id})
        for a in self.alarm_ids:
            a.message_post(body=_(
                'Hoãn tới %(d)s. Lý do: %(l)s', d=den, l=self.ly_do))
        return True


class EamAlarmAckWizard(models.TransientModel):
    _name = 'eam.alarm.ack.wizard'
    _description = 'Xác nhận cảnh báo hàng loạt'

    alarm_ids = fields.Many2many('eam.alarm', required=True)
    binh_luan = fields.Char(
        string='Bình luận', required=True,
        help='Một câu cho cả lô — nhưng mỗi cảnh báo vẫn ghi riêng ai xác '
             'nhận và lúc nào, để sau còn truy được từng cái.')

    def action_ack(self):
        self.ensure_one()
        bg = fields.Datetime.now()
        da = self.alarm_ids.filtered(
            lambda a: a.state in ('new',) and not a.ack_user_id)
        bo_qua = self.alarm_ids - da
        da.write({'state': 'ack', 'ack_user_id': self.env.user.id,
                  'ack_date': bg})
        for a in da:
            a.message_post(body=_('Xác nhận: %s', self.binh_luan))
        if bo_qua:
            # Nói ra số bị bỏ qua. Im lặng thì người bấm tưởng đã xác
            # nhận cả ba mươi dòng, trong khi có dòng đã đóng từ trước.
            return {
                'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'type': 'warning', 'sticky': False, 'message': _(
                    'Đã xác nhận %(a)d cảnh báo. BỎ QUA %(b)d cái vì chúng '
                    'không còn ở trạng thái "Mới" hoặc đã có người xác '
                    'nhận trước.', a=len(da), b=len(bo_qua))},
            }
        return True
