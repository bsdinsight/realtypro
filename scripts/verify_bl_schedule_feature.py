"""Verify feature #1 BL schedule deployed đúng.

Chạy:
    docker cp /root/realtypro/scripts/verify_bl_schedule_feature.py \\
      realtypro-odoo:/tmp/verify_bl_schedule_feature.py
    docker compose -p realtypro \\
      -f /root/realtypro-enterprise/docker-compose.yml \\
      exec -T odoo bash -c \\
      'odoo shell -d dev --no-http --db_password="$PASSWORD" \\
        < /tmp/verify_bl_schedule_feature.py'

Output expected:
    ✅ Model re.bank.guarantee.payment.schedule TỒN TẠI
    ✅ Field schedule_ids trên re.bank.guarantee TỒN TẠI
    ✅ Field schedule_id trên re.bank.guarantee.payment TỒN TẠI
    ✅ Method action_open_pay TỒN TẠI
"""

ok = True

# Check model schedule exist
Schedule = env.get('re.bank.guarantee.payment.schedule')
if Schedule is None:
    print("❌ Model re.bank.guarantee.payment.schedule KHÔNG tồn tại "
          "— module chưa update")
    ok = False
else:
    print("✅ Model re.bank.guarantee.payment.schedule TỒN TẠI")
    # Check fields
    needed_fields = [
        'guarantee_id', 'name', 'payment_kind', 'due_date',
        'amount_due', 'amount_paid', 'amount_remaining', 'state',
        'transaction_ids', 'transaction_count',
    ]
    for f in needed_fields:
        if f in Schedule._fields:
            print(f"  ✅ Field {f}")
        else:
            print(f"  ❌ Field {f} THIẾU")
            ok = False
    # Check methods
    if hasattr(Schedule, 'action_open_pay'):
        print("  ✅ Method action_open_pay")
    else:
        print("  ❌ Method action_open_pay THIẾU")
        ok = False

# Check schedule_ids on re.bank.guarantee
Guar = env['re.bank.guarantee']
if 'schedule_ids' in Guar._fields:
    print("✅ Field schedule_ids trên re.bank.guarantee TỒN TẠI")
else:
    print("❌ Field schedule_ids THIẾU — model chưa reload")
    ok = False

# Check schedule_id on re.bank.guarantee.payment
Pay = env['re.bank.guarantee.payment']
if 'schedule_id' in Pay._fields:
    print("✅ Field schedule_id trên re.bank.guarantee.payment TỒN TẠI")
else:
    print("❌ Field schedule_id THIẾU")
    ok = False

# Check module version
mod = env['ir.module.module'].search([('name', '=', 're_guarantee')])
if mod:
    print(f"\nre_guarantee version installed: {mod.installed_version}")
    if mod.installed_version >= '19.0.1.12.0':
        print("✅ Version đủ mới (≥ 19.0.1.12.0)")
    else:
        print("❌ Version cũ — cần update -u re_guarantee")
        ok = False

if ok:
    print("\n✅ Feature #1 BL schedule deploy XONG. "
          "Refresh browser (Cmd+Shift+R) → mở chứng thư BL.")
else:
    print("\n❌ Có vấn đề — chạy: odoo -d dev -u re_guarantee "
          "--db_password=\"$PASSWORD\" --stop-after-init --no-http")
