# -*- coding: utf-8 -*-
"""Gỡ neo hai trường Dự án / Gói thầu khỏi sổ của bên mời thầu.

`rp.bid.project_id` đổi từ `re.project` sang `rp.bid.project`, và
`package_id` từ `rp.tender.package` sang `rp.bid.package`.

BẪY: đổi comodel của một Many2one KHÔNG làm Odoo sửa khoá ngoại đã có
trong PostgreSQL. Cột vẫn còn ràng buộc trỏ sang bảng cũ, nên bản ghi
mới sẽ chết ngay lúc ghi với lỗi "violates foreign key constraint" —
nhìn rất khó hiểu vì trong code chẳng còn chỗ nào nhắc tới bảng cũ.

Nên ở đây phải tự tay: bỏ khoá ngoại, cất id cũ sang cột tạm, rồi xoá
trắng giá trị (id của `re.project` không có nghĩa gì trong bảng mới).
post-migrate dựng lại dự án / gói thầu của nhà thầu từ cột tạm đó.
"""

# Các cột ăn theo `rp.bid` bằng related store=True — cũng mang khoá ngoại
# trỏ sang bảng cũ, cũng phải gỡ. Sót một cái là hỏng lúc ghi.
COLS = [
    ('rp_bid', 'project_id'), ('rp_bid', 'package_id'),
    ('rp_bid_structure', 'project_id'), ('rp_bid_structure', 'package_id'),
    ('rp_bid_boq_line', 'project_id'), ('rp_bid_boq_line', 'package_id'),
    ('rp_bid_element', 'project_id'), ('rp_bid_element', 'package_id'),
    ('rp_bid_price', 'project_id'), ('rp_bid_price', 'package_id'),
    ('rp_bid_resource_line', 'project_id'),
    ('rp_bid_resource_line', 'package_id'),
]


def migrate(cr, version):
    if not version:
        return

    for table, col in COLS:
        cr.execute("SELECT to_regclass(%s)", ['public.%s' % table])
        if not cr.fetchone()[0]:
            continue
        cr.execute("""
            SELECT con.conname
              FROM pg_constraint con
              JOIN pg_class rel ON rel.oid = con.conrelid
              JOIN pg_attribute att
                ON att.attrelid = con.conrelid AND att.attnum = con.conkey[1]
             WHERE con.contype = 'f' AND rel.relname = %s AND att.attname = %s
        """, [table, col])
        for (name,) in cr.fetchall():
            cr.execute('ALTER TABLE "%s" DROP CONSTRAINT "%s"' % (table, name))

        if table == 'rp_bid':
            cr.execute('ALTER TABLE rp_bid ADD COLUMN IF NOT EXISTS '
                       'old_%s integer' % col)
            cr.execute('UPDATE rp_bid SET old_%s = %s '
                       'WHERE old_%s IS NULL' % (col, col, col))
        # required=True nên cột đang NOT NULL. Phải nới ra mới xoá trắng
        # được; post-migrate siết lại sau khi đã điền dự án / gói mới.
        cr.execute('ALTER TABLE "%s" ALTER COLUMN "%s" DROP NOT NULL'
                   % (table, col))
        cr.execute('UPDATE "%s" SET "%s" = NULL' % (table, col))
