"""Backup service - backup creation, restore orchestration, backup management"""

import base64
import json
import logging
import os
import shlex
import shutil
import subprocess
import tarfile
import threading
import time
from datetime import datetime, timedelta

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


logger = logging.getLogger(__name__)


class BackupError(Exception):
    pass


class BackupService:
    BACKUP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'backups')

    def __init__(self, ssh_service, k8s_service, rmq_service, settings):
        self.ssh = ssh_service
        self.k8s = k8s_service
        self.rmq = rmq_service
        self.settings = settings
        self._restore_state = {}
        os.makedirs(self.BACKUP_DIR, exist_ok=True)

    def _backup_path(self, name):
        return os.path.join(self.BACKUP_DIR, name)

    def _timestamp(self):
        return datetime.now().strftime('%d-%m-%Y_%H%M%S')

    def _fmt_date(self, ts):
        if not ts:
            return 'unknown'
        try:
            dt = datetime.strptime(ts, '%d-%m-%Y_%H%M%S')
            return dt.strftime('%d-%m-%Y %H:%M:%S')
        except (ValueError, TypeError):
            return ts

    # ── Backup Creation ───────────────────────────────────────────────

    def create_backup(self, password=''):
        ts = self._timestamp()
        backup_name = f'backup-{ts}'
        work_dir = self._backup_path(backup_name)
        os.makedirs(work_dir, exist_ok=True)

        components = []

        try:
            # 1. Battleground backup via VM tool
            logger.info('Backup: Running battlegroup backup on VM...')
            stdout, stderr, rc = self.ssh.run(
                '/home/dune/.dune/bin/battlegroup backup', timeout=300)
            if rc != 0:
                raise BackupError(f'battlegroup backup failed: {stderr}')

            bg_path = None
            for line in stdout.splitlines():
                line = line.strip()
                if line.endswith('.tar.gz') or 'backup' in line.lower():
                    bg_path = line
            if not bg_path:
                raise BackupError('Could not locate battlegroup backup file on VM')

            bg_local = os.path.join(work_dir, 'battlegroup-backup.tar.gz')
            logger.info(f'Backup: Downloading {bg_path}...')
            self._download_file(bg_path, bg_local)
            components.append({
                'name': 'battlegroup-backup.tar.gz',
                'source': 'VM battlegroup tool',
                'size': os.path.getsize(bg_local),
            })

            # 2. K8s manifests
            logger.info('Backup: Exporting K8s resources...')
            k8s_dir = os.path.join(work_dir, 'k8s-manifests')
            os.makedirs(k8s_dir, exist_ok=True)
            ns = self.k8s.namespace
            resources = [('battlegroup', 'battlegroup-crd.yaml'),
                         ('deploy', 'deployments.yaml'),
                         ('sts', 'statefulsets.yaml'),
                         ('svc', 'services.yaml'),
                         ('cm', 'configmaps.yaml'),
                         ('secret', 'secrets.yaml')]
            for res, fname in resources:
                stdout, stderr, rc = self.ssh.run(
                    f'sudo kubectl get {res} -n {ns} -o yaml', timeout=60)
                if rc == 0 and stdout.strip():
                    with open(os.path.join(k8s_dir, fname), 'w') as f:
                        f.write(stdout)
                    components.append({
                        'name': f'k8s-manifests/{fname}',
                        'source': f'kubectl get {res}',
                        'size': len(stdout),
                    })

            # 3. RMQ definitions
            logger.info('Backup: Exporting RMQ definitions...')
            rmq_dir = os.path.join(work_dir, 'rmq')
            os.makedirs(rmq_dir, exist_ok=True)
            for label, fetch_fn in [('admin-overview', self.rmq.overview),
                                    ('game-overview', self.rmq.game_overview)]:
                try:
                    data = fetch_fn()
                    if data:
                        with open(os.path.join(rmq_dir, f'{label}.json'), 'w') as f:
                            json.dump(data, f, indent=2)
                        components.append({
                            'name': f'rmq/{label}.json',
                            'source': f'RMQ {label}',
                            'size': len(json.dumps(data)),
                        })
                except Exception as e:
                    logger.warning(f'Backup: Could not export RMQ {label}: {e}')

            # 4. Dashboard database schema (bans, audit_log, chat_history, player_ips, player_actions, settings)
            logger.info('Backup: Dumping dashboard schema...')
            db_dump = None
            ns = self.k8s.namespace
            dbpod_cmd = (
                f'dbpod=$(sudo kubectl get pods -n {ns} -l role=db -o name | head -1) && '
                f'sudo kubectl exec -n {ns} $dbpod -- pg_dump -U postgres -d dune '
                f'--schema=dashboard --no-owner --no-acl 2>/dev/null'
            )
            stdout, stderr, rc = self.ssh.run(dbpod_cmd, timeout=120)
            if rc == 0 and stdout.strip():
                db_dump = os.path.join(work_dir, 'dashboard-db.sql')
                with open(db_dump, 'w') as f:
                    f.write(stdout)
                components.append({
                    'name': 'dashboard-db.sql',
                    'source': 'pg_dump dashboard schema',
                    'size': len(stdout),
                })
                logger.info(f'Backup: Dashboard schema dumped ({len(stdout)} bytes)')
            else:
                logger.warning(f'Backup: Could not dump dashboard schema: {stderr}')

            # 5. Dashboard settings.yaml
            settings_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'settings.yaml')
            if os.path.exists(settings_path):
                shutil.copy2(settings_path, os.path.join(work_dir, 'settings.yaml'))
                components.append({
                    'name': 'settings.yaml',
                    'source': 'local',
                    'size': os.path.getsize(settings_path),
                })

            # 6. Write manifest
            manifest = {
                'name': backup_name,
                'created': ts,
                'dashboard_version': 'v0.5.0',
                'components': components,
            }
            with open(os.path.join(work_dir, 'metadata.json'), 'w') as f:
                json.dump(manifest, f, indent=2)

            # 7. Package into tarball
            archive_path = self._backup_path(f'{backup_name}.tar.gz')
            with tarfile.open(archive_path, 'w:gz') as tar:
                tar.add(work_dir, arcname=backup_name)
            shutil.rmtree(work_dir)

            # 8. Encrypt with password if provided
            encrypted = False
            if password:
                logger.info('Backup: Encrypting with password...')
                self._encrypt_file(archive_path, password)
                encrypted = True

            # Write sidecar metadata so list/preview work without password
            meta_path = self._backup_path(f'{backup_name}.meta')
            with open(meta_path, 'w') as f:
                json.dump({'name': backup_name, 'created': ts, 'components': components}, f)

            total_size = os.path.getsize(archive_path)
            logger.info(f'Backup created: {archive_path} ({total_size} bytes)')
            return {
                'success': True,
                'backup': backup_name,
                'path': archive_path,
                'size': total_size,
                'components': components,
                'encrypted': encrypted,
            }

        except Exception as e:
            if os.path.exists(work_dir):
                shutil.rmtree(work_dir)
            logger.error(f'Backup failed: {e}')
            return {'success': False, 'error': str(e)}

    def _download_file(self, remote_path, local_path):
        stdout, stderr, rc = self.ssh.run(
            f'cat {shlex.quote(remote_path)} | base64', timeout=120)
        if rc != 0:
            raise BackupError(f'Failed to read remote file: {stderr}')
        raw = base64.b64decode(stdout)
        with open(local_path, 'wb') as f:
            f.write(raw)

    def _encrypt_file(self, filepath, password):
        salt = os.urandom(16)
        kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=600000)
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        f = Fernet(key)
        with open(filepath, 'rb') as fh:
            data = fh.read()
        encrypted = salt + f.encrypt(data)
        with open(filepath, 'wb') as fh:
            fh.write(encrypted)

    def _decrypt_file(self, filepath, password):
        with open(filepath, 'rb') as fh:
            data = fh.read()
        salt = data[:16]
        ciphertext = data[16:]
        kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=600000)
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        f = Fernet(key)
        return f.decrypt(ciphertext)

    def _backup_is_encrypted(self, name):
        path = self._backup_path(f'{name}.tar.gz')
        if not os.path.exists(path):
            return False
        try:
            with tarfile.open(path, 'r:gz') as tar:
                tar.getmembers()
            return False
        except Exception:
            return True

    def _schedule_path(self):
        return os.path.join(self.BACKUP_DIR, 'schedule.json')

    def load_schedule(self):
        path = self._schedule_path()
        if not os.path.exists(path):
            return {'enabled': False, 'mode': 'interval', 'interval_minutes': 1440,
                    'schedule_days': [], 'schedule_times': ['05:00'],
                    'keep': 5, 'password': '', 'next_run': ''}
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            return {'enabled': False, 'mode': 'interval', 'interval_minutes': 1440,
                    'schedule_days': [], 'schedule_times': ['05:00'],
                    'keep': 5, 'password': '', 'next_run': ''}

    def save_schedule(self, cfg):
        with open(self._schedule_path(), 'w') as f:
            json.dump(cfg, f, indent=2)

    def get_schedule(self):
        return self.load_schedule()

    def _next_run_from_schedule(self, cfg):
        now = datetime.now()
        days_set = set(cfg.get('schedule_days', []))
        times = cfg.get('schedule_times', [])
        if not days_set or not times:
            return ''
        best = None
        for offset in range(8):
            base = datetime(now.year, now.month, now.day) + timedelta(days=offset)
            wd = base.weekday()
            if wd not in days_set:
                continue
            for t in times:
                try:
                    h, m = (int(x) for x in t.split(':'))
                except Exception:
                    continue
                candidate = base.replace(hour=h, minute=m, second=0, microsecond=0)
                if candidate <= now:
                    continue
                if best is None or candidate < best:
                    best = candidate
        return best.isoformat() if best else ''

    def _next_run_from_interval(self, cfg):
        return datetime.fromtimestamp(time.time() + cfg['interval_minutes'] * 60).isoformat()

    def update_schedule(self, data):
        cfg = self.load_schedule()
        cfg['enabled'] = bool(data.get('enabled', cfg['enabled']))
        if 'mode' in data:
            cfg['mode'] = data['mode']
        if 'interval_minutes' in data:
            cfg['interval_minutes'] = int(data['interval_minutes'])
        if 'schedule_days' in data:
            cfg['schedule_days'] = data['schedule_days']
        if 'schedule_times' in data:
            cfg['schedule_times'] = data['schedule_times']
        cfg['keep'] = int(data.get('keep', cfg['keep']))
        if 'password' in data:
            cfg['password'] = data['password']
        if cfg.get('mode') == 'schedule':
            cfg['next_run'] = self._next_run_from_schedule(cfg)
        else:
            cfg['next_run'] = self._next_run_from_interval(cfg)
        self.save_schedule(cfg)
        return cfg

    def run_scheduled_backup(self):
        cfg = self.load_schedule()
        if not cfg.get('enabled'):
            return {'success': False, 'error': 'Scheduled backups are disabled'}
        pw = cfg.get('password', '') or None
        result = self.create_backup(password=pw or '')
        if result.get('success'):
            keep = cfg.get('keep', 5)
            if keep > 0:
                self._enforce_retention(keep)
            if cfg.get('mode') == 'schedule':
                cfg['next_run'] = self._next_run_from_schedule(cfg)
            else:
                cfg['next_run'] = self._next_run_from_interval(cfg)
            self.save_schedule(cfg)
        return result

    def _enforce_retention(self, keep):
        backups = []
        for fname in sorted(os.listdir(self.BACKUP_DIR), reverse=True):
            if fname.endswith('.tar.gz'):
                backups.append(fname.replace('.tar.gz', ''))
        backups.sort(reverse=True)
        for old in backups[keep:]:
            self.delete_backup(old)

    # ── Backup Listing ────────────────────────────────────────────────

    def list_backups(self):
        backups = []
        if not os.path.isdir(self.BACKUP_DIR):
            return backups
        for fname in sorted(os.listdir(self.BACKUP_DIR), reverse=True):
            if fname.endswith('.tar.gz'):
                fpath = os.path.join(self.BACKUP_DIR, fname)
                info = self.get_backup_info(fpath)
                name = fname.replace('.tar.gz', '')
                backups.append({
                    'name': name,
                    'path': fpath,
                    'size': os.path.getsize(fpath),
                    'created': self._fmt_date(info.get('created', '')),
                    'components': info.get('components', []),
                    'password_protected': self._backup_is_encrypted(name),
                })
        return backups

    def get_backup_info(self, path):
        if path.endswith('.tar.gz'):
            meta_path = path.replace('.tar.gz', '.meta')
            if os.path.exists(meta_path):
                try:
                    with open(meta_path) as f:
                        return json.load(f)
                except Exception as e:
                    logger.warning(f'Could not read sidecar meta from {meta_path}: {e}')
            try:
                with tarfile.open(path, 'r:gz') as tar:
                    for m in tar.getmembers():
                        if m.name.endswith('metadata.json'):
                            with tar.extractfile(m) as f:
                                return json.loads(f.read().decode('utf-8'))
            except Exception as e:
                logger.warning(f'Could not read metadata from {path}: {e}')
        return {}

    def delete_backup(self, name):
        path = self._backup_path(f'{name}.tar.gz')
        if os.path.exists(path):
            os.remove(path)
        meta_path = self._backup_path(f'{name}.meta')
        if os.path.exists(meta_path):
            os.remove(meta_path)
        return True

    def verify_backup(self, name, password=''):
        path = self._backup_path(f'{name}.tar.gz')
        if not os.path.exists(path):
            return {'success': False, 'error': 'Backup not found'}
        is_encrypted = self._backup_is_encrypted(name)
        meta = self.get_backup_info(path)
        if is_encrypted and not password:
            return {
                'success': True,
                'valid': True,
                'encrypted': True,
                'files': 0,
                'size': os.path.getsize(path),
                'components': meta.get('components', []),
                'note': 'Enter password to verify contents',
            }
        try:
            if is_encrypted:
                decrypted = self._decrypt_file(path, password)
                import tempfile
                tmp = tempfile.NamedTemporaryFile(suffix='.tar.gz', delete=False)
                tmp.write(decrypted)
                tmp_path = tmp.name
                tmp.close()
                try:
                    with tarfile.open(tmp_path, 'r:gz') as tar:
                        members = tar.getmembers()
                finally:
                    os.unlink(tmp_path)
            else:
                with tarfile.open(path, 'r:gz') as tar:
                    members = tar.getmembers()
            return {
                'success': True,
                'valid': True,
                'encrypted': is_encrypted,
                'files': len(members),
                'size': os.path.getsize(path),
                'components': meta.get('components', []),
            }
        except Exception as e:
            return {'success': False, 'valid': False, 'error': str(e)}

    # ── Restore Orchestration ─────────────────────────────────────────

    def restore_preview(self, name):
        path = self._backup_path(f'{name}.tar.gz')
        if not os.path.exists(path):
            return {'success': False, 'error': 'Backup not found'}
        info = self.get_backup_info(path)
        comps = info.get('components', [])
        return {
            'success': True,
            'backup': name,
            'created': self._fmt_date(info.get('created', '')),
            'components': comps,
            'has_db': any('battlegroup-backup' in c.get('name', '') for c in comps),
            'has_dash_db': any('dashboard-db.sql' in c.get('name', '') for c in comps),
            'has_k8s': any('k8s-manifests' in c.get('name', '') for c in comps),
            'has_settings': any('settings.yaml' in c.get('name', '') for c in comps),
            'has_rmq': any(c.get('name', '').startswith('rmq/') for c in comps),
            'password_protected': self._backup_is_encrypted(name),
        }

    def test_connection(self):
        ssh_user = self.settings.get('server', {}).get('user', 'dune')
        ssh_key = self.settings.get('server', {}).get('ssh_key', '')
        vm_ip = self.settings.get('server', {}).get('host', '')
        if not ssh_key:
            return {'success': False, 'error': 'No SSH key configured in dashboard settings'}
        if not vm_ip:
            return {'success': False, 'error': 'No server host configured in dashboard settings'}
        try:
            result = subprocess.run(
                ['ssh', '-o', 'StrictHostKeyChecking=no', '-o', 'ConnectTimeout=10',
                 '-o', 'LogLevel=QUIET', '-i', ssh_key,
                 f'{ssh_user}@{vm_ip}',
                 'hostname && sudo kubectl get nodes --no-headers 2>/dev/null | head -1'],
                capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                return {'success': False, 'error': result.stderr.strip() or 'Connection failed'}
            lines = [l for l in result.stdout.splitlines() if l.strip()]
            return {
                'success': True,
                'hostname': lines[0] if lines else 'unknown',
                'k8s_ok': len(lines) > 1,
            }
        except subprocess.TimeoutExpired:
            return {'success': False, 'error': 'Connection timed out'}
        except FileNotFoundError:
            return {'success': False, 'error': 'SSH client not found on dashboard machine'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def start_restore(self, backup_name, options):
        ssh_user = self.settings.get('server', {}).get('user', 'dune')
        ssh_key = self.settings.get('server', {}).get('ssh_key', '')
        vm_ip = self.settings.get('server', {}).get('host', '')
        if not ssh_key:
            return {'success': False, 'error': 'No SSH key configured in dashboard settings'}
        if not vm_ip:
            return {'success': False, 'error': 'No server host configured in dashboard settings'}
        state_key = backup_name
        self._restore_state[state_key] = {
            'status': 'preparing',
            'progress': 0,
            'steps': [],
            'current_step': 0,
            'backup_name': backup_name,
            'vm_ip': vm_ip,
            'ssh_user': ssh_user,
            'ssh_key_path': ssh_key,
            'options': options,
            'errors': [],
            'completed_steps': [],
            'started': time.time(),
        }
        t = threading.Thread(target=self._run_restore, args=(state_key,), daemon=True)
        t.start()
        return {'success': True, 'restore_id': state_key}

    def get_restore_status(self, restore_id):
        state = self._restore_state.get(restore_id)
        if not state:
            return {'success': False, 'error': 'Restore not found'}
        return {
            'success': True,
            'status': state['status'],
            'progress': state['progress'],
            'steps': state['steps'],
            'current_step': state['current_step'],
            'completed_steps': state['completed_steps'],
            'errors': state['errors'],
        }

    def _run_restore(self, state_key):
        state = self._restore_state[state_key]
        opts = state['options']
        vm_ip = state['vm_ip']
        ssh_user = state['ssh_user']
        ssh_key = state['ssh_key_path']
        backup_name = state['backup_name']
        ns = self.k8s.namespace

        def ssh_cmd(cmd, timeout=120):
            return subprocess.run(
                ['ssh', '-o', 'StrictHostKeyChecking=no', '-o', 'LogLevel=QUIET',
                 '-i', ssh_key, f'{ssh_user}@{vm_ip}', cmd],
                capture_output=True, text=True, timeout=timeout)

        def add_step(label):
            state['steps'].append(label)

        def complete_step(label, success, detail=''):
            state['completed_steps'].append({
                'label': label, 'success': success, 'detail': detail,
            })
            if not success:
                state['errors'].append(detail or f'{label} failed')
            state['current_step'] += 1
            total = max(len(state['steps']), 1)
            state['progress'] = min(int(state['current_step'] / total * 100), 99)

        archive_path = self._backup_path(f'{backup_name}.tar.gz')
        pw = opts.get('password', '')

        # Step 0: Decrypt backup if password provided
        if self._backup_is_encrypted(backup_name):
            add_step('Decrypting backup archive')
            try:
                if not pw:
                    raise BackupError('Backup is encrypted but no password provided')
                decrypted = self._decrypt_file(archive_path, pw)
                import tempfile
                tmp = tempfile.NamedTemporaryFile(suffix='.tar.gz', delete=False)
                tmp.write(decrypted)
                upload_path = tmp.name
                tmp.close()
                complete_step('Decrypting backup archive', True)
            except Exception as e:
                complete_step('Decrypting backup archive', False, str(e))
                state['status'] = 'failed'
                return
        else:
            upload_path = archive_path

        # Step 1: Upload backup archive to new VM
        add_step('Uploading backup archive to new VM')
        try:
            with open(upload_path, 'rb') as f:
                b64_data = base64.b64encode(f.read()).decode()
            r = ssh_cmd(f'echo {shlex.quote(b64_data)} | base64 -d > /tmp/restore-{backup_name}.tar.gz', timeout=300)
            if r.returncode != 0:
                raise BackupError(f'Upload failed: {r.stderr}')
            complete_step('Uploading backup archive to new VM', True)
        except Exception as e:
            complete_step('Uploading backup archive to new VM', False, str(e))
            state['status'] = 'failed'
            return
        finally:
            if upload_path != archive_path:
                try:
                    os.unlink(upload_path)
                except Exception:
                    pass

        # Step 2: Extract archive on VM
        add_step('Extracting backup archive on VM')
        try:
            r = ssh_cmd(
                f'mkdir -p /tmp/restore-{backup_name} && '
                f'cd /tmp/restore-{backup_name} && '
                f'tar xzf /tmp/restore-{backup_name}.tar.gz --strip-components=1',
                timeout=60)
            if r.returncode != 0:
                raise BackupError(f'Extract failed: {r.stderr}')
            complete_step('Extracting backup archive on VM', True)
        except Exception as e:
            complete_step('Extracting backup archive on VM', False, str(e))

        # Step 3: Restore K8s secrets and configmaps
        if opts.get('restore_k8s', True):
            add_step('Restoring K8s secrets and configmaps')
            try:
                d = f'/tmp/restore-{backup_name}'
                for fname in ['secrets.yaml', 'configmaps.yaml']:
                    r = ssh_cmd(
                        f'sudo kubectl apply -n {ns} -f {d}/k8s-manifests/{fname} 2>/dev/null || true',
                        timeout=30)
                    if r.returncode != 0:
                        logger.warning(f'Could not apply {fname}: {r.stderr}')
                complete_step('Restoring K8s secrets and configmaps', True)
            except Exception as e:
                complete_step('Restoring K8s secrets and configmaps', False, str(e))

        # Step 4: Restore battlegroup CRD and wait for pods
        if opts.get('restore_battlegroup', True):
            add_step('Applying battlegroup CRD')
            try:
                d = f'/tmp/restore-{backup_name}'
                r = ssh_cmd(
                    f'sudo kubectl apply -f {d}/k8s-manifests/battlegroup-crd.yaml', timeout=60)
                if r.returncode != 0:
                    raise BackupError(r.stderr)
                complete_step('Applying battlegroup CRD', True)
            except Exception as e:
                complete_step('Applying battlegroup CRD', False, str(e))

            add_step('Waiting for pods to provision (up to 5 min)')
            try:
                for i in range(30):
                    r = ssh_cmd(
                        f'sudo kubectl get pods -n {ns} --no-headers 2>/dev/null | '
                        f'grep -c -E "(dbdepl|mq-.*-sts)" || true', timeout=15)
                    if r.returncode == 0 and r.stdout.strip():
                        count = int(r.stdout.strip())
                        if count >= 2:
                            complete_step('Waiting for pods to provision', True)
                            break
                    time.sleep(10)
                else:
                    complete_step('Waiting for pods to provision', False, 'Timed out')
            except Exception as e:
                complete_step('Waiting for pods to provision', False, str(e))

            add_step('Waiting for DB pod to be Running')
            try:
                for i in range(30):
                    r = ssh_cmd(
                        f'sudo kubectl get pods -n {ns} -l role=db --no-headers '
                        f'-o custom-columns=STATUS:.status.phase 2>/dev/null | head -1',
                        timeout=15)
                    if 'Running' in r.stdout:
                        complete_step('Waiting for DB pod to be Running', True)
                        break
                    time.sleep(10)
                else:
                    complete_step('Waiting for DB pod to be Running', False, 'DB pod did not start')
            except Exception as e:
                complete_step('Waiting for DB pod to be Running', False, str(e))

        # Step 5: Import game database
        if opts.get('restore_db', True):
            add_step('Importing game database')
            try:
                r = ssh_cmd(
                    f'cd /tmp/restore-{backup_name} && '
                    f'/home/dune/.dune/bin/battlegroup import',
                    timeout=600)
                if r.returncode != 0:
                    raise BackupError(r.stderr)
                complete_step('Importing game database', True)
            except Exception as e:
                complete_step('Importing game database', False, str(e))

        # Step 6: Restore dashboard database schema
        if opts.get('restore_dash_db', True):
            add_step('Restoring dashboard schema (bans, chat, audit, settings)')
            try:
                dash_sql_path = self._backup_path(f'{backup_name}.tar.gz')
                dash_sql_content = None
                with tarfile.open(dash_sql_path, 'r:gz') as tar:
                    for m in tar.getmembers():
                        if m.name.endswith('dashboard-db.sql'):
                            with tar.extractfile(m) as f:
                                dash_sql_content = f.read()
                            break
                if dash_sql_content:
                    b64_sql = base64.b64encode(dash_sql_content).decode()
                    r = ssh_cmd(
                        f'dbpod=$(sudo kubectl get pods -n {ns} -l role=db -o name | head -1) && '
                        f'echo {shlex.quote(b64_sql)} | base64 -d | '
                        f'sudo kubectl exec -n {ns} -i $dbpod -- psql -U postgres -d dune',
                        timeout=120)
                    if r.returncode != 0:
                        logger.warning(f'Dashboard DB restore warning: {r.stderr}')
                    complete_step('Restoring dashboard schema (bans, chat, audit, settings)', True)
                else:
                    complete_step('Restoring dashboard schema (bans, chat, audit, settings)', True)
            except Exception as e:
                complete_step('Restoring dashboard schema (bans, chat, audit, settings)', False, str(e))

        if opts.get('restore_db', True) or opts.get('restore_dash_db', True):
            add_step('Re-applying dashboard schema ownership')
            try:
                sql = ("ALTER SCHEMA dashboard OWNER TO dune;"
                       "GRANT ALL PRIVILEGES ON SCHEMA dashboard TO dune;"
                       "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA dashboard TO dune;"
                       "GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA dashboard TO dune;")
                r = ssh_cmd(
                    f'dbpod=$(sudo kubectl get pods -n {ns} -l role=db -o name | head -1) && '
                    f'sudo kubectl exec -n {ns} $dbpod -- psql -U postgres -d dune '
                    f'-c {shlex.quote(sql)}', timeout=30)
                if r.returncode != 0:
                    logger.warning(f'Dashboard schema ownership warning: {r.stderr}')
                complete_step('Re-applying dashboard schema ownership', True)
            except Exception as e:
                complete_step('Re-applying dashboard schema ownership', False, str(e))

        # Step 7: Apply ping fix if new IP provided
        if opts.get('restore_ping_fix', True) and opts.get('new_ip'):
            add_step('Applying HOST_DATACENTER ping fix')
            try:
                r = ssh_cmd('hostname', timeout=10)
                hostname = r.stdout.strip()
                new_ip = opts['new_ip']
                for deploy_suffix in ['bgd-deploy', 'sgw-deploy', 'tr-deploy']:
                    full_name = f'{ns}-{deploy_suffix}'
                    ssh_cmd(
                        f'sudo kubectl set env deploy/{full_name} -n {ns} '
                        f'HOST_DATACENTER_ID={hostname} '
                        f'HOST_DATACENTER_IP_ADDRESS={new_ip}',
                        timeout=30)
                complete_step('Applying HOST_DATACENTER ping fix', True)
            except Exception as e:
                complete_step('Applying HOST_DATACENTER ping fix', False, str(e))

        # Step 8: Re-create RMQ dashboard_admin user
        if opts.get('restore_rmq', True):
            add_step('Re-creating RMQ dashboard_admin user on both instances')
            try:
                pw = self.settings.get('rabbitmq', {}).get('password', '')
                for side in ['admin', 'game']:
                    pod_r = ssh_cmd(
                        f'sudo kubectl get pods -n {ns} -o name | grep mq-{side}-sts | head -1',
                        timeout=15)
                    if pod_r.returncode != 0 or not pod_r.stdout.strip():
                        logger.warning(f'No mq-{side} pod found')
                        continue
                    pod = pod_r.stdout.strip()
                    for cmd in [
                        f'rabbitmqctl add_user dashboard_admin {pw}',
                        f'rabbitmqctl set_user_tags dashboard_admin administrator',
                        f'rabbitmqctl set_permissions -p / dashboard_admin ".*" ".*" ".*"',
                        f'rabbitmqctl eval '
                        f'\'application:set_env(rabbit, auth_backends, '
                        f'[rabbit_auth_backend_cache, rabbit_auth_backend_internal]).\'',
                    ]:
                        ssh_cmd(f'sudo kubectl exec -n {ns} {pod} -- {cmd}', timeout=15)
                complete_step('Re-creating RMQ dashboard_admin user on both instances', True)
            except Exception as e:
                complete_step('Re-creating RMQ dashboard_admin user on both instances', False, str(e))

        # Step 9: Restore settings.yaml locally
        if opts.get('restore_settings', True):
            add_step('Restoring dashboard settings.yaml locally')
            try:
                d = f'/tmp/restore-{backup_name}'
                r = ssh_cmd(f'cat {d}/settings.yaml', timeout=15)
                if r.returncode == 0 and r.stdout.strip():
                    local_settings = os.path.join(
                        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                        'settings.yaml')
                    with open(local_settings, 'w') as f:
                        f.write(r.stdout)
                    complete_step('Restoring dashboard settings.yaml locally', True)
                else:
                    complete_step('Restoring dashboard settings.yaml locally', True)
            except Exception as e:
                complete_step('Restoring dashboard settings.yaml locally', False, str(e))

        # Step 10: Cleanup
        add_step('Cleaning up temporary files on VM')
        try:
            ssh_cmd(f'rm -rf /tmp/restore-{backup_name} /tmp/restore-{backup_name}.tar.gz',
                    timeout=15)
            complete_step('Cleaning up temporary files on VM', True)
        except Exception as e:
            complete_step('Cleaning up temporary files on VM', False, str(e))

        state['status'] = 'completed' if not state['errors'] else 'completed_with_errors'
        state['progress'] = 100
        state['completed_at'] = time.time()
