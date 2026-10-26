# -*- coding: utf-8 -*-
"""Ký Biên bản xác nhận KPI/SLA của một kỳ hợp đồng O&M."""
from odoo import _, models
from odoo.exceptions import UserError


class EamOmPeriod(models.Model):
    _name = 'eam.om.period'
    _inherit = ['eam.om.period', 're.signable']

    # ------------------------------------------------------------------
    def _sign_payload(self):
        """Những gì chữ ký trên biên bản KPI bảo chứng.

        Đây là chứng từ ra TIỀN, nên phải băm cả ba tầng, không chỉ con
        số cuối:

        * **Mức cam kết và chiều** — sửa ngưỡng từ ≥97% xuống ≥95% là
          một cam kết không đạt bỗng thành đạt, mà tổng phạt thì có thể
          vẫn trùng nếu còn dòng khác bù vào.
        * **`gia_tri` lẫn `gia_tri_tho`** — con số đi vào biên bản là
          bản ĐÃ LÀM TRÒN; giữ cả bản thô vì tranh cãi về chỗ làm tròn
          là tranh cãi có thật, và nếu chỉ băm bản tròn thì sửa bản thô
          xong không ai phát hiện.
        * **`do_duoc` và lý do** — "chưa đo được" là một lời khẳng định
          về chất lượng dữ liệu, không phải một ô trống.
        * **Giờ chưa quy trách nhiệm** — phân loại lại một khoảng dừng
          là đổi hẳn con số khả dụng. Không băm thì biên bản ký rồi vẫn
          "hợp lệ" sau khi ai đó quy lại trách nhiệm.

        Và băm cả dòng thanh toán theo từng nhà máy, vì tổng có thể
        giữ nguyên trong khi phần chia giữa các nhà máy đổi.
        """
        self.ensure_one()
        tt = dict(self._fields['state'].selection)
        huong = dict(self.env['eam.om.period.line']._fields['huong'].selection)
        loai = dict(self.env['eam.om.period.line']._fields['loai'].selection)
        dong = [
            'Biên bản xác nhận KPI/SLA',
            'Hợp đồng: %s — %s' % (self.contract_id.name or '',
                                   self.contract_id.title or ''),
            'Nhà thầu O&M: %s' % (self.partner_id.name or ''),
            'Kỳ: %s → %s (%s)' % (self.date_start or '', self.date_end or '',
                                  self.chu_ky or ''),
            'Là kỳ tính phí: %s' % ('có' if self.la_ky_phi else 'không'),
            'Trạng thái: %s' % tt.get(self.state, self.state or ''),
            'Đo lúc: %s' % (self.date_measured or ''),
            '--- Kết quả cam kết ---',
        ]
        for ln in self.line_ids.sorted(lambda l: (l.plant_id.id, l.id)):
            if ln.do_duoc:
                do = '%.2f (thô %.6f)' % (ln.gia_tri or 0.0,
                                          ln.gia_tri_tho or 0.0)
            else:
                do = 'chưa đo được (%s)' % (ln.ly_do_chua_do or '')
            dong.append(
                '%s | %s | %s | cam kết %s %.2f | đo %s | %s | '
                'thiếu hụt %.2f | phạt %.2f | giờ chưa quy %.2f (%.2f%%)%s'
                % (ln.plant_id.name or '', ln.ten_cam_ket or '',
                   loai.get(ln.loai, ln.loai or ''),
                   huong.get(ln.huong, ln.huong or ''),
                   ln.muc_cam_ket or 0.0, do,
                   'ĐẠT' if ln.dat else 'KHÔNG ĐẠT',
                   ln.thieu_hut or 0.0, ln.phat or 0.0,
                   ln.gio_chua_quy or 0.0, ln.ty_le_chua_quy or 0.0,
                   ' [CẢNH BÁO]' if ln.canh_bao_chua_quy else ''))
        dong.append('--- Thanh toán theo nhà máy ---')
        for p in self.plant_ids.sorted(lambda x: x.plant_id.id):
            dong.append('%s | phí %.2f | phạt %.2f | phải trả %.2f' % (
                p.plant_id.name or '', p.phi or 0.0, p.phat or 0.0,
                p.thanh_toan or 0.0))
        dong += [
            '--- Tổng ---',
            'Tổng phí: %.2f %s' % (self.tong_phi or 0.0,
                                   self.currency_id.name or ''),
            'Tổng phạt: %.2f' % (self.tong_phat or 0.0),
            'Phải trả: %.2f' % (self.tong_thanh_toan or 0.0),
            'Cam kết không đạt: %s' % (self.so_khong_dat or 0),
            'Ghi chú biên bản: %s' % (self.note or ''),
        ]
        return '\n'.join(dong)

    # ------------------------------------------------------------------
    def _ca_report_ref(self):
        return 'eam_sign.action_in_bien_ban_kpi'

    def _ca_file_name(self):
        self.ensure_one()
        return 'Bien ban KPI %s %s-%s - da ky so.pdf' % (
            (self.contract_id.name or '').replace('/', '-'),
            self.date_start or '', self.date_end or '')

    def _ca_reason(self):
        return _('Xác nhận KPI/SLA kỳ %(a)s → %(b)s',
                 a=self.date_start or '', b=self.date_end or '')

    def _approval_amount(self):
        """Giá trị khớp ngưỡng phê duyệt = số tiền PHẢI TRẢ của kỳ."""
        self.ensure_one()
        return self.tong_thanh_toan or 0.0

    def action_ky_so(self):
        """Hai cửa chặn trước khi ký.

        Cửa thứ hai mới là cửa đáng kể: `co_canh_bao` nghĩa là có dòng
        chưa đo được, hoặc giờ dừng chưa quy trách nhiệm vượt ngưỡng —
        con số khả dụng đang ĐẸP vì chưa ai phân loại. Ký lên đó rồi
        tuần sau người ta quy trách nhiệm xong, con số đổi, mà biên bản
        thì đã đóng dấu. Chặn ở đây rẻ hơn nhiều so với rút lại một
        biên bản đã gửi nhà thầu.
        """
        self.ensure_one()
        if self.state != 'chot':
            raise UserError(_(
                'Chỉ ký được kỳ ĐÃ CHỐT. Kỳ này đang ở "%s" — mức cam '
                'kết và phí chưa đóng băng, đo lại một lượt là số đổi.')
                % dict(self._fields['state'].selection).get(self.state))
        if self.co_canh_bao:
            raise UserError(_(
                'Kỳ này còn cảnh báo nên chưa nên ký: có dòng chưa đo '
                'được, hoặc giờ dừng chưa quy trách nhiệm vượt ngưỡng. '
                'Con số khả dụng có thể đang đẹp vì chưa ai phân loại — '
                'phân loại xong, đo lại, chốt lại rồi hãy ký.'))
        return super().action_ky_so()
