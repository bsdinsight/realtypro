# -*- coding: utf-8 -*-
"""Xuất tờ báo cáo ngày ra Excel.

Vì sao cần CẢ Excel, không chỉ PDF
-----------------------------------
PDF là bản để **gửi và lưu**: nó cố định, ký được, không ai sửa lén.
Excel là bản để **làm việc tiếp**: người nhận cộng thêm một cột, dán
sang báo cáo tháng, đối chiếu với tệp của nhà thầu. Tờ gốc của nhà máy
vốn là một tệp Excel, nên đưa họ PDF thôi là bắt họ gõ lại.

Hai bản, một nguồn
-------------------
Cả hai đều dựng từ **chính các dòng đã chốt trên tờ**, không tính lại.
Nếu Excel đi hỏi lại dữ liệu gốc thì tờ PDF đã chốt và tệp Excel của
cùng một ngày sẽ lệch nhau — và đó là loại lệch không ai phát hiện cho
tới lúc họp.

Ô trống vẫn là ô trống
-----------------------
Dòng chưa đo được ghi ``—`` kèm lý do ở cột bên cạnh, **không ghi 0**.
Trong Excel điều này còn quan trọng hơn PDF: số 0 sẽ bị cộng vào tổng
khi người nhận kéo công thức.
"""
import base64
import io
import logging

from odoo import _, models

_logger = logging.getLogger(__name__)


class EamDailyReport(models.Model):
    _inherit = 'eam.daily.report'

    def action_xuat_excel(self):
        """Dựng tệp .xlsx và trả về đường tải."""
        self.ensure_one()
        import xlsxwriter

        bo = io.BytesIO()
        wb = xlsxwriter.Workbook(bo, {'in_memory': True,
                                      'default_date_format': 'dd/mm/yyyy'})
        f = self._dinh_dang(wb)
        ws = wb.add_worksheet(self.date.strftime('%d%m%Y'))
        ws.set_column('A:A', 52)
        ws.set_column('B:B', 18)
        ws.set_column('C:C', 10)
        ws.set_column('D:D', 46)
        d = 0

        ws.merge_range(d, 0, d, 3, self.profile_id.tieu_de or '', f['h1'])
        d += 1
        ws.merge_range(d, 0, d, 3, '%s · %s' % (
            self.plant_id.name, self.date.strftime('%d/%m/%Y')), f['h2'])
        d += 2
        if self.state != 'chot':
            ws.merge_range(d, 0, d, 3, _(
                'NHÁP — chưa chốt. Số liệu còn có thể đổi.'), f['canh'])
            d += 2
        if self.ban_so > 1:
            ws.merge_range(d, 0, d, 3, _(
                'Bản %(n)d — thay cho bản %(c)d. Lý do: %(l)s',
                n=self.ban_so, c=self.ban_so - 1, l=self.ly_do_sua or ''),
                f['canh'])
            d += 2

        for k in self._khoi_in():
            dong = self.line_ids.filtered(
                lambda l: l.khoi == k['ma']
                and (l.do_duoc or l.profile_line_id.in_khi_trong))
            if not dong:
                continue
            ws.merge_range(d, 0, d, 3, k['ten'], f['khoi'])
            d += 1
            for l in dong:
                if l.nguon == 'khoi':
                    d = self._khoi_excel(ws, f, d, l)
                    continue
                ws.write(d, 0, l.name or '', f['nhan'])
                if not l.do_duoc:
                    # KHÔNG ghi 0: trong Excel số 0 sẽ bị cộng vào tổng
                    # khi người nhận kéo công thức.
                    ws.write(d, 1, '—', f['trong'])
                elif l.kieu == 'chu':
                    ws.write(d, 1, l.gia_tri_chu or '', f['chu'])
                else:
                    ws.write_number(d, 1, l.gia_tri or 0.0,
                                    f['so'][min(max(l.so_le, 0), 4)])
                ws.write(d, 2, l.don_vi or '', f['dv'])
                ws.write(d, 3, (l.ly_do_chua_do if not l.do_duoc
                                else (l.nguon_ghi or '')), f['ghi'])
                d += 1
            d += 1

        d = self._hoat_dong_excel(ws, f, d)
        ws.write(d, 0, _('Người lập'), f['nhan'])
        ws.write(d, 1, self.create_uid.name or '', f['chu'])
        d += 1
        ws.write(d, 0, _('Người chốt'), f['nhan'])
        ws.write(d, 1, self.nguoi_chot_id.name or _('(chưa chốt)'), f['chu'])
        d += 1
        ws.write(d, 0, _('Múi giờ dùng cho biên ngày'), f['nhan'])
        ws.write(d, 1, self.mui_gio or '', f['chu'])

        wb.close()
        ten = 'BCN_%s_%s.xlsx' % (self.plant_id.code or 'NM',
                                  self.date.strftime('%Y%m%d'))
        att = self.env['ir.attachment'].create({
            'name': ten,
            'datas': base64.b64encode(bo.getvalue()),
            'res_model': self._name, 'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument'
                        '.spreadsheetml.sheet',
        })
        return {'type': 'ir.actions.act_url', 'target': 'self',
                'url': '/web/content/%d?download=true' % att.id}

    # ==================================================================
    def _dinh_dang(self, wb):
        xanh = '#0F2C3F'
        return {
            'h1': wb.add_format({'bold': True, 'font_size': 15,
                                 'align': 'center', 'font_color': xanh}),
            'h2': wb.add_format({'font_size': 11, 'align': 'center',
                                 'font_color': '#666666'}),
            'khoi': wb.add_format({'bold': True, 'bg_color': '#E8EEF1',
                                   'font_color': xanh, 'border': 1}),
            'nhan': wb.add_format({'text_wrap': False}),
            'chu': wb.add_format({'bold': True}),
            'trong': wb.add_format({'bold': True, 'align': 'right',
                                    'font_color': '#999999'}),
            'dv': wb.add_format({'font_color': '#666666'}),
            'ghi': wb.add_format({'font_size': 9, 'font_color': '#888888',
                                  'text_wrap': True}),
            'canh': wb.add_format({'bg_color': '#FFF3CD', 'border': 1}),
            'th': wb.add_format({'bold': True, 'bg_color': '#F2F2F2',
                                 'border': 1, 'text_wrap': True,
                                 'align': 'center', 'valign': 'vcenter'}),
            'td': wb.add_format({'border': 1}),
            'tdn': wb.add_format({'border': 1, 'num_format': '#,##0'}),
            'tdp': wb.add_format({'border': 1, 'num_format': '0.00"%"'}),
            'tong': wb.add_format({'border': 1, 'bold': True,
                                   'bg_color': '#F2F2F2'}),
            'tongn': wb.add_format({'border': 1, 'bold': True,
                                    'bg_color': '#F2F2F2',
                                    'num_format': '#,##0'}),
            'tongp': wb.add_format({'border': 1, 'bold': True,
                                    'bg_color': '#F2F2F2',
                                    'num_format': '0.00"%"'}),
            'so': {i: wb.add_format(
                {'align': 'right',
                 'num_format': '#,##0' + ('.' + '0'*i if i else '')})
                for i in range(5)},
        }

    def _khoi_excel(self, ws, f, d, dong):
        """Khối dựng sẵn: bảng tổ máy ra BẢNG THẬT, phần vẽ thì ghi chú."""
        ma = dong.profile_line_id.khoi_dac_biet
        if ma == 'bang_to_may':
            return self._bang_to_may_excel(ws, f, d)
        # Hoa gió và biểu đồ là HÌNH. Excel không chép hình sang được
        # mà vẫn giữ ý nghĩa, nên ghi thẳng con số rút ra từ chúng —
        # đó mới là thứ người nhận dùng tiếp.
        if ma == 'hoa_gio':
            h = self.hoa_gio()
            ws.write(d, 0, _('Hoa gió — hướng trội'), f['nhan'])
            ws.write(d, 1, '%s %.1f%%' % (h['troi_nhat']['ten'],
                                          h['troi_nhat']['tan_suat'])
                     if h.get('do_duoc') else '—', f['chu'])
            ws.write(d, 3, _('%d mốc đo · xem biểu đồ trên bản PDF',
                             h.get('so_moc', 0)) if h.get('do_duoc')
                     else h.get('ly_do', ''), f['ghi'])
            return d + 1
        if ma == 'bieu_do_ngay':
            g = self.bieu_do_ngay()
            ws.write(d, 0, _('Công suất đỉnh trong ngày'), f['nhan'])
            ws.write(d, 1, g['cs_max'] if g.get('do_duoc') else '—',
                     f['so'][1] if g.get('do_duoc') else f['trong'])
            ws.write(d, 2, 'kW', f['dv'])
            ws.write(d, 3, _('%d điểm · xem biểu đồ trên bản PDF',
                             len(g.get('diem', []))) if g.get('do_duoc')
                     else g.get('ly_do', ''), f['ghi'])
            return d + 1
        ws.write(d, 0, dong.name or '', f['nhan'])
        ws.write(d, 1, '—', f['trong'])
        ws.write(d, 3, _('khối chưa dựng'), f['ghi'])
        return d + 1

    def _bang_to_may_excel(self, ws, f, d):
        b = self.bang_to_may()
        if not b['dong']:
            ws.write(d, 0, _('Bảng tổ máy'), f['nhan'])
            ws.write(d, 1, '—', f['trong'])
            ws.write(d, 3, _('chưa dựng bảng tổ máy cho ngày này'), f['ghi'])
            return d + 1
        cot = [_('Tổ máy'), _('Sản lượng ngày (kWh)'),
               _('Luỹ kế tháng (kWh)'), _('Hệ số công suất'),
               _('Khả dụng — mọi nguyên nhân'),
               _('Khả dụng — phạm vi hợp đồng'), _('Khả dụng theo hãng')]
        for i, c in enumerate(cot):
            ws.write(d, i, c, f['th'])
        ws.set_row(d, 30)
        d += 1
        for x in b['dong']:
            ws.write(d, 0, x.location_code or '', f['td'])
            ws.write(d, 1, x.san_luong, f['tdn']) if x.do_duoc_sl \
                else ws.write(d, 1, '—', f['td'])
            ws.write(d, 2, x.luy_ke_thang, f['tdn'])
            ws.write(d, 3, x.he_so_cong_suat, f['tdp']) if x.do_duoc_hs \
                else ws.write(d, 3, '—', f['td'])
            ws.write(d, 4, x.kd_san_luong, f['tdp']) if x.do_duoc_kd \
                else ws.write(d, 4, '—', f['td'])
            ws.write(d, 5, x.kd_om, f['tdp']) if x.do_duoc_kd \
                else ws.write(d, 5, '—', f['td'])
            ws.write(d, 6, x.kd_nha_san_xuat, f['tdp']) \
                if x.kd_nha_san_xuat else ws.write(d, 6, '—', f['td'])
            d += 1
        t = b['tong']
        ws.write(d, 0, 'TOTAL', f['tong'])
        ws.write(d, 1, t['san_luong'], f['tongn'])
        ws.write(d, 2, t['luy_ke_thang'], f['tongn'])
        for i, k in enumerate(('he_so_cong_suat', 'kd_san_luong',
                               'kd_om', 'kd_nha_san_xuat')):
            v = t.get(k)
            ws.write(d, 3 + i, v, f['tongp']) if v is not None \
                else ws.write(d, 3 + i, '—', f['tong'])
        return d + 2

    def _hoat_dong_excel(self, ws, f, d):
        import re
        ws.merge_range(d, 0, d, 3, _('HOẠT ĐỘNG'), f['khoi'])
        d += 1

        def goi(h):
            return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', h or '')).strip()

        for ten, gt in [(_('Đã làm trong ngày'), self.hoat_dong),
                        (_('Kế hoạch ngày mai'), self.ke_hoach_mai),
                        (_('Sự cố'), self.su_co),
                        (_('Ghi chú'), self.ghi_chu_bc)]:
            ws.write(d, 0, ten, f['chu'])
            ws.merge_range(d, 1, d, 3, goi(gt), f['ghi'])
            ws.set_row(d, 34)
            d += 1
        return d + 1
