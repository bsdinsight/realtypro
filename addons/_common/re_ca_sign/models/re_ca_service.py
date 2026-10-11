# -*- coding: utf-8 -*-
"""Ký số lên PDF theo chuẩn PAdES.

Khác hẳn ``re_sign``: ở đó chữ ký nằm trong cơ sở dữ liệu và chỉ Odoo
hiểu. Ở đây chữ ký nằm TRONG CHÍNH FILE PDF, nên gửi file đi đâu người
ta cũng mở Adobe Reader ra kiểm được — ai ký, lúc nào, và tài liệu có
bị sửa sau khi ký hay không.

Ba đường ký (tham số hệ thống ``re_ca_sign.provider``):

* ``test``     — chứng thư tự sinh, để chạy thử và demo.
* ``smartca``  — ký số từ xa: khoá riêng nằm trong HSM của nhà cung cấp,
                 hệ thống chỉ gửi MÃ BĂM đi và nhận chữ ký về.
* ``token``    — token USB ở máy người ký; máy chủ không với tới được.

Chỗ cần hiểu cho đúng: ở cả hai đường thật, **khoá riêng không bao giờ
đi qua hệ thống này**. Thứ gửi đi là mã băm của tài liệu, thứ nhận về
là chữ ký của mã băm đó. Nên kể cả hệ thống bị chiếm quyền thì cũng
không ai ký thay được người khác.
"""
import base64
import datetime
import logging

from odoo import _, api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

PARAM_PROVIDER = 're_ca_sign.provider'
PARAM_TEST_PFX = 're_ca_sign.test_pfx'
PARAM_TEST_PWD = 're_ca_sign.test_pfx_password'


class ReCaService(models.AbstractModel):
    _name = 're.ca.service'
    _description = 'Dịch vụ ký số CA'

    # ------------------------------------------------------------------
    @api.model
    def _param(self, key, default=''):
        return self.env['ir.config_parameter'].sudo().get_param(key, default)

    @api.model
    def get_provider(self):
        return self._param(PARAM_PROVIDER, 'test')

    @api.model
    def _require_pyhanko(self):
        try:
            import pyhanko  # noqa: F401
        except ImportError:
            raise UserError(_(
                "Máy chủ chưa cài thư viện ký số (pyhanko). Đây là việc "
                "của quản trị hệ thống: thư viện phải nằm TRONG image "
                "Docker, cài tay bằng pip sẽ mất khi dựng lại container."))

    # ------------------------------------------------------------------
    # Chứng thư thử — sinh một lần rồi cất vào tham số hệ thống
    # ------------------------------------------------------------------
    @api.model
    def _ensure_test_cert(self):
        """Sinh cặp CA + chứng thư người ký nếu chưa có.

        Dựng CẢ MỘT CA nhỏ chứ không chỉ một chứng thư tự ký: Adobe đọc
        chuỗi tin cậy, và một chứng thư đứng một mình thì bảng chữ ký
        hiện khác hẳn với chứng thư do một CA cấp. Muốn buổi chạy thử
        giống thật thì phải giống ở chỗ đó.
        """
        ICP = self.env['ir.config_parameter'].sudo()
        if ICP.get_param(PARAM_TEST_PFX):
            return
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives.serialization import pkcs12
        from cryptography.x509.oid import NameOID

        cong_ty = self.env.company.name or 'BSD Insight'
        now = datetime.datetime.now(datetime.timezone.utc)

        def ten(cn, o):
            return x509.Name([
                x509.NameAttribute(NameOID.COUNTRY_NAME, 'VN'),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, o),
                x509.NameAttribute(NameOID.COMMON_NAME, cn),
            ])

        ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        ca_name = ten('BSD Test Root CA (KHONG dung that)', 'BSD Insight')
        ca_cert = (
            x509.CertificateBuilder()
            .subject_name(ca_name).issuer_name(ca_name)
            .public_key(ca_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=3650))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0),
                           critical=True)
            .add_extension(x509.KeyUsage(
                digital_signature=True, key_cert_sign=True, crl_sign=True,
                content_commitment=False, key_encipherment=False,
                data_encipherment=False, key_agreement=False,
                encipher_only=False, decipher_only=False), critical=True)
            .sign(ca_key, hashes.SHA256())
        )

        u_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        u_cert = (
            x509.CertificateBuilder()
            .subject_name(ten(cong_ty, cong_ty)).issuer_name(ca_name)
            .public_key(u_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=1825))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None),
                           critical=True)
            # Không khai hai cái dưới thì Adobe vẫn mở được nhưng xếp
            # chữ ký vào loại "không rõ mục đích" — mất đúng dòng chữ mà
            # người xem cần đọc.
            .add_extension(x509.KeyUsage(
                digital_signature=True, content_commitment=True,
                key_cert_sign=False, crl_sign=False, key_encipherment=False,
                data_encipherment=False, key_agreement=False,
                encipher_only=False, decipher_only=False), critical=True)
            .add_extension(x509.ExtendedKeyUsage(
                [x509.ObjectIdentifier('1.3.6.1.5.5.7.3.4')]), critical=False)
            .sign(ca_key, hashes.SHA256())
        )

        pfx = pkcs12.serialize_key_and_certificates(
            name=b'bsd-test', key=u_key, cert=u_cert, cas=[ca_cert],
            encryption_algorithm=serialization.BestAvailableEncryption(
                b'bsdtest'))
        ICP.set_param(PARAM_TEST_PFX, base64.b64encode(pfx).decode())
        ICP.set_param(PARAM_TEST_PWD, 'bsdtest')
        _logger.info('re_ca_sign: đã sinh chứng thư thử (CA + người ký).')

    # ------------------------------------------------------------------
    @api.model
    def _signer_test(self):
        """Dựng signer THẲNG từ khoá và chứng thư, không qua tệp tạm.

        ``SimpleSigner.load_pkcs12`` đòi ĐƯỜNG DẪN tệp, không nhận luồng
        bộ nhớ — mà ghi khoá riêng ra đĩa dù chỉ vài mili-giây là thói
        quen không nên có. Nạp bằng `cryptography` rồi chuyển sang
        asn1crypto qua DER là xong, pyhanko nhận thẳng.
        """
        from cryptography.hazmat.primitives.serialization import (
            pkcs12, Encoding, PrivateFormat, NoEncryption)
        from asn1crypto import x509 as a_x509, keys as a_keys
        from pyhanko.sign import signers
        from pyhanko_certvalidator.registry import SimpleCertificateStore

        self._ensure_test_cert()
        pfx = base64.b64decode(self._param(PARAM_TEST_PFX))
        pwd = (self._param(PARAM_TEST_PWD) or '').encode()
        key, cert, chain = pkcs12.load_key_and_certificates(pfx, pwd)

        kho = SimpleCertificateStore()
        kho.register_multiple([
            a_x509.Certificate.load(c.public_bytes(Encoding.DER))
            for c in (chain or [])])
        return signers.SimpleSigner(
            signing_cert=a_x509.Certificate.load(
                cert.public_bytes(Encoding.DER)),
            signing_key=a_keys.PrivateKeyInfo.load(
                key.private_bytes(Encoding.DER, PrivateFormat.PKCS8,
                                  NoEncryption())),
            cert_registry=kho)

    # ------------------------------------------------------------------
    @api.model
    def sign_pdf(self, pdf_bytes, signer_name, reason=None, location=None,
                 field_name='ChuKySo'):
        """Ký PDF, trả về bytes PDF đã ký.

        Ký kiểu *incremental update*: nội dung cũ giữ nguyên từng byte,
        chữ ký nối thêm vào cuối file. Nhờ vậy Adobe mới nói được câu
        "tài liệu chưa bị sửa kể từ khi ký" — nó so đúng dải byte đã ký
        chứ không so một bản dựng lại.
        """
        self._require_pyhanko()
        import io
        from pyhanko.sign import signers
        from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter

        nha_cc = self.get_provider()
        if nha_cc == 'token':
            raise UserError(_(
                "Token USB cắm ở máy người ký thì máy chủ không với tới "
                "được — phải có phần mềm ký chạy trên chính máy đó. Chọn "
                "'Ký số từ xa' hoặc 'Chứng thư thử' trong cấu hình."))
        if nha_cc == 'smartca':
            signer = self._signer_smartca(signer_name)
        else:
            signer = self._signer_test()

        meta = signers.PdfSignatureMetadata(
            field_name=field_name,
            reason=reason or _('Phê duyệt trên hệ thống EPCOne'),
            location=location or (self.env.company.city or 'Việt Nam'),
            name=signer_name,
            # Không nhúng dấu thời gian của một máy chủ TSA thì mốc thời
            # gian chỉ là đồng hồ của máy ký — đổi được. Khi có hợp đồng
            # CA thật thì truyền `timestamper` vào đây.
        )
        out = io.BytesIO()
        w = IncrementalPdfFileWriter(io.BytesIO(pdf_bytes))
        signers.sign_pdf(w, meta, signer=signer, output=out)
        return out.getvalue()

    # ------------------------------------------------------------------
    # Ký số từ xa — khoá nằm trong HSM nhà cung cấp
    # ------------------------------------------------------------------
    @api.model
    def _signer_smartca(self, signer_name):
        """CHƯA CHẠY THẬT — cần hợp đồng và tài khoản của nhà cung cấp CA.

        Hình dạng chung của mọi nhà cung cấp ký số từ xa ở Việt Nam
        (VNPT SmartCA, Viettel, FPT.eSign) giống nhau, khác ở đường dẫn
        và tên trường:

        1. Lấy vé truy cập bằng client_id/client_secret.
        2. Hỏi danh sách chứng thư của người ký → lấy chuỗi chứng thư.
        3. Gửi MÃ BĂM của dải byte cần ký, kèm định danh người ký.
        4. Người ký bấm xác nhận trên ứng dụng điện thoại.
        5. Hỏi lại tới khi có kết quả → nhận chữ ký thô.
        6. Nhét chữ ký vào đúng chỗ trống đã chừa trong PDF.

        pyhanko làm được bước 6 bằng ``ExternalSigner`` + ký hai pha
        (``PdfTBSDocument``). Phần còn lại là gọi REST, viết khi có tài
        khoản — viết mò bây giờ thì không cách nào biết đúng hay sai, mà
        một lớp ký "trông như chạy" còn nguy hơn là chưa có.
        """
        raise UserError(_(
            "Ký số từ xa chưa nối được: cần tài khoản của nhà cung cấp "
            "chứng thực (VNPT SmartCA / Viettel-CA / FPT.eSign) gồm "
            "client_id, client_secret và định danh người ký.\n\n"
            "Hiện đang để chế độ 'Chứng thư thử' — cơ chế ký và kiểm tra "
            "là thật, chỉ thiếu việc chứng thư do tổ chức chứng thực cấp, "
            "nên Adobe sẽ báo chữ ký hợp lệ nhưng chưa tin cậy được người "
            "ký."))

    # ------------------------------------------------------------------
    @api.model
    def read_signatures(self, pdf_bytes):
        """Đọc lại các chữ ký trong một PDF đã ký — để hiện trên màn hình
        đúng những gì Adobe sẽ nói, chứ không bắt người dùng tải về mới
        biết."""
        self._require_pyhanko()
        import io
        from pyhanko.pdf_utils.reader import PdfFileReader
        from pyhanko.sign.validation import validate_pdf_signature

        kq = []
        r = PdfFileReader(io.BytesIO(pdf_bytes))
        for sig in r.embedded_signatures:
            try:
                st = validate_pdf_signature(sig)
                kq.append({
                    'name': sig.signer_cert.subject.human_friendly,
                    'signed_on': sig.self_reported_timestamp,
                    'intact': bool(st.intact),
                    'valid': bool(st.valid),
                    'trusted': bool(getattr(st, 'trusted', False)),
                    'coverage': str(st.coverage),
                    'summary': st.summary(),
                })
            except Exception as e:  # noqa: BLE001
                kq.append({'name': '?', 'error': str(e)[:300]})
        return kq
