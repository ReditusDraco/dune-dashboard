# File browser routes.

import base64
import logging
import posixpath

from flask import Blueprint, jsonify, request
from flask_login import login_required

from app.models import ApiResponse, ErrorDetail

files_bp = Blueprint("files", __name__)
logger = logging.getLogger(__name__)

FILEBROWSER_BASE_PATH = "/srv"


def _validate_fb_path(path: str) -> bool:
    path_str = str(path or "").lstrip("/")
    if ".." in path_str or "\x00" in path_str:
        return False
    normalized = posixpath.normpath("/" + path_str)
    return normalized == FILEBROWSER_BASE_PATH or normalized.startswith(FILEBROWSER_BASE_PATH + "/")


def _get_services():
    from app.factory import get_services
    return get_services()


def _fb_exec(command: str, timeout: int = 10):
    services = _get_services()
    k8s = services["k8s"]
    pod = k8s.get_filebrowser_pod()
    if not pod:
        return "", "FileBrowser pod not found", 1
    full_cmd = f"sudo kubectl exec {pod} -n {k8s.namespace} -- {command}"
    return k8s.ssh.run(full_cmd, timeout=timeout)


@files_bp.route("/list", methods=["POST"])
@login_required
def files_list():
    data = request.get_json() or {}
    path = data.get("path", "/srv")
    if not _validate_fb_path(path):
        return jsonify(ApiResponse(
            success=False,
            error=ErrorDetail(code="AccessDenied", message="Invalid path"),
        ).model_dump()), 403
    import shlex
    safe_path = shlex.quote(path)
    out, err, rc = _fb_exec(f"ls -la {safe_path}", timeout=10)
    if rc != 0:
        return jsonify(ApiResponse(
            success=False,
            error=ErrorDetail(code="CommandError", message=err or "Failed to list directory"),
        ).model_dump()), 500

    files = []
    for line in out.strip().split("\n")[1:]:
        parts = line.split(None, 8)
        if len(parts) >= 9:
            name = parts[8]
            if name in (".", ".."):
                continue
            files.append({
                "name": name,
                "is_dir": parts[0].startswith("d"),
                "size": parts[4] if not parts[0].startswith("d") else "",
                "perms": parts[0],
                "date": " ".join(parts[5:8]),
            })
    return jsonify(ApiResponse(success=True, data={"files": files}).model_dump())


@files_bp.route("/view", methods=["GET"])
@login_required
def files_view():
    path = request.args.get("path", "")
    if not path or not _validate_fb_path(path):
        return jsonify(ApiResponse(
            success=False,
            error=ErrorDetail(code="AccessDenied", message="Invalid path"),
        ).model_dump()), 403
    import shlex
    safe_path = shlex.quote(path)
    out, err, rc = _fb_exec(f"head -c 100000 {safe_path}", timeout=10)
    if rc != 0:
        return jsonify(ApiResponse(
            success=False,
            error=ErrorDetail(code="CommandError", message=err or "Failed to read file"),
        ).model_dump()), 500
    return jsonify(ApiResponse(success=True, data={"content": out, "path": path}).model_dump())


@files_bp.route("/save", methods=["POST"])
@login_required
def files_save():
    data = request.get_json() or {}
    path = data.get("path", "")
    content = data.get("content", "")
    if not path or not _validate_fb_path(path):
        return jsonify(ApiResponse(
            success=False,
            error=ErrorDetail(code="AccessDenied", message="Invalid path"),
        ).model_dump()), 403
    import shlex
    import base64
    content_b64 = base64.b64encode(content.encode()).decode()
    safe_path = shlex.quote(path)
    # Write via base64 decode inside pod
    cmd = f"echo {content_b64} | base64 -d > {safe_path}"
    out, err, rc = _fb_exec(cmd, timeout=15)
    if rc != 0:
        return jsonify(ApiResponse(
            success=False,
            error=ErrorDetail(code="CommandError", message=err or "Failed to save file"),
        ).model_dump()), 500
    return jsonify(ApiResponse(success=True).model_dump())
