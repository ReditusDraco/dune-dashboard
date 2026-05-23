# Application factory — creates and configures the Flask app.

import os
import sys
import logging
import logging.handlers
from datetime import datetime

from flask import Flask, jsonify, request, g, send_from_directory
from flask_cors import CORS
from flask_login import current_user
from flask_socketio import SocketIO
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from app.config import load_settings
from app.routes.auth import auth_bp, init_auth
from app.routes.health import health_bp
from app.routes.api import api_bp
from app.routes.director import director_bp
from app.routes.server import server_bp
from app.routes.files import files_bp
from app.routes.debug import debug_bp
from app.routes.chat import chat_bp
from app.websocket.shell import register_websocket_handlers

from app.services.database import DatabaseService
from app.services.ssh import SSHService
from app.services.k8s import K8sService
from app.services.bg_director import BgDirectorService
from app.services.rmq_admin import RmqAdminService
from app.services.rmq_game import RmqGameService
from app.services.realtime import RealtimeService
from app.services.player import PlayerService
from app.services.economy import EconomyService
from app.services.guild import GuildService
from app.services.world import WorldService
from app.services.progression import ProgressionService
from app.services.character import CharacterService
from app.services.audit import AuditService
from app.services.chat import ChatService

_services = None


def get_services():
    global _services
    return _services


def create_app(settings_path=None):
    global _services

    settings = load_settings(settings_path)
    base_dir = os.path.dirname(os.path.dirname(__file__))

    app = Flask(
        __name__,
        template_folder=os.path.join(base_dir, "frontend", "dist"),
        static_folder=os.path.join(base_dir, "frontend", "dist", "assets"),
        static_url_path="/assets",
    )
    app.config["SECRET_KEY"] = settings["dashboard"]["secret_key"]
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["WTF_CSRF_ENABLED"] = True
    app.config["WTF_CSRF_TIME_LIMIT"] = None

    CORS(app, resources={r"/api/*": {"origins": "*"}})

    ssl_enabled = bool(
        settings["dashboard"].get("ssl_cert")
        and settings["dashboard"].get("ssl_key")
        and settings["dashboard"]["ssl_cert"] != "null"
        and settings["dashboard"]["ssl_key"] != "null"
    )
    app.config["SESSION_COOKIE_SECURE"] = ssl_enabled

    if not settings["dashboard"]["debug"]:
        @app.after_request
        def add_security_headers(response):
            if ssl_enabled:
                response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            response.headers["X-Frame-Options"] = "SAMEORIGIN"
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-XSS-Protection"] = "1; mode=block"
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data:; "
                "connect-src 'self' ws: wss:; "
                "frame-ancestors 'self'; "
                "base-uri 'self'; "
                "form-action 'self'"
            )
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            return response

    # Error handlers
    @app.errorhandler(Exception)
    def handle_exception(e):
        logging.exception("Unhandled exception: %s", e)
        from app.models import ApiResponse, ErrorDetail
        if settings["dashboard"].get("debug", False):
            return jsonify(ApiResponse(
                success=False,
                error=ErrorDetail(code="InternalError", message=str(e)),
            ).model_dump()), 500
        return jsonify(ApiResponse(
            success=False,
            error=ErrorDetail(code="InternalError", message="An internal error occurred"),
        ).model_dump()), 500

    @app.errorhandler(404)
    def handle_not_found(e):
        from app.models import ApiResponse, ErrorDetail
        return jsonify(ApiResponse(
            success=False,
            error=ErrorDetail(code="NotFound", message="Resource not found"),
        ).model_dump()), 404

    @app.errorhandler(405)
    def handle_method_not_allowed(e):
        from app.models import ApiResponse, ErrorDetail
        return jsonify(ApiResponse(
            success=False,
            error=ErrorDetail(code="MethodNotAllowed", message="Method not allowed"),
        ).model_dump()), 405

    # Request logging
    @app.before_request
    def before_request_logging():
        import time as _time
        g._request_start_time = _time.time()

    @app.after_request
    def after_request_logging(response):
        import time as _time
        duration = _time.time() - g.get("_request_start_time", _time.time())
        user = current_user.id if current_user.is_authenticated else "anonymous"
        if request.path.startswith("/api") or request.path.startswith("/server"):
            logging.info("%s %s %d %.3fs user=%s", request.method, request.path, response.status_code, duration, user)
        response.headers["X-Response-Time"] = f"{duration:.3f}s"
        return response

    _setup_logging(settings)

    # ── Services ─────────────────────────────────────────────────

    db_config = {
        "host": settings["database"]["host"],
        "port": settings["database"]["port"],
        "user": settings["database"]["user"],
        "password": settings["database"]["password"],
        "database": settings["database"]["name"],
    }

    db_service = DatabaseService(
        db_config,
        min_conn=settings["database"]["min_connections"],
        max_conn=settings["database"]["max_connections"],
        dashboard_schema=settings["database"].get("dashboard_schema", "dashboard"),
    )
    db_service.ensure_tables()

    ssh_service = SSHService(
        host=settings["server"]["host"],
        user=settings["server"]["user"],
        ssh_key=settings["server"].get("ssh_key"),
    )

    k8s_service = K8sService(
        ssh_service=ssh_service,
        namespace=settings["kubernetes"]["namespace"],
    )

    bg_director = BgDirectorService(
        host=settings["director"].get("host", "127.0.0.1"),
        node_port=settings["director"].get("port", 32479),
    )

    rmq_admin = RmqAdminService(
        host=settings["rmq"]["admin_host"],
        port=settings["rmq"]["admin_port"],
        username=settings["rmq"]["username"],
        password=settings["rmq"]["password"],
    )

    rmq_game = RmqGameService(
        host=settings["rmq"]["game_host"],
        port=settings["rmq"]["game_port"],
        username=settings["rmq"]["username"],
        password=settings["rmq"]["password"],
    )

    player_svc = PlayerService(db_service)
    economy_svc = EconomyService(db_service)
    guild_svc = GuildService(db_service)
    world_svc = WorldService(db_service)
    progression_svc = ProgressionService(db_service)
    character_svc = CharacterService(db_service)
    audit_svc = AuditService(db_service)
    chat_svc = ChatService(db_service, k8s_service, ssh_service)

    realtime_svc = RealtimeService(bg_director, rmq_admin, chat_svc)
    realtime_svc.start()

    _services = {
        "db": db_service,
        "ssh": ssh_service,
        "k8s": k8s_service,
        "bg_director": bg_director,
        "rmq_admin": rmq_admin,
        "rmq_game": rmq_game,
        "realtime": realtime_svc,
        "player": player_svc,
        "economy": economy_svc,
        "guild": guild_svc,
        "world": world_svc,
        "progression": progression_svc,
        "character": character_svc,
        "audit": audit_svc,
        "chat": chat_svc,
    }

    app.dune_settings = settings
    app.dune_services = _services

    # ── Blueprints ───────────────────────────────────────────────

    init_auth(app, settings)

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(health_bp, url_prefix="/api")
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(director_bp, url_prefix="/api/director")
    app.register_blueprint(server_bp, url_prefix="/api/server")
    app.register_blueprint(files_bp, url_prefix="/api/files")
    app.register_blueprint(chat_bp, url_prefix="/api/chat")
    app.register_blueprint(debug_bp, url_prefix="/api/debug")

    # ── SocketIO ─────────────────────────────────────────────────
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")
    register_websocket_handlers(socketio, settings)
    app.socketio = socketio

    # ── Rate Limiter ─────────────────────────────────────────────
    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=[],
        storage_uri="memory://",
    )
    app.limiter = limiter

    # ── Catch-all for React SPA ─────────────────────────────────
    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve_react(path):
        if path.startswith("api/") or path.startswith("server/") or path.startswith("static/") or path.startswith("assets/"):
            from app.models import ApiResponse, ErrorDetail
            return jsonify(ApiResponse(
                success=False,
                error=ErrorDetail(code="NotFound", message="Resource not found"),
            ).model_dump()), 404
        return send_from_directory(os.path.join(base_dir, "frontend", "dist"), "index.html")

    # ── Auto-detect namespace if empty ───────────────────────────
    if settings["kubernetes"]["namespace"] == "":
        try:
            k8s_service.auto_detect_namespace()
            if k8s_service.namespace:
                settings["kubernetes"]["namespace"] = k8s_service.namespace
        except Exception as e:
            logging.warning("Could not auto-detect K8s namespace: %s", e)

    return app


def _setup_logging(settings):
    log_level = getattr(logging, settings["logging"]["level"].upper(), logging.INFO)
    log_file = settings["logging"]["file"]
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=settings["logging"]["max_bytes"],
        backupCount=settings["logging"]["backup_count"],
    )
    handler.setFormatter(logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    ))
    handler.setLevel(log_level)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    console.setLevel(log_level)

    root = logging.getLogger()
    root.setLevel(log_level)
    root.addHandler(handler)
    root.addHandler(console)
