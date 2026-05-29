"""Application factory - creates and configures the Flask app"""

import os
import sys
import time
import logging
import logging.handlers
import threading
from flask import Flask, request, g
from flask_login import current_user
from flask_socketio import SocketIO
from flask_limiter import Limiter
from flask_wtf.csrf import CSRFProtect
from flask_limiter.util import get_remote_address

from app.config import load_settings
from app.utils.debug_logging import create_debug_log_handler, sanitize_for_log, log_request_details, log_response_details
from app.services.database import DatabaseService, DashboardDatabaseService
from app.services.ssh import SSHService
from app.services.k8s import K8sService
from app.services.player import PlayerService
from app.services.vehicle import VehicleService
from app.services.chat import ChatService
from app.services.admin import AdminService
from app.services.updater import UpdateService
from app.services.director import DirectorService
from app.services.rmq import RmqService
from app.utils.cache import MultiCache
from app.routes.main import register_routes
from app.routes.api import register_api_routes
from app.routes.auth import init_auth
from app.websocket.shell import register_websocket_handlers


def create_app(settings_path=None):
    settings = load_settings(settings_path)

    base_dir = os.path.dirname(os.path.dirname(__file__))

    app = Flask(
        __name__,
        template_folder=os.path.join(base_dir, 'templates'),
        static_folder=os.path.join(base_dir, 'static'),
        static_url_path='/static'
    )
    app.config['SECRET_KEY'] = settings['dashboard']['secret_key']
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['PERMANENT_SESSION_LIFETIME'] = 28800  # 8 hours
    app.config['WTF_CSRF_ENABLED'] = True
    app.config['WTF_CSRF_TIME_LIMIT'] = None

    csrf = CSRFProtect(app)
    csrf.init_app(app)

    ssl_enabled = bool(
        settings['dashboard'].get('ssl_cert')
        and settings['dashboard'].get('ssl_key')
        and settings['dashboard']['ssl_cert'] != 'null'
        and settings['dashboard']['ssl_key'] != 'null'
    )

    app.config['SESSION_COOKIE_SECURE'] = ssl_enabled

    # Add security headers manually (replaces deprecated Flask-Talisman)
    if not settings['dashboard']['debug']:
        @app.after_request
        def add_security_headers(response):
            # HSTS - only when SSL is enabled
            if ssl_enabled:
                response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
            # Prevent clickjacking
            response.headers['X-Frame-Options'] = 'SAMEORIGIN'
            # Prevent MIME-type sniffing
            response.headers['X-Content-Type-Options'] = 'nosniff'
            # XSS protection
            response.headers['X-XSS-Protection'] = '1; mode=block'
            # Content Security Policy
            response.headers['Content-Security-Policy'] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "img-src 'self' data:; "
                "connect-src 'self' ws: wss: https://cdn.jsdelivr.net; "
                "frame-ancestors 'self'; "
                "base-uri 'self'; "
                "form-action 'self'"
            )
            # Referrer Policy - use strict-origin-when-cross-origin to allow CSRF checks
            response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
            # Permissions Policy
            response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
            return response

    # Global error handlers
    @app.errorhandler(Exception)
    def handle_exception(e):
        """Handle all unhandled exceptions."""
        logging.exception(f"Unhandled exception: {str(e)}")
        from flask import jsonify
        error_type = type(e).__name__
        error_msg = str(e)
        # Don't expose internal error details in production
        if settings['dashboard'].get('debug', False):
            return jsonify({
                'error': error_msg,
                'type': error_type,
                'trace': str(e)
            }), 500
        return jsonify({
            'error': 'An internal error occurred',
            'type': error_type
        }), 500

    @app.errorhandler(404)
    def handle_not_found(e):
        from flask import jsonify
        return jsonify({'error': 'Resource not found', 'type': 'NotFound'}), 404

    @app.errorhandler(405)
    def handle_method_not_allowed(e):
        from flask import jsonify
        return jsonify({'error': 'Method not allowed', 'type': 'MethodNotAllowed'}), 405

    # Request logging middleware
    @app.before_request
    def before_request_logging():
        from flask import request, session
        from flask_login import current_user
        import time
        g._request_start_time = time.time()
        user = current_user.id if current_user.is_authenticated else 'anonymous'
        
        debug_mode = settings['logging'].get('debug_enabled', False)
        
        if debug_mode:
            # Comprehensive debug logging for every request (all sanitized)
            logging.getLogger().debug("=" * 60)
            logging.getLogger().debug(f"REQUEST: {request.method} {request.path}")
            logging.getLogger().debug(f"  User: {sanitize_for_log(user)}")
            logging.getLogger().debug(f"  IP: {request.remote_addr}")
            logging.getLogger().debug(f"  UA: {sanitize_for_log(request.headers.get('User-Agent', 'Unknown')[:80])}")
            logging.getLogger().debug(f"  Referer: {sanitize_for_log(request.headers.get('Referer', 'None'))}")
            logging.getLogger().debug(f"  Args: {sanitize_for_log(request.args.to_dict())}")
            if request.is_json:
                logging.getLogger().debug(f"  JSON Body: {sanitize_for_log(request.get_json(silent=True) or {})}")
            elif request.form:
                logging.getLogger().debug(f"  Form: {sanitize_for_log(request.form.to_dict())}")
            logging.getLogger().debug(f"  Session: {sanitize_for_log(list(session.keys()) if session else 'None')}")
            log_request_details(logging.getLogger(), request)
        else:
            logging.debug(f"Request: {request.method} {request.path} from {user}")

    @app.after_request
    def after_request_logging(response):
        from flask import request, g
        import time
        duration = time.time() - g.get('_request_start_time', time.time())
        user = current_user.id if current_user.is_authenticated else 'anonymous'
        
        debug_mode = settings['logging'].get('debug_enabled', False)
        
        if debug_mode:
            # Comprehensive debug logging for every response
            logging.getLogger().debug(f"RESPONSE: {request.method} {request.path} -> {response.status_code}")
            logging.getLogger().debug(f"  Duration: {duration*1000:.1f}ms")
            logging.getLogger().debug(f"  Content-Type: {response.content_type}")
            logging.getLogger().debug(f"  Content-Length: {response.content_length}")
            log_response_details(logging.getLogger(), response, duration * 1000)
            logging.getLogger().debug("=" * 60)
        else:
            # Only log API requests to avoid noise
            if request.path.startswith('/api') or request.path.startswith('/server'):
                logging.info(f"{request.method} {request.path} {response.status_code} {duration:.3f}s user={user}")
        
        # Add timing header
        response.headers['X-Response-Time'] = f"{duration:.3f}s"
        return response

    _setup_logging(settings)

    db_host = settings['database']['host']

    db_config = {
        'host': db_host,
        'port': settings['database']['port'],
        'user': settings['database']['user'],
        'password': settings['database']['password'],
        'database': settings['database']['name'],
    }

    dash_db_config = {
        'host': db_host,
        'port': settings['database']['port'],
        'user': settings['database']['user'],
        'password': settings['database']['password'],
        'database': settings['database'].get('dashboard_database_name', 'dashboard'),
    }

    db_service = DatabaseService(
        db_config,
        min_conn=settings['database']['min_connections'],
        max_conn=settings['database']['max_connections'],
    )
    logging.debug(f"DatabaseService initialized: host={db_config['host']}, port={db_config['port']}, user={db_config['user']}")

    dash_db_service = DashboardDatabaseService(
        dash_db_config,
        min_conn=settings['database']['min_connections'],
        max_conn=settings['database']['max_connections'],
        owner=settings['database'].get('owner', 'dune'),
    )
    dash_db_service.ensure_tables(game_db=db_service)

    # Create performance indexes if they don't exist
    try:
        admin_svc_for_indexes = AdminService(db_service, None, dash_db=dash_db_service)
        success, created, error = admin_svc_for_indexes.create_indexes()
        if success and created:
            logging.info(f"Created {len(created)} database indexes")
            logging.debug(f"Created indexes: {created}")
    except Exception as e:
        logging.warning(f"Could not create indexes: {e}")

    ssh_service = SSHService(
        host=settings['server']['host'],
        user=settings['server']['user'],
        ssh_key=settings['server'].get('ssh_key')
    )
    logging.debug(f"SSHService initialized: host={settings['server']['host']}, user={settings['server']['user']}")

    k8s_service = K8sService(
        ssh_service=ssh_service,
        namespace=settings['kubernetes']['namespace']
    )
    logging.debug(f"K8sService initialized: namespace={settings['kubernetes']['namespace']}")

    static_cache = MultiCache(ttl_seconds=settings['cache']['static_data_ttl'])

    player_svc = PlayerService(db_service, dash_db=dash_db_service)
    vehicle_svc = VehicleService(db_service)
    chat_svc = ChatService(dash_db_service, k8s_service, ssh_service, static_cache)
    logging.debug("ChatService initialized")
    admin_svc = AdminService(db_service, ssh_service, dash_db=dash_db_service)
    logging.debug("AdminService initialized")
    updater_svc = UpdateService(base_dir)
    logging.debug("UpdateService initialized")
    director_svc = DirectorService(
        host='127.0.0.1',
        node_port=settings.get('director', {}).get('port', 32479),
        k8s_service=k8s_service,
        ssh_service=ssh_service,
        namespace=settings['kubernetes']['namespace'],
    )
    logging.debug(f"DirectorService initialized: port={settings.get('director', {}).get('port', 32479)}")
    rmq_svc = RmqService(
        admin_port=settings.get('rabbitmq', {}).get('admin_port', 30325),
        game_port=settings.get('rabbitmq', {}).get('game_port', 32716),
        username=settings.get('rabbitmq', {}).get('username', 'dashboard_admin'),
        password=settings.get('rabbitmq', {}).get('password', ''),
    )
    logging.debug(f"RmqService initialized: admin=localhost:{settings.get('rabbitmq', {}).get('admin_port', 30325)} game=localhost:{settings.get('rabbitmq', {}).get('game_port', 32716)}")

    services = {
        'db': db_service,
        'dash_db': dash_db_service,
        'ssh': ssh_service,
        'k8s': k8s_service,
        'player': player_svc,
        'vehicle': vehicle_svc,
        'chat': chat_svc,
        'admin': admin_svc,
        'static_cache': static_cache,
        'updater': updater_svc,
        'director': director_svc,
        'rmq': rmq_svc,
    }
    logging.debug(f"All services registered: {list(services.keys())}")

    # Initialize audit service
    from app.services.audit import AuditService
    audit_svc = AuditService()
    services['audit'] = audit_svc

    # Track start time for uptime calculation
    import time
    app._start_time = time.time()

    cors_origins = "*" if settings['dashboard']['host'] == '0.0.0.0' else []
    socketio = SocketIO(app, cors_allowed_origins=cors_origins, async_mode='threading')

    # Initialize rate limiter (enabled, per-route limits only)
    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=[],  # rate limits applied per-route only (login has 10/min)
        storage_uri="memory://",
    )
    app.limiter = limiter

    if settings['auth']['enabled']:
        init_auth(app, settings, limiter, audit_svc)

    register_routes(app, services, settings)
    register_api_routes(app, services, settings)
    register_websocket_handlers(socketio, settings)

    # Start update checker
    updater_svc.start_checker()

    @app.teardown_appcontext
    def cleanup_db(exc):
        pass

    if settings['kubernetes']['namespace'] == '':
        try:
            k8s_service.auto_detect_namespace()
            if k8s_service.namespace:
                settings['kubernetes']['namespace'] = k8s_service.namespace
        except Exception as e:
            logging.warning(f"Could not auto-detect K8s namespace: {e}")

    # Check SSL certificate expiry and start background monitor
    if ssl_enabled:
        try:
            from app.utils.ssl import check_cert_expiry, generate_cert
            cert_path = str(settings['dashboard']['ssl_cert']).strip("'\"")
            key_path = str(settings['dashboard']['ssl_key']).strip("'\"")
            is_expiring, days_remaining, msg = check_cert_expiry(cert_path)
            if is_expiring:
                logging.warning(f"SSL: {msg}")
            else:
                logging.info(f"SSL: {msg}")

            def _cert_monitor():
                """Background thread that checks and regenerates expiring SSL certs."""
                import time
                check_interval = settings.get('ssl', {}).get('check_interval_hours', 24) * 3600
                renewal_days = settings.get('ssl', {}).get('renewal_days_before_expiry', 30)
                server_ip = settings['server'].get('host', '')
                ssl_dir = os.path.dirname(cert_path)
                ca_cert = os.path.join(ssl_dir, 'ca.pem')
                ca_key = os.path.join(ssl_dir, 'ca-key.pem')
                ca_available = os.path.exists(ca_cert) and os.path.exists(ca_key)

                is_le = 'letsencrypt' in cert_path.lower() or 'certbot' in cert_path.lower()
                le_domain = settings['dashboard'].get('ssl_domain')

                def _restart_app():
                    import subprocess
                    if os.name == 'nt':
                        launcher = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'start.bat')
                        if os.path.exists(launcher):
                            subprocess.Popen(['cmd', '/c', 'start', '', launcher], shell=True)
                        else:
                            subprocess.Popen([sys.executable, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'run.py')], creationflags=subprocess.CREATE_NEW_CONSOLE)
                    else:
                        launcher = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'start.sh')
                        if os.path.exists(launcher):
                            subprocess.Popen(['bash', launcher], start_new_session=True)
                        else:
                            subprocess.Popen([sys.executable, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'run.py')], start_new_session=True)
                    os._exit(0)

                while True:
                    time.sleep(check_interval)
                    try:
                        is_expiring, days_left, _ = check_cert_expiry(cert_path, warning_days=renewal_days)
                        if is_expiring:
                            if is_le and le_domain:
                                logging.info(f"SSL: Let's Encrypt certificate expiring soon ({days_left} days). Running certbot renew...")
                                import subprocess
                                result = subprocess.run(['certbot', 'renew', '--quiet'], capture_output=True, timeout=300)
                                if result.returncode == 0:
                                    logging.info("SSL: Let's Encrypt certificate renewed. Restarting to apply...")
                                    _restart_app()
                                else:
                                    logging.error(f"SSL: certbot renew failed: {result.stderr.decode()}")
                            elif ca_available:
                                logging.info(f"SSL: Certificate expiring soon ({days_left} days). Regenerating...")
                                san_ips = [server_ip, '127.0.0.1'] if server_ip else ['127.0.0.1']
                                generate_cert(
                                    cert_path=cert_path,
                                    key_path=key_path,
                                    common_name=server_ip or 'localhost',
                                    san_ips=san_ips,
                                    san_dns=['localhost'],
                                    ca_cert_path=ca_cert,
                                    ca_key_path=ca_key,
                                )
                                logging.info("SSL: Certificate regenerated. Restarting to apply...")
                                _restart_app()
                            else:
                                logging.warning("SSL: Certificate expiring but no CA key available. Cannot regenerate.")
                    except Exception as e:
                        logging.error(f"SSL: Background cert check failed: {e}")

            monitor_thread = threading.Thread(target=_cert_monitor, daemon=True)
            monitor_thread.start()
            logging.info("SSL: Background certificate monitor started")
        except Exception as e:
            logging.debug(f"Could not initialize SSL cert monitor: {e}")

    # Re-apply firewall rules on startup (restores iptables after VM reboot)
    try:
        admin_svc = services.get('admin')
        k8s_svc = services.get('k8s')
        if admin_svc and settings.get('firewall'):
            success, applied, skipped, err = admin_svc.reapply_firewall_rules(settings, k8s_svc)
            if applied:
                logging.info(f"Firewall: re-applied rules for ports {applied}")
            if skipped:
                logging.info(f"Firewall: skipped {len(skipped)} ports ({', '.join(skipped)})")
            if err:
                logging.warning(f"Firewall: reapply error: {err}")
    except Exception as e:
        logging.debug(f"Could not reapply firewall rules on startup: {e}")

    # Start connection monitor for auto-reconnection on server restart/VM reboot
    try:
        def _connection_monitor():
            """Background thread that monitors and auto-reconnects services."""
            import time
            check_interval = 60  # Check every 60 seconds
            consecutive_failures = 0
            max_consecutive_failures = 5
            last_ssh_ok = True  # Track SSH state to detect reconnection

            while True:
                time.sleep(check_interval)
                try:
                    ssh_svc = services.get('ssh')
                    db_svc = services.get('db')

                    # Check SSH connection
                    ssh_ok = False
                    if ssh_svc:
                        try:
                            ssh_ok = ssh_svc.check_connection()
                        except Exception:
                            pass

                    # Check database connection
                    db_ok = False
                    if db_svc:
                        try:
                            db_ok = db_svc.check_health()
                        except Exception:
                            pass

                    if ssh_ok and db_ok:
                        consecutive_failures = 0
                        # Re-apply firewall rules after SSH reconnection (VM reboot recovery)
                        if not last_ssh_ok:
                            try:
                                admin_svc = services.get('admin')
                                k8s_svc = services.get('k8s')
                                if admin_svc and settings.get('firewall'):
                                    success, applied, skipped, err = admin_svc.reapply_firewall_rules(settings, k8s_svc)
                                    if applied:
                                        logging.info(f"Firewall: re-applied rules after reconnect for ports {applied}")
                                    if skipped:
                                        logging.info(f"Firewall: skipped {len(skipped)} ports after reconnect")
                            except Exception as e:
                                logging.debug(f"Firewall: reapply after reconnect failed: {e}")
                        last_ssh_ok = True
                        logging.debug("Connection monitor: All services healthy")
                    else:
                        consecutive_failures += 1
                        logging.warning(f"Connection monitor: Service issue detected (failures={consecutive_failures})")

                        # Force SSH reconnection if SSH check failed
                        if not ssh_ok and ssh_svc:
                            try:
                                ssh_svc.close()
                                logging.info("Connection monitor: SSH connection reset, will reconnect on next request")
                            except Exception:
                                pass
                        last_ssh_ok = False

                        # Reset database pool if multiple consecutive failures
                        if not db_ok and db_svc and consecutive_failures >= 3:
                            try:
                                db_svc.close_all()
                                logging.info("Connection monitor: Database pool reset due to connection issues")
                            except Exception:
                                pass

                except Exception as e:
                    logging.debug(f"Connection monitor: Background check failed: {e}")

        conn_monitor_thread = threading.Thread(target=_connection_monitor, daemon=True)
        conn_monitor_thread.start()
        logging.info("Connection monitor: Background service health monitor started")
    except Exception as e:
        logging.debug(f"Could not initialize connection monitor: {e}")

    app.dune_settings = settings
    app.dune_services = services

    return app, socketio


def _setup_logging(settings):
    log_level = getattr(logging, settings['logging']['level'].upper(), logging.INFO)
    log_file = settings['logging']['file']

    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=settings['logging']['max_bytes'],
        backupCount=settings['logging']['backup_count']
    )
    handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    handler.setLevel(log_level)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    ))
    console_handler.setLevel(log_level)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(handler)
    root_logger.addHandler(console_handler)

    audit_logger = logging.getLogger('audit')
    audit_handler = logging.handlers.RotatingFileHandler(
        'logs/audit.log',
        maxBytes=settings['logging']['max_bytes'],
        backupCount=settings['logging']['backup_count']
    )
    audit_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(message)s'
    ))
    audit_logger.addHandler(audit_handler)
    audit_logger.setLevel(logging.INFO)

    # Debug logging - separate file when debug is enabled
    if settings['logging'].get('debug_enabled', False):
        debug_file = settings['logging'].get('debug_file', 'logs/debug.log')
        os.makedirs(os.path.dirname(debug_file), exist_ok=True)
        debug_handler = create_debug_log_handler(
            debug_file,
            max_bytes=settings['logging']['max_bytes'],
            backup_count=settings['logging']['backup_count']
        )
        root_logger.addHandler(debug_handler)
        root_logger.setLevel(logging.DEBUG)
        logging.info(f"Debug logging enabled - writing to {debug_file}")
