# -*- coding: utf-8 -*-
"""Theo dõi tiến độ lệnh công việc: lệch kế hoạch và đẩy cảnh báo trễ hạn.

Dữ liệu đã có, thiếu chỗ nhìn — và thiếu cú ĐẨY
------------------------------------------------
Lệnh công việc đã có đủ bốn mốc: dự kiến bắt đầu, dự kiến xong, thực tế
bắt đầu, thực tế xong. Thứ thiếu là **đặt chúng cạnh nhau** và **nói cho
người phụ trách biết khi trễ** — chứ không chờ người ta mở màn hình mới
thấy. Lệnh trễ mà không ai mở màn hình thì nó trễ tiếp.

Vì sao `trễ hạn` là TRƯỜNG THƯỜNG, không phải trường tính
----------------------------------------------------------
"Đã quá hạn chưa" phụ thuộc vào **bây giờ là mấy giờ**, mà thời điểm
hiện tại không thể nằm trong ``@api.depends``. Khai thành trường tính có
lưu thì Odoo không bao giờ thấy lý do tính lại, và cờ đứng yên mãi ở giá
trị lúc tạo — một cái sai im lặng mà màn hình không báo gì. Đã dính đúng
kiểu này ở hạn nghĩa vụ và ở tổn thất bậc thang.

Nên ở đây là trường thường, do **cron** cập nhật. Lọc được, cộng được, và
không giả vờ tự biết.

Trễ vì bị bỏ quên KHÁC trễ vì đang chờ
---------------------------------------
Một lệnh quá hạn vì chờ phụ tùng chưa về là vấn đề của chuỗi cung ứng,
không phải của người thợ. Nhắc người phụ trách mỗi ngày về chuyện họ
không giải quyết được là cách nhanh nhất khiến họ bỏ qua mọi thông báo
về sau. Nên hai loại trễ tách riêng, và **chỉ loại bị bỏ quên mới đẩy
thông báo**.

Không nhắc lại mỗi ngày
------------------------
Cron chạy hằng ngày nhưng chỉ đẩy khi **vượt một nấc mới**: vừa quá hạn,
rồi ba ngày, rồi bảy ngày. Nhắc lại mỗi ngày thì sau một tuần người ta
lọc hết thông báo vào thùng rác, và lúc có lệnh thật sự gấp thì không ai
nhìn.
"""
from datetime import timedelta

from odoo import _, api, fields, models

#: Trạng thái coi là đã khép lại, không còn tính trễ.
XONG = ('done', 'closed', 'cancelled')

#: Các nấc leo thang, theo giờ quá hạn. Số nhỏ trước.
NAC = [('moi', 0), ('ba_ngay', 72), ('bay_ngay', 168)]


class EamWorkOrder(models.Model):
    _inherit = 'eam.work.order'

    # ----- Lệch kế hoạch so với thực tế (A06.1) ----------------------
    lech_bat_dau = fields.Float(
        string='Bắt đầu trễ (giờ)', digits=(10, 1), compute='_compute_lech',
        store=True, aggregator=False,
        help='Thực tế bắt đầu trừ dự kiến bắt đầu. Âm là bắt đầu sớm.')
    lech_ket_thuc = fields.Float(
        string='Xong trễ (giờ)', digits=(10, 1), compute='_compute_lech',
        store=True, aggregator=False)
    lech_gio_cong = fields.Float(
        string='Lệch giờ công', digits=(10, 1), compute='_compute_lech',
        store=True, aggregator=False,
        help='Số giờ làm thực tế trừ khoảng dự kiến. Dương là làm lâu hơn '
             'dự tính.')

    # ----- Trễ hạn: TRƯỜNG THƯỜNG, do cron cập nhật (A06.4) ----------
    tre_han = fields.Boolean(
        string='Đang trễ hạn', index=True, copy=False,
        help='Cron cập nhật. KHÔNG phải trường tính: "đã quá hạn chưa" '
             'phụ thuộc vào bây giờ là mấy giờ, mà thời điểm hiện tại '
             'không nằm được trong @api.depends — khai thành trường tính '
             'có lưu thì cờ đứng yên mãi mà không gì báo.')
    so_gio_tre = fields.Float(
        string='Quá hạn (giờ)', digits=(10, 1), copy=False)
    tre_vi_cho = fields.Boolean(
        string='Trễ vì đang chờ', copy=False,
        help='Quá hạn nhưng lệnh đang ở trạng thái chờ. Đây là vấn đề của '
             'chuỗi cung ứng chứ không phải của người thợ, nên KHÔNG đẩy '
             'thông báo — nhắc người ta mỗi ngày về việc họ không giải '
             'quyết được là cách nhanh nhất khiến họ bỏ qua mọi thông báo '
             'về sau.')
    muc_canh_bao = fields.Selection(
        [('khong', 'Chưa báo'),
         ('moi', 'Vừa quá hạn'),
         ('ba_ngay', 'Quá 3 ngày'),
         ('bay_ngay', 'Quá 7 ngày')],
        string='Đã báo tới nấc', default='khong', required=True, copy=False)
    lan_canh_bao_cuoi = fields.Datetime(
        string='Báo lần cuối', readonly=True, copy=False)

    # ==================================================================
    @api.depends('date_planned_start', 'date_planned_end',
                 'date_start', 'date_end', 'duration_hours')
    def _compute_lech(self):
        for o in self:
            o.lech_bat_dau = (
                (o.date_start - o.date_planned_start).total_seconds() / 3600.0
                if o.date_start and o.date_planned_start else 0.0)
            o.lech_ket_thuc = (
                (o.date_end - o.date_planned_end).total_seconds() / 3600.0
                if o.date_end and o.date_planned_end else 0.0)
            du_kien = (
                (o.date_planned_end - o.date_planned_start).total_seconds()
                / 3600.0
                if o.date_planned_end and o.date_planned_start else 0.0)
            o.lech_gio_cong = (o.duration_hours - du_kien
                               if o.duration_hours and du_kien else 0.0)

    # ==================================================================
    @api.model
    def _cron_canh_bao_tre_han(self):
        """Quét lệnh quá hạn, cập nhật cờ và đẩy thông báo theo NẤC.

        Chạy hằng ngày nhưng chỉ đẩy khi vượt một nấc mới. Nhắc lại mỗi
        ngày thì sau một tuần người ta lọc hết thông báo vào thùng rác,
        và lúc có lệnh thật sự gấp thì không ai nhìn.
        """
        bg = fields.Datetime.now()

        # Lệnh đã khép lại hoặc đã kịp xong thì gỡ cờ — cờ trễ còn treo
        # trên lệnh đã xong là cách làm hỏng mọi con số đếm sau này.
        het = self.search(['|', ('state', 'in', XONG),
                           ('date_planned_end', '>', bg),
                           ('tre_han', '=', True)])
        if het:
            het.write({'tre_han': False, 'so_gio_tre': 0.0,
                       'tre_vi_cho': False, 'muc_canh_bao': 'khong'})

        tre = self.search([
            ('state', 'not in', XONG),
            ('date_planned_end', '!=', False),
            ('date_planned_end', '<', bg)])
        day = 0
        for o in tre:
            gio = (bg - o.date_planned_end).total_seconds() / 3600.0
            cho = bool(o.is_on_hold) if 'is_on_hold' in o._fields else False
            nac = 'moi'
            for ten, nguong in NAC:
                if gio >= nguong:
                    nac = ten
            vals = {'tre_han': True, 'so_gio_tre': gio, 'tre_vi_cho': cho}

            # Chỉ đẩy khi LEO NẤC, và không đẩy cho lệnh đang chờ.
            cu = dict(NAC).get(o.muc_canh_bao, -1)
            if not cho and dict(NAC)[nac] > cu:
                o._day_canh_bao(gio, nac)
                vals['muc_canh_bao'] = nac
                vals['lan_canh_bao_cuoi'] = bg
                day += 1
            o.write(vals)
        return {'tre': len(tre), 'da_day': day}

    def _day_canh_bao(self, gio, nac):
        """Đẩy vào việc cần làm của người phụ trách, không gửi thư.

        Thư điện tử trôi mất giữa hàng trăm thư khác; việc cần làm nằm
        ngay trong màn làm việc hằng ngày và có người đóng nó lại.
        """
        self.ensure_one()
        if not self.user_id:
            return
        nhan = dict(self._fields['muc_canh_bao'].selection).get(nac, nac)
        self.activity_schedule(
            'mail.mail_activity_data_todo',
            user_id=self.user_id.id,
            summary=_('Lệnh công việc trễ hạn — %s', nhan),
            note=_('Lệnh "%(ten)s" tại %(vt)s đã quá hạn %(g).0f giờ '
                   '(dự kiến xong %(h)s).',
                   ten=self.display_name,
                   vt=self.location_id.complete_code or '—',
                   g=gio, h=self.date_planned_end))

    def action_quet_tre_han(self):
        """Quét tay — để không phải chờ tới giờ cron mới thấy kết quả."""
        kq = self._cron_canh_bao_tre_han()
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {
                'type': 'info',
                'message': _('Quét xong: %(t)d lệnh đang trễ, đã đẩy '
                             '%(d)d thông báo mới.',
                             t=kq['tre'], d=kq['da_day']),
                'sticky': False,
            },
        }
