"""RMQ service - RabbitMQ Management HTTP API client."""

import json
import logging
import base64
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class RmqService:
    """RabbitMQ Management HTTP API client.

    Communicates with RMQ Admin (port 30325) and RMQ Game (port 32716)
    HTTP API endpoints via SSH tunnel (localhost).
    """

    def __init__(self, admin_port: int = 30325, game_port: int = 32716,
                 username: str = 'dashboard_admin', password: str = ''):
        self.admin_port = admin_port
        self.game_port = game_port
        self.username = username
        self.password = password
        self._auth = base64.b64encode(
            f"{username}:{password}".encode()).decode()
        logger.info("RmqService initialized: admin=localhost:%s game=localhost:%s",
                     admin_port, game_port)

    def _request(self, port: int, path: str, method: str = 'GET',
                 body: Any = None, timeout: int = 15) -> Optional[Any]:
        """Execute an HTTP request against an RMQ API.

        Args:
            port: Tunnel port (30325 for admin, 32716 for game).
            path: API path (e.g., '/api/overview').
            method: HTTP method.
            body: Optional JSON-serializable request body.
            timeout: Request timeout in seconds.

        Returns:
            Parsed JSON response, or None on failure.
        """
        url = f"http://127.0.0.1:{port}{path}"
        headers = {
            'Authorization': f'Basic {self._auth}',
        }
        if body is not None:
            headers['Content-Type'] = 'application/json'
            data = json.dumps(body).encode()
        else:
            data = None

        req = urllib.request.Request(url, data=data, headers=headers)

        if method != 'GET' and method != 'POST':
            req.method = method

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode()
                return json.loads(raw) if raw.strip() else {}
        except urllib.error.HTTPError as e:
            logger.warning("RMQ HTTP %s %s -> %s: %s", method, url, e.code,
                           e.read().decode()[:200] if e.fp else '')
            return None
        except Exception as e:
            logger.warning("RMQ request error %s %s: %s", method, url, e)
            return None

    @staticmethod
    def _encode_vhost(vhost: str = '/') -> str:
        return vhost.replace('/', '%2F')

    # ── Admin API (port 30325) ───────────────────────────────────────

    def overview(self) -> Optional[Dict]:
        """Cluster overview: node info, message stats, queue totals."""
        return self._request(self.admin_port, '/api/overview')

    def nodes(self) -> Optional[List]:
        """List nodes with memory and disk info."""
        return self._request(self.admin_port, '/api/nodes')

    def exchanges(self) -> Optional[List]:
        """List all exchanges with message stats."""
        return self._request(self.admin_port, '/api/exchanges')

    def queues(self) -> Optional[List]:
        """List all queues with consumer counts and message depths."""
        return self._request(self.admin_port, '/api/queues')

    def bindings(self) -> Optional[List]:
        """List all bindings (source -> destination mappings)."""
        return self._request(self.admin_port, '/api/bindings')

    def consumers(self) -> Optional[List]:
        """List active consumers."""
        return self._request(self.admin_port, '/api/consumers')

    def connections(self) -> Optional[List]:
        """List active AMQP connections."""
        return self._request(self.admin_port, '/api/connections')

    def channels(self) -> Optional[List]:
        """List active channels."""
        return self._request(self.admin_port, '/api/channels')

    def health(self) -> Optional[Dict]:
        """Cluster health and alarm status."""
        return self._request(self.admin_port,
                             '/api/health/checks/alarms')

    def peek_messages(self, queue_name: str, vhost: str = '/',
                      count: int = 5) -> Optional[List]:
        """Peek at messages in a queue without consuming them."""
        vh = self._encode_vhost(vhost)
        body = {
            'count': count,
            'ackmode': 'ack_requeue_true',
            'encoding': 'auto',
        }
        return self._request(self.admin_port,
                             f'/api/queues/{vh}/{queue_name}/get',
                             method='POST', body=body)

    def publish(self, exchange: str, routing_key: str, message: Any,
                vhost: str = '/') -> Optional[Dict]:
        """Publish a message to an exchange.

        NOTE: RMQ HTTP API sets user_id to the authenticated username,
        which the game server may reject. For ServerCommands on the
        game RPC exchange, use the Erlang eval approach instead.
        """
        vh = self._encode_vhost(vhost)
        body = {
            'properties': {},
            'routing_key': routing_key,
            'payload': json.dumps(message) if not isinstance(message, str)
                       else message,
            'payload_encoding': 'string',
        }
        return self._request(self.admin_port,
                             f'/api/exchanges/{vh}/{exchange}/publish',
                             method='POST', body=body)

    def get_queue_bindings(self, queue_name: str,
                           vhost: str = '/') -> Optional[List]:
        vh = self._encode_vhost(vhost)
        return self._request(self.admin_port,
                             f'/api/queues/{vh}/{queue_name}/bindings')

    def get_exchange_bindings(self, exchange: str,
                               vhost: str = '/') -> Optional[List]:
        vh = self._encode_vhost(vhost)
        return self._request(self.admin_port,
                             f'/api/exchanges/{vh}/{exchange}/bindings/source')

    # ── Game API (port 32716) ────────────────────────────────────────

    def game_overview(self) -> Optional[Dict]:
        """Game RMQ cluster overview."""
        return self._request(self.game_port, '/api/overview')

    def game_queues(self) -> Optional[List]:
        """Game RMQ queues."""
        return self._request(self.game_port, '/api/queues')

    def game_exchanges(self) -> Optional[List]:
        """Game RMQ exchanges."""
        return self._request(self.game_port, '/api/exchanges')

    def game_publish(self, exchange: str, routing_key: str,
                     message: Any, vhost: str = '/') -> Optional[Dict]:
        """Publish a message to the game RMQ."""
        vh = self._encode_vhost(vhost)
        body = {
            'properties': {},
            'routing_key': routing_key,
            'payload': json.dumps(message) if not isinstance(message, str)
                       else message,
            'payload_encoding': 'string',
        }
        return self._request(self.game_port,
                             f'/api/exchanges/{vh}/{exchange}/publish',
                             method='POST', body=body)

    # ── Combined / convenience ───────────────────────────────────────

    def combined_overview(self) -> Dict[str, Any]:
        """Get overview from both RMQ instances."""
        return {
            'admin': self.overview(),
            'game': self.game_overview(),
        }

    def combined_queues(self) -> Dict[str, Any]:
        """Get queues from both RMQ instances."""
        return {
            'admin': self.queues(),
            'game': self.game_queues(),
        }

    def combined_exchanges(self) -> Dict[str, Any]:
        """Get exchanges from both RMQ instances."""
        return {
            'admin': self.exchanges(),
            'game': self.game_exchanges(),
        }
