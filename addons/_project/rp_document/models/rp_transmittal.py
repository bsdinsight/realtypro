# -*- coding: utf-8 -*-
"""rp.transmittal — Phiếu chuyển hồ sơ.

Ngoài hiện trường hồ sơ không đi lẻ: nhà thầu gửi một công văn kèm mười
hai bản vẽ. Đồng hồ 21 ngày của cả mười hai hồ sơ đó chạy từ cùng một
ngày — ngày nhận công văn — nên phải ghi một lần cho cả lô, vừa nhanh vừa
không lệch ngày giữa các hồ sơ trong cùng một phiếu.

Phiếu chuyển cũng là chỗ ghi một chi tiết hay bị bỏ: công văn có kèm
THÔNG BÁO theo điều 5.2 hay không. Có thì đồng hồ chạy, không thì hồ sơ
đã nằm trên bàn người duyệt mà hạn vẫn chưa bắt đầu đếm.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class RpTransmittal(models.Model):
    _name = 'rp.transmittal'
    _description = 'Phiếu chuyển hồ sơ'
    _inherit = ['mail.thread']
    _order = 'date desc, id desc'

    code = fields.Char(string='Số phiếu', copy=False, readonly=True,
                       index=True)
    name = fields.Char(string='Nội dung chuyển', required=True,
                       tracking=True)
    ref = fields.Char(string='Số công văn của bên gửi', tracking=True)
    project_id = fields.Many2one('re.project', string='Dự án', required=True,
                                 index=True)
    contract_id = fields.Many2one(
        'rp.contract', string='HĐ nhà thầu', index=True,
        domain="[('project_id', '=', project_id)]")
    direction = fields.Selection(
        [('inbound', 'Nhà thầu → Chủ đầu tư / TVGS'),
         ('outbound', 'Chủ đầu tư / TVGS → Nhà thầu')],
        string='Chiều chuyển', required=True, default='inbound',
        tracking=True)
    date = fields.Date(string='Ngày chuyển', required=True,
                       default=fields.Date.context_today, tracking=True)
    with_notice = fields.Boolean(
        string='Kèm thông báo theo điều 5.2', default=True, tracking=True,
        help='Công văn có kèm thông báo hồ sơ đã sẵn sàng để xem xét (và '
             'phê duyệt) hay không. Không kèm thì đồng hồ 21 ngày của các '
             'hồ sơ trong phiếu CHƯA chạy.')
    document_ids = fields.Many2many(
        'rp.document', 'rp_transmittal_document_rel', 'transmittal_id',
        'document_id', string='Hồ sơ trong phiếu')
    document_count = fields.Integer(string='Số hồ sơ',
                                    compute='_compute_document_count')
    note = fields.Text(string='Ghi chú')
    state = fields.Selection(
        [('draft', 'Nháp'), ('registered', 'Đã ghi nhận')],
        string='Trạng thái', default='draft', required=True, copy=False,
        tracking=True)

    @api.depends('document_ids')
    def _compute_document_count(self):
        for rec in self:
            rec.document_count = len(rec.document_ids)

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = (f'[{rec.code}] {rec.name}' if rec.code
                                else (rec.name or ''))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code'):
                vals['code'] = self.env['ir.sequence'].next_by_code(
                    'rp.transmittal') or '/'
        return super().create(vals_list)

    def action_register(self):
        """Ghi nhận cả lô: mở lần trình mới cho từng hồ sơ trong phiếu."""
        for rec in self:
            if not rec.document_ids:
                raise UserError(_('Phiếu chuyển chưa có hồ sơ nào.'))
            if rec.state == 'registered':
                raise UserError(_('Phiếu này đã ghi nhận.'))
            for doc in rec.document_ids:
                if doc.state == 'rejected':
                    # Hồ sơ bị trả lại mà gửi lại thì là lần trình mới.
                    doc.revision += 1
                doc._submit(date=rec.date, with_notice=rec.with_notice,
                            transmittal=rec)
            rec.state = 'registered'

    def action_open_documents(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Hồ sơ trong phiếu %s', self.code or ''),
            'res_model': 'rp.document',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.document_ids.ids)],
        }
