from . import models


def _post_init_set_home_action(env):
    """Sau khi install module → set Dashboard làm Home Action mặc định
    cho mọi user internal (group_user) CHƯA có custom action.

    Admin có thể override per-user qua Settings → Users → Home Action.
    """
    action = env.ref(
        'rp_dashboard.action_rp_project_dashboard',
        raise_if_not_found=False)
    if not action:
        return
    group_user = env.ref('base.group_user', raise_if_not_found=False)
    if not group_user:
        return
    # KHÔNG ép user đã set custom action — tôn trọng config tay.
    # Odoo 19: groups_id renamed → group_ids.
    users = env['res.users'].search([
        ('group_ids', 'in', group_user.ids),
        ('action_id', '=', False),
    ])
    users.write({'action_id': action.id})
