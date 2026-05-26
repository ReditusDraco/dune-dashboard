"""Realtime service — SSE broadcaster + BGD/RMQ poller."""

import asyncio
import json
import logging
import threading
import time
from typing import Any, Callable, Dict, Set

logger = logging.getLogger(__name__)


class SseClient:
    """Simple wrapper for an SSE client connection."""
    def __init__(self, queue: asyncio.Queue):
        self.queue = queue
        self.connected_at = time.time()


class RealtimeService:
    def __init__(self, bg_director, rmq_admin, chat_service):
        self.bg_director = bg_director
        self.rmq_admin = rmq_admin
        self.chat_service = chat_service
        self._clients: Set[asyncio.Queue] = set()
        self._lock = threading.Lock()
        self._previous_bg: dict | None = None
        self._running = False
        self._bgd_task = None
        self._rmq_task = None

    # ── Client Management ─────────────────────────────────────────

    def add_client(self, queue: asyncio.Queue):
        with self._lock:
            self._clients.add(queue)
        logger.debug("SSE client added. Total: %d", len(self._clients))

    def remove_client(self, queue: asyncio.Queue):
        with self._lock:
            self._clients.discard(queue)
        logger.debug("SSE client removed. Total: %d", len(self._clients))

    async def _broadcast(self, event: str, data: dict):
        """Broadcast an event to all connected SSE clients."""
        payload = f"event: {event}\ndata: {json.dumps(data)}\n\n"
        with self._lock:
            dead = set()
            for queue in self._clients:
                try:
                    queue.put_nowait(payload)
                except asyncio.QueueFull:
                    dead.add(queue)
                except Exception:
                    dead.add(queue)
            self._clients -= dead

    # ── Background Polling ──────────────────────────────────────

    def start(self):
        if self._running:
            return
        self._running = True
        self._bgd_task = threading.Thread(target=self._bgd_poll_loop, daemon=True)
        self._bgd_task.start()
        self._rmq_task = threading.Thread(target=self._rmq_poll_loop, daemon=True)
        self._rmq_task.start()
        logger.info("RealtimeService started")

    def stop(self):
        self._running = False
        logger.info("RealtimeService stopped")

    def _bgd_poll_loop(self):
        """Poll BGD every 10 seconds and broadcast deltas."""
        while self._running:
            try:
                bg = self.bg_director.get_battlegroup()
                current = bg.model_dump() if hasattr(bg, "model_dump") else bg.__dict__
                delta = self._compute_bg_delta(self._previous_bg, current)
                if delta:
                    asyncio.run(self._broadcast("battlegroup_update", delta))
                self._previous_bg = current
            except Exception as e:
                logger.warning("BGD poll failed: %s", e)
                asyncio.run(self._broadcast("connection_status", {"bgd": False}))
            time.sleep(10)

    def _rmq_poll_loop(self):
        """Poll RMQ every 30 seconds and broadcast health."""
        while self._running:
            try:
                overview = self.rmq_admin.get_overview()
                data = {
                    "cluster_name": overview.cluster_name,
                    "queue_totals": overview.queue_totals,
                    "message_stats": overview.message_stats,
                }
                asyncio.run(self._broadcast("rmq_health", data))
            except Exception as e:
                logger.warning("RMQ poll failed: %s", e)
                asyncio.run(self._broadcast("connection_status", {"rmq": False}))
            time.sleep(30)

    def _compute_bg_delta(self, previous: dict | None, current: dict) -> dict | None:
        """Compute meaningful deltas between battlegroup states."""
        if not previous:
            return {
                "online_count": self._count_online(current),
                "intransit_count": len(current.get("intransit_players", [])),
                "server_statuses": self._extract_server_statuses(current),
                "map_counts": self._extract_map_counts(current),
            }

        prev_online = self._count_online(previous)
        curr_online = self._count_online(current)
        prev_statuses = self._extract_server_statuses(previous)
        curr_statuses = self._extract_server_statuses(current)

        delta = {}
        if curr_online != prev_online:
            delta["online_count"] = curr_online
        if len(current.get("intransit_players", [])) != len(previous.get("intransit_players", [])):
            delta["intransit_count"] = len(current.get("intransit_players", []))
        if curr_statuses != prev_statuses:
            delta["server_statuses"] = curr_statuses

        return delta if delta else None

    def _count_online(self, state: dict) -> int:
        return len(state.get("online_players", []))

    def _extract_server_statuses(self, state: dict) -> dict:
        statuses = {}
        for key in ["dimension_maps", "single_server_maps", "instanced_maps"]:
            for mg in state.get(key, []):
                for sv in mg.get("servers", []):
                    partition = sv.get("partition", "")
                    if partition:
                        statuses[partition] = sv.get("status", "unknown")
        return statuses

    def _extract_map_counts(self, state: dict) -> dict:
        counts = {}
        for key in ["dimension_maps", "single_server_maps", "instanced_maps"]:
            for mg in state.get(key, []):
                name = mg.get("name", "")
                if name:
                    counts[name] = sum(sv.get("num_players", 0) for sv in mg.get("servers", []))
        return counts

    # ── Event Helpers ───────────────────────────────────────────

    async def notify_chat_message(self, msg: dict):
        await self._broadcast("chat_message", msg)

    async def notify_server_event(self, event: dict):
        await self._broadcast("server_event", event)

    async def notify_player_event(self, event: dict):
        await self._broadcast("player_event", event)

    async def notify_connection_status(self, status: dict):
        await self._broadcast("connection_status", status)
