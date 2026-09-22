"""Tests for channel-aware self updates (no network - releases are stubbed)."""

import pytest

from app.services.updater import (
    UpdateService,
    channel_of,
    compare_versions,
    parse_version,
    release_matches_channel,
)


def make_releases():
    return [
        {'tag_name': 'v0.7.5-experimental', 'body': 'exp notes',
         'zipball_url': 'https://example.com/exp.zip'},
        {'tag_name': 'v0.7.4', 'body': 'stable notes',
         'zipball_url': 'https://example.com/stable.zip'},
        {'tag_name': 'v0.7.3-Experimental', 'body': 'old exp',
         'zipball_url': 'https://example.com/old.zip'},
        {'tag_name': 'v0.7.3', 'draft': True, 'body': 'draft',
         'zipball_url': 'https://example.com/draft.zip'},
        {'tag_name': 'not-a-version', 'body': 'x',
         'zipball_url': 'https://example.com/x.zip'},
    ]


def make_service(tmp_path, version='0.7.4-experimental'):
    (tmp_path / 'VERSION').write_text(version + '\n')
    return UpdateService(str(tmp_path))


class TestVersions:
    def test_parse(self):
        assert parse_version('v0.7.5-experimental') == ((0, 7, 5), 'experimental')
        assert parse_version('0.7.3') == ((0, 7, 3), '')
        assert parse_version('  v1.2.3  ') == ((1, 2, 3), '')
        assert parse_version('garbage') is None
        assert parse_version('') is None
        assert parse_version(None) is None
        assert parse_version('1.2') is None

    def test_channel(self):
        assert channel_of('0.7.5-experimental') == 'experimental'
        assert channel_of('0.7.5-Experimental') == 'experimental'
        assert channel_of('0.7.3') == 'stable'
        assert channel_of('garbage') == 'stable'

    def test_compare(self):
        assert compare_versions('0.7.5-experimental', '0.7.4-experimental') > 0
        assert compare_versions('0.7.4', '0.7.4') == 0
        assert compare_versions('0.7.3', '0.7.4') < 0
        assert compare_versions('0.7.10', '0.7.9') > 0
        assert compare_versions('garbage', '0.7.4') < 0

    def test_channel_match(self):
        assert release_matches_channel('v0.7.5-experimental', 'experimental')
        assert release_matches_channel('v0.7.3-Experimental', 'experimental')
        assert not release_matches_channel('v0.7.4', 'experimental')
        assert release_matches_channel('v0.7.4', 'stable')
        assert not release_matches_channel('v0.7.5-experimental', 'stable')


class TestPickLatest:
    def test_experimental_picks_max_experimental(self):
        best = UpdateService._pick_latest(make_releases(), 'experimental')
        assert best['version'] == '0.7.5-experimental'

    def test_stable_ignores_drafts(self):
        best = UpdateService._pick_latest(make_releases(), 'stable')
        assert best['version'] == '0.7.4'

    def test_nothing_matching(self):
        assert UpdateService._pick_latest([], 'stable') is None


class TestApplyRules:
    def test_refuses_downgrade_without_network(self, tmp_path):
        svc = make_service(tmp_path, '0.7.5-experimental')
        svc._latest = {'version': '0.7.6-experimental', 'tag': 'v0.7.6-experimental',
                       'notes': '', 'zipball_url': 'https://example.com/x.zip'}
        ok, msg = svc.apply_update('0.7.4-experimental')
        assert ok is False
        assert 'owngrade' in msg or 'older' in msg
        assert svc._update_in_progress is False

    def test_refuses_unknown_version(self, tmp_path, monkeypatch):
        svc = make_service(tmp_path, '0.7.5-experimental')
        monkeypatch.setattr(svc, '_fetch_releases', lambda: [])
        ok, msg = svc.apply_update('9.9.9')
        assert ok is False
        assert 'Unknown version' in msg

    def test_refuses_garbage(self, tmp_path):
        svc = make_service(tmp_path, '0.7.5-experimental')
        ok, msg = svc.apply_update('not-a-version!!!')
        assert ok is False

    def test_same_version_allowed_to_proceed(self, tmp_path, monkeypatch):
        # Same version = reinstall. Must get past validation (it will then
        # fail downloading from example.com, which proves the rule passed).
        svc = make_service(tmp_path, '0.7.5-experimental')
        svc._latest = {'version': '0.7.5-experimental', 'tag': 'v0.7.5-experimental',
                       'notes': '', 'zipball_url': 'https://example.com/x.zip'}
        ok, msg = svc.apply_update('0.7.5-experimental')
        assert ok is False
        assert 'owngrade' not in msg and 'Unknown version' not in msg


class TestPreview:
    def test_set_clear_and_reject_garbage(self, tmp_path):
        svc = make_service(tmp_path)
        preview = svc.set_preview('0.7.6-experimental', 'notes here')
        assert preview == {'version': '0.7.6-experimental', 'notes': 'notes here'}
        assert svc.status()['preview'] == preview
        svc.clear_preview()
        assert svc.status()['preview'] is None
        with pytest.raises(ValueError):
            svc.set_preview('garbage!!!')


class TestSilence:
    def test_round_trip(self, tmp_path):
        svc = make_service(tmp_path)
        state = svc.silence_version('0.7.6-experimental')
        assert state['silenced_versions'] == ['0.7.6-experimental']
        assert svc.get_silence() == state
        state = svc.unsilence_version('0.7.6-experimental')
        assert state['silenced_versions'] == []
        state = svc.set_silence_all(True)
        assert state['silence_all'] is True
        state = svc.clear_silence()
        assert state == {'silenced_versions': [], 'silence_all': False}

    def test_status_reports_available_and_silence(self, tmp_path):
        svc = make_service(tmp_path, '0.7.5-experimental')
        svc._latest = {'version': '0.7.6-experimental', 'tag': 'v0.7.6-experimental',
                       'notes': 'n', 'zipball_url': 'u'}
        svc._other_latest = None
        status = svc.status()
        assert status['available'] is True
        assert status['latest']['version'] == '0.7.6-experimental'
        assert status['current_version'] == '0.7.5-experimental'
        assert status['channel'] == 'experimental'


class TestLocalVersion:
    def test_reads_version_file(self, tmp_path):
        svc = make_service(tmp_path, '0.7.3')
        assert svc.current_version == '0.7.3'
        assert svc.channel == 'stable'

    def test_missing_file_falls_back(self, tmp_path):
        svc = UpdateService(str(tmp_path))
        assert svc.current_version == '0.0.0'
