# Audit logging service — persistent PostgreSQL storage.

import logging
from datetime import datetime

from app.services.database import DashboardDatabaseService

logger = logging.getLogger(__name__)


class AuditService:
    def __init__(self, db: DashboardDatabaseService):
        self.db = db

    def log(self, action: str, user: str, details: dict | None = None,
            target_player_id: int | None = None, severity: str = "info",
            source_ip: str | None = None) -> bool:
        try:
            self.db.execute_mutation(
                """INSERT INTO dashboard.audit_log
                   (action_type, user_name, target_player_id, details, source_ip, severity, created_at)
                   VALUES (%s, %s, %s, %s, %s, %s, NOW())""",
                [action, user, target_player_id, details or {}, source_ip, severity],
            )
            logger.info("Audit: %s by %s", action, user)
            return True
        except Exception as e:
            logger.error("Audit log failed: %s", e)
            return False

    def get_logs(self, action: str | None = None, user: str | None = None,
                 target_player_id: int | None = None, limit: int = 100,
                 offset: int = 0) -> list[dict]:
        sql = """SELECT id, action_type, user_name, target_player_id, details,
                        source_ip, severity, created_at
                 FROM dashboard.audit_log WHERE 1=1"""
        params = []
        if action:
            sql += " AND action_type = %s"
            params.append(action)
        if user:
            sql += " AND user_name = %s"
            params.append(user)
        if target_player_id:
            sql += " AND target_player_id = %s"
            params.append(target_player_id)
        sql += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        return self.db.execute_readonly(sql, params)

    def get_stats(self) -> dict:
        rows = self.db.execute_readonly(
            """SELECT action_type, COUNT(*) as cnt FROM dashboard.audit_log
               GROUP BY action_type"""
        )
        return {r["action_type"]: r["cnt"] for r in rows}

    def cleanup_old(self, days: int = 90) -> int:
        result = self.db.execute_mutation(
            "DELETE FROM dashboard.audit_log WHERE created_at < NOW() - INTERVAL '%s days'",
            [days],
        )
        logger.info("Audit cleanup: removed %d entries older than %d days", result, days)
        return result
