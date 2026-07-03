def _reorg_menus(env):
    """No-op từ 2026-07-03 — cấu trúc menu đã chuyển vào XML nguồn
    (re_loan/views/menu_root.xml định nghĩa 3 group; từng menuitem
    parent thẳng vào group trong view XML gốc). SQL/hook move bị
    revert mỗi lần `odoo -u re_loan` nên bỏ pattern đó.

    Giữ function vì manifest post_init_hook còn reference — module
    này sẽ deprecated dần (xmlid 3 group đã transfer sang re_loan
    qua UPDATE ir_model_data).
    """
