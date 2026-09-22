"""Tests for the self-watchdog liveness probe."""

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from app.utils.watchdog import probe


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'ok')

    def log_message(self, *args):
        pass


def _serve_on_free_port():
    server = HTTPServer(('127.0.0.1', 0), _Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, port


class TestProbe:
    def test_healthy_server_answers(self):
        server, port = _serve_on_free_port()
        try:
            assert probe('127.0.0.1', port, use_ssl=False) is True
        finally:
            server.shutdown()

    def test_dead_port_fails(self):
        # Port 1 is never listening.
        assert probe('127.0.0.1', 1, use_ssl=False, timeout=2) is False

    def test_ssl_mismatch_fails_plain(self):
        server, port = _serve_on_free_port()
        try:
            # Plain HTTP server probed as HTTPS must fail, not hang.
            assert probe('127.0.0.1', port, use_ssl=True, timeout=5) is False
        finally:
            server.shutdown()
