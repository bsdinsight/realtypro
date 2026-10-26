# -*- coding: utf-8 -*-
"""Ký Báo cáo vận hành ngày."""
from odoo import _, models
from odoo.exceptions import UserError


class EamDailyReport(models.Model):
    _name = 'eam.daily.report'
    _inherit = ['eam.daily.report', 're.signable']

    # ------------------------------------------------------------------
    def _sign_payload(self):
        """Những gì chữ ký trên báo cáo ngày bảo chứng.

        Gồm TỪNG DÒNG SỐ, không chỉ `sl_ban`. Tờ báo cáo ngày là một
        bảng số: băm mỗi con số tổng thì sửa sản lượng từng bậc đo xong
        chữ ký vẫn báo hợp lệ, trong khi đó mới là thứ chủ đầu tư đọc.

        Gồm cả `do_duoc` và `ly_do_chua_do`: "chưa đo được" là một lời
        khẳng định, và đổi một dòng từ "chưa đo được" sang một con số
        (hay ngược lại) là đổi nội dung chịu trách nhiệm.

        Gồm bốn khối chữ. Khối *Sự cố* và *Hoạt động* chính là phần hay
        bị viết lại nhất sau khi đã ký — bỏ ra ngoài thì chữ ký không
        bảo chứng được đúng cái người ta sẽ tranh cãi.

        Gồm `ban_so`: bản 2 của cùng một ngày là một tờ KHÁC, không phải
        tờ cũ sửa lại.
        """
        self.ensure_one()
        tt = dict(self._fields['state'].selection)
        dong = [
            'Báo cáo vận hành ngày',
            'Nhà máy: %s [%s]' % (self.plant_id.name or '',
                                  self.plant_id.code or ''),
            'Ngày: %s' % (self.date or ''),
            'Bản số: %s' % (self.ban_so or 1),
            'Múi giờ đã dùng: %s' % (self.mui_gio or ''),
            'Hồ sơ cấu hình: %s' % (self.profile_id.name or ''),
            'Trạng thái: %s' % tt.get(self.state, self.state or ''),
            'Sản lượng bán (kWh): %.1f' % (self.sl_ban or 0.0),
            '--- Dòng số ---',
        ]
        # Thứ tự PHẢI ổn định, nếu không cùng một nội dung băm ra hai mã
        # khác nhau và chữ ký tự báo hỏng. `sequence, id` là thứ tự của
        # chính bảng con.
        for ln in self.line_ids.sorted(lambda l: (l.sequence, l.id)):
            if not ln.do_duoc:
                gt = 'chưa đo được (%s)' % (ln.ly_do_chua_do or '')
            elif ln.gia_tri_chu:
                gt = ln.gia_tri_chu
            else:
                gt = '%.4f' % (ln.gia_tri or 0.0)
            dong.append('%s | %s = %s %s' % (
                ln.khoi or '', ln.name or '', gt, ln.don_vi or ''))
        dong += [
            '--- Khối chữ ---',
            'Hoạt động: %s' % (self.hoat_dong or ''),
            'Kế hoạch ngày mai: %s' % (self.ke_hoach_mai or ''),
            'Sự cố: %s' % (self.su_co or ''),
            'Ghi chú: %s' % (self.ghi_chu_bc or ''),
        ]
        return '\n'.join(dong)

    # ------------------------------------------------------------------
    def _ca_report_ref(self):
        return 'eam_daily_report.action_in_bao_cao_ngay'

    def _ca_reason(self):
        return _('Xác nhận báo cáo vận hành ngày %s') % (self.date or '')

    def action_ky_so(self):
        """Chặn ký bản chưa chốt.

        Bản nháp còn rót lại số được. Ký lên nó là đóng dấu vào con số
        sẽ đổi, mà chữ ký số thì không biết chuyện đó — nó chỉ bảo chứng
        tờ PDF tại thời điểm ký.
        """
        self.ensure_one()
        if self.state != 'chot':
            raise UserError(_(
                'Chỉ ký số được bản ĐÃ CHỐT. Bản này đang ở trạng thái '
                '"%s" — số còn rót lại được, ký bây giờ là đóng dấu vào '
                'con số sẽ đổi.')
                % dict(self._fields['state'].selection).get(self.state))
        return super().action_ky_so()
