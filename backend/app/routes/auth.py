# Authentication routes — login, logout.

import time
import threading
from functools import wraps

from flask import Blueprint, request, jsonify, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user

from app.models import ApiResponse, ErrorDetail

auth_bp = Blueprint("auth", __name__)
login_manager = LoginManager()

_failed_attempts = {}
_failed_lock = threading.Lock()
_MAX_FAILED_ATTEMPTS = 5
_BLOCK_DURATION = 900


class AdminUser(UserMixin):
    def __init__(self, username):
        self.id = username


def _is_ip_blocked(ip):
    with _failed_lock:
        record = _failed_attempts.get(ip)
        if record and record["count"] >= _MAX_FAILED_ATTEMPTS:
            elapsed = time.time() - record["first_attempt"]
            if elapsed < _BLOCK_DURATION:
                return True
            del _failed_attempts[ip]
        return False


def _record_failed_attempt(ip):
    with _failed_lock:
        now = time.time()
        record = _failed_attempts.get(ip)
        if record:
            record["count"] += 1
        else:
            _failed_attempts[ip] = {"count": 1, "first_attempt": now}
        return _failed_attempts[ip]["count"] >= _MAX_FAILED_ATTEMPTS


def _clear_failed_attempts(ip):
    with _failed_lock:
        _failed_attempts.pop(ip, None)


def init_auth(app, settings):
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in."

    @login_manager.user_loader
    def load_user(user_id):
        auth = settings.get("auth", {})
        if str(auth.get("username")) == str(user_id):
            return AdminUser(user_id)
        return None


def get_audit_user():
    return current_user.id if current_user.is_authenticated else "anonymous"


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    client_ip = request.remote_addr or "unknown"

    if _is_ip_blocked(client_ip):
        return jsonify(ApiResponse(
            success=False,
            error=ErrorDetail(code="IpBlocked", message="Too many failed attempts. Try again later."),
        ).model_dump()), 429

    auth = request.app.dune_settings.get("auth", {})
    cfg_u = str(auth.get("username", ""))
    password_hash = auth.get("password_hash")

    if username != cfg_u:
        _record_failed_attempt(client_ip)
        return jsonify(ApiResponse(
            success=False,
            error=ErrorDetail(code="InvalidCredentials", message="Invalid username or password"),
        ).model_dump()), 401

    if password_hash:
        try:
            from argon2 import PasswordHasher, exceptions
            ph = PasswordHasher(time_cost=3, memory_cost=65536)
            ph.verify(password_hash, password)
            _clear_failed_attempts(client_ip)
            login_user(AdminUser(username))
            return jsonify(ApiResponse(success=True, data={"user": username}).model_dump())
        except exceptions.VerifyMismatchError:
            _record_failed_attempt(client_ip)
            return jsonify(ApiResponse(
                success=False,
                error=ErrorDetail(code="InvalidCredentials", message="Invalid username or password"),
            ).model_dump()), 401
        except Exception:
            return jsonify(ApiResponse(
                success=False,
                error=ErrorDetail(code="AuthError", message="Authentication error"),
            ).model_dump()), 500
    else:
        return jsonify(ApiResponse(
            success=False,
            error=ErrorDetail(code="NotConfigured", message="Authentication not configured"),
        ).model_dump()), 403


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return jsonify(ApiResponse(success=True).model_dump())


@auth_bp.route("/me", methods=["GET"])
def me():
    if current_user.is_authenticated:
        return jsonify(ApiResponse(success=True, data={"user": current_user.id}).model_dump())
    return jsonify(ApiResponse(success=False, error=ErrorDetail(code="Unauthorized", message="Not authenticated")).model_dump()), 401
