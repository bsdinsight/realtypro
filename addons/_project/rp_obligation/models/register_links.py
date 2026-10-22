# -*- coding: utf-8 -*-
"""Đường về từ sổ chuyên sang sổ cái.

Chỉ khai quan hệ ngược, không thêm một trường dữ liệu nào. Đứng ở một hồ
sơ kỹ thuật mà muốn biết *"nghĩa vụ này nằm ở đâu trong bức tranh hợp
đồng"* thì có đường đi; còn số liệu vẫn chỉ có một nơi duy nhất là bản
ghi gốc.
"""
from odoo import fields, models


class RpDocument(models.Model):
    _inherit = 'rp.document'

    obligation_ids = fields.One2many(
        'rp.obligation', 'document_id', string='Nghĩa vụ trong sổ cái')


class RpVariation(models.Model):
    _inherit = 'rp.variation'

    obligation_ids = fields.One2many(
        'rp.obligation', 'variation_id', string='Nghĩa vụ trong sổ cái')


class RpClaim(models.Model):
    _inherit = 'rp.claim'

    obligation_ids = fields.One2many(
        'rp.obligation', 'claim_id', string='Nghĩa vụ trong sổ cái')


class RpContractGuarantee(models.Model):
    _inherit = 'rp.contract.guarantee'

    obligation_ids = fields.One2many(
        'rp.obligation', 'guarantee_id', string='Nghĩa vụ trong sổ cái')


class RpContractPaymentMilestone(models.Model):
    _inherit = 'rp.contract.payment.milestone'

    obligation_ids = fields.One2many(
        'rp.obligation', 'milestone_id', string='Nghĩa vụ trong sổ cái')


class ProjectTask(models.Model):
    _inherit = 'project.task'

    obligation_ids = fields.One2many(
        'rp.obligation', 'task_id', string='Nghĩa vụ trong sổ cái')


class RpInterface(models.Model):
    _inherit = 'rp.interface'

    obligation_ids = fields.One2many(
        'rp.obligation', 'interface_id', string='Nghĩa vụ trong sổ cái')


class RpRfi(models.Model):
    _inherit = 'rp.rfi'

    obligation_ids = fields.One2many(
        'rp.obligation', 'rfi_id', string='Nghĩa vụ trong sổ cái')
