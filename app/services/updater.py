"""Update service - channel-aware self updates from GitHub Releases.

Version source of truth: the committed VERSION file (e.g. ``0.7.5`` for
stable, ``0.7.5-experimental`` for experimental). The channel is the suffix.

Rules (all enforced server-side):
- experimental installs track ``vX.Y.Z-experimental`` releases (matched
  case-insensitively); stable installs track exact ``vX.Y.Z`` releases.
- An update target must be newer than OR equal to the running version
  (equal = reinstall/repair). Older versions are always refused.
- Checking is automatic (background thread); installing is always manual.
"""

import os
import re
import sys
import json
import time
import shutil
import logging
import threading
import urllib.request
import zipfile
import tempfile
import subprocess
from datetime import datetime

logger = logging.getLogger(__name__)

GITHUB_REPO = "ReditusDraco/dune-dashboard"
GITHUB_API = f"https://api.github.com/repos/{GITHUB_REPO}"

# Paths that should NEVER be overwritten during update
PROTECTED_PATHS = {
    'settings.yaml',
    'logs',
    'instance',
    'internal-scripts',
    '.git',
    '.env',
}

_VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:-([A-Za-z0-9]+))?$")
_STABLE_RE = re.compile(r"^v\d+\.\d+\.\d+$", re.IGNORECASE)
_EXPERIMENTAL_RE = re.compile(r"^v\d+\.\d+\.\d+-experimental$", re.IGNORECASE)


def parse_version(value):
    """Parse 'v0.7.5-experimental' -> ((0, 7, 5), 'experimental').

    Returns None for anything that is not a plain dotted version with an
    optional single suffix. Never raises.
    """
    if not value:
        return None
    match = _VERSION_RE.fullmatch(str(value).strip())
    if not match:
        return None
    numbers = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
    return numbers, (match.group(4) or '')


def channel_of(version):
    """'experimental' for *-experimental versions, else 'stable'."""
    parsed = parse_version(version)
    if parsed and parsed[1].lower() == 'experimental':
        return 'experimental'
    return 'stable'


def compare_versions(a, b):
    """Compare numeric parts only. Returns -1, 0 or 1. Unknowns sort last."""
    pa, pb = parse_version(a), parse_version(b)
    if pa is None and pb is None:
        return 0
    if pa is None:
        return -1
    if pb is None:
        return 1
    if pa[0] < pb[0]:
        return -1
    if pa[0] > pb[0]:
        return 1
    return 0


def release_matches_channel(tag, channel):
    """True when a release tag belongs to the channel (case-insensitive)."""
    tag = str(tag or '')
    if channel == 'experimental':
        return bool(_EXPERIMENTAL_RE.fullmatch(tag))
    return bool(_STABLE_RE.fullmatch(tag))


class UpdateService:
    def __init__(self, project_root):
        self.project_root = project_root
        self._current_version = self._read_local_version()
        self._channel = channel_of(self._current_version)
        self._latest = None  # {'version', 'tag', 'notes', 'zipball_url'}
        self._other_latest = None
        self._last_check = 0
        self._check_interval = 1800  # 30 minutes
        self._update_in_progress = False
        self._update_status = None
        self._preview = None  # {'version', 'notes'} - in-memory test helper

    # ── version / channel ────────────────────────────────────────────

    def _read_local_version(self):
        try:
            with open(os.path.join(self.project_root, 'VERSION')) as f:
                version = f.read().strip().replace('\r', '').replace('\n', '')
                if parse_version(version):
                    return version
        except Exception:
            pass
        return '0.0.0'

    @property
    def current_version(self):
        return self._current_version

    @property
    def channel(self):
        return self._channel

    # ── silence state (backups/update-silence.json) ──────────────────

    def _silence_path(self):
        return os.path.join(self.project_root, 'backups', 'update-silence.json')

    def get_silence(self):
        try:
            with open(self._silence_path()) as f:
                stored = json.load(f) or {}
            return {
                'silenced_versions': list(stored.get('silenced_versions', [])),
                'silence_all': bool(stored.get('silence_all', False)),
            }
        except (FileNotFoundError, ValueError, OSError):
            return {'silenced_versions': [], 'silence_all': False}

    def _save_silence(self, state):
        try:
            os.makedirs(os.path.dirname(self._silence_path()), exist_ok=True)
            with open(self._silence_path(), 'w') as f:
                json.dump({
                    'silenced_versions': list(state.get('silenced_versions', [])),
                    'silence_all': bool(state.get('silence_all', False)),
                }, f, indent=2)
        except OSError as e:
            logger.warning(f'Update silence: could not save: {e}')
        return self.get_silence()

    def silence_version(self, version):
        state = self.get_silence()
        version = str(version or '').strip()
        if version and version not in state['silenced_versions']:
            state['silenced_versions'].append(version)
        return self._save_silence(state)

    def unsilence_version(self, version):
        state = self.get_silence()
        version = str(version or '').strip()
        if version in state['silenced_versions']:
            state['silenced_versions'].remove(version)
        return self._save_silence(state)

    def set_silence_all(self, enabled):
        state = self.get_silence()
        state['silence_all'] = bool(enabled)
        return self._save_silence(state)

    def clear_silence(self):
        return self._save_silence({'silenced_versions': [], 'silence_all': False})

    # ── preview helper (banner testing only, never installable) ─────

    def set_preview(self, version, notes=''):
        version = str(version or '').strip()
        if not parse_version(version):
            raise ValueError('Preview version is not a valid version number.')
        self._preview = {'version': version, 'notes': str(notes or '')}
        return dict(self._preview)

    def clear_preview(self):
        self._preview = None

    # ── background checker ───────────────────────────────────────────

    def start_checker(self):
        """Start background update checker thread."""
        thread = threading.Thread(target=self._checker_loop, daemon=True)
        thread.start()
        logger.info("Update checker started")

    def _checker_loop(self):
        """Periodically check for updates."""
        while True:
            try:
                self.check_for_updates()
            except Exception as e:
                logger.debug(f"Update check failed: {e}")
            time.sleep(self._check_interval)

    def _fetch_releases(self):
        """All releases from GitHub (follows pagination)."""
        releases = []
        url = f"{GITHUB_API}/releases?per_page=100"
        while url:
            req = urllib.request.Request(url)
            req.add_header('Accept', 'application/vnd.github.v3+json')
            req.add_header('User-Agent', 'DuneDashboard-UpdateChecker')
            with urllib.request.urlopen(req, timeout=15) as resp:
                releases.extend(json.loads(resp.read().decode()))
                url = self._next_page(resp.headers.get('Link', ''))
        return releases

    @staticmethod
    def _next_page(link_header):
        for part in (link_header or '').split(','):
            segments = part.split(';')
            if len(segments) == 2 and 'rel="next"' in segments[1]:
                return segments[0].strip().strip('<>')
        return ''

    @staticmethod
    def _pick_latest(releases, channel):
        """Newest release for a channel. Returns entry dict or None."""
        best = None
        for release in releases:
            if not isinstance(release, dict) or release.get('draft'):
                continue
            tag = str(release.get('tag_name') or '')
            if not release_matches_channel(tag, channel):
                continue
            parsed = parse_version(tag)
            if parsed is None:
                continue
            version = tag[1:] if tag.lower().startswith('v') else tag
            entry = {
                'version': version,
                'tag': tag,
                'notes': str(release.get('body') or ''),
                'zipball_url': str(release.get('zipball_url') or ''),
            }
            if best is None or compare_versions(entry['version'], best['version']) > 0:
                best = entry
        return best

    def check_for_updates(self):
        """Refresh latest-version info for our channel (and the other one)."""
        try:
            releases = self._fetch_releases()
            other = 'stable' if self._channel == 'experimental' else 'experimental'
            self._latest = self._pick_latest(releases, self._channel)
            self._other_latest = self._pick_latest(releases, other)
            self._last_check = time.time()
            if self._latest:
                logger.info(
                    f"Update check ({self._channel}): latest={self._latest['version']} "
                    f"current={self._current_version}")
            else:
                logger.info(f"Update check ({self._channel}): no releases found")
        except Exception as e:
            logger.debug(f"Update check error: {e}")

    def _is_newer_or_same(self, version):
        return compare_versions(version, self._current_version) >= 0

    def status(self):
        """Full status payload for the banner/API."""
        silence = self.get_silence()
        latest = dict(self._latest) if self._latest else None
        available = bool(
            latest and self._is_newer_or_same(latest['version'])
            and compare_versions(latest['version'], self._current_version) != 0)
        other = dict(self._other_latest) if self._other_latest else None
        show_other = bool(
            other and other['version'] != (latest['version'] if latest else None)
            and self._is_newer_or_same(other['version']))
        return {
            'current_version': self._current_version,
            'channel': self._channel,
            'available': available,
            'latest': latest,
            'other_channel': {
                'channel': 'stable' if self._channel == 'experimental' else 'experimental',
                'latest': other,
                'available': show_other,
            },
            'preview': dict(self._preview) if self._preview else None,
            'silenced_versions': silence['silenced_versions'],
            'silence_all': silence['silence_all'],
            'update_in_progress': self._update_in_progress,
            'update_status': self._update_status,
            'last_check': self._last_check,
        }

    @property
    def update_available(self):
        status = self.status()
        return status['available'] or status['preview'] is not None

    @property
    def update_status(self):
        return self._update_status

    # ── apply ────────────────────────────────────────────────────────

    def _find_release(self, version):
        """Find a known release matching a version string exactly."""
        for entry in (self._latest, self._other_latest):
            if entry and entry['version'] == version:
                return entry
        return None

    def apply_update(self, version=None):
        """Download and apply a release. Version must be known and not older."""
        if self._update_in_progress:
            return False, "Update already in progress"

        target = str(version or '').strip()
        if not target:
            # Default: newest for our own channel.
            if not self._latest:
                return False, "No release found for this channel"
            target = self._latest['version']

        if parse_version(target) is None:
            return False, "Invalid version number"
        if not self._is_newer_or_same(target):
            return False, (
                f"Refusing downgrade: {target} is older than "
                f"the running {self._current_version}")
        entry = self._find_release(target)
        if entry is None:
            # Refresh once in case a release landed since the last check.
            self.check_for_updates()
            entry = self._find_release(target)
        if entry is None:
            return False, f"Unknown version: {target} (not a published release)"
        if not entry.get('zipball_url'):
            return False, "Release has no downloadable archive"

        self._update_in_progress = True
        self._update_status = f"Downloading {target}..."

        try:
            req = urllib.request.Request(entry['zipball_url'])
            req.add_header('Accept', 'application/vnd.github.v3+json')
            req.add_header('User-Agent', 'DuneDashboard-UpdateChecker')
            with urllib.request.urlopen(req, timeout=120) as resp:
                zip_data = resp.read()
            if not zip_data.startswith(b'PK\x03\x04'):
                raise ValueError("Downloaded file is not a zip archive")

            self._update_status = "Extracting update..."
            temp_dir = tempfile.mkdtemp(prefix='dune_update_')
            zip_path = os.path.join(temp_dir, 'update.zip')
            with open(zip_path, 'wb') as f:
                f.write(zip_data)

            with zipfile.ZipFile(zip_path, 'r') as zf:
                # Reject archives with absolute paths or parent escapes.
                for member in zf.namelist():
                    if member.startswith('/') or '..' in member.split('/'):
                        raise ValueError(f"Unsafe archive entry: {member!r}")
                zf.extractall(temp_dir)

            extracted = [d for d in os.listdir(temp_dir)
                         if os.path.isdir(os.path.join(temp_dir, d))
                         and d != '__MACOSX']
            if not extracted:
                return False, "Failed to extract update"

            source_dir = os.path.join(temp_dir, extracted[0])

            backup_dir = os.path.join(
                self.project_root, 'backups',
                f'update_{datetime.now().strftime("%Y%m%d_%H%M%S")}')
            os.makedirs(backup_dir, exist_ok=True)

            self._update_status = "Applying files..."
            files_updated = 0
            for root, dirs, files in os.walk(source_dir):
                rel_root = os.path.relpath(root, source_dir)
                target_root = os.path.join(self.project_root, rel_root)

                if any(p in PROTECTED_PATHS for p in rel_root.split(os.sep)):
                    continue

                os.makedirs(target_root, exist_ok=True)

                for file in files:
                    if file.startswith('.'):
                        continue
                    src_file = os.path.join(root, file)
                    dst_file = os.path.join(target_root, file)

                    if file in PROTECTED_PATHS:
                        continue

                    if os.path.exists(dst_file):
                        backup_file = os.path.join(backup_dir, rel_root, file)
                        os.makedirs(os.path.dirname(backup_file), exist_ok=True)
                        shutil.copy2(dst_file, backup_file)

                    shutil.copy2(src_file, dst_file)
                    files_updated += 1

            shutil.rmtree(temp_dir, ignore_errors=True)

            with open(os.path.join(self.project_root, 'VERSION'), 'w') as f:
                f.write(target + '\n')

            self._current_version = target
            self._channel = channel_of(target)
            self._update_status = f"Update applied! {files_updated} files updated. Restarting..."

            self._restart_app()

            return True, f"Update applied successfully ({files_updated} files)"

        except Exception as e:
            logger.error(f"Update failed: {e}")
            self._update_status = f"Update failed: {e}"
            self._update_in_progress = False
            return False, str(e)

    def _restart_app(self):
        """Restart the dashboard via the launcher script to preserve SSH/DB tunnels."""
        try:
            if os.name == 'nt':
                launcher = os.path.join(self.project_root, 'launcher.ps1')
                if os.path.exists(launcher):
                    subprocess.Popen(
                        ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', launcher],
                        creationflags=subprocess.CREATE_NEW_CONSOLE
                    )
                else:
                    subprocess.Popen([sys.executable, os.path.join(self.project_root, 'run.py')], creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:
                launcher = os.path.join(self.project_root, 'start.sh')
                if os.path.exists(launcher):
                    subprocess.Popen(['bash', launcher], start_new_session=True)
                else:
                    subprocess.Popen([sys.executable, os.path.join(self.project_root, 'run.py')], start_new_session=True)
            os._exit(0)
        except Exception as e:
            logger.error(f"Restart failed: {e}")
