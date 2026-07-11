# -*- coding: utf-8 -*-
"""Hồ sơ năng lực nhà thầu (cấp nhà thầu, dùng lại cho mọi gói) — theo
mẫu HSMT xây lắp: tư cách pháp lý + tài chính + 4 bảng PoQ (nhân sự,
thiết bị, hợp đồng tương tự, doanh thu) + chứng chỉ năng lực (NĐ 15/2021).

Ngưỡng đánh giá (k, t, %HĐ tương tự) KHÔNG để ở đây — thuộc cấu hình gói
thầu — vì mỗi gói HSMT quy định khác nhau trong biên độ luật cho phép.
"""
from odoo import api, fields, models

FIELD_AREA = [
    ('survey', 'Khảo sát xây dựng'),
    ('planning', 'Lập quy hoạch'),
    ('design', 'Thiết kế / thẩm tra thiết kế'),
    ('construction', 'Thi công xây dựng'),
    ('pm', 'Tư vấn quản lý dự án'),
    ('supervision', 'Giám sát thi công'),
    ('cost', 'Quản lý chi phí'),
    ('project', 'Lập / thẩm tra dự án'),
]
WORK_TYPE = [
    ('civil', 'Dân dụng'),
    ('industrial', 'Công nghiệp'),
    ('transport', 'Giao thông'),
    ('agri', 'Nông nghiệp & PTNT'),
    ('infra', 'Hạ tầng kỹ thuật'),
]
GRADE = [('1', 'Hạng I'), ('2', 'Hạng II'), ('3', 'Hạng III')]


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # ----- Nhóm 1: tư cách pháp lý / thông tin doanh nghiệp -----
    cn_tax_code = fields.Char(string='Mã số thuế')
    cn_reg_number = fields.Char(string='Số ĐKKD')
    cn_reg_date = fields.Date(string='Ngày cấp ĐKKD')
    cn_reg_place = fields.Char(string='Nơi cấp ĐKKD')
    cn_company_type = fields.Selection(
        [('llc', 'TNHH'), ('jsc', 'Cổ phần'), ('private', 'DN tư nhân'),
         ('coop', 'Hợp tác xã'), ('other', 'Khác')],
        string='Loại hình doanh nghiệp')
    cn_founded_year = fields.Integer(string='Năm thành lập')
    cn_legal_rep = fields.Char(string='Người đại diện pháp luật')
    cn_legal_rep_title = fields.Char(string='Chức danh người đại diện')
    cn_bank_account = fields.Char(string='Số tài khoản')
    cn_bank_name = fields.Char(string='Ngân hàng')

    # ----- Tư cách hợp lệ (Điều 5 Luật 22/2023) -----
    cn_independent_accounting = fields.Boolean(string='Hạch toán độc lập')
    cn_not_banned = fields.Boolean(string='Không đang bị cấm thầu')
    cn_not_bankrupt = fields.Boolean(string='Không đang giải thể/phá sản')
    cn_registered_egp = fields.Boolean(
        string='Đã đăng ký mạng đấu thầu quốc gia')

    # ----- Nhóm 3: năng lực tài chính (tóm tắt) -----
    cn_currency_id = fields.Many2one(
        'res.currency', string='Tiền tệ',
        default=lambda self: self.env.company.currency_id)
    cn_avg_revenue = fields.Monetary(
        string='Doanh thu XD bình quân/năm', currency_field='cn_currency_id',
        help='Bình quân doanh thu hoạt động xây dựng 3-5 năm gần nhất, '
             'KHÔNG gồm VAT. Tự tính từ bảng doanh thu nếu để trống.')
    cn_financial_resource = fields.Monetary(
        string='Nguồn lực tài chính khả dụng', currency_field='cn_currency_id',
        help='Tài sản thanh khoản cao + hạn mức tín dụng khả dụng cho gói.')
    cn_net_asset = fields.Monetary(
        string='Giá trị tài sản ròng', currency_field='cn_currency_id')
    cn_tax_compliant = fields.Boolean(string='Đã hoàn thành nghĩa vụ thuế')
    cn_credit_commitment = fields.Boolean(string='Có cam kết tín dụng NH')
    cn_credit_value = fields.Monetary(
        string='Giá trị cam kết tín dụng', currency_field='cn_currency_id')
    cn_credit_bank = fields.Char(string='Ngân hàng cam kết')

    # ----- Bảng con (One2many) -----
    cn_certificate_ids = fields.One2many(
        'cn.contractor.certificate', 'partner_id', string='Chứng chỉ năng lực')
    cn_personnel_ids = fields.One2many(
        'cn.contractor.personnel', 'partner_id', string='Nhân sự chủ chốt')
    cn_equipment_ids = fields.One2many(
        'cn.contractor.equipment', 'partner_id', string='Thiết bị thi công')
    cn_experience_ids = fields.One2many(
        'cn.contractor.experience', 'partner_id', string='Hợp đồng tương tự')
    cn_revenue_year_ids = fields.One2many(
        'cn.contractor.revenue.year', 'partner_id', string='Doanh thu theo năm')

    cn_profile_progress = fields.Integer(
        string='% hoàn thiện hồ sơ', compute='_compute_cn_profile_progress')

    @api.depends('cn_tax_code', 'cn_legal_rep', 'cn_avg_revenue',
                 'cn_certificate_ids', 'cn_personnel_ids',
                 'cn_equipment_ids', 'cn_experience_ids')
    def _compute_cn_profile_progress(self):
        checks = [
            lambda p: bool(p.cn_tax_code),
            lambda p: bool(p.cn_legal_rep),
            lambda p: p.cn_avg_revenue > 0 or bool(p.cn_revenue_year_ids),
            lambda p: bool(p.cn_certificate_ids),
            lambda p: bool(p.cn_personnel_ids),
            lambda p: bool(p.cn_equipment_ids),
            lambda p: bool(p.cn_experience_ids),
        ]
        for p in self:
            done = sum(1 for c in checks if c(p))
            p.cn_profile_progress = round(100 * done / len(checks))


class CnContractorCertificate(models.Model):
    _name = 'cn.contractor.certificate'
    _description = 'Chứng chỉ năng lực hoạt động xây dựng'
    _order = 'partner_id, id'

    partner_id = fields.Many2one(
        'res.partner', string='Nhà thầu', required=True, ondelete='cascade',
        index=True)
    field_area = fields.Selection(FIELD_AREA, string='Lĩnh vực', required=True)
    work_type = fields.Selection(WORK_TYPE, string='Loại công trình')
    grade = fields.Selection(GRADE, string='Hạng')
    cert_number = fields.Char(string='Số chứng chỉ')
    issuer = fields.Char(string='Cơ quan cấp')
    issue_date = fields.Date(string='Ngày cấp')
    expiry_date = fields.Date(string='Ngày hết hạn')
    attachment = fields.Binary(string='Tệp scan', attachment=True)
    filename = fields.Char()


class CnContractorPersonnel(models.Model):
    _name = 'cn.contractor.personnel'
    _description = 'Nhân sự chủ chốt'
    _order = 'partner_id, id'

    partner_id = fields.Many2one(
        'res.partner', string='Nhà thầu', required=True, ondelete='cascade',
        index=True)
    position = fields.Char(string='Vị trí/chức danh', required=True)
    name = fields.Char(string='Họ tên', required=True)
    degree = fields.Char(string='Trình độ / chuyên ngành')
    cchn_number = fields.Char(string='Chứng chỉ hành nghề (số)')
    cchn_grade = fields.Selection(GRADE, string='Hạng CCHN')
    years_exp = fields.Integer(string='Số năm kinh nghiệm')
    similar_projects = fields.Integer(string='Số CT tương tự đã làm')
    mobilization = fields.Selection(
        [('permanent', 'Cơ hữu'), ('contract', 'Hợp đồng/cam kết')],
        string='Hình thức huy động', default='permanent')
    attachment = fields.Binary(string='Bằng cấp / CCHN', attachment=True)
    filename = fields.Char()


class CnContractorEquipment(models.Model):
    _name = 'cn.contractor.equipment'
    _description = 'Thiết bị thi công chủ yếu'
    _order = 'partner_id, id'

    partner_id = fields.Many2one(
        'res.partner', string='Nhà thầu', required=True, ondelete='cascade',
        index=True)
    name = fields.Char(string='Loại thiết bị', required=True)
    quantity = fields.Integer(string='Số lượng', default=1)
    capacity = fields.Char(string='Công suất / thông số')
    ownership = fields.Selection(
        [('owned', 'Sở hữu'), ('rented', 'Thuê'),
         ('committed', 'Cam kết huy động')],
        string='Hình thức', default='owned')
    condition = fields.Char(string='Tình trạng / năm SX')
    attachment = fields.Binary(string='Tài liệu chứng minh', attachment=True)
    filename = fields.Char()


class CnContractorExperience(models.Model):
    _name = 'cn.contractor.experience'
    _description = 'Hợp đồng tương tự (kinh nghiệm)'
    _order = 'partner_id, date_end desc, id'

    partner_id = fields.Many2one(
        'res.partner', string='Nhà thầu', required=True, ondelete='cascade',
        index=True)
    currency_id = fields.Many2one(
        'res.currency', default=lambda self: self.env.company.currency_id)
    contract_name = fields.Char(string='Tên hợp đồng/công trình', required=True)
    owner_name = fields.Char(string='Chủ đầu tư')
    value = fields.Monetary(string='Giá trị HĐ', currency_field='currency_id')
    role = fields.Selection(
        [('independent', 'Độc lập'), ('joint', 'Thành viên liên danh'),
         ('main', 'Thầu chính'), ('sub', 'Thầu phụ')],
        string='Vai trò', default='independent')
    role_pct = fields.Float(string='% đảm nhận')
    work_type = fields.Selection(WORK_TYPE, string='Loại công trình')
    work_grade = fields.Char(string='Cấp công trình')
    scope = fields.Char(string='Quy mô / phần việc chính')
    date_start = fields.Date(string='Bắt đầu')
    date_end = fields.Date(string='Kết thúc')
    accepted = fields.Boolean(string='Đã nghiệm thu/hoàn thành')
    attachment = fields.Binary(string='HĐ + BB nghiệm thu', attachment=True)
    filename = fields.Char()


class CnContractorRevenueYear(models.Model):
    _name = 'cn.contractor.revenue.year'
    _description = 'Doanh thu xây dựng theo năm'
    _order = 'partner_id, year desc'

    partner_id = fields.Many2one(
        'res.partner', string='Nhà thầu', required=True, ondelete='cascade',
        index=True)
    currency_id = fields.Many2one(
        'res.currency', default=lambda self: self.env.company.currency_id)
    year = fields.Integer(string='Năm', required=True)
    revenue = fields.Monetary(
        string='Doanh thu XD (chưa VAT)', currency_field='currency_id')

    _uniq_year = models.Constraint(
        'unique(partner_id, year)',
        'Mỗi năm chỉ khai 1 dòng doanh thu / nhà thầu.')
