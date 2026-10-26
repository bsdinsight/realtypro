# -*- coding: utf-8 -*-
"""Kết nối tới nhà cung cấp ký số từ xa — hiện làm Viettel MySign.

ĐỌC KỸ CHỖ NÀY TRƯỚC KHI DEMO: màn hình này là KHAI BÁO, không phải là
tính năng. Khai đủ bốn ô không có nghĩa là ký được. Nên ô *Tình trạng*
ở đây CHỈ được ghi bởi một lượt gọi thật tới máy chủ Viettel, và tự
quay về "Chưa kiểm" ngay khi ai đó sửa bất kỳ thông tin đăng nhập nào.
Không có đường nào làm nó xanh bằng cách gõ tay.

Luật đó viết vào code chứ không nhắc nhau, vì một màn cấu hình *trông
như đã nối* là thứ nguy hiểm nhất khi demo: khách tin là xong, tới lúc
ký thật mới vỡ. Cùng lý do, ``_signer_mysign`` từ chối chạy khi tình
trạng chưa phải "ok".

Bốn hàm của MySign, theo tài liệu tích hợp ký BẤT ĐỒNG BỘ của
Viettel-CA:

1. ``POST {base}/vtss/service/ras/v1/login``             → access_token
2. ``POST {base}/adss/service/ras/csc/v1/credentials/list``
                                              → chuỗi chứng thư + credential_id
3. ``POST {base}/vtss/service/signHash``                 → transactionId
4. ``POST {base}/vtss/service/requests/status``          → chữ ký, hoặc đang chờ

Đường dẫn KHÔNG cùng một gốc: ``login``, ``signHash`` và
``requests/status`` nằm dưới ``/vtss``, còn danh sách chứng thư nằm
dưới ``/adss/service/ras/csc/v1`` theo chuẩn Cloud Signature
Consortium. Đừng "dọn cho gọn" thành một gốc chung — đó là hai hệ con
khác nhau của Viettel.

KHOÁ RIÊNG KHÔNG BAO GIỜ ĐI QUA ĐÂY. Thứ gửi đi là mã băm của tài
liệu, thứ nhận về là chữ ký của mã băm đó. Kể cả hệ thống này bị chiếm
quyền thì cũng không ai ký thay người khác được — muốn ký vẫn phải có
người bấm xác nhận trên điện thoại.
"""
import base64
import hashlib
import json
import logging
import time

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

# OID — để dạng hằng có tên vì chuỗi số trần trong thân hàm thì không ai
# soi ra được là sai.
OID_BAM = {
    'sha256': '2.16.840.1.101.3.4.2.1',
    'sha384': '2.16.840.1.101.3.4.2.2',
    'sha512': '2.16.840.1.101.3.4.2.3',
}
OID_KY_RSA = {
    'sha256': '1.2.840.113549.1.1.11',   # sha256WithRSAEncryption
    'sha384': '1.2.840.113549.1.1.12',
    'sha512': '1.2.840.113549.1.1.13',
}

# Mã trạng thái của requests/status, theo tài liệu Viettel-CA.
TT_XONG = '1'
TT_CHO = '4000'
TT_HET_GIO = '4001'
TT_TU_CHOI = '4002'
TT_THAT_BAI = '4004'
TT_LOI_DOC = '50000'
TT_NGHIA = {
    TT_CHO: 'người ký chưa xác nhận trên ứng dụng MySign',
    TT_HET_GIO: 'hết thời gian chờ xác nhận',
    TT_TU_CHOI: 'người ký đã từ chối',
    TT_THAT_BAI: 'nhà cung cấp báo ký thất bại',
    TT_LOI_DOC: 'không lấy được thông tin giao dịch',
}

# Những ô mà hễ đổi là tình trạng kết nối phải coi như chưa biết.
O_DANG_NHAP = ('base_url', 'client_id', 'client_secret', 'user_id',
               'profile_id', 'kieu')


class ReCaProvider(models.Model):
    _name = 're.ca.provider'
    _description = 'Kết nối ký số từ xa'
    _order = 'company_id, name'

    name = fields.Char(string='Tên gợi nhớ', required=True,
                       default='Viettel MySign')
    kieu = fields.Selection(
        [('mysign', 'Viettel MySign')],
        string='Nhà cung cấp', required=True, default='mysign',
        help='Hiện mới làm Viettel MySign. Các nhà cung cấp ký số từ xa '
             'khác ở Việt Nam cũng theo chuẩn Cloud Signature Consortium '
             'nên khác nhau chủ yếu ở đường dẫn và tên trường.')
    company_id = fields.Many2one(
        'res.company', string='Công ty', required=True,
        default=lambda self: self.env.company)
    active = fields.Boolean(string='Đang dùng', default=True)

    base_url = fields.Char(
        string='Địa chỉ máy chủ', required=True,
        help='Gốc địa chỉ do Viettel-CA cấp, KHÔNG kèm đường dẫn hàm. '
             'Ví dụ: https://remotesigning.viettel.vn')
    client_id = fields.Char(
        string='Client ID', required=True,
        help='ID ứng dụng ký, Viettel-CA cấp khi ký hợp đồng tích hợp.')
    client_secret = fields.Char(
        string='Client secret', required=True,
        groups='re_base.group_re_manager',
        help='Khoá bảo mật của ứng dụng ký. Chỉ người quản trị Realty '
             'đọc được ô này; Odoo không có két riêng cho bí mật nên ai '
             'có quyền ghi trên màn hình này là đọc được.')
    user_id = fields.Char(
        string='ID người ký', required=True,
        help='Định danh người ký do Viettel cấp — KHÁC với tài khoản '
             'Odoo. Mỗi người ký một chứng thư, nên mỗi người ký cần '
             'một bản khai riêng.')
    profile_id = fields.Char(
        string='Profile ID',
        help='Để trống nếu Viettel không cấp. Dùng khi một người ký có '
             'nhiều profile.')

    nguoi_ky_id = fields.Many2one(
        'res.users', string='Tài khoản Odoo của người ký',
        help='Nối bản khai này với một tài khoản Odoo. Để trống thì bản '
             'khai dùng chung cho cả công ty.')

    thuat_toan_bam = fields.Selection(
        [('sha256', 'SHA-256'), ('sha384', 'SHA-384'),
         ('sha512', 'SHA-512')],
        string='Thuật toán băm', required=True, default='sha256')
    cho_toi_da_giay = fields.Integer(
        string='Chờ xác nhận tối đa (giây)', default=90,
        help='Sau khi gửi yêu cầu, hệ thống hỏi lại liên tục cho tới khi '
             'người ký bấm xác nhận trên điện thoại. Đừng để quá 110 '
             'giây: Odoo tự cắt một yêu cầu web ở khoảng 120 giây, chờ '
             'lâu hơn là mất luôn tiến trình thay vì nhận được lời báo '
             'tử tế.')
    nhip_hoi_giay = fields.Integer(string='Nhịp hỏi lại (giây)', default=3)

    # ---- chỉ do lượt kiểm tra THẬT ghi vào, không ai gõ tay được ----
    trang_thai = fields.Selection(
        [('chua', 'Chưa kiểm'), ('ok', 'Kết nối được'), ('loi', 'Lỗi')],
        string='Tình trạng', default='chua', readonly=True, copy=False,
        help='Chỉ chuyển sang "Kết nối được" sau một lượt gọi THẬT tới '
             'máy chủ Viettel lấy được chứng thư về. Sửa bất kỳ thông '
             'tin đăng nhập nào là quay lại "Chưa kiểm".')
    kiem_luc = fields.Datetime(string='Kiểm lúc', readonly=True, copy=False)
    ghi_chu = fields.Text(string='Kết quả kiểm tra', readonly=True,
                          copy=False)

    credential_id = fields.Char(string='Credential ID', readonly=True,
                                copy=False)
    cert_subject = fields.Char(string='Chủ thể chứng thư', readonly=True,
                               copy=False)
    cert_issuer = fields.Char(string='Nơi cấp', readonly=True, copy=False)
    cert_valid_from = fields.Char(string='Hiệu lực từ', readonly=True,
                                  copy=False)
    cert_valid_to = fields.Char(string='Hiệu lực đến', readonly=True,
                                copy=False)
    key_algo = fields.Char(string='Thuật toán khoá', readonly=True,
                           copy=False)
    key_len = fields.Integer(string='Độ dài khoá (bit)', readonly=True,
                             copy=False)
    cert_chain = fields.Text(
        string='Chuỗi chứng thư', readonly=True, copy=False,
        help='Danh sách chứng thư Base64 lấy về từ Viettel, dạng JSON. '
             'Giữ lại để lúc ký không phải hỏi lại máy chủ.')

    _sql_constraints = [
        ('uniq_nguoi_ky',
         'unique(company_id, nguoi_ky_id, kieu)',
         'Mỗi người ký chỉ khai một kết nối cho mỗi nhà cung cấp.'),
    ]

    # ------------------------------------------------------------------
    @api.constrains('cho_toi_da_giay', 'nhip_hoi_giay')
    def _check_cho(self):
        for rec in self:
            if not 10 <= rec.cho_toi_da_giay <= 110:
                raise ValidationError(_(
                    'Thời gian chờ phải từ 10 tới 110 giây. Dưới 10 giây '
                    'thì không ai kịp mở điện thoại; trên 110 giây thì '
                    'Odoo cắt yêu cầu web trước khi ta kịp báo lỗi.'))
            if not 1 <= rec.nhip_hoi_giay <= 30:
                raise ValidationError(
                    _('Nhịp hỏi lại phải từ 1 tới 30 giây.'))

    @api.constrains('nguoi_ky_id', 'company_id', 'kieu', 'active')
    def _check_mot_ban_chung(self):
        """Ràng buộc SQL ở trên không chặn được trường hợp để trống người
        ký: Postgres coi hai NULL là khác nhau. Mà đúng chỗ ấy mới dễ
        nhầm — hai bản khai dùng chung thì không ai đoán được lượt ký
        đang chạy bằng bản nào."""
        for rec in self:
            if rec.nguoi_ky_id or not rec.active:
                continue
            if self.search_count([
                    ('id', '!=', rec.id), ('active', '=', True),
                    ('company_id', '=', rec.company_id.id),
                    ('kieu', '=', rec.kieu),
                    ('nguoi_ky_id', '=', False)]):
                raise ValidationError(_(
                    'Mỗi công ty chỉ được MỘT bản khai dùng chung cho '
                    'mỗi nhà cung cấp. Muốn khai thêm thì gắn bản mới '
                    'vào một tài khoản Odoo cụ thể.'))

    def write(self, vals):
        """Đổi thông tin đăng nhập là tình trạng kết nối hết giá trị.

        Không chỉ để cho gọn: nếu giữ nguyên chữ "Kết nối được" sau khi
        ai đó sửa client_secret, thì cái nhãn ấy đang nói dối về một thứ
        chưa từng được thử.
        """
        if any(o in vals for o in O_DANG_NHAP):
            vals = dict(vals, trang_thai='chua', credential_id=False,
                        cert_chain=False, ghi_chu=False, kiem_luc=False)
        return super().write(vals)

    # ------------------------------------------------------------------
    # Gọi REST
    # ------------------------------------------------------------------
    def _goi(self, duong_dan, payload, token=None, timeout=30):
        """POST JSON tới MySign, trả về dict đã giải mã.

        Lỗi của nhà cung cấp được ném lên nguyên văn (`error_description`)
        chứ không dịch lại: khi nối với một hệ bên ngoài, câu chữ của
        chính hệ đó là manh mối duy nhất để lần ra chuyện gì hỏng.
        """
        import requests
        self.ensure_one()
        url = '%s/%s' % ((self.base_url or '').rstrip('/'),
                         duong_dan.lstrip('/'))
        headers = {'Content-Type': 'application/json',
                   'Accept': 'application/json'}
        if token:
            headers['Authorization'] = 'Bearer %s' % token
        try:
            r = requests.post(url, json=payload, headers=headers,
                              timeout=timeout)
        except requests.exceptions.RequestException as e:
            raise UserError(_(
                'Không gọi được %(u)s:\n%(e)s', u=url, e=str(e)[:400]))
        try:
            data = r.json()
        except ValueError:
            raise UserError(_(
                'Máy chủ trả về thứ không phải JSON (HTTP %(s)s):\n%(t)s',
                s=r.status_code, t=r.text[:400]))
        if r.status_code >= 400 or data.get('error'):
            raise UserError(_(
                'Viettel MySign báo lỗi (HTTP %(s)s): %(e)s\n%(d)s',
                s=r.status_code, e=data.get('error') or '',
                d=data.get('error_description') or ''))
        return data

    def _dang_nhap(self):
        """Lấy access_token. Không cất lại: phiên ngắn, và cất một bí mật
        sống thêm một chỗ nữa thì được rất ít mà mất rất nhiều."""
        self.ensure_one()
        p = {'client_id': self.client_id,
             'client_secret': self.sudo().client_secret,
             'user_id': self.user_id}
        if self.profile_id:
            p['profile_id'] = self.profile_id
        d = self._goi('/vtss/service/ras/v1/login', p)
        tok = d.get('access_token')
        if not tok:
            raise UserError(_(
                'Đăng nhập được nhưng máy chủ không trả access_token. '
                'Nguyên văn: %s') % json.dumps(d)[:400])
        return tok

    def _lay_chung_thu(self, token):
        """credentials/list — xin CẢ CHUỖI chứng thư, không chỉ một tờ.

        `certificates='Chain'` vì PDF ký xong phải mang theo chứng thư
        trung gian, nếu không Adobe mở ra sẽ không dựng được đường tin
        cậy tới gốc và báo "chưa xác minh được người ký".
        """
        self.ensure_one()
        p = {'client_id': self.client_id,
             'client_secret': self.sudo().client_secret,
             'user_id': self.user_id,
             'certificates': 'Chain',
             'certInfo': True,
             'authInfo': True}
        if self.profile_id:
            p['profile_id'] = self.profile_id
        return self._goi('/adss/service/ras/csc/v1/credentials/list', p,
                         token=token)

    def _gui_bam(self, token, bam_b64, ten_tai_lieu):
        """signHash ở chế độ BẤT ĐỒNG BỘ (async=1).

        Chọn async vì đây là việc có người ở giữa: yêu cầu nhảy sang
        điện thoại, người ký đọc rồi mới bấm. Gọi đồng bộ thì Viettel
        giữ kết nối suốt quãng đó, mà Odoo lại cắt yêu cầu web ở khoảng
        120 giây — hỏng theo kiểu không ai đọc được log.
        """
        self.ensure_one()
        tt = self.thuat_toan_bam
        mo_ta = base64.b64encode(
            (ten_tai_lieu or 'Tài liệu')[:95].encode('utf-8')).decode()
        p = {'credentialID': self.credential_id,
             'numSignatures': 1,
             'hash': bam_b64,
             'hashAlgo': OID_BAM[tt],
             'signAlgo': OID_KY_RSA[tt],
             'description': mo_ta,
             'documents': [{'document_id': '1', 'document_name': mo_ta}],
             'async': 1}
        d = self._goi('/vtss/service/signHash', p, token=token)
        tx = d.get('transactionId')
        if not tx:
            raise UserError(_(
                'Gửi được mã băm nhưng không nhận lại transactionId. '
                'Nguyên văn: %s') % json.dumps(d)[:400])
        return tx

    def _cho_chu_ky(self, token, tx):
        """Hỏi lại tới khi người ký bấm xác nhận, hoặc tới hạn thì thôi.

        Hết giờ thì BỎ HẲN lượt ký này chứ không giữ lại trạng thái dở:
        chữ ký chưa chèn vào PDF nào cả nên không có gì hỏng, ký lại là
        xong. Giữ một bản PDF "đang chờ chữ ký" mới là thứ sinh ra rác
        và nhầm lẫn.
        """
        self.ensure_one()
        han = time.time() + max(self.cho_toi_da_giay, 10)
        lan = 0
        while time.time() < han:
            lan += 1
            d = self._goi('/vtss/service/requests/status',
                          {'transactionId': tx}, token=token)
            tt = str(d.get('status') or '')
            if tt == TT_XONG:
                ds = d.get('signatures') or []
                if not ds:
                    raise UserError(_(
                        'Máy chủ báo ký xong nhưng không trả chữ ký nào.'))
                return base64.b64decode(ds[0])
            if tt != TT_CHO:
                raise UserError(_(
                    'Ký không thành: %(n)s (mã %(m)s).',
                    n=TT_NGHIA.get(tt, 'không rõ'), m=tt or '?'))
            time.sleep(max(self.nhip_hoi_giay, 1))
        raise UserError(_(
            'Chờ %(g)s giây mà người ký chưa xác nhận trên ứng dụng '
            'MySign. Giao dịch %(t)s đã huỷ phía hệ thống này — mở app '
            'xác nhận sẵn rồi bấm ký lại.',
            g=self.cho_toi_da_giay, t=tx))

    # ------------------------------------------------------------------
    def action_kiem_tra(self):
        """Nút *Kiểm tra kết nối* — gọi THẬT, rồi ghi lại đúng những gì
        máy chủ trả về.

        Đây là chỗ duy nhất trong module ghi được `trang_thai='ok'`.
        """
        self.ensure_one()
        try:
            token = self._dang_nhap()
            d = self._lay_chung_thu(token)
        except UserError as e:
            self.sudo().write({
                'trang_thai': 'loi', 'kiem_luc': fields.Datetime.now(),
                'ghi_chu': str(e)})
            return self._mo_lai()

        cert = d.get('cert') or {}
        key = d.get('key') or {}
        ds = cert.get('certificates') or []
        cred = d.get('credential_id') or d.get('credentialID')
        if not ds or not cred:
            self.sudo().write({
                'trang_thai': 'loi', 'kiem_luc': fields.Datetime.now(),
                'ghi_chu': _(
                    'Đăng nhập được nhưng không lấy được chứng thư hoặc '
                    'credential_id. Thường là tài khoản chưa được cấp '
                    'chứng thư, hoặc chứng thư đã hết hạn.\n\n'
                    'Nguyên văn: %s') % json.dumps(d)[:800]})
            return self._mo_lai()

        algo = key.get('algo')
        self.sudo().write({
            'trang_thai': 'ok',
            'kiem_luc': fields.Datetime.now(),
            'credential_id': cred,
            'cert_chain': json.dumps(ds),
            'cert_subject': cert.get('subjectDN') or '',
            'cert_issuer': cert.get('issuerDN') or '',
            'cert_valid_from': cert.get('validFrom') or '',
            'cert_valid_to': cert.get('validTo') or '',
            'key_algo': ', '.join(algo) if isinstance(algo, list) else (
                algo or ''),
            'key_len': int(key.get('len') or 0),
            'ghi_chu': _(
                'Kết nối được. Lấy về %(n)d chứng thư, trạng thái khoá: '
                '%(k)s, trạng thái chứng thư: %(c)s.',
                n=len(ds), k=key.get('status') or '?',
                c=cert.get('status') or '?'),
        })
        return self._mo_lai()

    def _mo_lai(self):
        return {'type': 'ir.actions.act_window', 'res_model': self._name,
                'res_id': self.id, 'view_mode': 'form', 'target': 'current'}

    # ------------------------------------------------------------------
    @api.model
    def _tim_cho(self, user=None):
        """Bản khai dùng cho người đang ký: ưu tiên bản gắn đích danh."""
        user = user or self.env.user
        mien = [('company_id', '=', self.env.company.id), ('active', '=', True)]
        return (self.search(mien + [('nguoi_ky_id', '=', user.id)], limit=1)
                or self.search(mien + [('nguoi_ky_id', '=', False)], limit=1))


class MySignSigner:
    """Bộ ký cắm vào pyhanko, đẩy phần ký ra cho MySign.

    pyhanko đưa cho ``async_sign_raw`` đúng dải byte cần ký; ta băm dải
    đó rồi gửi mã băm đi. Khoá riêng nằm trong HSM của Viettel và không
    rời khỏi đó.

    ``dry_run`` là lượt pyhanko chạy thử để biết phải chừa bao nhiêu
    chỗ trống trong PDF cho chữ ký. Lượt này KHÔNG được gọi ra ngoài —
    gọi thì người ký lĩnh hai lần yêu cầu xác nhận cho một lần ký, và
    một trong hai cái sẽ bị bỏ rơi. Trả về bấy nhiêu byte rỗng theo độ
    dài khoá là đủ cho pyhanko đo chỗ.
    """

    def __init__(self, prov, ten_tai_lieu):
        from asn1crypto import algos, x509
        from pyhanko.sign.signers.pdf_cms import Signer
        from pyhanko_certvalidator.registry import SimpleCertificateStore

        ds = [base64.b64decode(c) for c in json.loads(prov.cert_chain)]
        certs = [x509.Certificate.load(b) for b in ds]
        tt = prov.thuat_toan_bam

        class _S(Signer):
            def __init__(s):
                kho = SimpleCertificateStore()
                kho.register_multiple(certs[1:])
                super().__init__(
                    signing_cert=certs[0],
                    cert_registry=kho,
                    signature_mechanism=algos.SignedDigestAlgorithm(
                        {'algorithm': '%s_rsa' % tt}),
                )

            async def async_sign_raw(self, data, digest_algorithm,
                                     dry_run=False):
                if dry_run:
                    return b'\0' * max(int(prov.key_len or 2048) // 8, 256)
                h = hashlib.new(digest_algorithm or tt, data).digest()
                token = prov._dang_nhap()
                tx = prov._gui_bam(token, base64.b64encode(h).decode(),
                                   ten_tai_lieu)
                _logger.info('MySign: gửi mã băm, giao dịch %s', tx)
                return prov._cho_chu_ky(token, tx)

        self.signer = _S()
