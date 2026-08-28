# -*- coding: utf-8 -*-
"""Dựng lại Dự án / Gói thầu của nhà thầu từ dữ liệu cũ.

Hồ sơ cũ trỏ vào dự án và gói thầu của bên mời thầu. Không vứt đi được —
đó là hồ sơ thật đang làm dở. Nên chép sang sổ của nhà thầu: mỗi dự án
cũ thành một dự án đang theo, mỗi gói thầu cũ thành một gói được mời,
và giữ nguyên tên để người dùng nhận ra.

Dự án cũ được gắn luôn vào `exec_project_id`: nó là một `re.project` có
thật trong hệ thống này, nên vẫn dùng được để chuyển sang thi công.
"""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})

    cr.execute("""SELECT column_name FROM information_schema.columns
                   WHERE table_name = 'rp_bid'
                     AND column_name IN ('old_project_id', 'old_package_id')""")
    if len(cr.fetchall()) < 2:
        return

    cr.execute("""SELECT id, old_project_id, old_package_id
                    FROM rp_bid
                   WHERE old_project_id IS NOT NULL""")
    rows = cr.fetchall()

    Project = env['rp.bid.project']
    Package = env['rp.bid.package']
    proj_map, pkg_map = {}, {}

    for bid_id, old_proj, old_pkg in rows:
        if old_proj not in proj_map:
            src = env['re.project'].browse(old_proj).exists()
            proj_map[old_proj] = Project.create({
                'name': src.name or 'Dự án %s' % old_proj,
                'code': src.code if 'code' in src._fields else False,
                'exec_project_id': src.id or False,
                'note': 'Chuyển từ dự án của bên mời thầu khi tách sổ '
                        'nhà thầu (rp_bid 19.0.9.0.0).',
            })
        project = proj_map[old_proj]

        if old_pkg and old_pkg not in pkg_map:
            src = env['rp.tender.package'].browse(old_pkg).exists()
            pkg_map[old_pkg] = Package.create({
                'project_id': project.id,
                'name': src.name or 'Gói thầu %s' % old_pkg,
                'code': src.code if src and 'code' in src._fields else False,
                'max_approved_price': (
                    src.max_approved_price
                    if src and 'max_approved_price' in src._fields else 0.0),
                'state': 'bidding',
            })

        vals = {'project_id': project.id}
        if old_pkg:
            vals['package_id'] = pkg_map[old_pkg].id
        env['rp.bid'].browse(bid_id).write(vals)

    cr.execute('ALTER TABLE rp_bid DROP COLUMN IF EXISTS old_project_id')
    cr.execute('ALTER TABLE rp_bid DROP COLUMN IF EXISTS old_package_id')

    # Siết lại NOT NULL đã nới ở pre-migrate. Bỏ qua nếu vẫn còn hồ sơ
    # rỗng — thà để cột lỏng còn hơn làm hỏng cả lần nâng cấp.
    for col in ('project_id', 'package_id'):
        cr.execute('SELECT COUNT(*) FROM rp_bid WHERE %s IS NULL' % col)
        if not cr.fetchone()[0]:
            cr.execute('ALTER TABLE rp_bid ALTER COLUMN %s SET NOT NULL'
                       % col)
