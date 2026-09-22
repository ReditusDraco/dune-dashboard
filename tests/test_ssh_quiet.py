"""Tests for SSHService.run(quiet=...) - log level only, same results."""

import logging

from app.services.ssh import SSHService


class _FakeChannel:
    def __init__(self, rc):
        self._rc = rc

    def settimeout(self, timeout):
        pass

    def recv_exit_status(self):
        return self._rc


class _FakeStream:
    def __init__(self, data, rc):
        self._data = data
        self.channel = _FakeChannel(rc)

    def read(self):
        return self._data


class _FakeClient:
    def __init__(self, out=b'', err=b'Error from server (NotFound)', rc=1):
        self._out = _FakeStream(out, rc)
        self._err = _FakeStream(err, rc)

    def get_transport(self):
        return None

    def exec_command(self, command, timeout=None):
        return None, self._out, self._err


def _service_with_fake_client():
    svc = SSHService.__new__(SSHService)
    import threading
    svc.host = 'h'
    svc.user = 'u'
    svc.ssh_key = None
    svc._client = _FakeClient()
    svc._lock = threading.Lock()
    # Bypass reconnect logic: _get_client returns the fake directly when
    # its transport check is skipped. Patch at instance level.
    svc._get_client = lambda: svc._client
    return svc


class TestQuietFlag:
    def test_results_identical_quiet_or_not(self, caplog):
        svc = _service_with_fake_client()
        with caplog.at_level(logging.DEBUG, logger='app.services.ssh'):
            out1, err1, rc1 = svc.run('kubectl get x', quiet=False)
        with caplog.at_level(logging.DEBUG, logger='app.services.ssh'):
            out2, err2, rc2 = svc.run('kubectl get x', quiet=True)
        assert (out1, err1, rc1) == (out2, err2, rc2) == ('', 'Error from server (NotFound)', 1)

    def test_loud_logs_warning_quiet_logs_debug(self, caplog):
        svc = _service_with_fake_client()
        with caplog.at_level(logging.DEBUG, logger='app.services.ssh'):
            caplog.clear()
            svc.run('kubectl get x', quiet=False)
            loud_levels = {r.levelno for r in caplog.records if 'rc=1' in r.message}
        with caplog.at_level(logging.DEBUG, logger='app.services.ssh'):
            caplog.clear()
            svc.run('kubectl get x', quiet=True)
            quiet_levels = {r.levelno for r in caplog.records if 'rc=1' in r.message}
        assert logging.WARNING in loud_levels
        assert logging.WARNING not in quiet_levels
