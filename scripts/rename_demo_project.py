"""Rename project demo capture: Khu đô thị Greenview → KĐT nghỉ dưỡng Đà Lạt.

Chạy trên VPS:
    docker cp /root/realtypro/scripts/rename_demo_project.py \\
      realtypro-odoo:/tmp/rename_demo_project.py
    docker compose -p realtypro \\
      -f /root/realtypro-enterprise/docker-compose.yml \\
      exec -T odoo bash -c \\
      'odoo shell -d dev --no-http --db_password="$PASSWORD" \\
        < /tmp/rename_demo_project.py'

Idempotent: chạy nhiều lần OK.
"""

OLD_NAME = 'Khu đô thị Greenview'
NEW_NAME = 'KĐT nghỉ dưỡng Đà Lạt'

projs = env['re.project'].search([
    ('name', '=', OLD_NAME),
])
print(f"\n=== Tìm thấy {len(projs)} project '{OLD_NAME}' ===")

if not projs:
    # Check xem đã rename rồi không
    existing = env['re.project'].search([('name', '=', NEW_NAME)])
    if existing:
        print(f"Đã rename trước đó → '{NEW_NAME}' (ID={existing.id})")
    else:
        print(f"Không tìm thấy project nào tên '{OLD_NAME}' cần rename.")
else:
    for p in projs:
        old = p.name
        p.write({'name': NEW_NAME})
        print(f"  ID={p.id}: '{old}' → '{p.name}'")
    env.cr.commit()
    print(f"\n✅ Done — đã commit. Refresh browser thấy tên mới.")
