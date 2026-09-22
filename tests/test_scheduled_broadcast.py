"""Tests for scheduled custom notifications."""

from datetime import datetime, timedelta

import pytest

from app.services.scheduled_broadcast import ScheduledBroadcastService


class FakeAdmin:
    def __init__(self):
        self.broadcasts = []

    def send_global_broadcast(self, title, message, duration=30):
        self.broadcasts.append((title, message, duration))
        return True, 'sent'


def make_service(tmp_path):
    admin = FakeAdmin()
    svc = ScheduledBroadcastService(admin, state_dir=str(tmp_path))
    return svc, admin


def base_entry(**overrides):
    entry = {
        'title': 'Notice',
        'message': 'Hello players',
        'duration': 30,
        'mode': 'daily',
        'daily_times': ['12:00'],
    }
    entry.update(overrides)
    return entry


class TestEntryCrud:
    def test_save_and_list(self, tmp_path):
        svc, _ = make_service(tmp_path)
        entry = svc.save_entry(base_entry())
        assert entry['id']
        assert entry['next_run']
        assert [e['id'] for e in svc.list_entries()] == [entry['id']]

    def test_requires_title_and_message(self, tmp_path):
        svc, _ = make_service(tmp_path)
        with pytest.raises(ValueError):
            svc.save_entry(base_entry(title=''))
        with pytest.raises(ValueError):
            svc.save_entry(base_entry(message=''))

    def test_duration_clamped(self, tmp_path):
        svc, _ = make_service(tmp_path)
        assert svc.save_entry(base_entry(duration=999))['duration'] == 300
        assert svc.save_entry(base_entry(duration=1))['duration'] == 5

    def test_rejects_bad_mode(self, tmp_path):
        svc, _ = make_service(tmp_path)
        with pytest.raises(ValueError):
            svc.save_entry(base_entry(mode='yearly'))

    def test_delete(self, tmp_path):
        svc, _ = make_service(tmp_path)
        entry = svc.save_entry(base_entry())
        assert svc.delete_entry(entry['id']) is True
        assert svc.list_entries() == []
        assert svc.delete_entry(entry['id']) is False

    def test_enable_disable_preserves_settings(self, tmp_path):
        svc, _ = make_service(tmp_path)
        entry = svc.save_entry(base_entry(daily_times=['06:00', '18:00']))
        disabled = svc.set_enabled(entry['id'], False)
        assert disabled['enabled'] is False
        assert disabled['daily_times'] == ['06:00', '18:00']
        assert disabled['title'] == 'Notice'
        assert disabled['message'] == 'Hello players'
        enabled = svc.set_enabled(entry['id'], True)
        assert enabled['enabled'] is True
        assert enabled['daily_times'] == ['06:00', '18:00']


class TestFiring:
    def test_daily_fires_at_time(self, tmp_path):
        svc, admin = make_service(tmp_path)
        target = (datetime.now() + timedelta(minutes=1)).replace(second=0, microsecond=0)
        entry = svc.save_entry(base_entry(
            daily_times=[target.strftime('%H:%M')]))
        assert entry['next_run'] != ''
        fired = svc.check_and_fire(target + timedelta(seconds=5))
        assert len(fired) == 1
        assert admin.broadcasts and admin.broadcasts[0][:2] == ('Notice', 'Hello players')
        # Must not fire twice for the same occurrence.
        assert svc.check_and_fire(target + timedelta(seconds=10)) == []
        # ... but the next occurrence is armed.
        updated = svc.list_entries()[0]
        assert updated['next_run'] and updated['next_run'] != entry['next_run']

    def test_once_past_never_arms(self, tmp_path):
        svc, _ = make_service(tmp_path)
        now = datetime.now().replace(second=0, microsecond=0)
        entry = svc.save_entry(base_entry(
            mode='once', once_at=(now - timedelta(minutes=1)).isoformat()))
        assert entry['next_run'] == ''

    def test_once_fires_then_disables_keeping_settings(self, tmp_path):
        svc, admin = make_service(tmp_path)
        now = datetime.now().replace(second=0, microsecond=0)
        entry = svc.save_entry(base_entry(
            mode='once', once_at=(now + timedelta(minutes=1)).isoformat()))
        assert entry['next_run'] != ''
        fired = svc.check_and_fire(now + timedelta(minutes=2))
        assert len(fired) == 1
        updated = [e for e in svc.list_entries() if e['id'] == entry['id']][0]
        assert updated['enabled'] is False
        assert updated['title'] == 'Notice'  # settings kept for reuse
        assert updated['once_at'] != ''

    def test_disabled_entry_never_fires(self, tmp_path):
        svc, admin = make_service(tmp_path)
        target = (datetime.now() + timedelta(minutes=1)).replace(second=0, microsecond=0)
        svc.save_entry(base_entry(
            enabled=False, daily_times=[target.strftime('%H:%M')]))
        assert svc.check_and_fire(target + timedelta(seconds=5)) == []
        assert admin.broadcasts == []

    def test_missed_window_rolls_forward_without_firing(self, tmp_path):
        svc, admin = make_service(tmp_path)
        now = datetime.now().replace(second=0, microsecond=0)
        svc.save_entry(base_entry(
            daily_times=[(now - timedelta(hours=3)).strftime('%H:%M')]))
        # Force the stored next_run into the past to simulate downtime.
        entries = svc.list_entries()
        past = (now - timedelta(hours=2)).isoformat()
        entries[0]['next_run'] = past
        entries[0]['last_fired_for'] = ''
        svc._save(entries)
        assert svc.check_and_fire(now) == []
        assert admin.broadcasts == []
