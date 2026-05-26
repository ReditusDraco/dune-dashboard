"""RabbitMQ Game Management HTTP API client."""

import json
import logging

import httpx

logger = logging.getLogger(__name__)


class RmqGameService:
    def __init__(self, host: str, port: int, username: str, password: str):
        self.base_url = f"http://{host}:{port}"
        self.auth = (username, password)
        self.client = httpx.Client(base_url=self.base_url, auth=self.auth, timeout=15)
        logger.debug("RmqGameService initialized: %s", self.base_url)

    def _get(self, path: str) -> dict | list:
        try:
            resp = self.client.get(path)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            logger.error("RMQ Game GET %s failed: %s", path, e)
            raise RmqGameError(f"RMQ Game HTTP {e.response.status_code}")
        except httpx.ConnectError as e:
            logger.error("RMQ Game connection failed: %s", e)
            raise RmqGameError("Cannot connect to RMQ Game API")

    def _post(self, path: str, data: dict) -> dict:
        try:
            resp = self.client.post(path, json=data)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            logger.error("RMQ Game POST %s failed: %s", path, e)
            raise RmqGameError(f"RMQ Game HTTP {e.response.status_code}")
        except httpx.ConnectError as e:
            logger.error("RMQ Game connection failed: %s", e)
            raise RmqGameError("Cannot connect to RMQ Game API")

    # ── Overview ──────────────────────────────────────────────────

    def get_overview(self) -> dict:
        return self._get("/api/overview")

    def get_exchanges(self) -> list[dict]:
        return self._get("/api/exchanges")

    def get_queues(self) -> list[dict]:
        return self._get("/api/queues")

    # ── Publish ───────────────────────────────────────────────────

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

    # ── Broadcast ─────────────────────────────────────────────────

    def send_broadcast(self, message: str, title: str = "", duration: int = 30, server: str | None = None, partition: str | None = None) -> bool:
        """Send an in-game broadcast via the heartbeats exchange."""
        display_title = title or "Admin Broadcast"
        inner = {
            "ServerCommand": "ServiceBroadcast",
            "BroadcastType": "Generic",
            "BroadcastPayload": {
                "BroadcastDuration": duration,
                "LocalizedText": [
                    {"Key": "en", "Title": display_title, "Body": message},
                    {"Key": "en-US", "Title": display_title, "Body": message},
                ],
            },
        }
        body = {
            "Version": 2,
            "AuthToken": "Nu6VmPWUMvdPMeB7qErr",
            "MessageContent": inner,
        }
        return self.publish(
            exchange="heartbeats",
            routing_key="notifications",
            payload=json.dumps(body),
            payload_encoding="string",
            properties={
                "content_type": "application/json",
                "message_id": f"manual-service-broadcast-{int(time.time() * 1000)}",
                "app_id": "fls",
                "user_id": "fls_backend",
            },
        )

    # ── Chat Intercept ────────────────────────────────────────────

    def peek_chat_intercept(self, count: int = 10) -> list[dict]:
        """Peek messages from the chat.intercept queue."""
        return self.peek_messages("queue.intercept", count=count)

    def close(self):
        self.client.close()


class RmqGameError(Exception):
    pass


import time
