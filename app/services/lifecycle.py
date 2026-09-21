"""Lifecycle service - graceful shutdown/start/restart with in-game countdown.

Notification path reuses the Experimental In-Game Broadcast
(AdminService.send_global_broadcast) - no duplicate RMQ code.

Countdown (seconds before action -> spoken label -> broadcast duration):
  15m, 10m, 5m, 3m, 2m, 1m, 30s -> duration 10
  10s -> duration 5 (so it does not overlap the final 1s notice)
  1s  -> final "now" notice, duration 10

Scheduled restarts use the same marks but say "Scheduled restart in X ...".
"""

import copy
import json
import logging
import os
import threading
import time
from datetime import datetime, timedelta

from app.services.schedule_util import (
    SCHEDULE_MODES,
    clean_days,
    clean_times,
    compute_next_run as util_compute_next_run,
    parse_hhmm,
    parse_when,
)

logger = logging.getLogger(__name__)


# (seconds_before_action, spoken label, broadcast duration seconds)
COUNTDOWN_MARKS = [
    (900, '15 minutes', 10),
    (600, '10 minutes', 10),
    (300, '5 minutes', 10),
    (180, '3 minutes', 10),
    (120, '2 minutes', 10),
    (60, '1 minute', 10),
    (30, '30 seconds', 10),
    (10, '10 seconds', 5),
]

FINAL_MARK_SECONDS = 1
FINAL_DURATION = 10
FULL_COUNTDOWN_SECONDS = 900
# A mark that became due within the last N seconds is sent immediately
# (covers thread startup delay, e.g. the first 15-minute notice at job start).
# Marks older than this were missed while the dashboard was down: skipped.
MARK_GRACE_SECONDS = 60


def _default_state_dir():
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'backups')


def default_schedule():
    return {
        'enabled': False,
        'mode': 'daily',
        'daily_times': ['05:00'],
        'weekly_days': [6],
        'weekly_times': ['05:00'],
        'monthly_days': [1],
        'monthly_time': '05:00',
        'once_at': '',
        'next_run': '',
        'last_started_for': '',
    }


class LifecycleService:
    """Owns one active countdown at a time + the restart schedule file."""

    def __init__(self, ssh_service, admin_service, settings, state_dir=None):
        self.ssh = ssh_service
        self.admin = admin_service
        self.settings = settings or {}
        self.state_dir = state_dir or _default_state_dir()
        os.makedirs(self.state_dir, exist_ok=True)
        self._lock = threading.Lock()
        self._active = None
        self._cancel_event = threading.Event()
        self._thread = None

    # ── schedule persistence ──────────────────────────────────────────

    def _schedule_path(self):
        return os.path.join(self.state_dir, 'lifecycle-schedule.json')

    def get_schedule(self):
        cfg = default_schedule()
        try:
            with open(self._schedule_path()) as f:
                stored = json.load(f) or {}
            for key in cfg:
                if key in stored:
                    cfg[key] = stored[key]
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.warning(f'Lifecycle: could not read schedule: {e}')
        return cfg

    def _save_schedule(self, cfg):
        with open(self._schedule_path(), 'w') as f:
            json.dump(cfg, f, indent=2)

    def update_schedule(self, data):
        """Validate + store schedule, recompute next_run. Returns stored cfg."""
        cfg = self.get_schedule()
        data = dict(data or {})

        if 'enabled' in data:
            cfg['enabled'] = bool(data['enabled'])
        if 'mode' in data:
            mode = str(data['mode']).strip().lower()
            if mode not in SCHEDULE_MODES:
                raise ValueError(f'Invalid mode: {mode!r}')
            cfg['mode'] = mode
        if 'daily_times' in data:
            cfg['daily_times'] = self._clean_times(data['daily_times'])
        if 'weekly_times' in data:
            cfg['weekly_times'] = self._clean_times(data['weekly_times'])
        if 'weekly_days' in data:
            cfg['weekly_days'] = self._clean_days(data['weekly_days'], 0, 6)
        if 'monthly_days' in data:
            cfg['monthly_days'] = self._clean_days(data['monthly_days'], 1, 31)
        if 'monthly_time' in data:
            parse_hhmm(data['monthly_time'])
            cfg['monthly_time'] = str(data['monthly_time']).strip()
        if 'once_at' in data:
            cfg['once_at'] = str(data['once_at'] or '').strip()
            if cfg['once_at']:
                try:
                    parse_when(cfg['once_at'])
                except ValueError:
                    raise ValueError('One-shot date/time is not valid.')

        # Mode-specific sanity so a bad form cannot arm a silent never-fire job.
        if cfg['mode'] == 'daily' and not cfg['daily_times']:
            raise ValueError('Daily mode needs at least one time (HH:MM).')
        if cfg['mode'] == 'weekly' and (not cfg['weekly_days'] or not cfg['weekly_times']):
            raise ValueError('Weekly mode needs days and at least one time.')
        if cfg['mode'] == 'monthly' and (not cfg['monthly_days'] or not cfg['monthly_time']):
            raise ValueError('Monthly mode needs days of month and a time.')
        if cfg['mode'] == 'once' and not cfg['once_at']:
            raise ValueError('One-shot mode needs a date/time.')

        cfg['next_run'] = self.compute_next_run(cfg)
        # Arming a new schedule must not replay an old occurrence marker.
        if 'next_run' in cfg and cfg.get('last_started_for') == cfg['next_run']:
            cfg['last_started_for'] = ''
        self._save_schedule(cfg)
        return cfg

    @staticmethod
    def _clean_times(values):
        return clean_times(values)

    @staticmethod
    def _clean_days(values, low, high):
        return clean_days(values, low, high)

    def compute_next_run(self, cfg=None, now=None):
        """Next action time as ISO string, or '' when nothing upcoming."""
        return util_compute_next_run(cfg or self.get_schedule(), now)

    def set_enabled(self, enabled):
        """Flip the enabled flag only; all schedule settings are preserved."""
        cfg = self.get_schedule()
        cfg['enabled'] = bool(enabled)
        cfg['next_run'] = self.compute_next_run(cfg)
        if cfg.get('last_started_for') == cfg['next_run']:
            cfg['last_started_for'] = ''
        self._save_schedule(cfg)
        return cfg

    def clear_schedule(self):
        """Disarm the schedule but keep mode/times/days settings.

        Clears the armed one-shot date, any pending next_run and the
        last-fired marker; the configured mode, times and days are kept
        so the schedule can be re-enabled without re-typing everything.
        """
        cfg = self.get_schedule()
        cfg['enabled'] = False
        cfg['once_at'] = ''
        cfg['next_run'] = ''
        cfg['last_started_for'] = ''
        self._save_schedule(cfg)
        return cfg

    # ── active countdown ──────────────────────────────────────────────

    def status(self):
        with self._lock:
            if not self._active:
                return {'active': False}
            active = copy.deepcopy(self._active)
        active['active'] = True
        active['now'] = time.time()
        return active

    def start_shutdown(self, reason='manual', context=''):
        return self._start('shutdown', time.time() + FULL_COUNTDOWN_SECONDS,
                           reason, context)

    def start_restart(self, reason='manual', context=''):
        return self._start('restart', time.time() + FULL_COUNTDOWN_SECONDS,
                           reason, context)

    def start_restart_at(self, action_at, reason='scheduled', context=''):
        return self._start('restart', float(action_at), reason, context)

    def _start(self, kind, action_at, reason, context):
        if kind not in ('shutdown', 'restart'):
            return {'success': False, 'error': f'Unknown action: {kind}'}
        with self._lock:
            if self._active:
                return {'success': False,
                        'error': f"A {self._active['kind']} countdown is already running"}
            self._cancel_event.clear()
            self._active = {
                'kind': kind,
                'reason': reason,
                'context': context or '',
                'started_at': time.time(),
                'action_at': float(action_at),
                'status': 'countdown',
                'sent': [],
                'log': [],
                'error': '',
            }
            thread = threading.Thread(target=self._run_countdown, daemon=True)
            self._thread = thread
            thread.start()
            action_iso = datetime.fromtimestamp(float(action_at)).isoformat()
            logger.info(f'Lifecycle: {kind} countdown started ({reason}) -> {action_iso}')
            return {'success': True, 'kind': kind,
                    'action_at': datetime.fromtimestamp(float(action_at)).isoformat()}

    def cancel(self):
        with self._lock:
            if not self._active:
                return {'success': False, 'error': 'No active countdown'}
            if self._active.get('status') in ('executing', 'completed', 'failed'):
                return {'success': False,
                        'error': 'Countdown already finished executing and cannot be cancelled'}
            kind = self._active['kind']
            reason = self._active.get('reason', 'manual')
            context = self._active.get('context', '')
            self._active['status'] = 'cancelling'
        self._cancel_event.set()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=30)
        with self._lock:
            self._active = None
            self._thread = None
        self._cancel_event.clear()
        logger.info(f'Lifecycle: {kind} countdown cancelled')
        # Tell players in-game so they know the shutdown/restart is off.
        # The countdown thread itself stays silent on cancel: this is the
        # single place the cancellation notice is sent (no duplicates).
        notice_ok, notice_detail = self._cancellation_notice(kind, reason, context)
        result = {'success': True, 'kind': kind,
                  'notice_sent': bool(notice_ok), 'notice': str(notice_detail)[:300]}
        if not notice_ok:
            logger.warning(f'Lifecycle: cancellation notice failed: {notice_detail}')
        return result

    def _cancellation_notice(self, kind, reason, context):
        """In-game broadcast announcing the countdown was cancelled."""
        if kind == 'shutdown':
            title = 'Server Shutdown'
            message = 'Shutdown called off - the server is staying online.'
        elif reason == 'scheduled':
            context_suffix = f' ({context})' if context else ''
            title = 'Scheduled Server Restart'
            message = (f'Scheduled restart{context_suffix} called off - '
                       f'staying online.')
        else:
            title = 'Server Restart'
            message = 'Restart called off - the server is staying online.'
        try:
            return self.admin.send_global_broadcast(title, message, 10)
        except Exception as e:
            logger.error(f'Lifecycle cancellation-notice error: {e}')
            return False, str(e)

    def _wait_until(self, target_ts):
        """Sleep until target_ts, waking early on cancel (1s slices)."""
        while True:
            if self._cancel_event.is_set():
                return False
            remaining = float(target_ts) - time.time()
            if remaining <= 0:
                return True
            self._cancel_event.wait(timeout=min(1.0, remaining))
            if self._cancel_event.is_set():
                return False

    def _run_countdown(self):
        with self._lock:
            active = self._active
            if not active:
                return
            kind = active['kind']
            reason = active.get('reason', 'manual')
            context = active.get('context', '')
            action_at = float(active['action_at'])
        scheduled = (reason == 'scheduled')

        for seconds_before, label, duration in COUNTDOWN_MARKS:
            mark_at = action_at - seconds_before
            now = time.time()
            if now >= mark_at:
                if now - mark_at <= MARK_GRACE_SECONDS:
                    # Due right now (e.g. the first notice at job start):
                    # send immediately instead of waiting.
                    pass
                else:
                    # Missed while the dashboard was down: skip the stale mark.
                    self._record_sent(label, True, 'skipped (past due)')
                    continue
            elif not self._wait_until(mark_at):
                self._finish_cancelled()
                return
            title, message = self._message_for(kind, label, duration, scheduled, context,
                                               final=False)
            ok, detail = self._broadcast(title, message, duration)
            self._record_sent(label, ok, detail)
            if not ok:
                # Keep counting down: a missed notice must not strand players
                # without the final warning, but the miss is visible in status.
                logger.warning(f'Lifecycle: broadcast failed at {label}: {detail}')

        if not self._wait_until(action_at - FINAL_MARK_SECONDS):
            self._finish_cancelled()
            return
        final_label = 'shutting down now' if kind == 'shutdown' else 'restarting now'
        if scheduled and kind == 'restart':
            final_label = 'scheduled restart starting now'
        title, message = self._message_for(kind, final_label, FINAL_DURATION,
                                           scheduled, context, final=True)
        ok, detail = self._broadcast(title, message, FINAL_DURATION)
        self._record_sent('now', ok, detail)

        # Small buffer so the final notice is visible before the stop/restart.
        time.sleep(2)
        if self._cancel_event.is_set():
            self._finish_cancelled()
            return

        self._set_status('executing')
        ok, detail = self._execute(kind)
        with self._lock:
            if self._active:
                self._active['status'] = 'completed' if ok else 'failed'
                self._active['error'] = '' if ok else detail
                self._active['completed_at'] = time.time()
                self._active['log'].append(f'action: {detail}')
            finished = copy.deepcopy(self._active)
            # Leave the finished record briefly for the UI poll, then clear.
            self._active = None
            self._thread = None
        logger.info(f"Lifecycle: {kind} finished ok={ok}: {detail}")
        return finished

    def _finish_cancelled(self):
        with self._lock:
            if self._active:
                self._active['status'] = 'cancelled'
                self._active = None
                self._thread = None
        self._cancel_event.clear()
        logger.info('Lifecycle: countdown cancelled during wait')

    def _set_status(self, status):
        with self._lock:
            if self._active:
                self._active['status'] = status

    def _record_sent(self, label, ok, detail):
        with self._lock:
            if self._active is not None:
                self._active['sent'].append(
                    {'mark': label, 'ok': bool(ok), 'detail': str(detail)[:200],
                     'at': time.time()})

    @staticmethod
    def _message_for(kind, label, duration, scheduled, context, final=False):
        context_suffix = f' ({context})' if scheduled and context else ''
        if kind == 'shutdown':
            if final:
                return ('Server Shutdown', 'Shutting down now - see you soon!')
            return ('Server Shutdown',
                    f'Heads up - the server is shutting down in {label}. '
                    f'Get somewhere safe!')
        # restart
        if final:
            if scheduled:
                return ('Scheduled Server Restart',
                        f'Scheduled restart starting now{context_suffix} - back shortly!')
            return ('Server Restart', 'Restarting now - back shortly!')
        if scheduled:
            return ('Scheduled Server Restart',
                    f'Heads up - scheduled restart in {label}{context_suffix}. '
                    f'Get somewhere safe!')
        return ('Server Restart',
                f'Heads up - server restart in {label}. Get somewhere safe!')

    def _broadcast(self, title, message, duration):
        try:
            return self.admin.send_global_broadcast(title, message, int(duration))
        except Exception as e:
            logger.error(f'Lifecycle broadcast error: {e}')
            return False, str(e)

    def _execute(self, kind):
        script = (self.settings.get('kubernetes', {}) or {}).get(
            'battlegroup_script', '/home/dune/.dune/bin/battlegroup')
        action = 'stop' if kind == 'shutdown' else 'restart'
        try:
            out, err, rc = self.ssh.run(f'{script} {action}', timeout=300)
            detail = (out or '') + (err or '')
            detail = detail.strip() or f'{action} completed'
            if rc != 0:
                return False, f'{action} failed (rc={rc}): {detail[:500]}'
            return True, detail[:1000]
        except Exception as e:
            return False, str(e)

    # ── scheduler tick (called from factory background thread) ─────────

    def describe_context(self, cfg=None):
        cfg = cfg or self.get_schedule()
        mode = cfg.get('mode', 'daily')
        if mode == 'once':
            return 'one-time'
        if mode == 'daily':
            return 'daily ' + ', '.join(cfg.get('daily_times') or [])
        if mode == 'weekly':
            day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
            days = ', '.join(day_names[d] for d in (cfg.get('weekly_days') or []))
            return f"weekly {days} {', '.join(cfg.get('weekly_times') or [])}"
        if mode == 'monthly':
            return (f"monthly day {', '.join(str(d) for d in (cfg.get('monthly_days') or []))} "
                    f"{cfg.get('monthly_time', '')}")
        return mode

    def check_and_fire(self, now=None):
        """Start the countdown when inside the 15-minute window before next_run."""
        cfg = self.get_schedule()
        if not cfg.get('enabled'):
            return None
        next_run = cfg.get('next_run') or self.compute_next_run(cfg, now)
        if not next_run:
            return None
        # Keep next_run fresh if the mode changed underneath us.
        if cfg.get('next_run') != next_run:
            cfg['next_run'] = next_run
            self._save_schedule(cfg)
        try:
            action_at = parse_when(next_run).timestamp()
        except ValueError:
            return None
        now_ts = time.time() if now is None else now.timestamp()
        if cfg.get('last_started_for') == next_run:
            return None
        with self._lock:
            if self._active:
                return None
        if now_ts < action_at - FULL_COUNTDOWN_SECONDS:
            return None
        if now_ts > action_at + 120:
            # Missed window (dashboard was down): roll forward, do not fire late.
            cfg['last_started_for'] = next_run
            cfg['next_run'] = self.compute_next_run(cfg, datetime.now())
            self._save_schedule(cfg)
            logger.warning(f'Lifecycle: missed scheduled restart for {next_run}, rolled forward')
            return None
        context = self.describe_context(cfg)
        result = self.start_restart_at(action_at, reason='scheduled', context=context)
        if result.get('success'):
            cfg['last_started_for'] = next_run
            # Advance to the occurrence *after* this one, not after now.
            anchor = datetime.fromtimestamp(action_at) + timedelta(seconds=1)
            cfg['next_run'] = self.compute_next_run(cfg, anchor)
            self._save_schedule(cfg)
            logger.info(f'Lifecycle: scheduled restart countdown started for {next_run}')
            return result
        return None
