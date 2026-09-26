"""Tests for SSH known-hosts persistence (kills the unknown-key warning)."""

import os

from app.services import ssh as ssh_module
from app.services.ssh import SSHService


class _FakeTransport:
    def is_active(self):
        return True

    def set_keepalive(self, interval):
        pass


class _FakeClient:
    instances = []

    def __init__(self):
        self.loaded = []
        self.saved = []
        self.connected = False
        _FakeClient.instances.append(self)

    def load_host_keys(self, path):
        self.loaded.append(path)
        if not os.path.exists(path):
            raise FileNotFoundError(path)

    def set_missing_host_key_policy(self, policy):
        pass

    def connect(self, **kwargs):
        self.connected = True

    def get_transport(self):
        return _FakeTransport()

    def save_host_keys(self, path):
        self.saved.append(path)
        with open(path, 'w') as f:
            f.write('# test known hosts\n')

    def close(self):
        pass


def _service(monkeypatch, tmp_path):
    monkeypatch.setattr(ssh_module.paramiko, 'SSHClient', _FakeClient)
    monkeypatch.setenv('DUNE_KNOWN_HOSTS', str(tmp_path / 'known_hosts'))
    _FakeClient.instances.clear()
    return SSHService('example.com', 'dune', ssh_key=None)


class TestKnownHosts:
    def test_saves_after_connect(self, tmp_path, monkeypatch):
        svc = _service(monkeypatch, tmp_path)
        client = svc._get_client()
        assert client.connected is True
        assert client.saved == [str(tmp_path / 'known_hosts')]
        assert os.path.exists(str(tmp_path / 'known_hosts'))

    def test_loads_existing_file(self, tmp_path, monkeypatch):
        hosts = tmp_path / 'known_hosts'
        hosts.write_text('# existing\n')
        svc = _service(monkeypatch, tmp_path)
        client = svc._get_client()
        assert client.loaded == [str(hosts)]

    def test_reuses_live_client(self, tmp_path, monkeypatch):
        svc = _service(monkeypatch, tmp_path)
        first = svc._get_client()
        second = svc._get_client()
        assert first is second
        assert len(_FakeClient.instances) == 1
