# -*- coding: utf-8 -*-
"""BoQ nhà thầu: ĐVT chuyển từ `rp.progress.uom` sang `uom.uom` (việc 1383).

Chạy TRƯỚC khi model mới nạp: cột `rp_bid_boq_line.uom_id` đang giữ id
của bảng xây dựng cũ và có khoá ngoại trỏ về bảng đó. Để nguyên thì lúc
nạp model, Odoo tạo khoá ngoại mới sang `uom_uom` trên những id không có
ở đó — hỏng, hoặc tệ hơn là trỏ nhầm sang một ĐVT khác cùng số id.

Ba bước:
1. Chép id cũ sang cột `progress_uom_id` — giữ vết, lần ngược được.
2. Bỏ khoá ngoại cũ.
3. Ghi id `uom.uom` tương ứng, quy theo tên đã chuẩn hoá (xem
   `rp_bid_uom.py`): "1m³" → m³, "100m³" → m³ × 100, thiếu thì tạo.

Không đụng BoQ dự án và nghiệm thu (`rp_progress`) — chúng ở lại bảng cũ
tới bước chuyển `rp_progress`, phải nâng đủ mọi DB cùng lúc.
"""
import importlib.util
import logging
import os

from psycopg2 import sql

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def _helpers():
    """Nạp thẳng `rp_bid_uom.py` theo đường dẫn.

    Không `import odoo.addons.rp_bid...`: thế là nạp cả gói rp_bid (mọi
    model) ngay trong pre-migrate, trước khi Odoo tự nạp nó.
    """
    path = os.path.join(os.path.dirname(__file__), '..', '..', 'models',
                        'rp_bid_uom.py')
    spec = importlib.util.spec_from_file_location('rp_bid_uom_mig', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def migrate(cr, version):
    if not version:
        return
    cr.execute("""
        SELECT c.conname
          FROM pg_constraint c
          JOIN pg_attribute a ON a.attrelid = c.conrelid
                             AND a.attnum = ANY(c.conkey)
         WHERE c.conrelid = 'rp_bid_boq_line'::regclass
           AND c.contype = 'f' AND a.attname = 'uom_id'
           AND c.confrelid = 'rp_progress_uom'::regclass
    """)
    fks = [r[0] for r in cr.fetchall()]
    if not fks:
        _logger.info('rp_bid 19.0.18: uom_id không còn trỏ rp_progress_uom '
                     '— bỏ qua.')
        return

    cr.execute("""ALTER TABLE rp_bid_boq_line
                  ADD COLUMN IF NOT EXISTS progress_uom_id integer""")
    cr.execute("""UPDATE rp_bid_boq_line SET progress_uom_id = uom_id
                   WHERE progress_uom_id IS NULL""")
    for name in fks:
        cr.execute(sql.SQL('ALTER TABLE rp_bid_boq_line DROP CONSTRAINT {}')
                   .format(sql.Identifier(name)))

    h = _helpers()
    env = api.Environment(cr, SUPERUSER_ID, {})
    cr.execute("""SELECT progress_uom_id, count(*) FROM rp_bid_boq_line
                   WHERE progress_uom_id IS NOT NULL GROUP BY 1""")
    used = dict(cr.fetchall())
    PU = env['rp.progress.uom'].with_context(active_test=False)
    cache = {}
    for pu in PU.browse(list(used)):
        uom = h.uom_from_progress(env, pu, cache)
        cr.execute("""UPDATE rp_bid_boq_line SET uom_id = %s
                       WHERE progress_uom_id = %s""", (uom.id, pu.id))
        _logger.info('rp_bid 19.0.18: ĐVT "%s" (rp.progress.uom %s, %s dòng) '
                     '→ uom.uom %s "%s"', pu.name, pu.id, used[pu.id],
                     uom.id, uom.name)
