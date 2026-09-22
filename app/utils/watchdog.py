"""Self-watchdog - exits the process when the dashboard stops responding.

The dashboard is exposed to the public internet, where scanners constantly
open connections that never complete. If the WSGI server ever wedges again
(accepts TCP but never answers HTTP), this thread is the backstop: after a
grace period it probes a light local endpoint, and if the probes keep
failing it exits with a dedicated exit code so the launcher restarts us.

Exit code 42 = watchdog trip (launcher auto-restarts, tunnels stay up).
Any other exit (e.g. Ctrl+C -> 0) shuts down normally.
"""

import http.client
import logging
import os
import ssl as sslmod
import threading
import time

logger = logging.getLogger(__name__)

WATCHDOG_EXIT_CODE = 42


def probe(host, port, use_ssl, path='/login', timeout=10):
    """Single liveness probe. True when the server answers HTTP."""
    conn = None
    try:
        if use_ssl:
            ctx = sslmod._create_unverified_context()
            conn = http.client.HTTPSConnection(host, port, timeout=timeout, context=ctx)
        else:
            conn = http.client.HTTPConnection(host, port, timeout=timeout)
        conn.request('GET', path)
        resp = conn.getresponse()
        # Any HTTP response (even 4xx/5xx) proves the server is alive.
        return 200 <= resp.status < 600
    except Exception:
        return False
    finally:
        try:
            if conn:
                conn.close()
        except Exception:
            pass


def start_watchdog(host, port, use_ssl):
    """Start the watchdog thread. Returns the thread (daemon)."""
    interval = int(os.environ.get('DUNE_WATCHDOG_INTERVAL', '30'))
    grace = int(os.environ.get('DUNE_WATCHDOG_GRACE', '180'))
    failures_needed = int(os.environ.get('DUNE_WATCHDOG_FAILURES', '3'))
    if os.environ.get('DUNE_WATCHDOG', '1') == '0':
        logger.info('Watchdog: disabled via DUNE_WATCHDOG=0')
        return None

    # The server may bind all interfaces or a specific IP; always probe
    # loopback when possible so the check never depends on the network.
    probe_host = '127.0.0.1' if host in ('0.0.0.0', '127.0.0.1', 'localhost') else host
    started = time.time()

    def _watch():
        failures = 0
        while True:
            time.sleep(interval)
            if time.time() - started < grace:
                continue
            if probe(probe_host, port, use_ssl):
                failures = 0
                continue
            failures += 1
            logger.warning(f'Watchdog: self-check failed ({failures}/{failures_needed})')
            if failures >= failures_needed:
                logger.critical(
                    'Watchdog: dashboard unresponsive - exiting '
                    f'with code {WATCHDOG_EXIT_CODE} for launcher restart')
                print('  [WATCHDOG] Dashboard unresponsive - exiting for launcher restart',
                      flush=True)
                os._exit(WATCHDOG_EXIT_CODE)

    thread = threading.Thread(target=_watch, daemon=True, name='watchdog')
    thread.start()
    logger.info(
        f'Watchdog: probing {probe_host}:{port} every {interval}s '
        f'(grace {grace}s, {failures_needed} failures to trip)')
    return thread
