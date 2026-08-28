# -*- coding: utf-8 -*-
"""Xuất hồ sơ chào giá ra Excel, và chuyển hồ sơ trúng thầu sang dự án.

XUẤT: trả lại ĐÚNG bộ khung file khách gửi — cùng mã, cùng nội dung,
cùng đơn vị, cùng thứ tự, kể cả dòng tiêu đề nhóm. Chỉ điền thêm hai
cột khách bỏ trống là Đơn giá và Thành tiền. Tự ý sắp xếp lại hay đổi
chữ là rủi ro bị loại hồ sơ, dù số có đúng.

CHUYỂN SANG DỰ ÁN: bóc tách lúc chào chính là baseline thi công. Gõ lại
vừa tốn công vừa tạo ra hai bộ số lệch nhau ngay từ ngày đầu — và về sau
không ai biết bộ nào mới đúng.
"""
import base64
import io

from odoo import _, fields, models
from odoo.exceptions import UserError


class RpBidExport(models.Model):
    _inherit = 'rp.bid'

    export_file = fields.Binary(string='File chào giá', readonly=True,
                                attachment=True, copy=False)
    export_filename = fields.Char(readonly=True, copy=False)

    # ==================================================================
    def action_export_offer(self):
        """Xuất bảng chào giá theo khuôn bên mời thầu."""
        self.ensure_one()
        if not self.item_ids:
            raise UserError(_(
                'Chưa có dòng chào giá nào. Nhập BoQ mời thầu từ file Excel '
                'của khách trước đã.'))
        try:
            import xlsxwriter
        except ImportError:
            raise UserError(_('Máy chủ thiếu thư viện xlsxwriter.'))

        buf = io.BytesIO()
        wb = xlsxwriter.Workbook(buf, {'in_memory': True})
        ws = wb.add_worksheet('Bang chao gia')

        f_title = wb.add_format({'bold': True, 'font_size': 13})
        f_hdr = wb.add_format({'bold': True, 'border': 1, 'align': 'center',
                               'valign': 'vcenter', 'bg_color': '#DDDDDD',
                               'text_wrap': True})
        f_sec = wb.add_format({'bold': True, 'border': 1,
                               'bg_color': '#F2F2F2'})
        f_txt = wb.add_format({'border': 1, 'text_wrap': True,
                               'valign': 'top'})
        f_ctr = wb.add_format({'border': 1, 'align': 'center'})
        f_qty = wb.add_format({'border': 1, 'num_format': '#,##0.###'})
        f_mny = wb.add_format({'border': 1, 'num_format': '#,##0'})
        f_tot = wb.add_format({'bold': True, 'border': 1,
                               'num_format': '#,##0', 'bg_color': '#F2F2F2'})

        ws.set_column(0, 0, 8)
        ws.set_column(1, 1, 60)
        ws.set_column(2, 2, 10)
        ws.set_column(3, 3, 14)
        ws.set_column(4, 5, 20)

        ws.write(0, 0, self.package_id.name or self.name, f_title)
        ws.write(1, 0, _('Đơn vị chào giá: %s',
                         self.company_id.name or ''))
        ws.write(2, 0, _('Ngày: %s', fields.Date.context_today(self)))

        row = 4
        for i, label in enumerate(
                ['STT', 'Nội dung', 'Đơn vị', 'Khối lượng',
                 'Đơn giá', 'Thành tiền']):
            ws.write(row, i, label, f_hdr)
        row += 1

        total = 0.0
        for item in self.item_ids.sorted('sequence'):
            if item.is_section:
                ws.write(row, 0, item.code or '', f_sec)
                ws.write(row, 1, item.name, f_sec)
                for c in range(2, 6):
                    ws.write(row, c, '', f_sec)
                row += 1
                continue
            ws.write(row, 0, item.code or '', f_ctr)
            ws.write(row, 1, item.name, f_txt)
            ws.write(row, 2, item.uom_text or '', f_ctr)
            ws.write_number(row, 3, item.quantity_client or 0.0, f_qty)
            ws.write_number(row, 4, round(item.unit_price_offer or 0.0), f_mny)
            ws.write_number(row, 5, round(item.amount_offer or 0.0), f_mny)
            total += item.amount_offer or 0.0
            row += 1

        ws.write(row, 1, _('Tổng cộng (đã gồm thuế GTGT)'), f_tot)
        ws.write(row, 5, round(total), f_tot)

        # Ghi rõ giả định — người nhận hồ sơ phải thấy, không giấu trong mail
        row += 2
        ws.write(row, 0, _('Ghi chú:'), wb.add_format({'bold': True}))
        notes = [_('Đơn giá đã bao gồm chi phí chung, nhà tạm, thu nhập '
                   'chịu thuế tính trước và thuế GTGT.')]
        if self.client_supplied_cost:
            notes.append(_(
                'Giá chào KHÔNG bao gồm vật tư do bên mời thầu cung cấp '
                '(giá trị tham chiếu %s).',
                '{:,.0f}'.format(self.client_supplied_cost)))
        if self.unallocated_cost:
            notes.append(_(
                'Có %s chi phí thuộc phạm vi công việc nhưng chưa có dòng '
                'tương ứng trong bảng mời thầu — đề nghị bên mời thầu làm '
                'rõ.', '{:,.0f}'.format(self.unallocated_cost)))
        for n in notes:
            row += 1
            ws.write(row, 1, n)

        wb.close()
        self.export_file = base64.b64encode(buf.getvalue())
        self.export_filename = 'Chao_gia_%s.xlsx' % (
            self.code or self.id)
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/rp.bid/%s/export_file/%s?download=true'
                   % (self.id, self.export_filename),
            'target': 'self',
        }

    # ==================================================================
    def action_convert_to_project(self):
        """Trúng thầu → sinh hạng mục + BoQ cho dự án từ cây của nhà thầu.

        Trước đây hàm này đổ BoQ vào hạng mục dự án đã có, dựa trên một
        liên kết ngược từ hạng mục nhà thầu lên hạng mục dự án. Bỏ liên
        kết đó đi (nhà thầu không biết cây hạng mục của chủ đầu tư) thì
        cách đúng là NGƯỢC LẠI: cách chia của nhà thầu chính là cách họ
        sẽ thi công, nên nó trở thành cây hạng mục của dự án.

        Hạng mục nhà thầu phẳng một cấp nên chuyển thẳng, không phải
        lọc bỏ cấp gom.
        """
        self.ensure_one()
        if self.state != 'won':
            raise UserError(_(
                'Chỉ chuyển sang dự án khi hồ sơ ở trạng thái Trúng thầu.'))

        Struct = self.env['rp.structure']
        Boq = self.env['rp.boq.line']
        # Dự án của nhà thầu chỉ là một cơ hội — không chạy tiến độ hay
        # thanh toán được trên đó. Muốn thi công thì phải có một `re.project`
        # thật, và nó chỉ sinh ra ở đúng thời điểm này.
        project = self.project_id.exec_project_id
        if not project:
            raise UserError(_(
                'Dự án "%(p)s" chưa gắn Dự án thi công. Mở dự án đó, tạo '
                'hoặc chọn một dự án thi công ở trường "Dự án thi công" '
                'rồi chuyển lại.', p=self.project_id.display_name))

        leaves = self.structure_ids
        if not leaves:
            raise UserError(_('Hồ sơ chưa có hạng mục nào để chuyển.'))

        # Phân khu: gom cả gói vào một phân khu mang tên gói thầu, để sau
        # này nhìn dự án là biết khối lượng nào đến từ gói nào.
        code = 'BID-%s' % (self.code or self.id)
        subzone = self.env['re.subzone'].search(
            [('project_id', '=', project.id), ('code', '=', code)], limit=1)
        if not subzone:
            subzone = self.env['re.subzone'].create({
                'project_id': project.id, 'code': code,
                'name': self.package_id.name or self.name,
            })

        category = self.env['rp.cost.category'].search(
            [('project_id', '=', project.id)], limit=1)
        if not category:
            raise UserError(_(
                'Dự án chưa có nhóm chi phí nào để gắn dòng BoQ.'))

        made_struct, made_line = 0, 0
        for seq, bs in enumerate(leaves.sorted('sequence'), 1):
            scode = '%s-%s' % (code, bs.code or seq)
            ps = Struct.search([('project_id', '=', project.id),
                                ('code', '=', scode)], limit=1)
            if not ps:
                ps = Struct.create({
                    'project_id': project.id,
                    'subzone_id': subzone.id,
                    'code': scode,
                    'name': bs.name,
                    'structure_level': 'item',
                    'structure_type': 'foundation',
                    'sequence': seq * 10,
                })
                made_struct += 1
            if ps.boq_line_ids:
                continue        # đã chuyển rồi, không cộng chồng
            vals = [{
                'structure_id': ps.id,
                'category_id': category.id,
                'sequence': line.sequence,
                'description': line.description,
                'uom_id': line.uom_id.id,
                'quantity': line.quantity,
                # BoQ dự án chỉ có MỘT ô đơn giá: lấy đơn giá đã vào giá
                # chào (đã loại vật tư bên mời thầu cấp).
                'unit_price': line.unit_price,
                'note': _(
                    'Từ hồ sơ dự thầu %(code)s — mã ĐM %(norm)s.\n'
                    'Tách gốc: VL %(vl)s | NC %(nc)s | Máy %(m)s',
                    code=self.code or self.id, norm=line.norm_code or '—',
                    vl='{:,.0f}'.format(line.material_amount),
                    nc='{:,.0f}'.format(line.labor_amount),
                    m='{:,.0f}'.format(line.machine_amount)),
            } for line in bs.line_ids]
            if vals:
                Boq.create(vals)
                made_line += len(vals)

        self.message_post(body=_(
            'Trúng thầu: đã sinh %(s)s hạng mục và %(l)s dòng BoQ cho dự '
            'án, gom trong phân khu "%(z)s".',
            s=made_struct, l=made_line, z=subzone.name))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Hạng mục dự án'),
            'res_model': 'rp.structure',
            'view_mode': 'list,form',
            'domain': [('subzone_id', '=', subzone.id)],
        }
