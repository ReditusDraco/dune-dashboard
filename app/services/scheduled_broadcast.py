"""Scheduled custom notifications - one-off/recurring in-game broadcasts.

Shares schedule validation + next-run computation with the restart
lifecycle scheduler (app/services/schedule_util.py). Delivery reuses the
confirmed In-Game Broadcast path (AdminService.send_global_broadcast).
"""

import json
import logging
import os
import threading
import uuid
from datetime import datetime, timedelta

from app.services.schedule_util import (
    SCHEDULE_MODES,
    clean_days,
    clean_times,
    compute_next_run,
    parse_hhmm,
    parse_when,
)

logger = logging.getLogger(__name__)

MIN_DURATION = 5
MAX_DURATION = 300
DEFAULT_DURATION = 30
# A missed occurrence older than this is rolled forward, never fired late.
MISSED_WINDOW_SECONDS = 3600


def _default_state_dir():
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'backups')


def default_entry():
    return {
        'id': uuid.uuid4().hex[:8],
        'enabled': True,
        'title': '',
        'message': '',
        'duration': DEFAULT_DURATION,
        'mode': 'daily',
        'daily_times': ['12:00'],
        'weekly_days': [6],
        'weekly_times': ['12:00'],
        'monthly_days': [1],
        'monthly_time': '12:00',
        'once_at': '',
        'next_run': '',
        'last_fired_for': '',
    }


class ScheduledBroadcastService:
    """Stores + fires scheduled custom notification entries."""

    def __init__(self, admin_service, state_dir=None):
        self.admin = admin_service
        self.state_dir = state_dir or _default_state_dir()
        os.makedirs(self.state_dir, exist_ok=True)
        self._lock = threading.Lock()

    # ── persistence ───────────────────────────────────────────────────

    def _path(self):
        return os.path.join(self.state_dir, 'broadcast-schedule.json')

    def list_entries(self):
        try:
            with open(self._path()) as f:
                stored = json.load(f) or {}
            entries = stored.get('entries') or []
            return [e for e in entries if isinstance(e, dict)]
        except FileNotFoundError:
            return []
        except Exception as e:
            logger.warning(f'ScheduledBroadcast: could not read schedule: {e}')
            return []

    def _save(self, entries):
        with open(self._path(), 'w') as f:
            json.dump({'entries': entries}, f, indent=2)

    def _find(self, entries, entry_id):
        for entry in entries:
            if entry.get('id') == entry_id:
                return entry
        return None

    # ── CRUD ──────────────────────────────────────────────────────────

    def save_entry(self, data):
        """Create or update an entry; validates, recomputes next_run."""
        data = dict(data or {})
        with self._lock:
            entries = self.list_entries()
            entry_id = str(data.get('id') or '').strip()
            if entry_id:
                entry = self._find(entries, entry_id)
                if entry is None:
                    raise ValueError(f'Unknown scheduled notification: {entry_id!r}')
            else:
                entry = default_entry()
                entries.append(entry)

            if 'enabled' in data:
                entry['enabled'] = bool(data['enabled'])
            for field in ('title', 'message'):
                if field in data:
                    entry[field] = str(data[field] or '').strip()
            if 'duration' in data:
                try:
                    duration = int(data['duration'])
                except (TypeError, ValueError):
                    raise ValueError('Duration must be a number of seconds.')
                entry['duration'] = max(MIN_DURATION, min(MAX_DURATION, duration))
            if 'mode' in data:
                mode = str(data['mode']).strip().lower()
                if mode not in SCHEDULE_MODES:
                    raise ValueError(f'Invalid mode: {mode!r}')
                entry['mode'] = mode
            if 'daily_times' in data:
                entry['daily_times'] = clean_times(data['daily_times'])
            if 'weekly_times' in data:
                entry['weekly_times'] = clean_times(data['weekly_times'])
            if 'weekly_days' in data:
                entry['weekly_days'] = clean_days(data['weekly_days'], 0, 6)
            if 'monthly_days' in data:
                entry['monthly_days'] = clean_days(data['monthly_days'], 1, 31)
            if 'monthly_time' in data:
                parse_hhmm(data['monthly_time'])
                entry['monthly_time'] = str(data['monthly_time']).strip()
            if 'once_at' in data:
                entry['once_at'] = str(data['once_at'] or '').strip()
                if entry['once_at']:
                    try:
                        parse_when(entry['once_at'])
                    except ValueError:
                        raise ValueError('One-shot date/time is not valid.')

            if not entry['title'] or not entry['message']:
                raise ValueError('Title and message are required.')
            mode = entry['mode']
            if mode == 'daily' and not entry['daily_times']:
                raise ValueError('Daily mode needs at least one time (HH:MM).')
            if mode == 'weekly' and (not entry['weekly_days'] or not entry['weekly_times']):
                raise ValueError('Weekly mode needs days and at least one time.')
            if mode == 'monthly' and (not entry['monthly_days'] or not entry['monthly_time']):
                raise ValueError('Monthly mode needs days of month and a time.')
            if mode == 'once' and not entry['once_at']:
                raise ValueError('One-shot mode needs a date/time.')

            entry['next_run'] = compute_next_run(entry)
            if entry.get('last_fired_for') == entry['next_run']:
                entry['last_fired_for'] = ''
            self._save(entries)
            logger.info(f"ScheduledBroadcast: saved entry {entry['id']} "
                        f"enabled={entry['enabled']} next={entry['next_run']}")
            return dict(entry)

    def delete_entry(self, entry_id):
        with self._lock:
            entries = self.list_entries()
            kept = [e for e in entries if e.get('id') != entry_id]
            if len(kept) == len(entries):
                return False
            self._save(kept)
            logger.info(f'ScheduledBroadcast: deleted entry {entry_id}')
            return True

    def set_enabled(self, entry_id, enabled):
        """Flip enabled only; message + schedule settings are preserved."""
        with self._lock:
            entries = self.list_entries()
            entry = self._find(entries, entry_id)
            if entry is None:
                raise ValueError(f'Unknown scheduled notification: {entry_id!r}')
            entry['enabled'] = bool(enabled)
            entry['next_run'] = compute_next_run(entry)
            if entry.get('last_fired_for') == entry['next_run']:
                entry['last_fired_for'] = ''
            self._save(entries)
            return dict(entry)

    # ── scheduler tick (called from factory background thread) ─────────

    def check_and_fire(self, now=None):
        """Send every due entry once. Returns list of fired entry summaries."""
        now_dt = now or datetime.now()
        now_ts = now_dt.timestamp()
        fired = []
        with self._lock:
            entries = self.list_entries()
            changed = False
            for entry in entries:
                if not entry.get('enabled'):
                    continue
                next_run = entry.get('next_run') or compute_next_run(entry, now_dt)
                if not next_run:
                    continue
                if entry.get('next_run') != next_run:
                    entry['next_run'] = next_run
                    changed = True
                if entry.get('last_fired_for') == next_run:
                    continue
                try:
                    action_ts = parse_when(next_run).timestamp()
                except ValueError:
                    continue
                if now_ts < action_ts:
                    continue
                if now_ts > action_ts + MISSED_WINDOW_SECONDS:
                    # Dashboard was down: roll forward, never fire late.
                    entry['last_fired_for'] = next_run
                    if entry['mode'] == 'once':
                        entry['enabled'] = False
                        entry['next_run'] = ''
                    else:
                        entry['next_run'] = compute_next_run(entry, now_dt)
                    changed = True
                    logger.warning(
                        f"ScheduledBroadcast: missed {entry['id']} for {next_run}, rolled forward")
                    continue
                ok, detail = self._send(entry)
                entry['last_fired_for'] = next_run
                if entry['mode'] == 'once':
                    # One-shot fires exactly once, settings are kept for reuse.
                    entry['enabled'] = False
                    entry['next_run'] = ''
                else:
                    anchor = datetime.fromtimestamp(action_ts) + timedelta(seconds=1)
                    entry['next_run'] = compute_next_run(entry, anchor)
                changed = True
                fired.append({'id': entry['id'], 'success': bool(ok),
                              'detail': str(detail)[:300]})
                logger.info(f"ScheduledBroadcast: fired {entry['id']} "
                            f"for {next_run} ok={ok}")
            if changed:
                self._save(entries)
        return fired

    def _send(self, entry):
        try:
            return self.admin.send_global_broadcast(
                entry['title'], entry['message'], int(entry.get('duration') or 30))
        except Exception as e:
            logger.error(f'ScheduledBroadcast send error: {e}')
            return False, str(e)