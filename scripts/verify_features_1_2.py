"""Verify cả #1 (BL schedule) + #2 (dossier remaining) deploy đúng."""

print("\n=== #1 BL SCHEDULE ===\n")
Schedule = env.get('re.bank.guarantee.payment.schedule')
if Schedule is None:
    print("❌ Model schedule KHÔNG tồn tại — chạy: odoo -u re_guarantee")
else:
    print("✅ Model re.bank.guarantee.payment.schedule")
    # In view arch
    view = env.ref('re_guarantee.view_re_bank_guarantee_form',
                   raise_if_not_found=False)
    if view:
        if 'schedule_ids' in (view.arch or ''):
            print("✅ View re.bank.guarantee form CHỨA field schedule_ids")
        else:
            print("❌ View KHÔNG có schedule_ids — view chưa reload")
        if 'action_open_pay' in (view.arch or ''):
            print("✅ View có button action_open_pay")
        else:
            print("❌ View KHÔNG có button action_open_pay")
    # Count records
    g_count = env['re.bank.guarantee'].search_count([])
    s_count = Schedule.search_count([])
    print(f"\nDB: {g_count} chứng thư BL, {s_count} đợt schedule "
          f"(MỚI — phải tạo manual)")
    # Old payment records
    p_count = env['re.bank.guarantee.payment'].search_count([])
    p_with_sched = env['re.bank.guarantee.payment'].search_count(
        [('schedule_id', '!=', False)])
    print(f"   {p_count} payment cũ tồn tại, {p_with_sched} đã link "
          f"schedule (còn lại {p_count - p_with_sched} là transaction "
          f"không thuộc đợt nào — vẫn show ở tab 'Lịch sử thanh toán')")

mod_g = env['ir.module.module'].search([('name', '=', 're_guarantee')])
if mod_g:
    print(f"   re_guarantee version: {mod_g.installed_version}")

print("\n=== #2 DOSSIER REMAINING ===\n")
Dossier = env['rp.loan.disbursement.dossier']
fields_needed = ['invoice_amount_total', 'invoice_amount_remaining']
for f in fields_needed:
    if f in Dossier._fields:
        print(f"✅ Field {f}")
    else:
        print(f"❌ Field {f} THIẾU")

# Check view
view_dos = env.ref(
    'rp_loan_bridge.view_rp_loan_disbursement_dossier_form',
    raise_if_not_found=False)
if view_dos:
    if 'invoice_amount_total' in (view_dos.arch or ''):
        print("✅ View dossier CHỨA invoice_amount_total")
    else:
        print("❌ View dossier KHÔNG có invoice_amount_total")

# Check inherited list view
view_dis = env.ref(
    'rp_loan_bridge.view_re_loan_note_disbursement_form_inherit_dossier',
    raise_if_not_found=False)
if view_dis:
    if 'invoice_amount_remaining' in (view_dis.arch or ''):
        print("✅ View inherited disbursement có invoice_amount_remaining")
    else:
        print("❌ View inherited THIẾU invoice_amount_remaining")

mod_b = env['ir.module.module'].search([('name', '=', 'rp_loan_bridge')])
if mod_b:
    print(f"\n   rp_loan_bridge version: {mod_b.installed_version}")

print("\n=== KIỂM TRA USER GROUP ===\n")
admin = env['res.users'].browse(2)  # admin user
groups_to_check = [
    're_guarantee.group_guarantee_user',
    're_loan.group_loan_user',
]
for g_xid in groups_to_check:
    g = env.ref(g_xid, raise_if_not_found=False)
    if g and g in admin.groups_id:
        print(f"✅ User admin có group {g_xid}")
    elif g:
        print(f"❌ User admin THIẾU group {g_xid} — không thấy menu/form")
    else:
        print(f"⚠ Group {g_xid} không tồn tại")

print("\n=== DONE ===")
print("Nếu mọi ✅: lỗi do BROWSER CACHE. Khắc phục:")
print("  1. DELETE FROM ir_attachment WHERE name LIKE '%web.assets%';")
print("  2. docker compose restart odoo")
print("  3. Browser: Cmd+Shift+R hoặc Incognito window")
print("  4. Logout/login lại để JS load mới")
