# -*- coding: utf-8 -*-
"""
OnlyOffice Plugin Sidecar — Field Picker double-click insert.

Background:
  DocEditor parent API (OnlyOffice 9.4) KHÔNG expose `callCommand`/`executeMethod`
  để insert text. Methods chỉ có ở Plugin layer chạy inside editor iframe.

  Workaround: register minimal autostart plugin via editor config. Plugin chạy
  inside editor iframe, có thể callCommand → InsertContent vào document.

Communication Odoo widget → Plugin (cross-iframe, cross-origin parent):
  - Plugin iframe served từ Odoo URL → SAME origin với Odoo main page →
    same localStorage scope.
  - Odoo widget write localStorage key 're_doc_oo_insert_queue' → browser
    fires 'storage' event ở plugin iframe → plugin process queue → callCommand
    insert text.
  - Plugin heartbeats key 're_doc_oo_plugin_ready_<id>' mỗi 4s → Odoo widget
    biết plugin có chạy không trước khi queue insert.

Endpoints (auth='public' vì DS browser fetch không có Odoo session):
  - GET /re_doc/plugin/<id>/config.json — plugin manifest cho DS
  - GET /re_doc/plugin/<id>/index.html — plugin iframe HTML

Plugin code.js là static asset cho stable URL (browser cache OK).
"""
import json
import logging

import os

from odoo import http
from odoo.http import request, Response

_logger = logging.getLogger(__name__)


PLUGIN_GUID = 'asc.{b5d17a40-9c31-4e62-8f10-realtycrm01}'


def _public_base_url():
    """Public URL Odoo accessible từ browser.

    Plugin iframe browser-loads dùng URL này → cùng origin với Odoo main
    page → same localStorage scope cho IPC. Lấy từ web.base.url ir.config,
    fallback derive từ current request host nếu chưa set.
    """
    pub = (request.env['ir.config_parameter'].sudo()
           .get_param('web.base.url', '').rstrip('/'))
    if not pub:
        pub = request.httprequest.host_url.rstrip('/')
    return pub


class ReDocPluginController(http.Controller):
    """OnlyOffice plugin sidecar endpoints."""

    @http.route(
        '/re_doc/plugin/<int:template_id>/config.json',
        type='http', auth='public', methods=['GET'], csrf=False)
    def plugin_config(self, template_id, **kwargs):
        """Plugin manifest cho OnlyOffice Document Server.

        DS frontend (browser-side) fetch URL này → đọc variations[0].url để
        biết URL plugin iframe → load iframe đó với src=URL.

        isVisual=False + events=[] → plugin chạy nền, không UI, không button.
        autostart trong editor config → plugin tự chạy khi doc load.
        """
        # variations[0].url MUST be relative — OnlyOffice plugin loader
        # đối xử absolute URL như path string + concatenate vào base URL của
        # config.json (gây 404 ở URL malformed `.../17/https:/parkone.../...`).
        # Relative `index.html` resolves đúng vào cùng directory như config.json.
        config = {
            "name": "Realty Field Inserter",
            "guid": PLUGIN_GUID,
            "variations": [{
                "url": "index.html",
                "isViewer": False,
                "EditorsSupport": ["word"],
                "isVisual": False,
                "isModal": False,
                "isInsideMode": False,
                "initDataType": "none",
                "events": [],
            }],
        }
        return Response(
            json.dumps(config),
            headers=[
                ('Content-Type', 'application/json'),
                ('Access-Control-Allow-Origin', '*'),
                ('Cache-Control', 'no-cache'),
            ],
        )

    @http.route(
        '/re_doc/plugin/<int:template_id>/translations/langs.json',
        type='http', auth='public', methods=['GET'], csrf=False)
    def plugin_langs(self, template_id, **kwargs):
        """OnlyOffice SDK tự động probe translations cho plugin — trả empty
        array để tắt 404 console errors. Plugin Parkone không cần i18n
        (UI ẩn, không có button)."""
        return Response(
            '[]',
            headers=[
                ('Content-Type', 'application/json'),
                ('Cache-Control', 'public, max-age=3600'),
            ],
        )

    @http.route(
        '/re_doc/plugin/<int:template_id>/translations/<lang>.json',
        type='http', auth='public', methods=['GET'], csrf=False)
    def plugin_lang_file(self, template_id, lang, **kwargs):
        """Empty translations dict cho mỗi locale — tắt 404."""
        return Response(
            '{}',
            headers=[
                ('Content-Type', 'application/json'),
                ('Cache-Control', 'public, max-age=3600'),
            ],
        )

    @http.route(
        '/re_doc/plugin/<int:template_id>/index.html',
        type='http', auth='public', methods=['GET'], csrf=False)
    def plugin_index(self, template_id, **kwargs):
        """Plugin iframe HTML.

        Inject template_id vào window scope cho plugin code biết template
        đang edit. Load OnlyOffice plugins.js từ DS public URL (oo.parkone.vn)
        để có Asc.plugin API. Sau đó load plugin code.js từ static assets.
        """
        # Plugin iframe origin = Odoo origin (same domain). Dùng path-absolute
        # URLs (không có host) để resolve về cùng origin tự động.
        #
        # plugins.js phải load từ OnlyOffice DS — cross-origin script load
        # (no CORS needed for <script src>). Hardcode oo.parkone.vn cho prod
        # (override via env nếu deploy khác).
        oo_pub = os.environ.get(
            'OO_BASE_URL', 'https://oo.parkone.vn').rstrip('/')
        # Cache-buster — Odoo serve static files với long max-age; index.html
        # tự no-cache để mỗi lần load code.js với ?v=<commit_sha hash thay được>
        # gây browser refetch khi deploy mới.
        import secrets
        cache_buster = secrets.token_hex(4)
        html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Realty Field Inserter</title>
<script>
  window.RE_DOC_TEMPLATE_ID = {template_id};
</script>
<script src="{oo_pub}/sdkjs-plugins/v1/plugins.js"></script>
<script src="/re_doc/static/src/oo_plugin/code.js?v={cache_buster}"></script>
</head>
<body>
<script>
  if (window.Asc && window.Asc.plugin) {{
    window.Asc.plugin.init = function() {{
      if (window.reDocPluginStart) window.reDocPluginStart();
    }};
    window.Asc.plugin.button = function() {{}};
  }} else {{
    console.error('[re-doc-plugin] Asc.plugin API not loaded — sdkjs-plugins/v1/plugins.js fail?');
  }}
</script>
</body>
</html>"""
        return Response(
            html,
            headers=[
                ('Content-Type', 'text/html; charset=utf-8'),
                ('Cache-Control', 'no-cache'),
            ],
        )
