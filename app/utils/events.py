"""Human-readable summaries for game event log entries.

Event types arrive as opaque numeric codes; the meaning lives in the
``custom_data`` JSONB payload. Labels below were decoded from live data.
Unknown codes fall back to "Event <n>" so new types never break the page.
"""

import ast
import json
import logging

logger = logging.getLogger(__name__)

GAME_EVENT_LABELS = {
    0: 'Death',
    10: 'Build placed',
    13: 'Shield change',
    19: 'Totem switch',
    20: 'Vehicle damage',
    23: 'Vehicle event',
    95: 'Totem power',
    97: 'Permission change',
    99: 'Vehicle stored',
}


def event_label(event_type):
    """Short label for a numeric event type."""
    try:
        return GAME_EVENT_LABELS.get(int(event_type), f'Event {event_type}')
    except (TypeError, ValueError):
        return f'Event {event_type}'


def clean_name(value):
    """Strip game ## prefixes; None/empty -> ''."""
    if not value or value in ('None', '!!act#0'):
        return ''
    text = str(value)
    while text.startswith('#'):
        text = text[1:]
    return text


def _payload(custom_data):
    """custom_data as a dict (psycopg2 returns JSONB as dict already)."""
    if not custom_data:
        return {}
    if isinstance(custom_data, dict):
        return custom_data
    try:
        parsed = json.loads(custom_data)
        return parsed if isinstance(parsed, dict) else {}
    except (ValueError, TypeError):
        return {}


def summarize_game_event(event_type, custom_data):
    """One-line human summary of a game event. Never raises."""
    try:
        data = _payload(custom_data)
        get = lambda *keys: next(
            (clean_name(data.get(k)) for k in keys if clean_name(data.get(k))), '')

        if event_type == 0:  # Death
            killer = get('m_KillerType') or 'Unknown'
            damage = get('m_DamageType')
            detail = f'killed by {killer}'
            if damage and damage != 'None':
                detail += f' ({damage})'
            return detail
        if event_type == 10:  # Build placed
            who = get('m_CauserType')
            what = get('m_BuildableName')
            return f'{who or "Someone"} placed {what or "a building"}'.strip()
        if event_type == 13:  # Shield change
            state = get('m_TotemShieldState')
            what = get('m_BuildableName')
            return f'Totem shield {state or "changed"}{f" ({what})" if what else ""}'
        if event_type == 19:  # Totem switch
            state = get('m_StateChange')
            what = get('m_BuildableName')
            return f'Totem {what or "totem"} turned {state or "unknown state"}'
        if event_type == 20:  # Vehicle damage
            vehicle = get('m_VehicleModelName', 'm_BuildableName')
            causer = get('m_CauserType')
            return f'{vehicle or "Vehicle"} damaged by {causer or "unknown"}'
        if event_type == 23:  # Vehicle event
            vehicle = get('m_VehicleModelName', 'm_BuildableName')
            return f'{vehicle or "Vehicle"} event'
        if event_type == 95:  # Totem power
            secs = data.get('m_PowerTimeLeftSeconds')
            what = get('m_BuildableName')
            if isinstance(secs, (int, float)):
                hours = int(secs) // 3600
                return f'{what or "Totem"} power: ~{hours}h left'
            return f'{what or "Totem"} power check'
        if event_type == 97:  # Permission change
            what = get('m_PermissionActorName', 'm_DefaultActorTypeName')
            old = get('m_OldPermissionRank')
            new = get('m_NewPermissionRank')
            return f'{what or "Something"}: {old or "?"} -> {new or "?"}'
        if event_type == 99:  # Vehicle stored
            vehicle = get('m_BuildableName')
            stored = data.get('m_bStored')
            action = 'stored' if stored else 'retrieved'
            return f'{vehicle or "Vehicle"} {action}'
        return ''
    except Exception as e:
        logger.debug(f'Event summary failed for type {event_type}: {e}')
        return ''


def parse_solaris_meta(meta):
    """Parse event_log meta into {fls_id, delta, balance}. Handles both
    JSON and the Python-repr format the game writes. Returns None if useless."""
    if not meta:
        return None
    data = None
    if isinstance(meta, dict):
        data = meta
    else:
        text = str(meta).strip()
        try:
            data = json.loads(text)
        except (ValueError, TypeError):
            try:
                data = ast.literal_eval(text)
            except (ValueError, TypeError, SyntaxError, MemoryError):
                return None
    if not isinstance(data, dict):
        return None
    try:
        return {
            'fls_id': str(data.get('fls_id') or ''),
            'delta': int(data.get('solaris_delta', 0)),
            'balance': int(data.get('solaris_balance', 0)),
        }
    except (TypeError, ValueError):
        return None
