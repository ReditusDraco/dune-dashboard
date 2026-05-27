# Chat service — chat history and log parsing.

import json
import logging
from datetime import datetime

from app.services.database import DashboardDatabaseService

logger = logging.getLogger(__name__)


class ChatService:
    def __init__(self, db: DashboardDatabaseService, k8s_service, ssh_service):
        self.db = db
        self.k8s = k8s_service
        self.ssh = ssh_service
        self.ensured_table = False

    def ensure_history_table(self):
        if self.ensured_table:
            return True
        try:
            self.db.execute_mutation("""
                CREATE TABLE IF NOT EXISTS dashboard.chat_history (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMP DEFAULT NOW(),
                    channel VARCHAR(50),
                    sender VARCHAR(255),
                    message TEXT,
                    target VARCHAR(255),
                    location_x FLOAT,
                    location_y FLOAT,
                    location_z FLOAT,
                    is_admin BOOLEAN DEFAULT FALSE
                )
            """)
            self.db.execute_mutation(
                "CREATE INDEX IF NOT EXISTS idx_chat_history_timestamp ON dashboard.chat_history (timestamp DESC)"
            )
            self.ensured_table = True
            logger.info("Chat history table ready")
            return True
        except Exception as e:
            logger.error("Failed to create chat history table: %s", e)
            return False

    def save_message(self, channel, sender, message, target="", location=None, is_admin=False):
        loc_x = location.get("X", 0) if location else 0
        loc_y = location.get("Y", 0) if location else 0
        loc_z = location.get("Z", 0) if location else 0
        return self.db.execute_mutation(
            """INSERT INTO dashboard.chat_history
               (channel, sender, message, target, location_x, location_y, location_z, is_admin)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            [channel, sender, message, target, loc_x, loc_y, loc_z, is_admin],
        )

    def get_history(self, limit: int = 200) -> list[dict]:
        return self.db.execute_readonly(
            """SELECT id, timestamp, channel, sender, message, target,
                      location_x, location_y, location_z, is_admin
               FROM dashboard.chat_history ORDER BY timestamp DESC LIMIT %s""",
            [limit],
        )

    def catch_up(self, namespace: str) -> int:
        db_messages = self.get_history(1)
        has_history = db_messages and len(db_messages) >= 10
        if has_history:
            return 0

        if not namespace:
            logger.warning("Cannot catch up — kubernetes namespace not set")
            return 0

        pod_name = self.k8s.get_text_router_pod()
        if not pod_name:
            logger.warning("Cannot catch up — no text-router pod found")
            return 0

        log_cmd = f"sudo kubectl logs -n {namespace} {pod_name} --tail=2000 2>/dev/null"
        out, err, rc = self.ssh.run(log_cmd, timeout=30)
        if rc != 0 or not out:
            logger.debug("Cannot catch up — failed to get pod logs (rc=%d)", rc)
            return 0

        lines = [line for line in out.split("\n") if "CLOG" in line and "TextChat" in line]
        lines = [line for line in lines if "Starting filtering" not in line]
        lines = [line for line in lines if "Skipping filtering" not in line]
        lines = [line for line in lines if "Redirected message" not in line]

        messages = []
        seen = set()
        for line in lines:
            if not line.strip():
                continue
            try:
                idx = line.index("received message from ")
                rest = line[idx + len("received message from "):]
                parts = rest.split(" to ", 1)
                if len(parts) < 2:
                    continue
                sender_id = parts[0].strip()
                target_and_json = parts[1]
                target_idx = target_and_json.index(": ")
                target = target_and_json[:target_idx].strip()
                msg_str = target_and_json[target_idx + 2:].strip()

                msg_data = json.loads(msg_str)
                content = json.loads(msg_data.get("content", "{}"))

                dedup_key = (
                    content.get("m_ChannelType", ""),
                    content.get("m_FuncomIdFrom", ""),
                    content.get("m_Message", {}).get("m_UnlocalizedMessage", ""),
                )
                if dedup_key in seen:
                    continue
                seen.add(dedup_key)

                messages.append({
                    "channel": content.get("m_ChannelType", "Unknown"),
                    "sender": content.get("m_FuncomIdFrom", sender_id),
                    "message": content.get("m_Message", {}).get("m_UnlocalizedMessage", ""),
                    "target": target,
                    "location": content.get("m_OriginLocation", {}),
                    "is_admin": False,
                })
            except (ValueError, KeyError, json.JSONDecodeError, IndexError):
                continue

        if messages:
            saved = self._save_batch(messages)
            logger.info("Caught up %d chat messages from pod logs", saved)
            return saved
        return 0

    def _save_batch(self, messages: list[dict]) -> int:
        if not messages:
            return 0
        count = 0
        for msg in messages:
            if self.save_message(
                msg["channel"], msg["sender"], msg["message"],
                msg.get("target", ""), msg.get("location"), msg.get("is_admin", False),
            ):
                count += 1
        return count
