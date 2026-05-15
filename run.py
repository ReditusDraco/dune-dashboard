#!/usr/bin/env python3
"""Dune Awakening Dashboard - Entry Point"""

import os
import sys
import socket
import threading

sys.path.insert(0, os.path.dirname(__file__))

from app.factory import create_app

app, socketio = create_app()

if __name__ == '__main__':
    import logging
    logging.getLogger('werkzeug').setLevel(logging.ERROR)

    settings = app.dune_settings
    host = settings['dashboard']['host']
    port = settings['dashboard']['port']
    debug = settings['dashboard']['debug']

    # SSL Configuration
    ssl_context = None
    ssl_cert = settings['dashboard'].get('ssl_cert')
    ssl_key = settings['dashboard'].get('ssl_key')

    if ssl_cert and ssl_key and ssl_cert != 'null' and ssl_key != 'null':
        cert_path = str(ssl_cert).strip("'\"")
        key_path = str(ssl_key).strip("'\"")
        if os.path.exists(cert_path) and os.path.exists(key_path):
            ssl_context = (cert_path, key_path)
            protocol = "https"
        else:
            print(f"  [WARN] SSL files not found: {cert_path}")
            protocol = "http"
    else:
        protocol = "http"

    print(f"\n  Dune Awakening Dashboard")
    print(f"  Bind: {host}:{port}")
    if host == '0.0.0.0':
        print(f"  Local: {protocol}://localhost:{port}")
        print(f"  Local: {protocol}://127.0.0.1:{port}")
        print(f"  Remote: {protocol}://<your-ip-or-domain>:{port}")
    else:
        print(f"  URL: {protocol}://{host}:{port}")
    print(f"  Debug: {debug}")

    if debug and host not in ('127.0.0.1', 'localhost', '0.0.0.0'):
        print("  [ERROR] Refusing to run debug mode on a non-loopback host!")
        print(f"  [ERROR] Host '{host}' is not 127.0.0.1, localhost, or 0.0.0.0")
        print("  [ERROR] Set dashboard.debug: false in settings.yaml or bind to loopback\n")
        sys.exit(1)

    if ssl_context:
        print(f"  SSL: Enabled\n")
    else:
        print(f"  SSL: Disabled (use http:// not https://)\n")
        if host == '0.0.0.0' and not os.environ.get('DUNE_ALLOW_INSECURE_REMOTE'):
            print("  [ERROR] Refusing to bind 0.0.0.0 without SSL!")
            print("  [ERROR] Set DUNE_ALLOW_INSECURE_REMOTE=1 to override (NOT RECOMMENDED)")
            print("  [ERROR] Enable SSL in settings.yaml or bind to 127.0.0.1\n")
            sys.exit(1)
        elif host == '0.0.0.0':
            print("  [WARN] Binding to 0.0.0.0 without SSL! Credentials sent in cleartext.")
            print("  [WARN] DUNE_ALLOW_INSECURE_REMOTE is set - override is active\n")

    # Start optional HTTP -> HTTPS redirect server when SSL is enabled.
    # This is convenience only; the dashboard works without port 80 if users visit https://host:port.
    if ssl_context and settings['dashboard'].get('http_redirect', False):
        from http.server import HTTPServer, BaseHTTPRequestHandler

        class RedirectHandler(BaseHTTPRequestHandler):
            def _redirect_url(self):
                host_header = self.headers.get("Host", "localhost")
                redirect_host = host_header.rsplit(":", 1)[0] if ":" in host_header else host_header
                if not redirect_host or redirect_host == "0.0.0.0":
                    redirect_host = "localhost"
                port_part = "" if int(port) == 443 else f":{port}"
                return f"https://{redirect_host}{port_part}{self.path}"

            def do_GET(self):
                self.send_response(301)
                self.send_header('Location', self._redirect_url())
                self.end_headers()

            def do_HEAD(self):
                self.do_GET()

            def do_POST(self):
                self.do_GET()

            def log_message(self, format, *args):
                pass

        # Try configured redirect port first, fall back to dashboard port+1.
        # Try 0.0.0.0 first (all interfaces), fall back to 127.0.0.1 (localhost only)
        http_port = None
        redirect_host = None
        redirect_port = int(settings['dashboard'].get('http_redirect_port', 80) or 80)
        for try_port in [redirect_port, port + 1]:
            for try_host in ['0.0.0.0', '127.0.0.1']:
                try:
                    test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    test_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    test_sock.bind((try_host, try_port))
                    test_sock.close()
                    http_port = try_port
                    redirect_host = try_host
                    break
                except OSError:
                    continue
            if http_port:
                break

        if http_port:
            redirect_server = HTTPServer((redirect_host, http_port), RedirectHandler)
            redirect_thread = threading.Thread(target=redirect_server.serve_forever, daemon=True)
            redirect_thread.start()
            target_host = '<same-host>'
            print(f"  HTTP redirect: http://0.0.0.0:{http_port} -> https://{target_host}:{port}" if redirect_host == '0.0.0.0' else f"  HTTP redirect: http://localhost:{http_port} -> https://localhost:{port}")
            if http_port == 80:
                print(f"  (visit http://localhost to auto-redirect to HTTPS)\n")
            else:
                print(f"  (visit http://localhost:{http_port} to auto-redirect to HTTPS)\n")
        else:
            print("  [WARN] Could not start HTTP redirect server\n")
    elif ssl_context:
        print("  HTTP redirect: Disabled (visit the HTTPS URL directly)\n")

    socketio.run(app, host=host, port=port, debug=debug, log_output=False, ssl_context=ssl_context)
