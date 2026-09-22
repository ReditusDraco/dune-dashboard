"""Tests for no-behavior-change security validations."""

import pytest

from app.routes.api import fb_within_roots
from app.services.backup import is_valid_backup_name


class TestFileBrowserJail:
    ROOTS = ['/srv', '/home/dune/.dune']

    def test_inside_roots(self):
        assert fb_within_roots('/srv', self.ROOTS)
        assert fb_within_roots('/srv/', self.ROOTS)
        assert fb_within_roots('/srv/sub/dir/file.txt', self.ROOTS)
        assert fb_within_roots('/home/dune/.dune/settings.conf', self.ROOTS)

    def test_outside_roots(self):
        assert not fb_within_roots('/', self.ROOTS)
        assert not fb_within_roots('/etc/passwd', self.ROOTS)
        assert not fb_within_roots('/etc/shadow', self.ROOTS)
        assert not fb_within_roots('/home/dune/.ssh/id_rsa', self.ROOTS)
        assert not fb_within_roots('/home/dune/.dune-evil/x', self.ROOTS)
        assert not fb_within_roots('/srv-evil/x', self.ROOTS)
        assert not fb_within_roots('', self.ROOTS)

    def test_prefix_trick_rejected(self):
        # '/srv-evil' must not match root '/srv'
        assert not fb_within_roots('/srv-evil', ['/srv'])
        assert fb_within_roots('/srv/a', ['/srv'])


class TestBackupNameWhitelist:
    def test_valid_names(self):
        assert is_valid_backup_name('backup-21-09-2026_103000')
        assert is_valid_backup_name('backup-01-01-2000_000000')

    def test_rejects_traversal_and_shell(self):
        assert not is_valid_backup_name('../../settings')
        assert not is_valid_backup_name('backup-21-09-2026_103000; id')
        assert not is_valid_backup_name('x; id>/tmp/pwn; echo ')
        assert not is_valid_backup_name('')
        assert not is_valid_backup_name(None)
        assert not is_valid_backup_name('backup-21-09-2026_103000.tar.gz')
        assert not is_valid_backup_name('something-else')


class TestOnceAtValidation:
    def test_lifecycle_rejects_garbage(self, tmp_path):
        from app.services.lifecycle import LifecycleService

        class FakeSSH:
            def run(self, *a, **k):
                return '', '', 0

        class FakeAdmin:
            def send_global_broadcast(self, *a, **k):
                return True, 'sent'

        svc = LifecycleService(FakeSSH(), FakeAdmin(), {}, state_dir=str(tmp_path))
        with pytest.raises(ValueError):
            svc.update_schedule({'mode': 'once', 'once_at': 'not-a-date'})

    def test_broadcast_rejects_garbage(self, tmp_path):
        from app.services.scheduled_broadcast import ScheduledBroadcastService

        class FakeAdmin:
            def send_global_broadcast(self, *a, **k):
                return True, 'sent'

        svc = ScheduledBroadcastService(FakeAdmin(), state_dir=str(tmp_path))
        with pytest.raises(ValueError):
            svc.save_entry({
                'title': 't', 'message': 'm', 'mode': 'once',
                'once_at': 'not-a-date',
            })
