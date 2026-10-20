# -*- coding: utf-8 -*-
"""Lệnh công việc — giữ chỗ, xuất kho, hoàn trả.

Ba mốc tách bạch, vì gộp lại là nguồn gốc mọi sai lệch tồn kho:

1. **Giữ chỗ** — việc đã duyệt thì hàng phải được để dành. Không giữ chỗ
   thì hai lệnh cùng nhắm một con hộp số, và chỉ phát hiện lúc tổ thứ hai
   đã lên tới trụ.
2. **Xuất kho** — hàng rời kệ, đi theo người.
3. **Hoàn trả** — phần không dùng tới quay về. Thiếu bước này thì chốt
   "đóng lệnh phải xuất hết" biến mọi lần xin dư thành tiêu hao vĩnh
   viễn: nó TẠO RA sai lệch thay vì ngăn.

Phiếu ở đây là ``stock.move`` trần, KHÔNG bọc ``stock.picking``: đích đến
là vị trí ảo nên không kiểu phiếu nội bộ nào hợp. Odoo tiêu hao nguyên
liệu sản xuất cũng bằng move trần.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class EamWorkOrder(models.Model):
    _inherit = 'eam.work.order'

    stock_location_id = fields.Many2one(
        'stock.location', string='Kho xuất',
        domain="[('usage', '=', 'internal'), ('eam_cam_xuat', '=', False)]",
        help='Lấy vật tư từ kho nào. Tổ thợ lấy ở container ngoài hiện '
             'trường thì chọn đúng kho đó — chọn sai thì sổ kho đúng tổng '
             'nhưng sai chỗ, và lần sau không ai tìm thấy hàng.')
    part_cho_giu = fields.Integer(
        string='Dòng chưa giữ chỗ', compute='_compute_dem_part')
    part_cho_xuat = fields.Integer(
        string='Dòng chờ xuất kho', compute='_compute_dem_part')
    part_cho_tra = fields.Integer(
        string='Dòng chờ hoàn trả', compute='_compute_dem_part')

    @api.depends('part_line_ids.product_id', 'part_line_ids.move_id',
                 'part_line_ids.move_id.state',
                 'part_line_ids.khong_qua_kho',
                 'part_line_ids.qty_tra_moi')
    def _compute_dem_part(self):
        for o in self:
            o.part_cho_giu = len(o._part_can_giu())
            o.part_cho_xuat = len(o._part_can_xuat())
            o.part_cho_tra = len(o._part_can_tra())

    # ------------------------------------------------------------------
    def _part_goc(self):
        """Dòng có vật tư trong danh mục và đi qua kho.

        Dòng chỉ có ``part_name`` thì vốn không nằm trong danh mục kho —
        không có gì để giữ chỗ hay xuất, và đó là chuyện bình thường với
        vật tư mua gấp một lần.
        """
        self.ensure_one()
        return self.part_line_ids.filtered(
            lambda l: l.product_id and not l.khong_qua_kho)

    def _part_can_giu(self):
        return self._part_goc().filtered(lambda l: not l.move_id)

    def _part_can_xuat(self):
        return self._part_goc().filtered(
            lambda l: not l.move_id or l.move_id.state != 'done')

    def _part_can_tra(self):
        return self._part_goc().filtered(
            lambda l: l.qty_tra_moi and l.qty_tra_moi > 0)

    def _vi_tri_dich(self, line):
        xml = ('eam_stock.loc_da_lap_thiet_bi' if line.is_rotable
               else 'eam_stock.loc_tieu_dung_bao_tri')
        return self.env.ref(xml)

    def _vi_tri_tra(self, line):
        if line.tinh_trang_tra == 'hong':
            return self.env.ref('eam_stock.loc_hong_cho_thanh_ly')
        if line.tinh_trang_tra == 'kiem':
            return self.env.ref('eam_stock.loc_cho_kiem_tra')
        return self.stock_location_id

    def _goi_y_cho_khac(self, product, tru_vi_tri):
        """Vật tư này đang nằm ở đâu khác — để câu báo lỗi nói được việc
        cần làm, chứ không chỉ nói 'không đủ'."""
        quants = self.env['stock.quant'].search([
            ('product_id', '=', product.id),
            ('location_id.usage', '=', 'internal'),
            ('location_id', '!=', tru_vi_tri.id),
            ('quantity', '>', 0),
        ])
        if not quants:
            return ''
        cho = ', '.join(
            '%s (%g%s)' % (q.location_id.complete_name, q.quantity,
                           ' — không dùng được'
                           if q.location_id.eam_cam_xuat else '')
            for q in quants[:5])
        return _('\n\nHàng đang nằm ở: %s', cho)

    def _kiem_quyen_kho(self, vi_tri):
        """Chặn lấy hàng từ kho mình không được giao (KHO-40).

        Luật xem (``ir.rule``) chỉ giấu bản ghi đi; nó KHÔNG chặn một lời
        gọi biết trước id. Nên quyền thao tác phải kiểm riêng ở đây, chứ
        không dựa vào việc người ta "không nhìn thấy".
        """
        self.ensure_one()
        cho_phep = self.env.user._eam_kho_duoc_phep()
        if cho_phep is None:
            return
        kho = vi_tri.warehouse_id
        if kho and kho not in cho_phep:
            raise UserError(_(
                'Bạn không được giao kho "%(kho)s" nên không lấy hàng từ '
                '"%(vt)s" được.\n\nKho được giao: %(ds)s',
                kho=kho.name, vt=vi_tri.complete_name,
                ds=', '.join(cho_phep.mapped('name')) or _('(chưa khai kho nào)')))

    def _kiem_truoc_khi_giu(self, line):
        """Chặn sớm những thứ không thể giữ chỗ được."""
        self.ensure_one()
        p = line.product_id
        if not p.is_storable:
            raise UserError(_(
                'Vật tư "%s" không phải loại lưu kho nên không có tồn để '
                'giữ chỗ. Nếu đây là dịch vụ hoặc hàng mua thẳng, đánh '
                'dấu "Không qua kho".', p.display_name))
        if (line.qty or 0.0) <= 0:
            raise UserError(_(
                'Dòng vật tư "%s" có số lượng bằng 0.', p.display_name))
        if p.tracking == 'serial' and not line.lot_id:
            raise UserError(_(
                'Vật tư "%s" theo dõi theo sê-ri. Phải chọn đúng con sẽ '
                'lắp vào máy.\n\nHãng chỉ bảo hành con mang đúng số sê-ri '
                'đó — để hệ thống tự chọn một con bất kỳ là vứt đi quyền '
                'đòi bảo hành.', p.display_name))

    # ------------------------------------------------------------------
    def action_giu_cho(self):
        """Giữ hàng cho việc đã duyệt. Chưa lấy ra khỏi kệ."""
        Move = self.env['stock.move']
        ML = self.env['stock.move.line']
        thieu = []
        for o in self:
            if o.state in ('draft', 'cancelled'):
                raise UserError(_(
                    'Lệnh "%s" đang ở trạng thái nháp hoặc đã huỷ — chưa '
                    'giữ chỗ vật tư được.', o.name))
            dong = o._part_can_giu()
            if not dong:
                raise UserError(_(
                    'Lệnh "%s" không còn dòng vật tư nào cần giữ chỗ.',
                    o.name))
            if not o.stock_location_id:
                raise UserError(_(
                    'Chưa chọn "Kho xuất" cho lệnh "%s".', o.name))
            src = o.stock_location_id
            o._kiem_quyen_kho(src)

            for l in dong:
                o._kiem_truoc_khi_giu(l)
                p = l.product_id
                uom = l.uom_id or p.uom_id
                mv = Move.create({
                    'product_id': p.id,
                    'product_uom': uom.id,
                    'product_uom_qty': l.qty,
                    'location_id': src.id,
                    'location_dest_id': o._vi_tri_dich(l).id,
                    'eam_work_order_id': o.id,
                    'company_id': o.company_id.id,
                })
                mv._action_confirm()
                if l.lot_id:
                    # Sê-ri đã chỉ đích danh: tự dựng dòng chi tiết, vì
                    # _action_assign chọn lô theo chiến lược xuất kho và
                    # sẽ giữ nhầm con khác.
                    mv.move_line_ids.unlink()
                    ML.create({
                        'move_id': mv.id, 'product_id': p.id,
                        'product_uom_id': uom.id, 'quantity': l.qty,
                        'lot_id': l.lot_id.id,
                        'location_id': src.id,
                        'location_dest_id': mv.location_dest_id.id,
                        'company_id': o.company_id.id,
                    })
                else:
                    mv._action_assign()
                l.move_id = mv.id
                if mv.state != 'assigned':
                    thieu.append('%s (giữ được %g/%g)' % (
                        p.display_name, mv.quantity, l.qty))

            o.message_post(body=_(
                'Đã giữ chỗ %(n)d dòng vật tư tại "%(kho)s".',
                n=len(dong), kho=src.complete_name))

        if thieu:
            # Giữ chỗ thiếu KHÔNG phải lỗi — giữ được bao nhiêu hay bấy
            # nhiêu. Nhưng phải nói ra ngay, chứ không để tới lúc tổ thợ
            # đã lên trụ mới biết.
            return self._bao(
                _('Đã giữ chỗ, nhưng KHÔNG ĐỦ: %s', '; '.join(thieu)),
                'warning')
        return self._bao(_('Đã giữ chỗ xong.'), 'success')

    # ------------------------------------------------------------------
    def action_xuat_vat_tu(self):
        """Xuất hàng ra khỏi kệ. Dòng chưa giữ chỗ thì giữ luôn rồi xuất."""
        tong = 0
        for o in self:
            if o.state in ('draft', 'cancelled'):
                raise UserError(_(
                    'Lệnh "%s" đang ở trạng thái nháp hoặc đã huỷ — chưa '
                    'xuất kho được.', o.name))
            if not o._part_can_xuat():
                raise UserError(_(
                    'Lệnh "%s" không còn dòng vật tư nào chờ xuất kho.',
                    o.name))
            if o._part_can_giu():
                o.action_giu_cho()

            for l in o._part_can_xuat():
                mv = l.move_id
                p = l.product_id
                if mv.state != 'assigned':
                    raise UserError(_(
                        'Kho "%(kho)s" không đủ "%(sp)s": giữ chỗ được '
                        '%(giu)g / cần %(can)g.%(goiy)s',
                        kho=o.stock_location_id.complete_name,
                        sp=p.display_name, giu=mv.quantity, can=l.qty,
                        goiy=o._goi_y_cho_khac(p, o.stock_location_id)))
                mv.picked = True
                mv._action_done()
                if l.is_rotable:
                    o._noi_so_lap_dat(l)
                tong += 1

            o.message_post(body=_(
                'Đã xuất kho %(n)d dòng vật tư từ "%(kho)s".',
                n=tong, kho=o.stock_location_id.complete_name))
        return self._bao(_('Đã xuất %d dòng vật tư.', tong), 'success')

    # ------------------------------------------------------------------

    def _noi_so_lap_dat(self, line):
        """Xuất một con quay vòng = MỞ một quãng lắp đặt (KHO-23).

        Một sự kiện, hai sổ ghi hai mặt: sổ kho ghi hàng rời kệ, sổ lắp
        đặt ghi con đó bắt đầu nằm ở trụ nào. Không ghi chéo, không ghi
        hai lần.

        Con tháo ra (``asset_out_id``) thì ĐÓNG quãng cũ của nó. Bỏ qua
        bước này là mất dấu một tài sản mang sê-ri — và đó đúng là thứ
        cần để đòi bảo hành vài năm sau.
        """
        self.ensure_one()
        I = self.env['eam.installation']
        hn = fields.Date.context_today(self)
        # con lắp vào: ưu tiên ô đã khai, nếu trống thì suy từ sê-ri
        vao = line.asset_in_id
        if not vao and line.lot_id:
            vao = line.lot_id.eam_asset_id
            if vao:
                line.asset_in_id = vao.id
        ra = line.asset_out_id
        if ra:
            q_cu = I.search([('asset_id', '=', ra.id),
                             ('date_remove', '=', False)], limit=1)
            if q_cu:
                if q_cu.date_install and q_cu.date_install > hn:
                    # Không bịa ngày. Quãng lắp đặt bắt đầu ở TƯƠNG LAI
                    # nghĩa là bản ghi đó là KẾ HOẠCH chứ chưa phải việc
                    # đã xảy ra — tháo hôm nay thành ra tháo trước khi
                    # lắp. Người biết việc phải sửa ngày, không phải phần
                    # mềm đoán hộ.
                    raise UserError(_(
                        'Quãng lắp đặt của "%(ts)s" ghi ngày lắp '
                        '%(ngay)s — ở tương lai, nên không tháo hôm nay '
                        'được.\n\nBản ghi đó đang là KẾ HOẠCH chứ chưa '
                        'phải việc đã xảy ra. Sửa ngày lắp cho đúng thực '
                        'tế rồi xuất lại.',
                        ts=ra.display_name, ngay=q_cu.date_install))
                # Lý do tháo suy từ LOẠI LỆNH: bảo trì phòng ngừa thì
                # là thay theo kế hoạch, sửa chữa mới là hỏng. Ghi cứng
                # 'hỏng' cho mọi lần tháo làm hỏng thống kê độ tin cậy —
                # MTBF sẽ đếm cả những lần thay đúng lịch.
                q_cu.write({
                    'date_remove': hn,
                    'reason_remove': ('preventive'
                                      if self.work_type == 'pm'
                                      else 'failure')})
        if vao and self.location_id:
            dang = I.search([('asset_id', '=', vao.id),
                             ('date_remove', '=', False)], limit=1)
            if not dang:
                vt = self._vi_tri_cau_phan(line)
                if not vt:
                    # Không bịa chỗ. Một vị trí chức năng chỉ chứa được
                    # MỘT tài sản, nên nhét máy phát vào ô của cả tua-bin
                    # là làm hỏng sổ lắp đặt — và chốt chống chồng quãng
                    # sẽ chặn, nhưng chặn giữa lúc xuất kho thì người
                    # dùng không hiểu vì sao.
                    self.message_post(body=_(
                        'Đã xuất "%(sp)s" nhưng CHƯA mở được quãng lắp '
                        'đặt: dưới "%(vt)s" không có vị trí chức năng nào '
                        'thuộc loại "%(loai)s". Khai thêm vị trí đó rồi '
                        'ghi lắp đặt bằng tay.',
                        sp=line.product_id.display_name,
                        vt=self.location_id.display_name,
                        loai=line.product_id.eam_category_id.name or '—'))
                    return False
                # Ô chức năng chỉ chứa MỘT tài sản. Đang có con cũ mà
                # chưa khai tháo thì phải dừng ở đây — nói rõ việc cần
                # làm, chứ để chốt chống chồng quãng bắn ra thông báo
                # thô giữa lúc xuất kho thì không ai hiểu vì sao.
                cu = I.search([('location_id', '=', vt.id),
                               ('date_remove', '=', False)], limit=1)
                if cu and cu.asset_id != vao:
                    raise UserError(_(
                        'Vị trí "%(vt)s" đang lắp "%(cu)s". Lắp con mới '
                        'thì phải khai con tháo ra: điền ô "Thiết bị '
                        'tháo ra" trên dòng vật tư.\n\nKhông khai thì '
                        'mất dấu một tài sản mang sê-ri — và đó đúng là '
                        'thứ cần để đòi bảo hành vài năm sau.',
                        vt=vt.display_name, cu=cu.asset_id.display_name))
                I.create({'asset_id': vao.id, 'location_id': vt.id,
                          'date_install': hn,
                          'reason_install': 'replacement' if ra else 'new'})
        return True

    def _vi_tri_cau_phan(self, line):
        """Ô chức năng dành cho đúng loại cấu phần này, dưới vị trí lệnh.

        Lệnh công việc trỏ vào cả tua-bin; con máy phát phải vào ô "Máy
        phát" của chính tua-bin đó. Lắp vào ô cha là sai chỗ, và vì một
        ô chỉ chứa một tài sản nên nó còn đá nhau với chính con tua-bin.
        """
        self.ensure_one()
        loai = line.product_id.eam_category_id
        if not loai or not self.location_id:
            return False
        L = self.env['eam.location']
        return L.search([('id', 'child_of', self.location_id.id),
                         ('id', '!=', self.location_id.id),
                         ('category_id', '=', loai.id)], limit=1)

    def action_ghi_nhan_hoan_tra(self):
        """Nhận lại phần không dùng tới.

        Hàng KHÔNG về thẳng tồn khả dụng trừ khi người khai xác nhận còn
        tốt. Tháo khỏi máy không có nghĩa là dùng lại được — một con ổ
        trục tháo ra trông y như mới vẫn phải qua kiểm tra.
        """
        Move = self.env['stock.move']
        ML = self.env['stock.move.line']
        tong = 0
        for o in self:
            dong = o._part_can_tra()
            if not dong:
                raise UserError(_(
                    'Lệnh "%s" không có dòng nào khai số lượng trả lại.',
                    o.name))
            for l in dong:
                con_lai = l.qty_xuat - l.qty_tra
                if l.qty_tra_moi > con_lai:
                    raise UserError(_(
                        'Dòng "%(sp)s" trả %(tra)g nhưng chỉ còn %(con)g '
                        'chưa trả (đã xuất %(xuat)g, đã trả %(dtra)g).',
                        sp=l.product_id.display_name, tra=l.qty_tra_moi,
                        con=con_lai, xuat=l.qty_xuat, dtra=l.qty_tra))
                p = l.product_id
                uom = l.uom_id or p.uom_id
                dich = o._vi_tri_tra(l)
                mv = Move.create({
                    'product_id': p.id,
                    'product_uom': uom.id,
                    'product_uom_qty': l.qty_tra_moi,
                    'location_id': l.move_id.location_dest_id.id,
                    'location_dest_id': dich.id,
                    'eam_work_order_id': o.id,
                    'company_id': o.company_id.id,
                })
                mv._action_confirm()
                mv.move_line_ids.unlink()
                ML.create({
                    'move_id': mv.id, 'product_id': p.id,
                    'product_uom_id': uom.id, 'quantity': l.qty_tra_moi,
                    'lot_id': l.lot_id.id if l.lot_id else False,
                    'location_id': mv.location_id.id,
                    'location_dest_id': dich.id,
                    'company_id': o.company_id.id,
                })
                mv.picked = True
                mv._action_done()
                l.move_tra_ids = [(4, mv.id)]
                nhan = dict(l._fields['tinh_trang_tra'].selection).get(
                    l.tinh_trang_tra, '')
                o.message_post(body=_(
                    'Hoàn trả %(q)g %(sp)s về "%(dich)s" — %(tt)s.',
                    q=l.qty_tra_moi, sp=p.display_name,
                    dich=dich.complete_name, tt=nhan))
                l.qty_tra_moi = 0.0
                tong += 1
        return self._bao(_('Đã ghi nhận hoàn trả %d dòng.', tong),
                         'success')

    # ------------------------------------------------------------------
    def _bao(self, loi_nhan, kieu='success'):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'type': kieu, 'message': loi_nhan,
                       'next': {'type': 'ir.actions.act_window_close'}},
        }

    # ------------------------------------------------------------------
    def action_dong_lenh(self):
        """Chốt giữ hai sổ không trôi khỏi nhau.

        Đóng lệnh là lúc cuối cùng còn ai nhớ đã lấy những gì và còn thừa
        gì. Cho đóng khi sổ chưa khớp thì sai lệch thành vĩnh viễn, và
        không ai phát hiện ra cho tới hôm cần hàng.
        """
        for o in self:
            con = o._part_can_xuat()
            if con:
                ten = ', '.join(l.product_id.display_name for l in con[:5])
                raise UserError(_(
                    'Lệnh "%(lenh)s" còn %(n)d dòng vật tư chưa xuất kho: '
                    '%(ten)s.\n\nXuất kho, hoặc đánh dấu "Không qua kho" '
                    'cho vật tư mua thẳng và hàng hãng cấp theo bảo hành.',
                    lenh=o.name, n=len(con), ten=ten))
            cho_tra = o._part_can_tra()
            if cho_tra:
                ten = ', '.join(
                    '%s (%g)' % (l.product_id.display_name, l.qty_tra_moi)
                    for l in cho_tra[:5])
                raise UserError(_(
                    'Lệnh "%(lenh)s" còn khai số lượng trả lại nhưng chưa '
                    'ghi nhận: %(ten)s.\n\nBấm "Ghi nhận hoàn trả" trước '
                    'khi đóng, nếu không số hàng đó bị tính là đã tiêu '
                    'dùng vĩnh viễn.', lenh=o.name, ten=ten))
        return super().action_dong_lenh()
