"""RabbitMQ Admin Management HTTP API client."""

import json
import logging
from typing import Any, Dict, List

import httpx

from app.models import RmqOverview, RmqQueueInfo

logger = logging.getLogger(__name__)


class RmqAdminService:
    def __init__(self, host: str, port: int, username: str, password: str):
        self.base_url = f"http://{host}:{port}"
        self.auth = (username, password)
        self.client = httpx.Client(base_url=self.base_url, auth=self.auth, timeout=15)
        logger.debug("RmqAdminService initialized: %s", self.base_url)

    def _get(self, path: str) -> dict | list:
        try:
            resp = self.client.get(path)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            logger.error("RMQ Admin GET %s failed: %s", path, e)
            raise RmqError(f"RMQ Admin HTTP {e.response.status_code}")
        except httpx.ConnectError as e:
            logger.error("RMQ Admin connection failed: %s", e)
            raise RmqError("Cannot connect to RMQ Admin API")

    def _post(self, path: str, data: dict) -> dict:
        try:
            resp = self.client.post(path, json=data)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            logger.error("RMQ Admin POST %s failed: %s", path, e)
            raise RmqError(f"RMQ Admin HTTP {e.response.status_code}")
        except httpx.ConnectError as e:
            logger.error("RMQ Admin connection failed: %s", e)
            raise RmqError("Cannot connect to RMQ Admin API")

    # ── Overview & Health ───────────────────────────────────────────

    def get_overview(self) -> RmqOverview:
        data = self._get("/api/overview")
        return RmqOverview(
            cluster_name=data.get("cluster_name", ""),
            node=data.get("node", ""),
            message_stats=data.get("message_stats", {}),
            queue_totals=data.get("queue_totals", {}),
            object_totals=data.get("object_totals", {}),
        )

    def get_nodes(self) -> list[dict]:
        return self._get("/api/nodes")

    def health_check(self) -> dict:
        return self._get("/api/health/checks/alarms")

    # ── Exchanges & Queues ────────────────────────────────────────

    def get_exchanges(self) -> list[dict]:
        return self._get("/api/exchanges")

    def get_queues(self) -> list[dict]:
        return self._get("/api/queues")

    def get_queue_info(self, name: str) -> dict:
        return self._get(f"/api/queues/%2f/{name}")

    def get_bindings(self) -> list[dict]:
        return self._get("/api/bindings")

    def get_consumers(self) -> list[dict]:
        return self._get("/api/consumers")

    def get_connections(self) -> list[dict]:
        return self._get("/api/connections")

    def get_channels(self) -> list[dict]:
        return self._get("/api/channels")

    # ── Publish / Consume ─────────────────────────────────────────

    def publish(
        self,
        exchange: str,
        routing_key: str,
        payload: str | dict,
        payload_encoding: str = "string",
        properties: dict | None = None,
    ) -> bool:
        body_payload = payload if isinstance(payload, str) else json.dumps(payload)
        body = {
            "routing_key": routing_key,
            "payload": body_payload,
            "payload_encoding": payload_encoding,
        }
        if properties:
            body["properties"] = properties
        result = self._post(f"/api/exchanges/%2f/{exchange}/publish", body)
        return result.get("routed", False)

    def peek_messages(self, queue: str, count: int = 5, ackmode: str = "ack_requeue_true") -> list[dict]:
        body = {"count": count, "ackmode": ackmode, "encoding": "auto"}
        return self._post(f"/api/queues/%2f/{queue}/get", body)

    def get_exchange_bindings(self, exchange: str) -> list[dict]:
        return self._get(f"/api/exchanges/%2f/{exchange}/bindings/source")

    def get_queue_bindings(self, queue: str) -> list[dict]:
        return self._get(f"/api/queues/%2f/{queue}/bindings")

    # ── Helpers ───────────────────────────────────────────────────

    def get_queue_depths(self) -> list[RmqQueueInfo]:
        queues = self.get_queues()
        return [
            RmqQueueInfo(
                name=q.get("name", ""),
                messages_ready=q.get("messages_ready", 0),
                messages_unacknowledged=q.get("messages_unacknowledged", 0),
                consumer_count=q.get("consumers", 0),
                state=q.get("state", ""),
            )
            for q in queues
        ]

    def publish_settings_update(self, payload: dict) -> bool:
        """Publish to the settingsUpdate fanout exchange."""
        return self.publish(
            exchange="settingsUpdate",
            routing_key="",
            payload=json.dumps(payload),
            properties={"content_type": "application/json"},
        )

    def close(self):
        self.client.close()


class RmqError(Exception):
    pass
