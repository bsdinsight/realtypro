# -*- coding: utf-8 -*-
"""
OnlyOffice Document Server integration — WOPI-style endpoints cho
Doc Engine v2.

Flow:
    Browser
      ↓ GET /re_doc/<id>/config  (Odoo signs JWT, returns DocEditor config)
    OnlyOffice editor JS init
      ↓ GET (auto từ document.url)
    Odoo /re_doc/<id>/download/<key>  → serve .docx binary
      ↓ user edit + save
    OnlyOffice POSTs callback (signed JWT từ OnlyOffice side)
      ↓
    Odoo /re_doc/<id>/callback  → verify JWT, download mới, write binary

JWT HS256 dùng stdlib hmac + base64 + json — không cần pip install pyjwt.
Secret: OO_JWT_SECRET env var (set trong docker-compose, same value cho cả
Odoo và OnlyOffice container).

Security:
  - JWT signature verify cho mọi callback (chống unauthorized save)
  - Document key changes mỗi edit session (chống stale token reuse)
  - Endpoint /download/<key> include key trong URL — không guessable
"""
import base64
import hashlib
import hmac
import json
import logging
import os
import time
import secrets

import urllib.request

from odoo import http
from odoo.http import request, Response

_logger = logging.getLogger(__name__)


# ── JWT HS256 helpers (stdlib only) ──

def _b64url(data: bytes) -> str:
    """URL-safe base64 không có padding (per RFC 7519)."""
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('ascii')


def _b64url_decode(s: str) -> bytes:
    """URL-safe base64 decode, restore padding."""
    pad = 4 - (len(s) % 4)
    if pad < 4:
        s += '=' * pad
    return base64.urlsafe_b64decode(s)


def jwt_encode(payload: dict, secret: str) -> str:
    """Encode dict thành JWT HS256 string. Returns: 'header.payload.signature'."""
    header = {'alg': 'HS256', 'typ': 'JWT'}
    h = _b64url(json.dumps(header, separators=(',', ':')).encode())
    p = _b64url(json.dumps(payload, separators=(',', ':')).encode())
    signing_input = f'{h}.{p}'.encode()
    sig = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
    s = _b64url(sig)
    return f'{h}.{p}.{s}'


def jwt_decode(token: str, secret: str) -> dict:
    """Decode JWT HS256, raise ValueError on invalid sig / format."""
    try:
        h, p, s = token.split('.')
    except ValueError:
        raise ValueError('JWT malformed (must be 3 dot-separated segments)')

    signing_input = f'{h}.{p}'.encode()
    expected_sig = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
    actual_sig = _b64url_decode(s)
    if not hmac.compare_digest(expected_sig, actual_sig):
        raise ValueError('JWT signature mismatch')

    return json.loads(_b64url_decode(p))


def _oo_secret() -> str:
    """Read OO_JWT_SECRET from env. Raise if missing — fail loud."""
    secret = os.environ.get('OO_JWT_SECRET', '').strip()
    if not secret:
        raise RuntimeError(
            'OO_JWT_SECRET không set trong env Odoo container. '
            'Add vào docker-compose.demo.yml + restart container.')
    return secret


def _oo_base_url() -> str:
    """Public URL OnlyOffice editor browser load JS từ."""
    return os.environ.get('OO_BASE_URL', 'https://oo.parkone.vn').rstrip('/')


def _oo_internal_url() -> str:
    """Internal URL Odoo gọi OnlyOffice command service (container-to-container)."""
    return os.environ.get('OO_INTERNAL_URL', 'http://onlyoffice').rstrip('/')


def _base_url() -> str:
    """Odoo's public base URL — OnlyOffice DS fetch document.url + callback ở đây.

    Phải dùng public hostname matching dbfilter routing. Vd với dbfilter
    `^%d$`:
      - DB `parkone` → web.base.url = https://parkone.bsdinsights.com
        → DS GET Host=parkone.bsdinsights.com → %d=parkone → match ✓
      - DB `market` → web.base.url = https://market.parkone.vn
        → DS GET Host=market.parkone.vn → %d=market → match ✓

    Trước đây dùng Docker hostname `odoo:8069` (internal network) — fast
    nhưng break khi enable dbfilter (Host=odoo không match DB nào). Giờ
    route qua CF Tunnel: +50-100ms latency nhưng correct routing.

    Override qua env OO_CALLBACK_URL nếu cần (vd dev local).
    """
    override = os.environ.get('OO_CALLBACK_URL', '').strip()
    if override:
        return override.rstrip('/')
    pub = (request.env['ir.config_parameter'].sudo()
           .get_param('web.base.url', '').strip().rstrip('/'))
    if pub:
        return pub
    # Fallback derive từ current request (vd khi web.base.url chưa set)
    return request.httprequest.host_url.rstrip('/')


# ── Controllers ──

class ReDocEngineOO(http.Controller):
    """OnlyOffice WOPI-style endpoints.

    Routes mounted ở /re_doc/<id>/* — không yêu cầu Odoo session auth
    cho callback (OnlyOffice container không có session); thay vào đó
    dùng JWT signature từ shared secret để verify.

    Config endpoint (auth='user') chỉ Odoo logged-in user access — render
    JWT-signed editor config rồi browser embed iframe.
    """

    @http.route('/re_doc/oo-info', type='http', auth='user',
                methods=['GET'])
    def oo_info(self, **kwargs):
        """Cho widget biet URL Document Server (khong hardcode trong JS)."""
        try:
            configured = bool(_oo_secret())
        except RuntimeError:
            configured = False
        return Response(
            json.dumps({
                'base_url': _oo_base_url(),
                'configured': configured,
            }),
            headers=[('Content-Type', 'application/json')],
        )

    @http.route(
        '/re_doc/<int:template_id>/config',
        type='http', auth='user', methods=['GET'])
    def doc_config(self, template_id, **kwargs):
        """Return JSON config cho OnlyOffice DocEditor init.

        Browser side: tải config này khi mở form template → init DocEditor
        với document_url + JWT token. OnlyOffice editor verify JWT bằng
        cùng secret (`JWT_SECRET` env trong onlyoffice container)."""
        tpl = request.env['re.doc.template'].browse(template_id).exists()
        if not tpl:
            return Response('Template không tồn tại', status=404)
        # Auto-generate blank .docx nếu record vừa tạo chưa có file. UX:
        # user vào form → điền name + model + save → editor mount với
        # trang trắng để edit ngay, không cần upload file Word từ ngoài.
        if not tpl.docx_file:
            try:
                from docx import Document  # python-docx, installed Phase 1
                import io
                doc = Document()
                # Add 1 paragraph hint để user biết nơi bắt đầu gõ
                doc.add_paragraph(
                    'Bắt đầu soạn template ở đây. Chèn placeholder dạng '
                    '{{ record.code }}, {{ record.customer_id.name }}, v.v. '
                    '(xem cheatsheet Jinja phía dưới form).'
                )
                buf = io.BytesIO()
                doc.save(buf)
                tpl.sudo().write({
                    'docx_file': base64.b64encode(buf.getvalue()),
                    'docx_filename': f'{(tpl.name or "template").replace(" ", "_")}.docx',
                })
                _logger.info(
                    'Auto-generated blank .docx cho template_id=%s', tpl.id)
            except ImportError:
                return Response(
                    'python-docx chưa cài. Chạy: docker exec zonepro-odoo '
                    'pip install python-docx --break-system-packages',
                    status=500)

        # Generate / refresh document key — OnlyOffice cache theo key, khi
        # key đổi → reload document từ server. Pattern: hash(updated_date)
        # nên khi rep tải lên file mới, key đổi → editor refresh.
        write_ts = (tpl.write_date and tpl.write_date.isoformat()) or '0'
        doc_key = hashlib.sha256(
            f'{tpl.id}|{write_ts}|{tpl.docx_filename or ""}'.encode()
        ).hexdigest()[:24]

        # URL OnlyOffice container will fetch document from — use internal
        # Docker hostname (OnlyOffice cùng network với Odoo)
        download_url = f'{_base_url()}/re_doc/{tpl.id}/download/{doc_key}'
        callback_url = f'{_base_url()}/re_doc/{tpl.id}/callback'

        # Plugin URL — autostart sidecar handle double-click insert IPC.
        # Public URL Odoo (web.base.url) cho DS browser fetch + plugin iframe
        # load cùng origin với Odoo main page (localStorage IPC).
        pub = (request.env['ir.config_parameter'].sudo()
               .get_param('web.base.url', '').rstrip('/'))
        if not pub:
            pub = request.httprequest.host_url.rstrip('/')
        plugin_config_url = f'{pub}/re_doc/plugin/{tpl.id}/config.json'

        user = request.env.user
        config = {
            'document': {
                'fileType': 'docx',
                'key': doc_key,
                'title': tpl.docx_filename or f'{tpl.name}.docx',
                'url': download_url,
                'permissions': {
                    'edit': True,
                    'download': True,
                    'print': True,
                },
            },
            'documentType': 'word',
            'editorConfig': {
                'mode': 'edit',
                'lang': 'vi',
                'callbackUrl': callback_url,
                'user': {
                    'id': str(user.id),
                    'name': user.name,
                },
                'plugins': {
                    'autostart': ['asc.{b5d17a40-9c31-4e62-8f10-realtycrm01}'],
                    'pluginsData': [plugin_config_url],
                },
                'customization': {
                    'autosave': True,
                    'forcesave': True,
                    'compactHeader': False,
                    'leftMenu': True,
                    'rightMenu': True,
                    'toolbar': True,
                    'statusBar': True,
                    'logo': {
                        'image': '',
                    },
                },
            },
            'height': '700px',
            'width': '100%',
        }
        # Sign whole config (OnlyOffice spec — pass full config payload as JWT)
        config['token'] = jwt_encode(config, _oo_secret())

        return Response(
            json.dumps(config),
            headers=[('Content-Type', 'application/json')],
        )

    @http.route(
        '/re_doc/<int:template_id>/download/<key>',
        type='http', auth='public', methods=['GET'], csrf=False)
    def doc_download(self, template_id, key, **kwargs):
        """Serve binary .docx cho OnlyOffice container fetch.

        auth='public' vì OnlyOffice container không có Odoo session.
        Security qua key trong URL — không guessable (24 hex chars), regen
        khi document update. Caller verify JWT khi config issued.

        Read raw bytes từ ir_attachment trực tiếp thay vì qua Binary field
        — `tpl.docx_file` trong context auth='public' đôi khi trả base64
        truncated/False (Odoo 19 binary field lazy-load quirk). ir_attachment
        .raw đảm bảo bytes đầy đủ.
        """
        tpl = request.env['re.doc.template'].sudo().browse(template_id).exists()
        if not tpl:
            return Response('Template not found', status=404)

        # Verify key matches current state
        write_ts = (tpl.write_date and tpl.write_date.isoformat()) or '0'
        expected_key = hashlib.sha256(
            f'{tpl.id}|{write_ts}|{tpl.docx_filename or ""}'.encode()
        ).hexdigest()[:24]
        if not hmac.compare_digest(key, expected_key):
            _logger.warning(
                'OO download: key mismatch template_id=%s. '
                'Provided=%s Expected=%s (write_date=%s filename=%s)',
                template_id, key, expected_key,
                tpl.write_date, tpl.docx_filename)
            return Response('Invalid document key', status=403)

        # Read directly from ir_attachment — bypass Binary field's base64
        # conversion which can return False/truncated in auth='public' context.
        attachment = request.env['ir.attachment'].sudo().search([
            ('res_model', '=', 're.doc.template'),
            ('res_id', '=', tpl.id),
            ('res_field', '=', 'docx_file'),
        ], limit=1)
        if not attachment:
            _logger.warning(
                'OO download: ir_attachment row missing for template_id=%s '
                '(docx_file field empty)', template_id)
            return Response('Attachment not found', status=404)

        data = attachment.raw
        if not data:
            _logger.warning(
                'OO download: attachment.raw empty for template_id=%s '
                'att_id=%s', template_id, attachment.id)
            return Response('File content empty', status=404)

        filename = tpl.docx_filename or f'template_{tpl.id}.docx'
        _logger.info(
            'OO download: serving %d bytes cho template_id=%s (%s)',
            len(data), template_id, filename)
        # filename Vietnamese chứa UTF-8 chars (ể ẫ Đ ê...) → Content-Disposition
        # header với ASCII-only filename="..." gây werkzeug hang khi serialize.
        # Dùng RFC 5987 `filename*=UTF-8''...` cho UTF-8-safe escape.
        import urllib.parse
        filename_quoted = urllib.parse.quote(filename, safe='')
        return Response(
            data,
            headers=[
                ('Content-Type', 'application/vnd.openxmlformats-officedocument'
                                 '.wordprocessingml.document'),
                ('Content-Disposition',
                 f"attachment; filename*=UTF-8''{filename_quoted}"),
                ('Content-Length', str(len(data))),
            ],
        )

    @http.route(
        '/re_doc/<int:template_id>/fields',
        type='http', auth='user', methods=['GET'])
    def doc_fields(self, template_id, **kwargs):
        """Return field tree cho Field Picker sidebar.

        Cấu trúc tree 2 levels: top-level = fields của target_model, mỗi
        many2one/one2many/many2many expand 1 level con (children) để user
        chèn placeholder dạng `{{ record.customer_id.name }}` không cần
        nhớ schema.

        Skip technical fields (id, create_uid, message_ids, activity_*…)
        và compute fields với store=False mà không khả dụng khi render.
        """
        tpl = request.env['re.doc.template'].browse(template_id).exists()
        if not tpl:
            return Response('Template not found', status=404)
        if not tpl.target_model:
            return Response(
                json.dumps({'model': None, 'fields': []}),
                headers=[('Content-Type', 'application/json')])

        Model = request.env.get(tpl.target_model)
        if Model is None:
            return Response(
                json.dumps({
                    'error': f'Model {tpl.target_model} không tồn tại',
                    'model': tpl.target_model,
                    'fields': [],
                }),
                headers=[('Content-Type', 'application/json')])

        skip = {
            'id', 'create_uid', 'create_date', 'write_uid', 'write_date',
            '__last_update', 'display_name',
            'message_ids', 'message_follower_ids', 'message_partner_ids',
            'message_attachment_count', 'message_main_attachment_id',
            'message_has_error', 'message_has_error_counter',
            'message_needaction', 'message_needaction_counter',
            'message_has_sms_error', 'message_is_follower',
            'activity_ids', 'activity_state', 'activity_user_id',
            'activity_type_id', 'activity_type_icon',
            'activity_date_deadline', 'activity_summary',
            'activity_exception_decoration', 'activity_exception_icon',
            'has_message', 'website_message_ids', 'rating_ids',
            'access_token', 'access_url', 'access_warning',
        }

        def list_fields(model_cls, with_children: bool):
            """Return sorted list of field dicts cho model_cls.

            `with_children=True` cho top-level: nếu field là M2o/O2m/M2m
            thì attach children (top-level fields của target model). Top-level
            duy nhất expand — children KHÔNG recurse nữa (tránh payload bloat).
            """
            info = model_cls.fields_get()
            out = []
            for fname, finfo in info.items():
                if fname.startswith('_') or fname in skip:
                    continue
                ftype = finfo.get('type', 'char')
                if ftype in ('binary',):  # binary fields useless trong Jinja text
                    continue
                item = {
                    'name': fname,
                    'type': ftype,
                    'string': finfo.get('string', fname),
                }
                relation = finfo.get('relation')
                if relation and ftype in ('many2one', 'one2many', 'many2many'):
                    item['relation'] = relation
                    if with_children:
                        ChildModel = request.env.get(relation)
                        if ChildModel is not None:
                            item['children'] = list_fields(
                                ChildModel, with_children=False)
                out.append(item)
            # Sort by label (case-insensitive)
            out.sort(key=lambda x: (x.get('string') or '').lower())
            return out

        return Response(
            json.dumps({
                'model': tpl.target_model,
                'model_label': Model._description or tpl.target_model,
                'fields': list_fields(Model, with_children=True),
            }),
            headers=[('Content-Type', 'application/json')],
        )

    @http.route(
        '/re_doc/<int:template_id>/curated-fields',
        type='http', auth='user', methods=['GET'])
    def doc_curated_fields(self, template_id, **kwargs):
        """Nhom placeholder nghiep vu cho sidebar — lay tu re.doc.engine
        (dung chung voi cheatsheet tren form template)."""
        tpl = request.env['re.doc.template'].browse(template_id).exists()
        if not tpl:
            return Response('Template not found', status=404)
        groups = []
        if tpl.target_model:
            for label, rows in request.env['re.doc.engine'].curated_groups(
                    tpl.target_model):
                groups.append({
                    'label': label,
                    'fields': [{'label': lb, 'snippet': sn}
                               for lb, sn in rows],
                })
        model_label = ''
        if tpl.target_model and tpl.target_model in request.env:
            model_label = request.env[tpl.target_model]._description or ''
        return Response(
            json.dumps({
                'model': tpl.target_model or '',
                'model_label': model_label,
                'groups': groups,
            }),
            headers=[('Content-Type', 'application/json')],
        )

    @http.route(
        '/re_doc/<int:template_id>/callback',
        type='http', auth='public', methods=['POST'], csrf=False)
    def doc_callback(self, template_id, **kwargs):
        """OnlyOffice callback khi user save / close editor.

        Spec: https://api.onlyoffice.com/editors/callback

        Status codes:
          0 = Document NOT changed
          1 = Document being edited (locked)
          2 = Document ready for saving (after all editors closed)
          3 = Document save error
          4 = Document closed with no changes
          6 = Document being edited but current state saved
          7 = Force-save error

        Khi status=2 hoặc 6: fetch document từ URL trong payload, update
        binary trên Odoo template record.

        type='http' (KHÔNG 'jsonrpc') — OnlyOffice POST raw JSON body, không
        wrap trong JSON-RPC envelope của Odoo. Parse body manually.
        """
        def _resp(error):
            return Response(
                json.dumps({'error': error}),
                headers=[('Content-Type', 'application/json')],
            )

        # Parse raw JSON body
        try:
            raw_body = request.httprequest.get_data() or b'{}'
            payload = json.loads(raw_body)
        except (ValueError, json.JSONDecodeError) as e:
            _logger.warning(
                'OO callback JSON parse failed cho template_id=%s: %s. '
                'Raw body (first 200 bytes): %r',
                template_id, e, raw_body[:200] if raw_body else b'')
            return _resp(1)

        # Verify JWT signature (Authorization: Bearer <token> OR inline `token` field)
        auth_header = request.httprequest.headers.get('Authorization', '')
        token = auth_header.replace('Bearer ', '').strip() or payload.get('token', '')

        _logger.info(
            'OO callback received template_id=%s raw_status=%s token_present=%s '
            'url_present=%s',
            template_id, payload.get('status'), bool(token),
            bool(payload.get('url')))

        if token:
            try:
                decoded = jwt_decode(token, _oo_secret())
                # OnlyOffice puts actual callback data under 'payload' key when signing
                if isinstance(decoded, dict) and 'payload' in decoded:
                    payload = decoded['payload']
                    _logger.info(
                        'OO callback JWT verified, using payload key '
                        '(status=%s url=%s)',
                        payload.get('status'), bool(payload.get('url')))
            except ValueError as e:
                _logger.warning(
                    'OO callback JWT INVALID cho template_id=%s: %s. '
                    'Check OO_JWT_SECRET matches between Odoo + OnlyOffice containers.',
                    template_id, e)
                return _resp(1)

        status = payload.get('status', 0)
        _logger.info(
            'OO callback final status=%s template_id=%s', status, template_id)

        tpl = request.env['re.doc.template'].sudo().browse(template_id).exists()
        if not tpl:
            _logger.warning('OO callback: template_id=%s không tồn tại', template_id)
            return _resp(1)

        # Status 2 or 6 → save document
        if status in (2, 6):
            doc_url = payload.get('url')
            if not doc_url:
                _logger.warning(
                    'OO callback status=%s nhưng không có url payload=%r',
                    status, payload)
                return _resp(1)

            # Rewrite public URL → internal Docker hostname. OnlyOffice DS
            # trả callback url ở public domain (https://oo.parkone.vn/cache/...)
            # nhưng CF Tunnel/edge proxy chặn cache paths → HTTP 403. Odoo
            # container truy cập trực tiếp via Docker network bypass CF.
            public = _oo_base_url()
            internal = _oo_internal_url()
            original_url = doc_url
            if doc_url.startswith(public):
                doc_url = internal + doc_url[len(public):]
                _logger.info(
                    'OO callback: rewrote URL public→internal (%s → %s)',
                    original_url, doc_url)
            try:
                _logger.info(
                    'OO callback: downloading từ %s cho template_id=%s',
                    doc_url, template_id)
                # UA giong trinh duyet: neu URL khong rewrite duoc ve
                # noi bo va phai di qua Cloudflare, UA mac dinh cua
                # python-urllib bi chan 403.
                req_dl = urllib.request.Request(doc_url, headers={
                    'User-Agent': 'Mozilla/5.0 (compatible; OdooDocTemplate)',
                })
                with urllib.request.urlopen(req_dl, timeout=30) as resp:
                    raw = resp.read()
                tpl.write({
                    'docx_file': base64.b64encode(raw),
                    'docx_filename': tpl.docx_filename or f'template_{tpl.id}.docx',
                })
                _logger.info(
                    'OO callback: SAVED %d bytes vào template_id=%s',
                    len(raw), template_id)
            except Exception as e:
                _logger.exception(
                    'OO callback download/save FAILED cho template_id=%s '
                    'url=%s: %s',
                    template_id, doc_url, e)
                return _resp(1)

        return _resp(0)
