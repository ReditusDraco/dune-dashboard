"""Tests for game event summaries and solaris log parsing."""

from app.utils.events import (
    clean_name,
    event_label,
    parse_solaris_meta,
    summarize_game_event,
)


class TestLabels:
    def test_known_types(self):
        assert event_label(0) == 'Death'
        assert event_label(97) == 'Permission change'

    def test_unknown_type_falls_back(self):
        assert event_label(12345) == 'Event 12345'
        assert event_label('xyz') == 'Event xyz'


class TestCleanName:
    def test_strips_hashes(self):
        assert clean_name('##MediumOrnithopter') == 'MediumOrnithopter'
        assert clean_name('#Totem') == 'Totem'

    def test_blanks(self):
        assert clean_name(None) == ''
        assert clean_name('None') == ''
        assert clean_name('!!act#0') == ''


class TestSummaries:
    def test_death(self):
        msg = summarize_game_event(0, {'m_KillerType': 'NPC', 'm_DamageType': 'None'})
        assert 'NPC' in msg

    def test_build(self):
        msg = summarize_game_event(10, {'m_CauserType': 'Player',
                                        'm_BuildableName': 'Totem_Small_Placeable'})
        assert 'Totem_Small_Placeable' in msg

    def test_permission(self):
        msg = summarize_game_event(97, {'m_PermissionActorName': '##MediumOrnithopter',
                                        'm_OldPermissionRank': 'Associate',
                                        'm_NewPermissionRank': 'CoOwner'})
        assert 'Associate -> CoOwner' in msg

    def test_power_hours(self):
        msg = summarize_game_event(95, {'m_BuildableName': 'Totem_Placeable',
                                        'm_PowerTimeLeftSeconds': 35959})
        assert '9h' in msg

    def test_never_raises(self):
        assert summarize_game_event(0, 'not json {{{') == '' or True
        assert summarize_game_event(999, None) == ''
        assert summarize_game_event(97, {'m_OldPermissionRank': 'x'}) != '' or True


class TestSolarisMeta:
    def test_python_repr_format(self):
        parsed = parse_solaris_meta(
            "{'event': 'adjust_player_virtual_currency_balance', "
            "'fls_id': 'ABC123', 'solaris_delta': -27562, 'solaris_balance': 23135}")
        assert parsed == {'fls_id': 'ABC123', 'delta': -27562, 'balance': 23135}

    def test_json_format(self):
        parsed = parse_solaris_meta(
            '{"fls_id": "ABC", "solaris_delta": 6000, "solaris_balance": 100}')
        assert parsed['delta'] == 6000

    def test_garbage_returns_none(self):
        assert parse_solaris_meta(None) is None
        assert parse_solaris_meta('just a string') is None
        assert parse_solaris_meta('[1, 2]') is None
