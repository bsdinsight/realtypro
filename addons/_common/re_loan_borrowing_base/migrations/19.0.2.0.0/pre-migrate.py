# -*- coding: utf-8 -*-
"""Tách re_loan_bb_project ra khỏi module này (19.0.2.0.0).

Các view / action / menu / cron dưới đây chuyển sang module mới. Chúng
vẫn nằm trong DB dưới tên module CŨ, và Odoo xác thực chúng ngay khi
nâng cấp module này — trước khi module mới kịp cài. Arch cũ tham chiếu
trường của bộ thi công (contract_id, ipc_count…) mà lúc đó registry
chưa nạp, nên cả lượt nâng cấp đổ.

Xoá trước cho sạch; module re_loan_bb_project tự cài ngay sau đó
(auto_install) và dựng lại đúng những bản ghi này. Không đụng tới dữ
liệu nghiệp vụ: bảng của các model vẫn nguyên, chỉ bản ghi giao diện bị
dựng lại.
"""
from odoo import SUPERUSER_ID, api

MOVED = [
    # views
    'view_re_loan_collateral_form_bb',
    'view_re_loan_credit_contract_form_ipc',
    'view_re_loan_kpi_board_list',
    'view_re_loan_kpi_policy_form',
    'view_re_loan_kpi_policy_form_capacity',
    'view_re_loan_kpi_policy_list',
    'view_re_loan_note_form_checklist',
    'view_re_loan_note_list_capacity',
    'view_re_loan_project_cashflow_form',
    'view_re_loan_project_cashflow_list',
    'view_re_loan_project_funding_form',
    'view_re_loan_project_funding_form_loss_plan',
    'view_re_loan_project_funding_list',
    'view_re_loan_weekly_review_form',
    'view_re_loan_weekly_review_list',
    'view_rp_owner_contract_form_funding_source',
    'view_rp_owner_ipc_form_bb',
    'view_rp_owner_ipc_pledge_wizard_form',
    'view_rp_owner_ipc_pledge_wizard_project',
    # actions + menu + cron
    'action_re_loan_kpi_board',
    'action_re_loan_kpi_policy',
    'action_re_loan_note_capacity',
    'action_re_loan_project_cashflow',
    'action_re_loan_project_funding',
    'action_re_loan_weekly_review',
    'menu_re_loan_kpi_board',
    'menu_re_loan_kpi_policy',
    'menu_re_loan_note_capacity',
    'menu_re_loan_project_cashflow',
    'menu_re_loan_project_funding',
    'menu_re_loan_weekly_review',
    'cron_re_loan_weekly_review',
]


def migrate(cr, version):
    if not version:
        return
    # Dùng ORM: tên BẢNG của action/cron không suy ra được từ tên model
    # (ir.actions.act_window → ir_act_window), xoá bằng SQL là sai bảng.
    env = api.Environment(cr, SUPERUSER_ID, {})
    imds = env['ir.model.data'].search([
        ('module', '=', 're_loan_borrowing_base'),
        ('name', 'in', MOVED)])
    # Xoá theo LÔ từng model: trong danh sách có cả view cha lẫn view
    # con kế thừa nó, xoá lẻ từng cái thì cha đi trước là vướng khoá
    # ngoại. Một lệnh cho cả lô thì Postgres xoá được.
    by_model = {}
    for imd in imds:
        by_model.setdefault(imd.model, []).append(imd.res_id)
    for model, res_ids in by_model.items():
        recs = env[model].browse(res_ids).exists()
        if recs:
            recs.unlink()
    imds.unlink()
