"""Application factory - creates and configures the Flask app"""

import os
import sys
import logging
import logging.handlers
from flask import Flask, request
from flask_socketio import SocketIO
from flask_talisman import Talisman

from app.config import load_settings
from app.services.database import DatabaseService
from app.services.ssh import SSHService
from app.services.k8s import K8sService
from app.services.player import PlayerService
from app.services.vehicle import VehicleService
from app.services.chat import ChatService
from app.services.admin import AdminService
from app.services.updater import UpdateService
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

    if not settings['dashboard']['debug']:
        Talisman(app, content_security_policy=None, force_https=False)

    _setup_logging(settings)

    db_config = {
        'host': settings['database']['host'],
        'port': settings['database']['port'],
        'user': settings['database']['user'],
        'password': settings['database']['password'],
        'database': settings['database']['name'],
    }

    db_service = DatabaseService(
        db_config,
        min_conn=settings['database']['min_connections'],
        max_conn=settings['database']['max_connections']
    )
    db_service.ensure_tables()

    ssh_service = SSHService(
        host=settings['server']['host'],
        user=settings['server']['user'],
        ssh_key=settings['server'].get('ssh_key')
    )

    k8s_service = K8sService(
        ssh_service=ssh_service,
        namespace=settings['kubernetes']['namespace']
    )

    static_cache = MultiCache(ttl_seconds=settings['cache']['static_data_ttl'])

    player_svc = PlayerService(db_service)
    vehicle_svc = VehicleService(db_service)
    chat_svc = ChatService(db_service, k8s_service, ssh_service, static_cache)
    admin_svc = AdminService(db_service, ssh_service)
    updater_svc = UpdateService(base_dir)

    services = {
        'db': db_service,
        'ssh': ssh_service,
        'k8s': k8s_service,
        'player': player_svc,
        'vehicle': vehicle_svc,
        'chat': chat_svc,
        'admin': admin_svc,
        'static_cache': static_cache,
        'updater': updater_svc,
    }

    socketio = SocketIO(app, cors_allowed_origins=[], async_mode='threading')

    if settings['auth']['enabled']:
        init_auth(app, settings)

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
