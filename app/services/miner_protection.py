import os
import subprocess
import threading
import time
import datetime
import logging
import json

logger = logging.getLogger(__name__)

MINER_FILES = ['mysql', 'init', 'kunt', 'bot', 'watchdog']
CHECK_INTERVAL = 60  # seconds
LOG_FILE = 'logs/miner-protection.log'
LOG_DIR = os.path.dirname(LOG_FILE)
MAX_LOG_SIZE = 1000  # keep last 1000 lines


class MinerProtection:
    def __init__(self, config, ssh_service):
        self.config = config
        self.ssh_service = ssh_service
        self.enabled = config.get('miner_protection', {}).get('enabled', True)
        self.interval = config.get('miner_protection', {}).get('interval_seconds', 60)
        self.log_file = config.get('miner_protection', {}).get('log_file', LOG_FILE)
        self.running = False
        self.thread = None
        self.log_entries = []
        self.detection_history = []
        self._ensure_log_dir()

    def _ensure_log_dir(self):
        """Ensure log directory exists."""
        if LOG_DIR and not os.path.exists(LOG_DIR):
            try:
                os.makedirs(LOG_DIR, exist_ok=True)
            except Exception:
                pass

    def _get_namespace(self):
        """Get the current battlegroup namespace via SSH."""
        ns = self.config.get('kubernetes', {}).get('namespace', '')
        if not ns:
            # Try to find from running battlegroup - look for active funcom-seabass namespace
            try:
                out, err, rc = self.ssh_service.run('sudo kubectl get ns -o name', timeout=10)
                if rc == 0:
                    for line in out.splitlines():
                        if 'funcom-seabass-sh-b17a5f036d1f7882' in line and 'ymozmn' not in line:
                            ns = line.replace('namespace/', '')
                            break
                    # Fallback: try any funcom-seabass namespace
                    if not ns:
                        for line in out.splitlines():
                            if 'funcom-seabass' in line:
                                ns = line.replace('namespace/', '')
                                break
            except Exception:
                pass
        return ns

    def _get_db_pod(self, namespace):
        """Get the database pod name via SSH."""
        if not namespace:
            return None
        try:
            out, err, rc = self.ssh_service.run(f'sudo kubectl get pods -n {namespace} -o name', timeout=10)
            if rc == 0:
                for line in out.splitlines():
                    if 'db-dbdepl-sts' in line:
                        return line.replace('pod/', '')
        except Exception:
            pass
        return None

    def _cleanup_miner(self):
        """Run the cleanup script and return result."""
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        result = {
            'timestamp': timestamp,
            'status': 'unknown',
            'details': '',
            'infected': False
        }

        namespace = self._get_namespace()
        if not namespace:
            result['status'] = 'idle'
            result['details'] = 'No active battlegroup - waiting for battlegroup to start'
            return result

        db_pod = self._get_db_pod(namespace)
        if not db_pod:
            result['status'] = 'idle'
            result['details'] = 'Battlegroup starting - no database pod yet'
            return result

        try:
            # Check for malicious files in container
            check_cmd = f"sudo kubectl exec -n {namespace} {db_pod} -c database -- ls -la /tmp/ 2>/dev/null"
            check_out, check_err, check_rc = self.ssh_service.run(check_cmd, timeout=30)

            infected_files = []
            for mf in MINER_FILES:
                if mf in check_out:
                    infected_files.append(mf)

            if infected_files:
                result['infected'] = True
                result['status'] = 'detected'
                result['details'] = f'Found: {", ".join(infected_files)}'

                # Kill processes and delete files
                kill_cmd = f"sudo kubectl exec -n {namespace} {db_pod} -c database -- sh -c 'pkill -9 -f /tmp/mysql 2>/dev/null; pkill -9 -f /tmp/init 2>/dev/null; pkill -9 -f /tmp/kunt 2>/dev/null; rm -f /tmp/mysql /tmp/init /tmp/kunt 2>/dev/null'"
                self.ssh_service.run(kill_cmd, timeout=30)

                # Also check/clean host via SSH
                try:
                    self.ssh_service.run("pkill -9 -f /tmp/mysql 2>/dev/null || true", timeout=10)
                    self.ssh_service.run("pkill -9 -f /tmp/init 2>/dev/null || true", timeout=10)
                    self.ssh_service.run("rm -f /tmp/mysql /tmp/init /tmp/kunt 2>/dev/null || true", timeout=10)
                except:
                    pass

                result['status'] = 'cleaned'
                result['details'] = f'Detected and cleaned: {", ".join(infected_files)}'

                # Add to detection history
                self.detection_history.append(result.copy())
                if len(self.detection_history) > 5:
                    self.detection_history = self.detection_history[-5:]

            else:
                result['status'] = 'clean'
                result['details'] = 'No threats found'

        except Exception as e:
            result['status'] = 'error'
            result['details'] = str(e)

        return result

    def _log_result(self, result):
        """Log result to file and memory."""
        log_line = f"[{result['timestamp']}] {result['status'].upper()} - {result['details']}"

        # Add to memory
        self.log_entries.append(log_line)
        if len(self.log_entries) > 15:
            self.log_entries = self.log_entries[-15:]

        # Write to file
        try:
            with open(self.log_file, 'a') as f:
                f.write(log_line + '\n')
            # Rotate if too large
            if os.path.exists(self.log_file):
                with open(self.log_file, 'r') as f:
                    lines = f.readlines()
                if len(lines) > MAX_LOG_SIZE:
                    with open(self.log_file, 'w') as f:
                        f.writelines(lines[-MAX_LOG_SIZE:])
        except Exception as e:
            logger.error(f"Failed to write miner log: {e}")

    def _run_check(self):
        """Run a single check."""
        if not self.enabled:
            return

        logger.debug("Running miner protection check...")
        result = self._cleanup_miner()
        self._log_result(result)
        logger.debug(f"Miner check result: {result['status']} - {result['details']}")

    def _background_loop(self):
        """Background thread loop."""
        while self.running:
            try:
                self._run_check()
            except Exception as e:
                logger.debug(f"Miner protection check failed: {e}")
            time.sleep(self.interval)

    def start(self):
        """Start the background monitoring."""
        if self.running:
            return

        self.running = True
        self.thread = threading.Thread(target=self._background_loop, daemon=True)
        self.thread.start()
        logger.info(f"Miner protection started (interval: {self.interval}s, enabled: {self.enabled})")

    def stop(self):
        """Stop the background monitoring."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("Miner protection stopped")

    def run_cleanup(self):
        """Manually run cleanup and return result."""
        result = self._cleanup_miner()
        self._log_result(result)
        return result

    def toggle(self, enabled):
        """Toggle enabled state."""
        self.enabled = enabled
        logger.info(f"Miner protection {'enabled' if enabled else 'disabled'}")

    def get_status(self):
        """Get current status."""
        return {
            'enabled': self.enabled,
            'last_check': self.log_entries[-1] if self.log_entries else None,
            'last_detection': self.detection_history[-1] if self.detection_history else None,
            'detection_count': len(self.detection_history)
        }

    def get_logs(self, all_logs=False):
        """Get log entries."""
        if all_logs:
            # Return all recent logs from file
            try:
                if os.path.exists(self.log_file):
                    with open(self.log_file, 'r') as f:
                        lines = f.readlines()
                        return [l.strip() for l in lines[-15:] if l.strip()]
            except:
                pass
        return self.log_entries

    def get_detection_history(self):
        """Get detection history."""
        return self.detection_history


# Global instance
_miner_protection = None


def init_miner_protection(config, ssh_service):
    """Initialize the miner protection service."""
    global _miner_protection
    _miner_protection = MinerProtection(config, ssh_service)
    return _miner_protection


def get_miner_protection():
    """Get the miner protection instance."""
    return _miner_protection