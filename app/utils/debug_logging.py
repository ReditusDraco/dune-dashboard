"""Enhanced logging utilities with debug logging and sanitization."""

import logging
import logging.handlers
import re
import os
from typing import Any, Dict, Optional


# Sensitive field patterns that should be sanitized
SENSITIVE_KEYS = {
    'password', 'passwd', 'pwd', 'secret', 'token', 'api_key', 'apikey',
    'auth', 'authorization', 'credential', 'private_key', 'ssh_key',
    'session', 'cookie', 'jwt', 'access_token', 'refresh_token',
    'credit_card', 'cvv', 'ssn', 'birth_date', 'dob', 'key', 'keyfile',
    'cert', 'certificate', 'secret_key', 'secret_key', 'salt', 'iv',
    'hmac', 'signature', 'encrypt', 'decrypt', 'connection_string',
    'connection', 'host', 'port'  # host/port can be sensitive in some contexts
}

# Patterns for sensitive data detection - enhanced
SENSITIVE_PATTERNS = [
    # JWT tokens
    (re.compile(r'eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+'), '[JWT_TOKEN]'),
    (re.compile(r'Bearer\s+[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+'), '[BEARER_TOKEN]'),
    # Password patterns
    (re.compile(r'(?i)(password|passwd|pwd)\s*[=:]\s*[^\s&"\'<]+'), 'password=[REDACTED]'),
    (re.compile(r'(?i)(secret|api_key|apikey|auth_token)\s*[=:]\s*[^\s&"\'<]+'), 'secret=[REDACTED]'),
    # Connection strings with passwords
    (re.compile(r'(?i)(postgresql|mysql|mongodb|redis)://[^\s]+:[^\s]+@'), '[DB_CONNECTION]'),
    # Authorization headers
    (re.compile(r'(?i)Authorization:\s*[^\s]+'), 'Authorization: [REDACTED]'),
    # SSH keys
    (re.compile(r'-----BEGIN\s+(RSA|DSA|EC|OPENSSH)\s+PRIVATE\s+KEY-----'), '[SSH_PRIVATE_KEY]'),
    # AWS keys pattern
    (re.compile(r'AKIA[0-9A-Z]{16}'), '[AWS_KEY]'),
    # IP addresses in sensitive contexts (optional - may want to keep IPs)
    # (re.compile(r'\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b'), '[IP]'),
]


def sanitize_value(value: Any, max_length: int = 100) -> str:
    """Sanitize a single value for logging."""
    if value is None:
        return 'null'
    
    if isinstance(value, (int, float, bool)):
        return str(value)
    
    if isinstance(value, dict):
        return sanitize_dict(value, max_length)
    
    if isinstance(value, (list, tuple)):
        items = [sanitize_value(v, max_length) for v in value[:5]]
        return f"[{', '.join(items)}]"
    
    s = str(value)
    
    if len(s) > max_length:
        return s[:max_length] + '...'
    
    return s


def sanitize_dict(data: Dict, max_length: int = 100, _depth: int = 0) -> str:
    """Sanitize a dictionary for logging."""
    if _depth > 2:
        return '[nested]'
    
    sanitized = {}
    for key, value in data.items():
        key_lower = key.lower()
        
        if any(sk in key_lower for sk in SENSITIVE_KEYS):
            sanitized[key] = '[REDACTED]'
        else:
            sanitized[key] = sanitize_value(value, max_length)
    
    return str(sanitized)


def sanitize_for_log(data: Any) -> str:
    """Main sanitization function for any data before logging."""
    try:
        if isinstance(data, dict):
            return sanitize_dict(data)
        elif isinstance(data, str):
            for pattern, replacement in SENSITIVE_PATTERNS:
                data = pattern.sub(replacement, data)
            return data
        else:
            return sanitize_value(data)
    except Exception:
        return '[unserializable]'


def create_debug_log_handler(log_file: str, max_bytes: int = 10485760, backup_count: int = 5):
    """Create a rotating file handler for debug logs."""
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count
    )
    handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    handler.setLevel(logging.DEBUG)
    
    return handler


def log_request_details(logger: logging.Logger, request, include_body: bool = False):
    """Log detailed request information for debugging."""
    if not logger.isEnabledFor(logging.DEBUG):
        return
    
    details = {
        'method': request.method,
        'path': request.path,
        'query': request.query_string.decode() if request.query_string else None,
        'remote_addr': request.remote_addr,
        'user_agent': request.headers.get('User-Agent', 'Unknown'),
    }
    
    if request.is_json:
        details['content_type'] = 'application/json'
    
    logger.debug(f"Request: {sanitize_for_log(details)}")


def log_response_details(logger: logging.Logger, response, duration_ms: float):
    """Log detailed response information for debugging."""
    if not logger.isEnabledFor(logging.DEBUG):
        return
    
    details = {
        'status_code': response.status_code,
        'content_length': response.content_length,
        'duration_ms': round(duration_ms, 2)
    }
    
    logger.debug(f"Response: {sanitize_for_log(details)}")


def log_ssh_command(logger: logging.Logger, command: str, sanitize: bool = True):
    """Log SSH command execution."""
    if not logger.isEnabledFor(logging.DEBUG):
        return
    
    if sanitize:
        cmd_to_log = sanitize_for_log(command)
    else:
        cmd_to_log = command
    
    logger.debug(f"SSH command: {cmd_to_log}")


def log_ssh_result(logger: logging.Logger, stdout: str, stderr: str, rc: int):
    """Log SSH command result."""
    if not logger.isEnabledFor(logging.DEBUG):
        return
    
    logger.debug(f"SSH result: rc={rc}, stdout_len={len(stdout)}, stderr_len={len(stderr)}")
    if stderr:
        logger.debug(f"SSH stderr: {stderr[:200]}")


def log_database_query(logger: logging.Logger, query: str, params: Optional[tuple] = None):
    """Log database query for debugging."""
    if not logger.isEnabledFor(logging.DEBUG):
        return
    
    query_log = query
    if params:
        query_log = f"{query} | params: {sanitize_for_log(params)}"
    
    logger.debug(f"DB query: {query_log[:500]}")


def log_service_call(logger: logging.Logger, service: str, method: str, **kwargs):
    """Log service method call."""
    if not logger.isEnabledFor(logging.DEBUG):
        return
    
    safe_kwargs = {k: sanitize_for_log(v) for k, v in kwargs.items() if k != 'password'}
    logger.debug(f"Service call: {service}.{method}({safe_kwargs})")


class DebugLogger:
    """Enhanced logger wrapper with debug capabilities."""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self._debug_file_handler = None
    
    def set_debug_file(self, log_file: str):
        """Add a debug file handler."""
        if self._debug_file_handler is None:
            self._debug_file_handler = create_debug_log_handler(log_file)
            self.logger.addHandler(self._debug_file_handler)
            self.logger.setLevel(logging.DEBUG)
    
    def debug_dict(self, message: str, data: Dict):
        """Log a dictionary with sanitization."""
        self.logger.debug(f"{message}: {sanitize_for_log(data)}")
    
    def debug_request(self, request):
        """Log HTTP request details."""
        log_request_details(self.logger, request)
    
    def debug_response(self, response, duration_ms: float):
        """Log HTTP response details."""
        log_response_details(self.logger, response, duration_ms)
    
    def debug_ssh(self, command: str, result: tuple = None):
        """Log SSH command and optionally result."""
        log_ssh_command(self.logger, command)
        if result:
            stdout, stderr, rc = result
            log_ssh_result(self.logger, stdout, stderr, rc)
    
    def debug_db(self, query: str, params: tuple = None):
        """Log database query."""
        log_database_query(self.logger, query, params)


def get_debug_logger(name: str) -> DebugLogger:
    """Get a debug logger instance."""
    return DebugLogger(name)


# Auto-sanitizing debug log function
def debug(logger: logging.Logger, message: str, *args, **kwargs):
    """Debug logging that auto-sanitizes all arguments before logging."""
    if not logger.isEnabledFor(logging.DEBUG):
        return
    
    # Sanitize all positional arguments
    sanitized_args = tuple(sanitize_for_log(arg) for arg in args)
    
    # Sanitize all keyword argument values
    sanitized_kwargs = {k: sanitize_for_log(v) for k, v in kwargs.items()}
    
    logger.debug(message, *sanitized_args, **sanitized_kwargs)


def info(logger: logging.Logger, message: str, *args, **kwargs):
    """Info logging that sanitizes sensitive data."""
    sanitized_args = tuple(sanitize_for_log(arg) for arg in args)
    sanitized_kwargs = {k: sanitize_for_log(v) for k, v in kwargs.items()}
    logger.info(message, *sanitized_args, **sanitized_kwargs)


def warning(logger: logging.Logger, message: str, *args, **kwargs):
    """Warning logging that sanitizes sensitive data."""
    sanitized_args = tuple(sanitize_for_log(arg) for arg in args)
    sanitized_kwargs = {k: sanitize_for_log(v) for k, v in kwargs.items()}
    logger.warning(message, *sanitized_args, **sanitized_kwargs)