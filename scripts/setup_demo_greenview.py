# -*- coding: utf-8 -*-
"""Setup demo data 'Khu đô thị Greenview' cho screenshots docs.

Idempotent: chạy lại sẽ:
  - Archive (set active=False) các record cũ tên 'Vinhomes Green Paradise'
  - Tạo / re-update 'Khu đô thị Greenview' với data đầy đủ cho Section 4-6 docs

Usage (trên VPS):
    docker compose -p realtypro -f /root/realtypro-enterprise/docker-compose.yml \\
      exec odoo odoo shell -d dev --no-http < setup_demo_greenview.py

Hoặc copy paste vào shell tương tác:
    docker compose -p realtypro -f /root/realtypro-enterprise/docker-compose.yml \\
      exec odoo odoo shell -d dev --no-http
    >>> exec(open('/tmp/setup_demo_greenview.py').read())
"""

from datetime import date, timedelta

# ============================================================
# 0. Archive demo data cũ (Vinhomes Green Paradise) nếu có
# ============================================================
print("\n=== Step 0: Archive demo data cũ ===")

old_projects = env['re.project'].search([
    ('name', 'ilike', 'Vinhomes Green Paradise'),
])
if old_projects:
    print(f"Archive {len(old_projects)} project cũ + structures + tenders + contracts liên quan")
    # Archive structures
    old_structures = env['rp.structure'].search([
        ('project_id', 'in', old_projects.ids)])
    old_structures.write({'active': False})
    # Archive tender packages
    old_packages = env['rp.tender.package'].search([
        ('project_id', 'in', old_projects.ids)])
    # Cascade: bidder, criterion, contracts, BBN
    old_bidders = env['rp.tender.bidder'].search([
        ('package_id', 'in', old_packages.ids)])
    old_bidders.unlink()
    old_criteria = env['rp.tender.eval.criterion'].search([
        ('package_id', 'in', old_packages.ids)])
    old_criteria.unlink()
    old_contracts = env['rp.contract'].search([
        ('tender_package_id', 'in', old_packages.ids)])
    old_bbns = env['rp.progress.acceptance'].search([
        ('contract_id', 'in', old_contracts.ids)])
    old_bbns.write({'state': 'cancelled'})
    old_bbns.write({'active': False})
    old_contracts.write({'active': False})
    old_packages.write({'active': False, 'state': 'cancelled'})
    # Archive subzones + project
    old_subzones = env['re.subzone'].search([
        ('project_id', 'in', old_projects.ids)])
    old_subzones.write({'active': False})
    old_projects.write({'active': False})
    print(f"  Archived {len(old_projects)} project, {len(old_subzones)} subzone, "
          f"{len(old_structures)} structure, {len(old_packages)} package, "
          f"{len(old_contracts)} contract, {len(old_bbns)} BBN")
else:
    print("  Không có data cũ cần archive")

# ============================================================
# 1. Re-use hoặc tạo project 'Khu đô thị Greenview'
# ============================================================
print("\n=== Step 1: Project 'Khu đô thị Greenview' ===")

Project = env['re.project']
project = Project.search([('code', '=', 'GV')], limit=1)
if project:
    print(f"  Re-use project ID={project.id} (đã tồn tại)")
    project.write({'active': True})
else:
    project = Project.create({
        'name': 'Khu đô thị Greenview',
        'code': 'GV',
        'development_type': 'mixed',
        'lifecycle_level': 'building',
        'project_type': 'mixed_use',
        'segment': 'high_end',
    })
    print(f"  Created project ID={project.id}")

# Explicit seed cost categories — hook @api.model_create_multi đôi khi
# không trigger do inherit chain. Force call seeder, idempotent.
env['rp.cost.category']._seed_defaults_for_project(project)
cc_count = env['rp.cost.category'].search_count(
    [('project_id', '=', project.id)])
print(f"  Cost categories seeded: {cc_count}")

# ============================================================
# 2. Subzones
# ============================================================
print("\n=== Step 2: Subzones ===")

Subzone = env['re.subzone']
subzones_data = [
    ('Đảo Mặt Trời',     'DMT', 'apartment',  12.5, 3.2, 35.0, 1200,
     'Khu căn hộ cao cấp ven biển'),
    ('Mũi Danh Vọng',    'MDV', 'commercial', 8.0,  2.5, 25.0, 0,
     'Trung tâm thương mại + văn phòng'),
    ('The Paradise',     'TP',  'villa',      15.0, 4.0, 50.0, 80,
     'Cụm biệt thự ven hồ'),
]
subzones = {}
for name, code, sztype, area, built, green, units, tag in subzones_data:
    sz = Subzone.search([('project_id', '=', project.id),
                         ('code', '=', code)], limit=1)
    if sz:
        sz.write({'active': True})
    else:
        sz = Subzone.create({
            'project_id': project.id,
            'name': name, 'code': code,
            'subzone_type': sztype,
            'area_ha': area, 'built_area_ha': built,
            'green_area_percent': green,
            'total_units_planned': units,
            'tagline': tag,
        })
    subzones[code] = sz
    print(f"  Subzone {code} → ID={sz.id}")

# ============================================================
# 3. Structures (item + sub_item)
# ============================================================
print("\n=== Step 3: Structures ===")

Structure = env['rp.structure']
today = date.today()

# Item-level structures
items_data = [
    # (name, code, subzone_code, type, planned_start_offset, planned_end_offset, estimate_value)
    ('Tháp căn hộ S1',       'S1',  'DMT', 'tower', -30, 365, 50_000_000_000),
    ('Tháp căn hộ S2',       'S2',  'DMT', 'tower', 0, 400, 48_000_000_000),
    ('Hạ tầng kỹ thuật DMT', 'HT-DMT', 'DMT', 'infrastructure',
     None, None, 15_000_000_000),  # Không có ngày — showcase Gantt empty
    ('Tháp văn phòng OF1',   'OF1', 'MDV', 'office', 30, 450, 60_000_000_000),
    ('Biệt thự cụm A',       'BT-A', 'TP', 'villa_block', None, None, 25_000_000_000),
]
items = {}
for name, code, sz_code, stype, start_off, end_off, est in items_data:
    s = Structure.search([
        ('project_id', '=', project.id),
        ('code', '=', code),
        ('structure_level', '=', 'item'),
    ], limit=1)
    vals = {
        'project_id': project.id,
        'subzone_id': subzones[sz_code].id,
        'structure_level': 'item',
        'structure_type': stype,
        'name': name, 'code': code,
    }
    if start_off is not None:
        vals['date_planned_start'] = today + timedelta(days=start_off)
        vals['date_planned_end'] = today + timedelta(days=end_off)
    if s:
        s.write({**vals, 'active': True})
    else:
        s = Structure.create(vals)
    items[code] = s
    print(f"  Item {code} → ID={s.id}")

# Sub-items dưới Tháp S1
subitems_data = [
    ('Móng-cọc Tháp S1', 'S1-MC', 'S1', 'foundation', -30, 90),
    ('Phần thân Tháp S1', 'S1-PT', 'S1', 'structure_body', 60, 300),
]
for name, code, parent_code, stype, start_off, end_off in subitems_data:
    parent = items[parent_code]
    s = Structure.search([
        ('project_id', '=', project.id),
        ('code', '=', code),
        ('structure_level', '=', 'sub_item'),
    ], limit=1)
    vals = {
        'project_id': project.id,
        'parent_id': parent.id,
        # Subzone explicit từ parent — inherit qua onchange chỉ chạy ở
        # UI form, không qua create() ORM call
        'subzone_id': parent.subzone_id.id,
        'structure_level': 'sub_item',
        'structure_type': stype,
        'name': name, 'code': code,
        'date_planned_start': today + timedelta(days=start_off),
        'date_planned_end': today + timedelta(days=end_off),
    }
    if s:
        s.write({**vals, 'active': True})
    else:
        s = Structure.create(vals)
    print(f"  Sub-item {code} (parent={parent_code}) → ID={s.id}")

# ============================================================
# 4. Estimate lines (cho Section 4.7 + weighted progress)
# ============================================================
print("\n=== Step 4: Estimate lines ===")

EstLine = env['rp.structure.estimate.line']
CostCat = env['rp.cost.category']

# Pick 3 L2 cost categories (parent_id set) — search by name ilike
# trên JSONB translated không reliable, dùng parent_id structural.
l2_cats = CostCat.search([
    ('project_id', '=', project.id),
    ('parent_id', '!=', False),
], limit=3, order='sequence, id')

if l2_cats and len(l2_cats) >= 3:
    cat1, cat2, cat3 = l2_cats[0], l2_cats[1], l2_cats[2]
    for code in ['S1', 'S2', 'OF1']:
        s = items[code]
        existing = EstLine.search([('structure_id', '=', s.id)])
        if existing:
            continue
        EstLine.create({
            'structure_id': s.id,
            'category_id': cat1.id,
            'description': f'Chi phí xây dựng phần thô {code}',
            'amount': 25_000_000_000 if code != 'OF1' else 35_000_000_000,
        })
        EstLine.create({
            'structure_id': s.id,
            'category_id': cat2.id,
            'description': f'Chi phí hoàn thiện {code}',
            'amount': 15_000_000_000 if code != 'OF1' else 18_000_000_000,
        })
        EstLine.create({
            'structure_id': s.id,
            'category_id': cat3.id,
            'description': f'Chi phí thiết bị + MEP {code}',
            'amount': 10_000_000_000 if code != 'OF1' else 12_000_000_000,
        })
    print(f"  Created estimate lines cho 3 items (S1, S2, OF1) "
          f"với 3 cost categories: {cat1.name}, {cat2.name}, {cat3.name}")
else:
    print(f"  ⚠ L2 cost categories không đủ "
          f"(found {len(l2_cats)}) — skip estimate lines")

# ============================================================
# 5. Contractors (master nhà thầu)
# ============================================================
print("\n=== Step 5: Contractors ===")

Contractor = env['rp.contractor']
contractors_data = [
    ('NT-A', 'Công ty CP Xây dựng A', 'general', 'hang_1', 'approved'),
    ('NT-B', 'Công ty CP Cơ điện B',   'subcontractor', 'hang_2', 'approved'),
    ('NT-C', 'Công ty TNHH Hoàn thiện C', 'subcontractor', 'hang_2', 'approved'),
    ('NT-D', 'Công ty CP Mới D', 'subcontractor', 'hang_3', 'approved'),
]
contractors = {}
company = env.user.company_id
for code, name, ctype, lic_class, state in contractors_data:
    c = Contractor.search([('code', '=', code)], limit=1)
    vals = {
        'code': code, 'name': name,
        'contractor_type': ctype,
        'construction_license_class': lic_class,
        'state': state,
    }
    if c:
        c.write(vals)
    else:
        c = Contractor.create(vals)
    # Ensure partner shared company (cross-company partners) — tránh
    # constraint _check_contractor_company trên rp.tender.package
    if c.partner_id and c.partner_id.company_id:
        c.partner_id.company_id = False
    contractors[code] = c
    print(f"  Contractor {code} ({name}) → ID={c.id}")

# Force tất cả contractor partners cùng company với current company —
# pre-emptive trước khi tạo packages
for code, c in contractors.items():
    c.partner_id.sudo().write({'company_id': company.id})
env.cr.commit()
print(f"  Aligned {len(contractors)} contractor partners → company {company.id}")

# ============================================================
# 6. Tender package "PKG-MEP-001" — state = contracted
# ============================================================
print("\n=== Step 6: Tender package PKG-MEP-001 ===")

Package = env['rp.tender.package']
pkg = Package.search([
    ('project_id', '=', project.id),
    ('code', '=', 'PKG-MEP-001'),
], limit=1)
pkg_vals = {
    'name': 'Gói MEP — Tower S1-S2',
    'code': 'PKG-MEP-001',
    'project_id': project.id,
    'subzone_filter_id': subzones['DMT'].id,
    'selection_method': 'open',
    'deadline_contract': today + timedelta(days=60),
    'max_approved_price': 100_000_000_000,
    'award_amount': 90_000_000_000,
    'contract_amount': 90_000_000_000,
    'contractor_id': contractors['NT-A'].partner_id.id,
    'date_rfp_issue': today - timedelta(days=30),
    'date_bid_close': today - timedelta(days=20),
    'date_bid_open': today - timedelta(days=18),
    'date_eval_done': today - timedelta(days=10),
    'date_negotiation_done': today - timedelta(days=5),
    'date_award_signed': today - timedelta(days=2),
    'scope_summary': 'Hệ thống điện + nước + điều hoà cho Tower S1 + S2',
    'instructions_html': '<p>Nhà thầu tham gia phải có chứng chỉ năng lực hạng 2 trở lên cho MEP. Hồ sơ pháp nhân + GPKD phải còn hiệu lực.</p>',
    'technical_requirements_html': '<p>Phạm vi: cung cấp + lắp đặt hệ MEP (điện, nước, ĐHKK, PCCC) cho 2 toà 30 tầng. Tuân thủ TCVN 9385 + QCVN 06.</p>',
    'state': 'contracted',
    'active': True,
}
if pkg:
    pkg.write(pkg_vals)
    print(f"  Re-use package ID={pkg.id}")
else:
    pkg = Package.create(pkg_vals)
    print(f"  Created package ID={pkg.id}")

# Lines (2 hạng mục)
existing_lines = pkg.line_ids
if not existing_lines:
    env['rp.tender.package.line'].create([
        {'package_id': pkg.id, 'structure_id': items['S1'].id,
         'estimated_amount': 45_000_000_000,
         'scope_note': 'MEP Tower S1'},
        {'package_id': pkg.id, 'structure_id': items['S2'].id,
         'estimated_amount': 45_000_000_000,
         'scope_note': 'MEP Tower S2'},
    ])
    print("  Created 2 lines")

# Seed criteria mẫu
if not pkg.eval_criterion_ids:
    pkg.action_seed_default_criteria()
    print(f"  Seeded {len(pkg.eval_criterion_ids)} criteria")

# 3 Bidders
Bidder = env['rp.tender.bidder']
if not pkg.bidder_ids:
    # NT-A awarded
    b_a = Bidder.create({
        'package_id': pkg.id,
        'contractor_id': contractors['NT-A'].id,
        'submitted_date': today - timedelta(days=25),
        'technical_score': 85.0,
        'price_offered': 90_000_000_000,
        'status': 'awarded',
    })
    # NT-B qualified
    b_b = Bidder.create({
        'package_id': pkg.id,
        'contractor_id': contractors['NT-B'].id,
        'submitted_date': today - timedelta(days=25),
        'technical_score': 80.0,
        'price_offered': 92_000_000_000,
        'status': 'qualified',
    })
    # NT-C disqualified
    b_c = Bidder.create({
        'package_id': pkg.id,
        'contractor_id': contractors['NT-C'].id,
        'submitted_date': today - timedelta(days=25),
        'technical_score': 65.0,
        'price_offered': 88_000_000_000,
        'disqualification_reason': 'Điểm kỹ thuật dưới ngưỡng pass (70) — không đáp ứng yêu cầu MEP',
        'status': 'disqualified',
    })
    print(f"  Created 3 bidders (NT-A awarded, NT-B qualified, NT-C disqualified)")

# ============================================================
# 6b. Extra packages cho screens #5.4 (banner overdue) + #5.11 (state buttons draft)
# ============================================================
print("\n=== Step 6b: Extra packages cho demo screens ===")

# Gói "PKG-XD-002" — deadline đã quá hạn, state evaluating → banner đỏ
pkg_overdue = Package.search([
    ('project_id', '=', project.id),
    ('code', '=', 'PKG-XD-002'),
], limit=1)
pkg_overdue_vals = {
    'name': 'Gói XD — Tháp văn phòng OF1',
    'code': 'PKG-XD-002',
    'project_id': project.id,
    'subzone_filter_id': subzones['MDV'].id,
    'selection_method': 'open',
    'deadline_contract': today - timedelta(days=5),  # ← QUÁ HẠN
    'max_approved_price': 60_000_000_000,
    'date_rfp_issue': today - timedelta(days=40),
    'date_bid_close': today - timedelta(days=25),
    'date_bid_open': today - timedelta(days=23),
    'scope_summary': 'Xây dựng phần thô + hoàn thiện Tháp văn phòng OF1',
    'state': 'evaluating',
    'active': True,
}
if pkg_overdue:
    pkg_overdue.write(pkg_overdue_vals)
else:
    pkg_overdue = Package.create(pkg_overdue_vals)
    env['rp.tender.package.line'].create({
        'package_id': pkg_overdue.id,
        'structure_id': items['OF1'].id,
        'estimated_amount': 60_000_000_000,
    })
print(f"  Created/updated package PKG-XD-002 (overdue banner demo) ID={pkg_overdue.id}")

# Gói "PKG-XD-003" — state draft → show "Duyệt KH" button
pkg_draft = Package.search([
    ('project_id', '=', project.id),
    ('code', '=', 'PKG-XD-003'),
], limit=1)
pkg_draft_vals = {
    'name': 'Gói XD — Hạ tầng kỹ thuật DMT',
    'code': 'PKG-XD-003',
    'project_id': project.id,
    'subzone_filter_id': subzones['DMT'].id,
    'selection_method': 'designated',
    'deadline_contract': today + timedelta(days=90),
    'max_approved_price': 20_000_000_000,
    'scope_summary': 'Hạ tầng kỹ thuật chính cho phân khu Đảo Mặt Trời',
    'state': 'draft',
    'active': True,
}
if pkg_draft:
    pkg_draft.write(pkg_draft_vals)
else:
    pkg_draft = Package.create(pkg_draft_vals)
    env['rp.tender.package.line'].create({
        'package_id': pkg_draft.id,
        'structure_id': items['HT-DMT'].id,
        'estimated_amount': 20_000_000_000,
    })
print(f"  Created/updated package PKG-XD-003 (draft state demo) ID={pkg_draft.id}")

# ============================================================
# 7. Contract PKG-MEP-001-HD
# ============================================================
print("\n=== Step 7: Contract PKG-MEP-001-HD ===")

Contract = env['rp.contract']
hd = Contract.search([('tender_package_id', '=', pkg.id)], limit=1)
hd_vals = {
    'tender_package_id': pkg.id,
    'name': 'PKG-MEP-001-HD',
    'code': 'HD-2026-001',
    'contract_date': today - timedelta(days=2),
    'date_start': today + timedelta(days=5),
    'date_end': today + timedelta(days=300),
    'contractor_id': contractors['NT-A'].partner_id.id,
    'contract_value_pretax': 90_000_000_000,
    'vat_rate': 8.0,
    'advance_percent': 20.0,
    'retention_percent': 5.0,
    'sla_response_days': 7,
    'state': 'executing',
    'guarantee_performance_no': 'BL-2026-001',
    'guarantee_performance_amount': 9_000_000_000,
    'guarantee_performance_expiry': today + timedelta(days=365),
    'guarantee_advance_no': 'BL-2026-002',
    'guarantee_advance_amount': 19_440_000_000,
    'guarantee_advance_expiry': today + timedelta(days=180),
    'active': True,
}
# Tìm Vietcombank
vcb = env['res.partner'].search([
    ('is_bank', '=', True),
    ('name', 'ilike', 'Vietcombank'),
], limit=1)
if vcb:
    hd_vals['guarantee_performance_bank_id'] = vcb.id
    hd_vals['guarantee_advance_bank_id'] = vcb.id

if hd:
    hd.write(hd_vals)
    print(f"  Re-use contract ID={hd.id}")
else:
    hd = Contract.create(hd_vals)
    print(f"  Created contract ID={hd.id}")

# 3 Payment milestones
Milestone = env['rp.contract.payment.milestone']
if not hd.payment_milestone_ids:
    Milestone.create([
        {'contract_id': hd.id, 'sequence': 10,
         'name': 'Tạm ứng 20%',
         'percent': 20.0,
         'due_date': today + timedelta(days=10)},
        {'contract_id': hd.id, 'sequence': 20,
         'name': 'Nghiệm thu 75%',
         'percent': 75.0,
         'due_date': today + timedelta(days=240)},
        {'contract_id': hd.id, 'sequence': 30,
         'name': 'Bảo hành 5%',
         'percent': 5.0,
         'due_date': today + timedelta(days=420)},
    ])
    print("  Created 3 payment milestones")

# 5 BOQ lines
ContractLine = env['rp.contract.line']
if not hd.line_ids:
    ContractLine.create([
        {'contract_id': hd.id, 'sequence': 10,
         'structure_id': items['S1'].id,
         'description': 'Lắp đặt hệ điện chính Tower S1',
         'unit_of_measure': 'gói',
         'quantity': 1, 'unit_price': 18_000_000_000},
        {'contract_id': hd.id, 'sequence': 20,
         'structure_id': items['S1'].id,
         'description': 'Lắp đặt hệ nước + xử lý nước thải S1',
         'unit_of_measure': 'gói',
         'quantity': 1, 'unit_price': 12_000_000_000},
        {'contract_id': hd.id, 'sequence': 30,
         'structure_id': items['S1'].id,
         'description': 'Lắp đặt ĐHKK + thông gió S1',
         'unit_of_measure': 'gói',
         'quantity': 1, 'unit_price': 15_000_000_000},
        {'contract_id': hd.id, 'sequence': 40,
         'structure_id': items['S2'].id,
         'description': 'Lắp đặt MEP toàn bộ Tower S2',
         'unit_of_measure': 'gói',
         'quantity': 1, 'unit_price': 42_000_000_000},
        {'contract_id': hd.id, 'sequence': 50,
         'structure_id': items['S2'].id,
         'description': 'Hệ thống PCCC + báo cháy 2 tower',
         'unit_of_measure': 'gói',
         'quantity': 1, 'unit_price': 3_000_000_000},
    ])
    print("  Created 5 BOQ lines")

# 1 Amendment
Amendment = env['rp.contract.amendment']
if not hd.amendment_ids:
    Amendment.create({
        'contract_id': hd.id,
        'name': 'PL-01',
        'amendment_type': 'scope',
        'date_effective': today - timedelta(days=1),
        'description': 'Bổ sung khối lượng PCCC tầng hầm phát sinh do '
                       'thay đổi thiết kế',
    })
    print("  Created 1 amendment")

# ============================================================
# 8. BBN nghiệm thu (BBN-2026-00001)
# ============================================================
print("\n=== Step 8: BBN approved ===")

BBN = env['rp.progress.acceptance']
bbn = BBN.search([('contract_id', '=', hd.id)], limit=1)
bbn_vals = {
    'contract_id': hd.id,
    'date_submitted': today - timedelta(days=5),
    'date_approved': today - timedelta(days=2),
    'state': 'approved',
    'note': 'Nghiệm thu giai đoạn đầu — hệ điện chính + nước cho Tower S1',
    'active': True,
}
# Link milestone
milestone_2 = hd.payment_milestone_ids.filtered(
    lambda m: m.sequence == 20)[:1]
if milestone_2:
    bbn_vals['payment_milestone_id'] = milestone_2.id

if bbn:
    bbn.write(bbn_vals)
    print(f"  Re-use BBN ID={bbn.id}")
else:
    bbn = BBN.create(bbn_vals)
    print(f"  Created BBN ID={bbn.id}")

# BBN lines — uom_id M2O, fallback nếu chưa có UoM
BBNLine = env['rp.progress.acceptance.line']
ProgressUom = env['rp.progress.uom']
uom_set = ProgressUom.search([('name', 'ilike', 'gói')], limit=1) \
          or ProgressUom.search([], limit=1)
if not bbn.line_ids:
    common_vals = {'acceptance_id': bbn.id}
    if uom_set:
        common_vals['uom_id'] = uom_set.id
    BBNLine.create([
        {**common_vals, 'sequence': 10,
         'structure_id': items['S1'].id,
         'description': 'Lắp đặt hệ điện chính Tower S1 — giai đoạn 1',
         'quantity_this_period': 0.4,
         'unit_price': 18_000_000_000},
        {**common_vals, 'sequence': 20,
         'structure_id': items['S2'].id,
         'description': 'Lắp đặt MEP Tower S2 — giai đoạn 1',
         'quantity_this_period': 0.3,
         'unit_price': 42_000_000_000},
    ])
    print("  Created 2 BBN lines")

# ============================================================
# 9. Commit + summary
# ============================================================
env.cr.commit()
print("\n" + "=" * 60)
print("✅ SETUP COMPLETE — Khu đô thị Greenview")
print("=" * 60)
print(f"""
Project:        {project.name} (ID={project.id})
Subzones:       {len(subzones)} ({', '.join(subzones.keys())})
Items:          {len(items)} ({', '.join(items.keys())})
Sub-items:      2 (S1-MC, S1-PT)
Contractors:    {len(contractors)} ({', '.join(contractors.keys())})
Tender Packages:
  - {pkg.code} state={pkg.state} (main demo)
    Lines: {len(pkg.line_ids)} · Bidders: {len(pkg.bidder_ids)} · Criteria: {len(pkg.eval_criterion_ids)}
  - {pkg_overdue.code} state={pkg_overdue.state} (overdue banner demo)
  - {pkg_draft.code} state={pkg_draft.state} (draft state buttons demo)
Contract:       {hd.name} state={hd.state}
  - Milestones: {len(hd.payment_milestone_ids)}
  - BOQ lines:  {len(hd.line_ids)}
  - Amendments: {len(hd.amendment_ids)}
BBN:            {bbn.name} state={bbn.state}
  - Lines:      {len(bbn.line_ids)}

URL truy cập: https://realtypro.bsdinsights.com/odoo
Open project: /odoo/action-200/{project.id}
Open Gantt:   /odoo/action-362/{project.id}/bsd_gantt_view
""")
