"""SSH service - remote command execution"""

import subprocess
import logging
import os

logger = logging.getLogger(__name__)


class SSHService:
    def __init__(self, host, user, ssh_key=None):
        self.host = host
        self.user = user
        self.ssh_key = self._resolve_ssh_key(ssh_key)
        key_status = self.ssh_key if self.ssh_key else 'default ssh identity/agent'
        logger.info(f"SSHService initialized: {user}@{host} using {key_status}")

    def _resolve_ssh_key(self, ssh_key):
        if ssh_key:
            key = str(ssh_key).strip("'\"")
            if os.path.exists(key):
                return key

        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        temp_dir = os.environ.get('TEMP') or os.environ.get('TMPDIR') or ('/tmp' if os.name != 'nt' else 'C:\\Temp')
        local_appdata = os.environ.get('LOCALAPPDATA', '')
        potential_paths = [
            os.path.join(temp_dir, 'dune-tunnel-key'),
            os.path.join(temp_dir, 'dune-awakening-server-sshKey'),
            os.path.join(base_dir, 'internal-scripts', 'ssh', 'sshKey'),
            os.path.join(os.path.dirname(base_dir), 'internal-scripts', 'ssh', 'sshKey'),
        ]
        if local_appdata:
            potential_paths.insert(2, os.path.join(local_appdata, 'DuneAwakeningServer', 'sshKey'))

        for path in potential_paths:
            if os.path.exists(path):
                return path
        return None

    def run(self, command, timeout=30):
        args = [
            'ssh',
            '-o', 'StrictHostKeyChecking=accept-new',
            '-o', 'ConnectTimeout=10',
            '-o', 'BatchMode=yes',
        ]
        if self.ssh_key:
            args.extend(['-i', self.ssh_key])
        args.extend([f'{self.user}@{self.host}', command])
        logger.debug(f"SSH command: {command[:100]}...")
        try:
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            if result.returncode != 0:
                logger.warning(f"SSH command failed (rc={result.returncode}): {result.stderr[:200]}")
            return result.stdout, result.stderr, result.returncode
        except FileNotFoundError:
            logger.error("SSH command not found. Is OpenSSH installed?")
            return '', 'ssh command not found', -1
        except subprocess.TimeoutExpired:
            logger.error(f"SSH command timed out after {timeout}s: {command[:100]}")
            return '', 'SSH command timed out', -1
        except Exception as ex:
            logger.error(f"SSH command error: {ex}")
            return '', str(ex), -1

    def check_connection(self):
        out, err, rc = self.run('echo ok', timeout=5)
        if rc == 0 and 'ok' in out:
            logger.debug("SSH connection check passed")
        else:
            logger.warning("SSH connection check failed")
        return rc == 0 and 'ok' in out
