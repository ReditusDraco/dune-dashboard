"""Settings loader — reads settings.yaml with env var overrides."""

import os
import socket
import yaml
import logging
import copy
import secrets

logger = logging.getLogger(__name__)

DEFAULTS = {
    "server": {
        "host": "127.0.0.1",
        "user": "dune",
        "ssh_key": None,
        "local_ip": None,
    },
    "dashboard": {
        "host": "127.0.0.1",
        "port": 5050,
        "debug": False,
        "secret_key": None,
        "ssl_cert": None,
        "ssl_key": None,
        "ssl_domain": None,
        "ssl_email": None,
        "http_redirect": False,
        "http_redirect_port": 80,
    },
    "database": {
        "host": "127.0.0.1",
        "port": 15433,
        "user": "postgres",
        "password": None,
        "name": "dune",
        "schema": "dune",
        "min_connections": 2,
        "max_connections": 10,
        "owner": "dune",
        "dashboard_schema": "dashboard",
    },
    "kubernetes": {
        "namespace": "",
        "battlegroup_script": "/home/dune/.dune/bin/battlegroup",
    },
    "director": {
        "port": 32479,
        "host": "127.0.0.1",
    },
    "rmq": {
        "admin_host": "127.0.0.1",
        "admin_port": 32686,
        "game_host": "127.0.0.1",
        "game_port": 32021,
        "username": "admin",
        "password": None,
        "vhost": "%2f",
    },
    "filebrowser": {
        "port": 18888,
    },
    "firewall": {
        "block_filebrowser": True,
        "block_director": True,
    },
    "cache": {
        "chat_pod_ttl": 60,
        "chat_messages_ttl": 10,
        "static_data_ttl": 300,
        "bgd_ttl": 10,
        "rmq_ttl": 15,
    },
    "auth": {
        "enabled": True,
        "username": None,
        "password_hash": None,
        "shell_enabled": True,
    },
    "logging": {
        "level": "INFO",
        "file": "logs/dashboard.log",
        "debug_file": "logs/debug.log",
        "debug_enabled": False,
        "max_bytes": 10485760,
        "backup_count": 5,
    },
    "ssl": {
        "check_interval_hours": 24,
        "renewal_days_before_expiry": 30,
    },
    "maps": {
        "default_map": "HaggaBasin",
        "DeepDesert": {
            "image": "maps/Deep_Desert.webp",
            "label": "The Deep Desert",
            "bounds": {
                "min_x": -1268624.82,
                "max_x": 1163312.83,
                "min_y": -1266548.17,
                "max_y": 1162416.13,
            },
            "flip_y": False,
            "image_size": {"width": 8000, "height": 8000},
            "default_zoom": 0.15,
        },
        "HaggaBasin": {
            "image": "maps/HaggaBasin_8k.webp",
            "label": "Hagga Basin",
            "bounds": {
                "min_x": -456752.21,
                "max_x": 354547.46,
                "min_y": -450630.14,
                "max_y": 353821.95,
            },
            "flip_y": False,
            "image_size": {"width": 8000, "height": 8000},
            "default_zoom": 0.15,
        },
    },
}


def deep_merge(base, override):
    """Deep merge override dict into base dict."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _detect_local_ip():
    """Detect local IP address for VM connectivity."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(1)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        if local_ip:
            logger.debug(f"Detected local IP: {local_ip}")
            return local_ip
    except Exception as e:
        logger.debug(f"Could not detect local IP: {e}")
    return "127.0.0.1"


def _validate_server_host(settings):
    """Validate and fix server.host if invalid or placeholder."""
    server = settings.setdefault("server", {})
    host = server.get("host", "")

    local_ip = server.get("local_ip")
    if local_ip:
        local_ip_str = str(local_ip).strip()
        if local_ip_str and local_ip_str not in ("", "null", "None", "YOUR_SERVER_IP", "YOUR_VM_IP"):
            if local_ip_str.count(".") == 3 and all(part.isdigit() and 0 <= int(part) <= 255 for part in local_ip_str.split(".")):
                server["host"] = local_ip_str
                logger.info(f"Using server.local_ip override: {server['host']}")
                return settings

    host_str = str(host).strip() if host else ""
    invalid_hosts = ("", "YOUR_SERVER_IP", "YOUR_VM_IP", "null", "None")

    if host_str in invalid_hosts or not host_str:
        detected_ip = _detect_local_ip()
        server["host"] = detected_ip
        logger.warning(f"Invalid server.host detected, using auto-detected IP: {detected_ip}")
        logger.warning("To fix: Edit settings.yaml and set server.host to your VM's IP address")

    return settings


def _find_missing_keys(defaults, current, path=""):
    """Find keys present in defaults but missing in current."""
    missing = []
    for key, val in defaults.items():
        new_path = f"{path}.{key}" if path else key
        if key not in current:
            missing.append(new_path)
        elif isinstance(val, dict) and isinstance(current.get(key), dict):
            missing.extend(_find_missing_keys(val, current[key], new_path))
    return missing


def load_settings(settings_path=None):
    """Load settings from YAML file with defaults and env var overrides."""
    if settings_path is None:
        settings_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "settings.yaml")

    settings = copy.deepcopy(DEFAULTS)

    if os.path.exists(settings_path):
        try:
            with open(settings_path, "r") as f:
                file_settings = yaml.safe_load(f) or {}
            settings = deep_merge(settings, file_settings)
            logger.info(f"Settings loaded from {settings_path}")
        except Exception as e:
            logger.error(f"Failed to load settings from {settings_path}: {e}")
            logger.warning("Using default settings")
    else:
        logger.warning(f"Settings file not found at {settings_path}, using defaults")

    env_overrides = {}

    if os.environ.get("DUNE_SERVER_HOST"):
        env_overrides.setdefault("server", {})["host"] = os.environ["DUNE_SERVER_HOST"]
    if os.environ.get("DUNE_SERVER_USER"):
        env_overrides.setdefault("server", {})["user"] = os.environ["DUNE_SERVER_USER"]
    if os.environ.get("DUNE_DB_PASSWORD"):
        env_overrides.setdefault("database", {})["password"] = os.environ["DUNE_DB_PASSWORD"]
    if os.environ.get("DUNE_K8S_NAMESPACE"):
        env_overrides.setdefault("kubernetes", {})["namespace"] = os.environ["DUNE_K8S_NAMESPACE"]
    if os.environ.get("DUNE_AUTH_PASSWORD"):
        env_overrides.setdefault("auth", {})["password"] = os.environ["DUNE_AUTH_PASSWORD"]
    if os.environ.get("DUNE_DASHBOARD_PORT"):
        env_overrides.setdefault("dashboard", {})["port"] = int(os.environ["DUNE_DASHBOARD_PORT"])
    if os.environ.get("DUNE_RMQ_PASSWORD"):
        env_overrides.setdefault("rmq", {})["password"] = os.environ["DUNE_RMQ_PASSWORD"]

    if env_overrides:
        settings = deep_merge(settings, env_overrides)
        logger.info("Environment variable overrides applied")

    if not settings["dashboard"].get("secret_key"):
        settings["dashboard"]["secret_key"] = secrets.token_hex(32)
        logger.info("Generated secure SECRET_KEY")

    auth = settings.get("auth", {})
    password_migrated = False
    if auth.get("password") and not auth.get("password_hash"):
        try:
            from argon2 import PasswordHasher
            ph = PasswordHasher(time_cost=3, memory_cost=65536)
            settings["auth"]["password_hash"] = ph.hash(str(auth["password"]))
            del settings["auth"]["password"]
            password_migrated = True
            logger.info("Migrated plaintext password to Argon2 hash")
        except ImportError:
            logger.error("argon2-cffi not installed. Password hashing unavailable.")
            settings["auth"]["password_hash"] = None

    if password_migrated:
        settings["dashboard"]["secret_key"] = secrets.token_hex(32)
        logger.warning("Rotated secret_key to invalidate sessions after password migration")

    settings = _validate_server_host(settings)

    return settings


_settings_cache = None


def get_settings():
    """Get current settings (cached for performance)."""
    global _settings_cache
    if _settings_cache is None:
        _settings_cache = load_settings()
    return _settings_cache


def save_settings(settings):
    """Save settings to YAML file."""
    global _settings_cache
    settings_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "settings.yaml")
    try:
        with open(settings_path, "w") as f:
            yaml.safe_dump(settings, f, default_flow_style=False, sort_keys=False)
        _settings_cache = settings
        logger.info(f"Settings saved to {settings_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to save settings to {settings_path}: {e}")
        return False


def reload_settings():
    """Force reload settings from file."""
    global _settings_cache
    _settings_cache = load_settings()
    return _settings_cache
