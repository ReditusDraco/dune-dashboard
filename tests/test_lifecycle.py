"""Tests for graceful shutdown/restart lifecycle service."""

import time
from datetime import datetime, timedelta

import pytest

from app.services.lifecycle import (
    COUNTDOWN_MARKS,
    FINAL_DURATION,
    LifecycleService,
)


class FakeSSH:
    def __init__(self):
        self.commands = []

    def run(self, command, timeout=30, quiet=False):
        self.commands.append(command)
        return ('ok', '', 0)


class FakeAdmin:
    def __init__(self):
        self.broadcasts = []

    def send_global_broadcast(self, title, message, duration=30):
        self.broadcasts.append((title, message, duration))
        return True, 'sent'


def make_service(tmp_path):
    ssh = FakeSSH()
    admin = FakeAdmin()
    svc = LifecycleService(
        ssh, admin,
        {'kubernetes': {'battlegroup_script': '/home/dune/.dune/bin/battlegroup'}},
        state_dir=str(tmp_path),
    )
    return svc, ssh, admin


class TestCountdownTable:
    def test_marks_match_spec(self):
        """15m..30s last 10s, 10s lasts 5s, final lasts 10s."""
        assert [(s, d) for s, _, d in COUNTDOWN_MARKS] == [
            (900, 10), (600, 10), (300, 10), (180, 10),
            (120, 10), (60, 10), (30, 10), (10, 5),
        ]
        assert FINAL_DURATION == 10

    def test_manual_messages(self):
        title, msg = LifecycleService._message_for(
            'restart', '5 minutes', 10, False, '', final=False)
        assert 'restart' in title.lower()
        assert '5 minutes' in msg
        title, msg = LifecycleService._message_for(
            'shutdown', '30 seconds', 10, False, '', final=False)
        assert 'shut' in msg.lower()

    def test_scheduled_messages_mention_schedule(self):
        title, msg = LifecycleService._message_for(
            'restart', '5 minutes', 10, True, 'daily 05:00', final=False)
        assert 'Scheduled' in title
        assert 'daily 05:00' in msg


class TestActiveJob:
    def test_start_and_cancel(self, tmp_path):
        svc, _, _ = make_service(tmp_path)
        try:
            result = svc.start_restart(reason='manual')
            assert result['success']
            assert svc.status()['active'] is True
            assert svc.status()['kind'] == 'restart'
            # Second job must be rejected while one is active.
            again = svc.start_shutdown()
            assert not again['success']
        finally:
            cancelled = svc.cancel()
            assert cancelled['success']
            assert svc.status()['active'] is False

    def test_cancel_without_active(self, tmp_path):
        svc, _, _ = make_service(tmp_path)
        assert not svc.cancel()['success']

    def test_first_notice_sent_immediately(self, tmp_path):
        """The 15-minute notice is due at job start: it must be sent, not skipped."""
        svc, _, admin = make_service(tmp_path)
        try:
            assert svc.start_restart(reason='manual')['success']
            deadline = time.time() + 10
            while time.time() < deadline and not admin.broadcasts:
                time.sleep(0.2)
            assert admin.broadcasts, 'expected the 15-minute notice right after start'
            title, message, duration = admin.broadcasts[0]
            assert '15 minutes' in message and duration == 10
        finally:
            svc.cancel()

    def test_cancel_sends_ingame_notice(self, tmp_path):
        svc, _, admin = make_service(tmp_path)
        assert svc.start_shutdown(reason='manual')['success']
        deadline = time.time() + 10
        while time.time() < deadline and not admin.broadcasts:
            time.sleep(0.2)
        result = svc.cancel()
        assert result['success']
        assert result['notice_sent'] is True
        assert any('called off' in msg.lower() for _, msg, _ in admin.broadcasts)

    def test_short_countdown_runs_to_execute(self, tmp_path):
        """12s countdown: stale marks skipped, late marks sent, action executed."""
        import time as _time
        svc, ssh, admin = make_service(tmp_path)
        action_at = _time.time() + 12
        assert svc.start_restart_at(action_at, reason='manual')['success']
        deadline = _time.time() + 40
        while _time.time() < deadline and svc.status().get('active', False):
            _time.sleep(0.5)
        assert not svc.status().get('active', False)
        assert any('battlegroup' in cmd and 'restart' in cmd for cmd in ssh.commands)
        assert any('restarting now' in msg.lower() for _, msg, _ in admin.broadcasts)


class TestScheduleCalc:
    def test_daily_next_run(self, tmp_path):
        svc, _, _ = make_service(tmp_path)
        now = datetime(2026, 9, 21, 4, 0, 0)  # Monday
        cfg = {'mode': 'daily', 'daily_times': ['05:00']}
        assert svc.compute_next_run(cfg, now) == '2026-09-21T05:00:00'

    def test_daily_rolls_to_tomorrow(self, tmp_path):
        svc, _, _ = make_service(tmp_path)
        now = datetime(2026, 9, 21, 6, 0, 0)
        cfg = {'mode': 'daily', 'daily_times': ['05:00']}
        assert svc.compute_next_run(cfg, now) == '2026-09-22T05:00:00'

    def test_weekly_next_run(self, tmp_path):
        svc, _, _ = make_service(tmp_path)
        now = datetime(2026, 9, 21, 4, 0, 0)  # Monday (weekday 0)
        cfg = {'mode': 'weekly', 'weekly_days': [6], 'weekly_times': ['05:00']}
        nxt = datetime.fromisoformat(svc.compute_next_run(cfg, now))
        assert nxt.weekday() == 6
        assert (nxt.hour, nxt.minute) == (5, 0)

    def test_monthly_next_run(self, tmp_path):
        svc, _, _ = make_service(tmp_path)
        now = datetime(2026, 9, 21, 6, 0, 0)
        cfg = {'mode': 'monthly', 'monthly_days': [1], 'monthly_time': '05:00'}
        nxt = datetime.fromisoformat(svc.compute_next_run(cfg, now))
        assert (nxt.month, nxt.day, nxt.hour) == (10, 1, 5)

    def test_once_future_and_past(self, tmp_path):
        svc, _, _ = make_service(tmp_path)
        now = datetime(2026, 9, 21, 4, 0, 0)
        future = (now + timedelta(hours=2)).isoformat()
        assert svc.compute_next_run({'mode': 'once', 'once_at': future}, now) == future
        past = (now - timedelta(hours=1)).isoformat()
        assert svc.compute_next_run({'mode': 'once', 'once_at': past}, now) == ''

    def test_update_schedule_rejects_bad_mode(self, tmp_path):
        svc, _, _ = make_service(tmp_path)
        with pytest.raises(ValueError):
            svc.update_schedule({'mode': 'yearly'})

    def test_disable_preserves_settings(self, tmp_path):
        svc, _, _ = make_service(tmp_path)
        svc.update_schedule({'enabled': True, 'mode': 'daily',
                             'daily_times': ['06:00']})
        cfg = svc.set_enabled(False)
        assert cfg['enabled'] is False
        assert cfg['daily_times'] == ['06:00']
        assert cfg['mode'] == 'daily'
        cfg = svc.set_enabled(True)
        assert cfg['enabled'] is True
        assert cfg['daily_times'] == ['06:00']

    def test_clear_disarms_but_keeps_settings(self, tmp_path):
        svc, _, _ = make_service(tmp_path)
        svc.update_schedule({'enabled': True, 'mode': 'weekly',
                             'weekly_days': [1, 3],
                             'weekly_times': ['07:00']})
        cfg = svc.clear_schedule()
        assert cfg['enabled'] is False
        assert cfg['next_run'] == ''
        assert cfg['mode'] == 'weekly'
        assert cfg['weekly_days'] == [1, 3]
        assert cfg['weekly_times'] == ['07:00']

    def test_once_accepts_utc_and_local_strings(self, tmp_path):
        svc, _, _ = make_service(tmp_path)
        now = datetime.now().replace(second=0, microsecond=0)
        future_local = (now + timedelta(hours=2)).replace(microsecond=0)
        assert svc.compute_next_run(
            {'mode': 'once', 'once_at': future_local.isoformat()}, now) != ''
        future_utc = future_local.strftime('%Y-%m-%dT%H:%M:%SZ')
        assert svc.compute_next_run(
            {'mode': 'once', 'once_at': future_utc}, now) != ''


class TestSchedulerFire:
    def test_fire_inside_window_starts_countdown(self, tmp_path):
        svc, _, _ = make_service(tmp_path)
        try:
            action_at = (datetime.now() + timedelta(minutes=10)).replace(
                second=0, microsecond=0)
            svc.update_schedule({
                'enabled': True, 'mode': 'once',
                'once_at': action_at.isoformat(),
            })
            result = svc.check_and_fire()
            assert result and result['success']
            assert svc.status()['active'] is True
            assert svc.status()['reason'] == 'scheduled'
            # Second tick must not double-fire the same occurrence.
            assert svc.check_and_fire() is None
        finally:
            svc.cancel()

    def test_no_fire_outside_window(self, tmp_path):
        svc, _, _ = make_service(tmp_path)
        action_at = datetime.now() + timedelta(hours=5)
        svc.update_schedule({
            'enabled': True, 'mode': 'once',
            'once_at': action_at.replace(second=0, microsecond=0).isoformat(),
        })
        assert svc.check_and_fire() is None
        assert svc.status()['active'] is False

    def test_disabled_schedule_never_fires(self, tmp_path):
        svc, _, _ = make_service(tmp_path)
        action_at = datetime.now() + timedelta(minutes=5)
        svc.update_schedule({
            'enabled': False, 'mode': 'once',
            'once_at': action_at.replace(second=0, microsecond=0).isoformat(),
        })
        assert svc.check_and_fire() is None
