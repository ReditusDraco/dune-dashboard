"""Production HTTP server builder (cheroot) with noise filtering.

Cheroot writes server-level errors (e.g. scanners dropping TLS handshakes)
straight to stderr, bypassing the dashboard's log levels. The filter below
sends the known-benign handshake noise to the debug log and lets everything
else through untouched.
"""

import logging

logger = logging.getLogger(__name__)

# Fragments identifying a peer that vanished mid-handshake (typically an
# internet scanner hitting the public HTTPS port). Never real failures.
_HANDSHAKE_NOISE = (
    'during handshake',
    'SSLV3_ALERT',
    'UNEXPECTED_EOF',
    'TLSV1_ALERT',
)


def cheroot_error_filter(original_error_log, msg='', level=20, traceback=False):
    """Drop-in replacement for ``server.error_log``.

    Handshake noise -> debug log. Everything else -> original handler.
    """
    text = str(msg)
    lowered = text.lower()
    if any(fragment.lower() in lowered for fragment in _HANDSHAKE_NOISE):
        logger.debug('TLS handshake dropped by peer: %s', text[:200])
        return
    original_error_log(msg, level=level, traceback=traceback)


def build_server(host, port, wsgi_app, cert_path=None, key_path=None,
                 numthreads=16, socket_timeout=60):
    """Build a cheroot server with timeouts, bounded queues and TLS support."""
    from cheroot import wsgi as cheroot_wsgi

    server = cheroot_wsgi.Server(
        (host, port), wsgi_app,
        numthreads=numthreads,
        request_queue_size=128,
        timeout=socket_timeout,
        accepted_queue_size=128,
        accepted_queue_timeout=10,
    )
    if cert_path and key_path:
        from cheroot.ssl.builtin import BuiltinSSLAdapter
        server.ssl_adapter = BuiltinSSLAdapter(cert_path, key_path)
    original = server.error_log
    server.error_log = lambda msg='', level=20, traceback=False: \
        cheroot_error_filter(original, msg, level=level, traceback=traceback)
    return server
