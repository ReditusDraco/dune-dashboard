"""SSH service - remote command execution via paramiko."""

import logging
import threading
import paramiko

from app.utils.ssh_key import resolve_ssh_key
from app.utils.debug_logging import sanitize_for_log, log_ssh_command, log_ssh_result

KEEPALIVE_INTERVAL = 15

logger = logging.getLogger(__name__)


class SSHService:
    """SSH service using paramiko for connection reuse.

    Replaces the previous subprocess-based implementation.
    Benefits:
    - Connection reuse (no SSH handshake per command)
    - Better error handling
    - No dependency on system ssh binary
    - Thread-safe via lock
    """

    def __init__(self, host, user, ssh_key=None):
        self.host = host
        self.user = user
        self.ssh_key = resolve_ssh_key(ssh_key)
        self._client = None
        self._lock = threading.Lock()
        key_status = self.ssh_key if self.ssh_key else 'default ssh identity/agent'
        logger.info("SSHService initialized: %s@%s using %s", user, host, key_status)

    def _get_client(self):
        """Get or create a paramiko SSH client. Thread-safe."""
        with self._lock:
            if self._client is not None:
                transport = self._client.get_transport()
                if transport and transport.is_active():
                    return self._client
                logger.debug("SSH: closing stale client before reconnect")
                try:
                    self._client.close()
                except Exception:
                    pass
                self._client = None

            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            logger.debug("SSH host key verification policy set to AutoAddPolicy")

            connect_kwargs = {
                'hostname': self.host,
                'username': self.user,
                'timeout': 15,
                'allow_agent': True,
                'look_for_keys': True,
            }
            if self.ssh_key:
                connect_kwargs['key_filename'] = self.ssh_key

            try:
                client.connect(**connect_kwargs)
                logger.debug("SSH connection established to %s@%s", self.user, self.host)
                transport = client.get_transport()
                if transport:
                    transport.set_keepalive(KEEPALIVE_INTERVAL)
            except paramiko.AuthenticationException:
                logger.error("SSH authentication failed for %s@%s", self.user, self.host)
                raise
            except paramiko.SSHException as e:
                logger.error("SSH connection error: %s", e)
                raise
            except Exception as e:
                logger.error("Unexpected SSH error: %s", e)
                raise

            self._client = client
            return self._client

    def run(self, command, timeout=30, quiet=False):
        """Execute a remote command via SSH.

        Args:
            command: The shell command to execute.
            timeout: Maximum time in seconds to wait for the command.
            quiet: When True, expected non-zero results (e.g. probing for
                an optional resource) are logged at debug level instead of
                warning. Return values are unchanged.

        Returns:
            Tuple of (stdout, stderr, return_code).
        """
        cmd_display = command[:150] + '...' if len(command) > 150 else command
        logger.debug(f"SSH executing: {cmd_display}")

        try:
            client = self._get_client()
            stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
            stdout.channel.settimeout(timeout)
            out = stdout.read().decode('utf-8', errors='replace')
            err = stderr.read().decode('utf-8', errors='replace')
            rc = stdout.channel.recv_exit_status()

            # Debug logging for result
            logger.debug(f"SSH result: host={self.host}, user={self.user}, rc={rc}, stdout_len={len(out)}, stderr_len={len(err)}")
            if err and rc != 0:
                if quiet:
                    logger.debug(f"SSH stderr (rc={rc}): {err[:200]}")
                else:
                    logger.warning(f"SSH stderr (rc={rc}): {err[:200]}")
            if out:
                logger.debug(f"SSH stdout preview: {out[:200]}")

            if rc != 0:
                cmd_short = command[:80] + '...' if len(command) > 80 else command
                if quiet:
                    logger.debug("SSH command rc=%d (quiet): cmd=%s err=%s", rc, cmd_short, err[:100] if err else 'none')
                else:
                    logger.warning("SSH command failed (rc=%d): cmd=%s err=%s", rc, cmd_short, err[:100] if err else 'none')
            return out, err, rc
        except paramiko.SSHException as e:
            logger.error(f"SSH command error ({self.host}): {e}")
            logger.debug(f"SSH error details: type={type(e).__name__}, args={e.args}")
            self._client = None
            return '', str(e), -1
        except Exception as ex:
            logger.error(f"Unexpected SSH command error ({self.host}): {ex}")
            logger.debug(f"SSH exception details: type={type(ex).__name__}, args={ex.args}")
            self._client = None
            return '', str(ex), -1

    def write_file(self, remote_path, data, timeout=30):
        """Write text data to a remote file via base64 over stdin.

        Args:
            remote_path: Absolute path on the remote machine.
            data: String content to write.
            timeout: Max seconds to wait for command completion.

        Returns:
            Tuple of (stdout, stderr, return_code).
        """
        import base64
        encoded = base64.b64encode(data.encode('utf-8'))
        try:
            client = self._get_client()
            stdin, stdout, stderr = client.exec_command(
                f'base64 -d > {remote_path}',
                timeout=timeout
            )
            stdout.channel.settimeout(timeout)
            stdin.write(encoded)
            stdin.flush()
            stdin.channel.shutdown_write()
            out = stdout.read().decode('utf-8', errors='replace')
            err = stderr.read().decode('utf-8', errors='replace')
            rc = stdout.channel.recv_exit_status()
            if rc != 0:
                logger.warning(f"SSH write_file failed (rc={rc}, path={remote_path}): {err[:200]}")
            return out, err, rc
        except Exception as ex:
            logger.error(f"SSH write_file error ({remote_path}): {ex}")
            self._client = None
            return '', str(ex), -1

    def check_connection(self):
        """Test SSH connectivity with a simple echo command.

        Returns:
            True if the connection works, False otherwise.
        """
        try:
            out, err, rc = self.run('echo ok', timeout=10)
            if rc == 0 and 'ok' in out:
                logger.debug("SSH connection check passed")
                return True
            logger.warning("SSH connection check failed: rc=%d, out=%s", rc, out[:50])
            return False
        except Exception:
            logger.warning("SSH connection check failed with exception")
            return False

    def close(self):
        """Close the SSH connection. Safe to call multiple times."""
        with self._lock:
            if self._client:
                try:
                    self._client.close()
                    logger.debug("SSH connection closed")
                except Exception as e:
                    logger.debug("Error closing SSH connection: %s", e)
                self._client = None
