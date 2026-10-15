# -*- coding: utf-8 -*-
"""Áp luật mùa vào lịch bảo trì.

Hạn gốc KHÔNG bị ghi đè — ngày đề xuất theo mùa là một cột riêng. Ghi
đè lên hạn thật thì mất luôn thông tin *"việc này lẽ ra tới hạn ngày
nào"*, và sau vài lần dời không ai biết thiết bị đã trễ bao lâu so với
chu kỳ thiết kế.

Chỗ dễ bỏ sót nhất: **việc bị kéo lên sớm phải được SINH LỆNH sớm hơn
tương ứng.** Nếu cron vẫn chỉ sinh lệnh khi hạn gốc tới gần, thì tới lúc
đó ngày đề xuất đã trôi qua từ lâu — và cả tính năng lập lịch theo mùa
chỉ còn là một dòng ghi chú không ai làm được gì với nó.
"""
from odoo import _, api, fields, models


class EamPmSchedule(models.Model):
    _inherit = 'eam.pm.schedule'

    date_seasonal = fields.Date(
        string='Ngày nên làm (xét mùa)', compute='_compute_mua', store=True,
        help='Hạn gốc giữ nguyên ở cột "Hạn theo lịch". Cột này là ngày đề '
             'xuất sau khi xét mùa — chênh lệch giữa hai cột chính là thứ '
             'cần nhìn.')
    season_shift_days = fields.Integer(
        string='Dời (ngày)', compute='_compute_mua', store=True,
        aggregator=False,
        help='Số âm là KÉO LÊN SỚM, số dương là đẩy lùi. Với bảo trì '
             'phòng ngừa, kéo lên sớm là an toàn còn đẩy lùi là để thiết '
             'bị chạy quá chu kỳ thiết kế — nên hai hướng không ngang '
             'nhau, và số dương luôn kèm cảnh báo.')
    # Text, KHÔNG phải Char: lời giải thích dài tới ~250 ký tự, và đoạn
    # bị cắt đầu tiên lại đúng là đoạn nói hậu quả ("thiết bị sẽ chạy
    # thêm 20 ngày quá chu kỳ thiết kế"). Cắt mất câu đó thì cột này chỉ
    # còn nói đã dời, không nói dời thì mất gì.
    season_note = fields.Text(
        string='Vì sao dời', compute='_compute_mua', store=True)
    season_same_day = fields.Integer(
        string='Việc khác cùng ngày', compute='_compute_same_day',
        aggregator=False,
        help='Số việc của cùng nhà máy cũng rơi vào ngày đề xuất này. '
             'Luật mùa tối ưu TỪNG lịch riêng lẻ và không biết tổ có bao '
             'nhiêu người — nên nhiều việc hay bị dồn về cùng một ngày '
             '(thường là ngày trước khi mùa xấu mở). Cột này để nhìn thấy '
             'chỗ dồn, chứ hệ thống KHÔNG tự giãn ra: giãn thì phải có số '
             'năng lực tổ, mà số đó chưa khai ở đâu cả.')
    season_conflict = fields.Boolean(
        string='Xung đột mùa', compute='_compute_mua', store=True,
        index=True,
        help='Hạn rơi vào mùa nên tránh hoặc không làm được.')
    season_blocked = fields.Boolean(
        string='Không tránh được mùa', compute='_compute_mua', store=True,
        index=True,
        help='Có xung đột mùa mà không dời đi đâu được trong giới hạn — '
             'hoặc là kiểm định bắt buộc, vốn không được dời. Đây là danh '
             'sách phải bố trí làm trong mùa, tức phải chuẩn bị khác.')

    @api.depends('date_next', 'location_id', 'plan_id',
                 'plan_id.work_type', 'plan_id.trade')
    def _compute_mua(self):
        R = self.env['eam.season.rule']
        hn = fields.Date.context_today(self)
        for s in self:
            s.date_seasonal = s.date_next
            s.season_shift_days = 0
            s.season_note = False
            s.season_conflict = False
            s.season_blocked = False
            if not s.date_next or not s.plan_id or not s.location_id:
                continue
            ngay, doi, ghi_chu, tranh_duoc = R._de_xuat_ngay(
                s.plan_id, s.location_id, s.date_next, hom_nay=hn)
            s.date_seasonal = ngay
            s.season_shift_days = doi
            s.season_note = ghi_chu or False
            # Có ghi chú mà không dời được nghĩa là đang vướng mùa xấu.
            s.season_conflict = bool(doi) or (bool(ghi_chu)
                                              and not tranh_duoc)
            s.season_blocked = bool(ghi_chu) and not tranh_duoc

    @api.depends('date_seasonal', 'location_id')
    def _compute_same_day(self):
        """Đếm chỗ dồn ngày. Hai câu truy vấn cho cả recordset, không
        phải một câu mỗi dòng."""
        ngay = [s.date_seasonal for s in self if s.date_seasonal]
        if not ngay:
            for s in self:
                s.season_same_day = 0
            return
        dem = {}
        for s in self.search([('date_seasonal', 'in', ngay)]):
            k = (s.location_id.plant_id.id, s.date_seasonal)
            dem[k] = dem.get(k, 0) + 1
        for s in self:
            s.season_same_day = dem.get(
                (s.location_id.plant_id.id, s.date_seasonal), 0)

    # ------------------------------------------------------------------
    def _sinh_lenh(self):
        w = super()._sinh_lenh()
        if self.season_shift_days or self.season_note:
            ngay = self.date_seasonal or self.date_next
            w.write({
                'date_planned_start': ngay,
                'date_planned_end': ngay,
                'description': '\n\n'.join(filter(None, [
                    w.description,
                    _('Lịch theo mùa: %s', self.season_note or ''),
                ])),
            })
            if self.season_blocked:
                w.message_post(body=_(
                    'Việc này KHÔNG tránh được mùa: %s. Phải chuẩn bị điều '
                    'kiện thi công khác, không phải hoãn.',
                    self.season_note or ''))
        return w

    @api.model
    def _cron_sinh_lenh(self):
        """Sinh lệnh sớm cho những việc bị mùa kéo lên trước.

        Chạy TRƯỚC phần sinh lệnh thường. Những việc đã được sinh ở đây
        sẽ tự bị phần sau bỏ qua, vì chúng đã có lệnh đang mở.
        """
        hn = fields.Date.context_today(self)
        som = self.search([('season_shift_days', '<', 0),
                           ('date_seasonal', '!=', False)])
        n = 0
        for s in som:
            if s.wo_id and s.wo_id.state not in ('done', 'closed',
                                                 'cancelled'):
                continue
            if (s.date_seasonal - hn).days <= (s.plan_id.lead_days or 0):
                s._sinh_lenh()
                n += 1
        if n:
            self.env['ir.logging'].sudo().create({
                'name': 'eam_pm.season', 'type': 'server',
                'dbname': self.env.cr.dbname, 'level': 'INFO',
                'message': 'Sinh %d lệnh sớm theo luật mùa.' % n,
                'path': 'eam_pm', 'func': '_cron_sinh_lenh', 'line': '0',
            })
        return super()._cron_sinh_lenh()

    def action_tinh_lai_mua(self):
        # Gọi thẳng hàm tính. Ngoài vòng tính của ORM thì phép gán vào
        # trường có lưu là một lượt ghi thật, nên giá trị mới xuống cột —
        # cùng cách ``eam.meter`` đã làm với giá trị liên tục.
        self._compute_mua()
        return True


class EamSeason(models.Model):
    """Sửa mùa thì phải TÍNH LẠI lịch đang chịu ảnh hưởng.

    Hàm tính của lịch không thể khai ``@api.depends`` sang bảng mùa — hai
    model không có đường quan hệ nào nối chúng, luật mùa khớp bằng cách
    so nhà máy và loại việc lúc chạy. Nên nếu không gọi tính lại ở đây,
    người dùng sửa cửa sổ mùa xong sẽ thấy lịch **không đổi gì**, kết
    luận là tính năng hỏng, và thôi dùng.
    """
    _inherit = 'eam.season'

    def _tinh_lai_lich(self):
        S = self.env['eam.pm.schedule']
        dom = [('date_next', '!=', False)]
        # Mùa khai cho một nhà máy thì chỉ tính lại lịch của nhà máy đó.
        # Mùa để trống nhà máy áp cho tất cả, nên phải quét hết.
        if self and all(s.plant_id for s in self):
            trong = self.env['eam.location'].search(
                [('id', 'child_of', self.mapped('plant_id').ids)])
            dom.append(('location_id', 'in', trong.ids))
        ds = S.search(dom)
        if ds:
            ds.action_tinh_lai_mua()
        return True

    @api.model_create_multi
    def create(self, vals_list):
        rs = super().create(vals_list)
        rs._tinh_lai_lich()
        return rs

    def write(self, vals):
        res = super().write(vals)
        self._tinh_lai_lich()
        return res

    def unlink(self):
        env = self.env
        res = super().unlink()
        env['eam.season']._tinh_lai_lich()
        return res


class EamSeasonRule(models.Model):
    _inherit = 'eam.season.rule'

    @api.model_create_multi
    def create(self, vals_list):
        rs = super().create(vals_list)
        rs.mapped('season_id')._tinh_lai_lich()
        return rs

    def write(self, vals):
        res = super().write(vals)
        self.mapped('season_id')._tinh_lai_lich()
        return res

    def unlink(self):
        mua = self.mapped('season_id')
        res = super().unlink()
        mua._tinh_lai_lich()
        return res
