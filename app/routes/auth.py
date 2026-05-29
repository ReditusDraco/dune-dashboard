"""Authentication routes - login, logout"""

import time
import threading
from flask import render_template, request, redirect, url_for, flash, session, make_response
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in.'

# In-memory failed login tracker: {ip: {"count": int, "first_attempt": float}}
_failed_attempts = {}
_failed_lock = threading.Lock()

# Reusable Argon2 verifier (created once, not per-request)
try:
    from argon2 import PasswordHasher, exceptions as argon2_exceptions
    _password_hasher = PasswordHasher(time_cost=3, memory_cost=65536)
except ImportError:
    _password_hasher = None
    argon2_exceptions = None
_failed_lock = threading.Lock()
_MAX_FAILED_ATTEMPTS = 5
_BLOCK_DURATION = 900  # 15 minutes


def _is_ip_blocked(ip):
    """Check if an IP is currently blocked due to too many failed logins."""
    with _failed_lock:
        record = _failed_attempts.get(ip)
        if record and record['count'] >= _MAX_FAILED_ATTEMPTS:
            elapsed = time.time() - record['first_attempt']
            if elapsed < _BLOCK_DURATION:
                return True
            del _failed_attempts[ip]
        return False


def _record_failed_attempt(ip):
    """Record a failed login attempt and return True if IP should now be blocked."""
    with _failed_lock:
        now = time.time()
        record = _failed_attempts.get(ip)
        if record:
            record['count'] += 1
        else:
            _failed_attempts[ip] = {'count': 1, 'first_attempt': now}
            record = _failed_attempts[ip]
        return record['count'] >= _MAX_FAILED_ATTEMPTS


def _clear_failed_attempts(ip):
    """Clear failed attempt records on successful login."""
    with _failed_lock:
        _failed_attempts.pop(ip, None)


class AdminUser(UserMixin):
    def __init__(self, username):
        self.id = username

def init_auth(app, settings, limiter=None, audit_svc=None):
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        auth = settings.get('auth', {})
        if str(auth.get('username')) == str(user_id):
            return AdminUser(user_id)
        return None

    def _apply_rate_limit(f):
        return limiter.limit("10 per minute")(f) if limiter else f

    @app.route('/login', methods=['GET', 'POST'])
    @_apply_rate_limit
    def login():
        if current_user.is_authenticated:
            return redirect(url_for('overview'))

        client_ip = request.remote_addr or 'unknown'

        if _is_ip_blocked(client_ip):
            flash('Too many failed attempts. Try again later.')
            return render_template('login.html')

        if request.method == 'POST':
            u = request.form.get('username', '')
            p = request.form.get('password', '')
            auth = settings.get('auth', {})
            cfg_u = str(auth.get('username', ''))
            password_hash = auth.get('password_hash')

            if not password_hash:
                flash('Authentication not configured. Please run setup.')
                return render_template('login.html')

            try:
                # Always run Argon2 verify regardless of username (prevents timing enumeration)
                from argon2 import exceptions
                _DUMMY = '$argon2id$v=19$m=65536,t=3,p=4$AAAAAAAAAAAAAAAAAAAAAA$AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
                hash_to_verify = password_hash if u == cfg_u else _DUMMY
                verified = _password_hasher.verify(hash_to_verify, p)

                if verified and u == cfg_u:
                    _clear_failed_attempts(client_ip)
                    login_user(AdminUser(u))
                    if audit_svc:
                        audit_svc.log('login_success', {'username': u}, user=u, severity='info')
                    return redirect(url_for('overview'))
                else:
                    # Dummy always fails; wrong password also fails here
                    _record_failed_attempt(client_ip)
                    if u == cfg_u and audit_svc:
                        audit_svc.log('login_failed', {'username': u, 'reason': 'invalid_password'}, user=u, severity='warning')
                    elif audit_svc:
                        audit_svc.log('login_failed', {'username': u, 'reason': 'invalid_credentials'}, user='unknown', severity='warning')
                    flash('Invalid username or password')
                    return render_template('login.html')
            except exceptions.VerifyMismatchError:
                _record_failed_attempt(client_ip)
                flash('Invalid username or password')
                return render_template('login.html')
            except Exception as e:
                flash('Authentication error. Please try again.')
                return render_template('login.html')

            _record_failed_attempt(client_ip)
            flash('Invalid username or password')

        return render_template('login.html')

    @app.route('/logout')
    def logout():
        user = current_user.id if current_user.is_authenticated else 'unknown'
        logout_user()
        session.clear()
        if audit_svc:
            audit_svc.log('logout', {}, user=user, severity='info')
        resp = make_response(redirect(url_for('login')))
        resp.delete_cookie('session')
        resp.delete_cookie('remember_token')
        return resp
