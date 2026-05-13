"""SSH service - remote command execution"""

import subprocess
import logging
import os

logger = logging.getLogger(__name__)


class SSHService:
    def __init__(self, host, user, ssh_key=None):
        self.host = host
        self.user = user
        self.ssh_key = ssh_key
        logger.info(f"SSHService initialized: {user}@{host}")

    def run(self, command, timeout=30):
        args = [
            'ssh',
            '-i', self.ssh_key,
            '-o', 'StrictHostKeyChecking=accept-new',
            '-o', 'ConnectTimeout=10',
            '-o', 'BatchMode=yes',
            f'{self.user}@{self.host}',
            command
        ]
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
