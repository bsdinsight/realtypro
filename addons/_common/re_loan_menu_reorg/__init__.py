def _reorg_menus(env):
    """Re-parent existing menu items vào 3 group container mới.

    Pattern Python hook thay vì XML <menuitem> shortcut vì shortcut
    với id cross-module (chứa dot) tạo MỚI menu rỗng thay vì update —
    user thấy label thô "re_loan.menu_..." thay vì label tiếng Việt.

    Chạy cả post_init + post_update để defensive khi module re-upgrade.
    """
    Menu = env['ir.ui.menu']

    # 3 group container — đã tạo bởi XML <menuitem> nội module.
    grp_credit = env.ref(
        're_loan_menu_reorg.menu_grp_credit_contract',
        raise_if_not_found=False)
    grp_note = env.ref(
        're_loan_menu_reorg.menu_grp_note',
        raise_if_not_found=False)
    grp_payment = env.ref(
        're_loan_menu_reorg.menu_grp_payment',
        raise_if_not_found=False)

    # Map xmlid -> (parent_group, sequence). Skip silently nếu menu
    # nguồn không tồn tại (vd module chưa install).
    moves = [
        # HĐ tín dụng group
        ('re_loan.menu_re_loan_credit_contract', grp_credit, 10),
        ('re_loan.menu_re_loan_facility',        grp_credit, 20),
        ('re_loan.menu_re_loan_collateral',      grp_credit, 30),
        # Khế ước group
        ('re_loan.menu_re_loan_note',            grp_note, 10),
        ('re_loan.menu_re_loan_onlending',       grp_note, 20),
        ('rp_loan_bridge.menu_account_move_contractor_invoice',
                                                  grp_note, 30),
        # Trích thu & Thanh toán group
        ('re_loan.menu_re_loan_bank_advice',         grp_payment, 10),
        ('re_loan.menu_re_loan_bank_advice_import',  grp_payment, 20),
        # menu_re_loan_adjustment_note KHÔNG move vào group payment —
        # Giấy báo Nợ/Có là chức năng ghi nhận chứng từ độc lập, đứng
        # riêng top-level dưới Quản lý Vay (anh Đại chốt 2026-07-03).
    ]
    for xmlid, parent, seq in moves:
        if not parent:
            continue
        menu = env.ref(xmlid, raise_if_not_found=False)
        if menu:
            menu.write({'parent_id': parent.id, 'sequence': seq})

    # Re-sequence top-level menus (giữ structure, chỉ order lại).
    top_seqs = [
        ('re_loan_dashboard.menu_re_loan_dashboard_sub', 1),
        ('re_guarantee.menu_re_guarantee_root', 50),
        ('re_loan.menu_re_loan_report', 70),
        ('re_loan.menu_re_loan_config', 90),
    ]
    for xmlid, seq in top_seqs:
        menu = env.ref(xmlid, raise_if_not_found=False)
        if menu:
            menu.write({'sequence': seq})
