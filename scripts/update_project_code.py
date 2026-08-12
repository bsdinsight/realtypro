"""Đổi project code của dự án demo: GV → DL.

Chạy trên VPS:
    docker cp /root/realtypro/scripts/update_project_code.py \
      realtypro-odoo:/tmp/update_project_code.py
    docker compose -p realtypro \
      -f /root/realtypro-enterprise/docker-compose.yml \
      exec -T odoo bash -c \
      'odoo shell -d dev --no-http --db_password="$PASSWORD" \
        < /tmp/update_project_code.py'
"""

projs = env['re.project'].search([('code', '=', 'GV')])
if projs:
    for p in projs:
        print(f"ID={p.id}: code 'GV' → 'DL'")
        p.write({'code': 'DL'})
    env.cr.commit()
    print("✅ Done")
else:
    print("Không có project nào code='GV'. Skip.")
