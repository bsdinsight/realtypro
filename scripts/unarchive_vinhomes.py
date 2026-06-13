"""Unarchive project 'Vinhomes Green Paradise' + cascade các record con.

Chạy trên VPS:
    docker cp /root/realtypro/scripts/unarchive_vinhomes.py \\
      realtypro-odoo:/tmp/unarchive_vinhomes.py
    docker compose -p realtypro \\
      -f /root/realtypro-enterprise/docker-compose.yml \\
      exec -T odoo bash -c \\
      'odoo shell -d dev --no-http --db_password="$PASSWORD" \\
        < /tmp/unarchive_vinhomes.py'

Idempotent: chạy nhiều lần OK, chỉ unarchive record đang active=False.
"""


def model_has_active(env, model_name):
    """Check model có field `active` không (để tránh KeyError)."""
    return 'active' in env[model_name]._fields


# === Step 1: Find archived Vinhomes projects ===
projs = env['re.project'].search([
    ('name', 'ilike', 'Vinhomes Green Paradise'),
    ('active', '=', False),
])
print(f"\n=== Tìm thấy {len(projs)} archived Vinhomes project ===")
for p in projs:
    print(f"  - ID={p.id}: {p.name}")

if not projs:
    print("Không có project Vinhomes nào archived. Done.")
else:
    for p in projs:
        print(f"\n=== Unarchive project ID={p.id}: {p.name} ===")
        p.write({'active': True})

        # Subzones
        if model_has_active(env, 're.subzone'):
            subzones = env['re.subzone'].search([
                ('project_id', '=', p.id),
                ('active', '=', False),
            ])
            subzones.write({'active': True})
            print(f"  Subzones unarchived: {len(subzones)}")

        # Structures
        structs = env['rp.structure'].search([
            ('project_id', '=', p.id),
            ('active', '=', False),
        ])
        structs.write({'active': True})
        print(f"  Structures unarchived: {len(structs)}")

        # Tender packages
        pkgs = env['rp.tender.package'].search([
            ('project_id', '=', p.id),
            ('active', '=', False),
        ])
        pkgs.write({'active': True})
        print(f"  Tender packages unarchived: {len(pkgs)}")

        # Contracts (rp.contract)
        contracts = env['rp.contract'].search([
            ('project_id', '=', p.id),
            ('active', '=', False),
        ])
        contracts.write({'active': True})
        print(f"  Contracts unarchived: {len(contracts)}")

        # BBN nghiệm thu — chỉ unarchive nếu có field active
        if model_has_active(env, 'rp.progress.acceptance') and contracts:
            bbns = env['rp.progress.acceptance'].search([
                ('contract_id', 'in', contracts.ids),
                ('active', '=', False),
            ])
            bbns.write({'active': True})
            print(f"  BBN nghiệm thu unarchived: {len(bbns)}")

    env.cr.commit()
    print("\n✅ Done — đã commit DB.")
    print("Refresh browser → Quản lý Dự án → Dự án → Vinhomes hiện lại.")
