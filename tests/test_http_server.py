"""Tests for the cheroot server builder + handshake-noise filter."""

import logging

from app.utils.http_server import build_server, cheroot_error_filter


class TestHandshakeFilter:
    def test_handshake_drops_go_to_debug_only(self, caplog):
        calls = []

        def orig(msg='', level=20, traceback=False):
            calls.append((msg, level))

        with caplog.at_level(logging.DEBUG, logger='app.utils.http_server'):
            cheroot_error_filter(orig, 'Client (\'1.2.3.4\', 123) lost - peer '
                                 'dropped the TLS connection suddenly, during '
                                 'handshake: (8, \'[SSL: SSLV3_ALERT_CERTIFICATE_UNKNOWN] \')')
        assert calls == []
        assert any('handshake dropped' in r.message for r in caplog.records)
        assert all(r.levelno == logging.DEBUG for r in caplog.records)

    def test_real_errors_pass_through(self):
        calls = []

        def orig(msg='', level=20, traceback=False):
            calls.append((msg, level, traceback))

        cheroot_error_filter(orig, 'socket.error 104', level=30, traceback=True)
        assert calls == [('socket.error 104', 30, True)]


def _self_signed_pair(tmp_path):
    import datetime
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'localhost')])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now).not_valid_after(now + datetime.timedelta(days=1))
            .sign(key, hashes.SHA256()))
    cert_path = tmp_path / 'c.pem'
    key_path = tmp_path / 'k.pem'
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption()))
    return str(cert_path), str(key_path)


class TestBuildServer:
    def test_timeouts_and_queues(self):
        server = build_server('127.0.0.1', 0, None)
        try:
            assert server.numthreads == 16
            assert server.timeout == 60
            assert server.request_queue_size == 128
        finally:
            server.stop()

    def test_tls_adapter(self, tmp_path):
        cert, key = _self_signed_pair(tmp_path)
        server = build_server('127.0.0.1', 0, None, cert, key)
        try:
            assert server.ssl_adapter is not None
        finally:
            server.stop()
