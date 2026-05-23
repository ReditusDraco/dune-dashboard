# WebSocket shell handler — interactive terminal via SSH.

import os
import time
import threading
import logging
import re
import shlex

import paramiko
from flask import request, session
from flask_socketio import emit

logger = logging.getLogger(__name__)

shell_processes = {}
K8S_NAME_RE = re.compile(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")


def require_k8s_name(value, label):
    value = str(value or "").strip()
    if not value or not K8S_NAME_RE.fullmatch(value):
        raise ValueError(f"Invalid {label}")
    return value


def quote_remote(value):
    return shlex.quote(str(value))


def register_websocket_handlers(socketio, settings):
    @socketio.on("shell_create")
    def handle_shell_create(data):
        shell_enabled = settings.get("auth", {}).get("shell_enabled", True)
        if not shell_enabled:
            return emit("shell_created", {"success": False, "error": "Shell access is disabled"})

        auth_enabled = settings.get("auth", {}).get("enabled", True)
        if auth_enabled and not session.get("_user_id"):
            return emit("shell_created", {"success": False, "error": "Authentication required"})

        shell_type = data.get("type", "vm")
        shell_id = request.sid

        try:
            ssh_key = _find_ssh_key(settings)
            if not ssh_key:
                return emit("shell_created", {"success": False, "error": "SSH key not found"})

            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.WarningPolicy())
            server_host = settings["server"]["host"]
            server_user = settings["server"]["user"]

            if shell_type == "vm":
                client.connect(server_host, username=server_user, key_filename=ssh_key, timeout=10)
                chan = client.invoke_shell(term="xterm-256color", width=80, height=24)
            else:
                namespace = settings["kubernetes"]["namespace"]
                pod = data.get("pod", "")
                pod = require_k8s_name(pod, "pod")
                client.connect(server_host, username=server_user, key_filename=ssh_key, timeout=10)
                transport = client.get_transport()
                chan = transport.open_session()
                chan.get_pty(term="xterm-256color", width=80, height=24)
                safe_pod = quote_remote(pod)
                safe_ns = quote_remote(namespace)
                chan.exec_command(f"sudo kubectl exec -it {safe_pod} -n {safe_ns} -- /bin/bash")

            shell_processes[shell_id] = {"client": client, "channel": chan, "type": shell_type}

            def read_channel():
                time.sleep(0.5)
                socketio.emit("shell_output", {"data": "\r\nConnected. Press Enter...\r\n", "type": "stdout", "target": shell_type}, room=shell_id)
                while shell_id in shell_processes:
                    try:
                        while chan.recv_ready():
                            data = chan.recv(65535).decode("utf-8", errors="replace")
                            if data:
                                socketio.emit("shell_output", {"data": data, "type": "stdout", "target": shell_type}, room=shell_id)
                        while chan.recv_stderr_ready():
                            data = chan.recv_stderr(65535).decode("utf-8", errors="replace")
                            if data:
                                socketio.emit("shell_output", {"data": data, "type": "stderr", "target": shell_type}, room=shell_id)
                        if chan.closed:
                            socketio.emit("shell_output", {"data": "\r\n[Disconnected]\r\n", "type": "stdout", "target": shell_type}, room=shell_id)
                            break
                    except Exception as e:
                        logger.error("Shell read error: %s", e)
                        break
                    time.sleep(0.1)

            threading.Thread(target=read_channel, daemon=True).start()
            socketio.emit("shell_created", {"success": True, "shell_id": shell_id}, room=shell_id)
        except Exception as e:
            logger.error("Shell creation failed: %s", e)
            socketio.emit("shell_created", {"success": False, "error": str(e)}, room=shell_id)

    @socketio.on("shell_input")
    def handle_shell_input(data):
        shell_id = request.sid
        if shell_id in shell_processes:
            try:
                chan = shell_processes[shell_id]["channel"]
                if chan and chan.send_ready():
                    chan.send(data.get("data", ""))
            except Exception as e:
                logger.error("Shell input error: %s", e)

    @socketio.on("shell_disconnect")
    def handle_shell_disconnect(data=None):
        shell_id = request.sid
        if shell_id in shell_processes:
            try:
                if "client" in shell_processes[shell_id]:
                    shell_processes[shell_id]["client"].close()
            except Exception as e:
                logger.error("Shell disconnect error: %s", e)
            del shell_processes[shell_id]


def _find_ssh_key(settings):
    ssh_key = settings["server"].get("ssh_key")
    if ssh_key:
        return ssh_key
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        default_key = os.path.join(local_appdata, "DuneAwakeningServer", "sshKey")
        if os.path.exists(default_key):
            return default_key
    return None
