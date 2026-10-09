# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ReProject(models.Model):
    """Nối dự án EPCOne với vị trí nhà máy trên bản đồ hiện trường.

    Vì sao nối ở ĐÂY chứ không nhét trường ``project_id`` vào vị trí
    -----------------------------------------------------------------
    Một vị trí chức năng sống LÂU HƠN dự án tạo ra nó. Trụ tua-bin số 7
    được dựng bởi dự án xây lắp, rồi vận hành 25 năm, rồi có thể được
    một dự án nâng cấp khác động tới. Gắn ``project_id`` lên vị trí là
    ngầm bảo "chỗ này thuộc về dự án đó" — đúng trong năm đầu, sai suốt
    phần đời còn lại, và sai lặng lẽ.

    Nối theo chiều này thì dự án chỉ ra nhà máy nó đang làm, còn vị trí
    vẫn trung lập. Muốn biết vị trí nào do dự án nào dựng thì đó là câu
    hỏi của cầu bàn giao, trả lời bằng chứng từ bàn giao chứ không bằng
    một ô khai tay.
    """
    _inherit = 're.project'

    plant_location_id = fields.Many2one(
        'eam.location', string='Vị trí nhà máy',
        domain="[('location_type', '=', 'plant')]", tracking=True,
        help='Nút gốc của nhà máy trên bản đồ hiện trường. Khai vào thì '
             'mở được bản đồ thẳng từ dự án.')
    site_position_count = fields.Integer(
        string='Số vị trí thiết bị', compute='_compute_site_count')
    site_no_coords = fields.Integer(
        string='Vị trí chưa có toạ độ', compute='_compute_site_count',
        help='Chưa có toạ độ thì không cắm lên bản đồ được. Đây là số '
             'cần dọn trước khi đem bản đồ đi họp.')

    @api.depends('plant_location_id')
    def _compute_site_count(self):
        L = self.env['eam.location']
        for p in self:
            if not p.plant_location_id:
                p.site_position_count = p.site_no_coords = 0
                continue
            vt = L.search([('id', 'child_of', p.plant_location_id.id),
                           ('location_type', '=', 'position')])
            p.site_position_count = len(vt)
            p.site_no_coords = len(vt.filtered(lambda l: not l.has_coords))

    def action_mo_ban_do_hien_truong(self):
        self.ensure_one()
        if not self.plant_location_id:
            raise UserError(_(
                'Dự án "%s" chưa khai vị trí nhà máy.\n\n'
                'Bản đồ cắm theo cây vị trí chức năng, nên phải chỉ ra '
                'nút gốc của nhà máy trước. Khai ở tab thông tin chung.',
                self.display_name))
        return {
            'type': 'ir.actions.client',
            'tag': 'eam_map.plant_map',
            'name': _('Bản đồ hiện trường — %s', self.name or ''),
            'params': {'plant_code': self.plant_location_id.complete_code},
        }
