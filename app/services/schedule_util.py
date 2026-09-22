"""Shared schedule helpers: validation + next-run computation.

Used by the restart lifecycle scheduler and the custom-notification
scheduler. All times are server-local naive datetimes. ISO strings from
`<input type="datetime-local">` ("YYYY-MM-DDTHH:MM") and UTC ("...Z")
strings are both accepted.
"""

import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

SCHEDULE_MODES = ('once', 'daily', 'weekly', 'monthly')


def parse_hhmm(value):
    """Parse 'HH:MM' -> (hour, minute), raising ValueError when invalid."""
    parts = str(value or '').strip().split(':')
    if len(parts) != 2:
        raise ValueError(f'Invalid time: {value!r} (expected HH:MM)')
    hour, minute = int(parts[0]), int(parts[1])
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(f'Invalid time: {value!r}')
    return hour, minute


def clean_times(values):
    """Validate a list of 'HH:MM' strings; returns sorted unique list."""
    if isinstance(values, str):
        values = [values]
    cleaned = []
    for value in values or []:
        value = str(value).strip()
        if not value:
            continue
        parse_hhmm(value)
        if value not in cleaned:
            cleaned.append(value)
    return sorted(cleaned)


def clean_days(values, low, high):
    """Validate a list of integer days in [low, high]; sorted unique list."""
    if isinstance(values, (int, str)):
        values = [values]
    cleaned = []
    for value in values or []:
        try:
            day = int(value)
        except (TypeError, ValueError):
            raise ValueError(f'Invalid day: {value!r}')
        if not (low <= day <= high):
            raise ValueError(f'Day out of range: {value!r}')
        if day not in cleaned:
            cleaned.append(day)
    return sorted(cleaned)


def parse_when(raw):
    """Parse an ISO datetime string -> naive server-local datetime."""
    dt = datetime.fromisoformat(str(raw).strip())
    if dt.tzinfo is not None:
        dt = dt.astimezone().replace(tzinfo=None)
    return dt


def next_once(cfg, now):
    raw = str(cfg.get('once_at') or '').strip()
    if not raw:
        return ''
    candidate = parse_when(raw)
    return candidate.isoformat() if candidate > now else ''


def next_daily_weekly(now, days, times):
    cleaned_times = []
    for value in times or []:
        try:
            cleaned_times.append(parse_hhmm(value))
        except ValueError:
            continue
    if not cleaned_times:
        return ''
    best = None
    for offset in range(8):
        base = datetime(now.year, now.month, now.day) + timedelta(days=offset)
        if days is not None and base.weekday() not in days:
            continue
        for hour, minute in cleaned_times:
            candidate = base.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if candidate <= now:
                continue
            if best is None or candidate < best:
                best = candidate
    return best.isoformat() if best else ''


def next_monthly(now, cfg, time_key='monthly_time', days_key='monthly_days'):
    try:
        hour, minute = parse_hhmm(cfg.get(time_key, '05:00'))
    except ValueError:
        return ''
    month_days = set(cfg.get(days_key) or [])
    if not month_days:
        return ''
    # Scan day-by-day (covers varying month lengths without dateutil).
    base = datetime(now.year, now.month, now.day)
    for offset in range(1, 370):
        day = base + timedelta(days=offset)
        if day.day not in month_days:
            continue
        candidate = day.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate > now:
            return candidate.isoformat()
    return ''


def compute_next_run(cfg, now=None):
    """Next action time as ISO string, or '' when nothing upcoming."""
    cfg = cfg or {}
    now = now or datetime.now()
    mode = cfg.get('mode', 'daily')
    try:
        if mode == 'once':
            return next_once(cfg, now)
        if mode == 'daily':
            return next_daily_weekly(now, days=None, times=cfg.get('daily_times') or [])
        if mode == 'weekly':
            return next_daily_weekly(now, days=set(cfg.get('weekly_days') or []),
                                     times=cfg.get('weekly_times') or [])
        if mode == 'monthly':
            return next_monthly(now, cfg)
    except Exception as e:
        logger.warning(f'Schedule: next-run calc failed: {e}')
    return ''
