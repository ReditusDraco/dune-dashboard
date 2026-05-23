"""SSH service — remote command execution via paramiko."""

import logging
import threading
import paramiko

logger = logging.getLogger(__name__)


class SSHService:
    def __init__(self, host, user, ssh_key=None):
        self.host = host
        self.user = user
        self.ssh_key = ssh_key
        self._client = None
        self._lock = threading.Lock()
        key_status = self.ssh_key if self.ssh_key else "default ssh identity/agent"
        logger.info("SSHService initialized: %s@%s using %s", user, host, key_status)

    def _get_client(self):
        with self._lock:
            if self._client is not None:
                transport = self._client.get_transport()
                if transport and transport.is_active():
                    return self._client
                self._client = None

            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            connect_kwargs = {
                "hostname": self.host,
                "username": self.user,
                "timeout": 15,
                "allow_agent": True,
                "look_for_keys": True,
            }
            if self.ssh_key:
                connect_kwargs["key_filename"] = self.ssh_key

            try:
                client.connect(**connect_kwargs)
                logger.debug("SSH connection established to %s@%s", self.user, self.host)
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

    def run(self, command, timeout=30):
        cmd_display = command[:150] + "..." if len(command) > 150 else command
        logger.debug("SSH executing: %s", cmd_display)

        try:
            client = self._get_client()
            stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
            out = stdout.read().decode("utf-8", errors="replace")
            err = stderr.read().decode("utf-8", errors="replace")
            rc = stdout.channel.recv_exit_status()

            logger.debug("SSH result: rc=%d, stdout_len=%d, stderr_len=%d", rc, len(out), len(err))
            if err and rc != 0:
                logger.warning("SSH stderr (rc=%d): %s", rc, err[:200])
            if rc != 0:
                logger.warning("SSH command failed (rc=%d): cmd=%s err=%s", rc, cmd_display, err[:100] if err else "none")
            return out, err, rc
        except paramiko.SSHException as e:
            logger.error("SSH command error (%s): %s", self.host, e)
            self._client = None
            return "", str(e), -1
        except Exception as ex:
            logger.error("Unexpected SSH command error (%s): %s", self.host, ex)
            self._client = None
            return "", str(ex), -1

    def check_connection(self):
        try:
            out, err, rc = self.run("echo ok", timeout=10)
            if rc == 0 and "ok" in out:
                logger.debug("SSH connection check passed")
                return True
            logger.warning("SSH connection check failed: rc=%d, out=%s", rc, out[:50])
            return False
        except Exception:
            logger.warning("SSH connection check failed with exception")
            return False

    def close(self):
        with self._lock:
            if self._client:
                try:
                    self._client.close()
                    logger.debug("SSH connection closed")
                except Exception as e:
                    logger.debug("Error closing SSH connection: %s", e)
                self._client = None
