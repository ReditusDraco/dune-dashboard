# Guild service — uses direct SQL matching old working dashboard.

import logging

from app.services.database import DatabaseService

logger = logging.getLogger(__name__)

GUILD_ROLES = {100: "Leader", 90: "Officer", 80: "Officer", 50: "Member", 1: "Member"}


class GuildService:
    def __init__(self, db: DatabaseService):
        self.db = db

    def list_all(self) -> list[dict]:
        try:
            return self.db.execute_readonly("""
                SELECT g.id as guild_id, g.name as guild_name,
                       g.description as guild_description,
                       f.name as faction_name,
                       (SELECT COUNT(*) FROM dune.guild_members gm WHERE gm.guild_id = g.id) as member_count
                FROM dune.guilds g
                LEFT JOIN dune.factions f ON g.faction_id = f.id
                ORDER BY g.id
            """)
        except Exception as e:
            logger.warning(f"Guild list via faction join failed: {e}, trying fallback")
            try:
                return self.db.execute_readonly("""
                    SELECT g.id as guild_id, g.name as guild_name,
                           g.description as guild_description,
                           NULL as faction_name,
                           (SELECT COUNT(*) FROM dune.guild_members gm WHERE gm.guild_id = g.id) as member_count
                    FROM dune.guilds g
                    ORDER BY g.id
                """)
            except Exception:
                return []

    def get_detail(self, guild_id: int) -> dict | None:
        try:
            guild_rows = self.db.execute_readonly("""
                SELECT g.id as guild_id, g.name as guild_name,
                       g.description as guild_description,
                       f.name as faction_name, g.faction_id as guild_faction,
                       (SELECT COUNT(*) FROM dune.guild_members gm WHERE gm.guild_id = g.id) as member_count
                FROM dune.guilds g
                LEFT JOIN dune.factions f ON g.faction_id = f.id
                WHERE g.id = %s
            """, [guild_id])
        except Exception:
            guild_rows = self.db.execute_readonly("""
                SELECT g.id as guild_id, g.name as guild_name,
                       g.description as guild_description,
                       NULL as faction_name, NULL as guild_faction,
                       (SELECT COUNT(*) FROM dune.guild_members gm WHERE gm.guild_id = g.id) as member_count
                FROM dune.guilds g
                WHERE g.id = %s
            """, [guild_id])

        if not guild_rows:
            return None

        g = guild_rows[0]
        try:
            member_rows = self.db.execute_readonly("""
                SELECT gm.player_id, gm.role_id, ps.character_name as name,
                       ps.online_status::text as online_status
                FROM dune.guild_members gm
                LEFT JOIN dune.player_state ps ON gm.player_id = ps.player_controller_id
                WHERE gm.guild_id = %s
            """, [guild_id])
        except Exception:
            member_rows = self.db.execute_readonly("""
                SELECT gm.player_id, gm.role_id, NULL as name, NULL as online_status
                FROM dune.guild_members gm
                WHERE gm.guild_id = %s
            """, [guild_id])

        members = [{
            "player_id": r.get("player_id"),
            "role_id": r.get("role_id"),
            "role_name": GUILD_ROLES.get(r.get("role_id", 50), "Member"),
            "name": r.get("name") or "Unknown",
            "online_status": r.get("online_status") or "Unknown",
        } for r in (member_rows or [])]

        return {
            "guild_id": g.get("guild_id"),
            "guild_name": g.get("guild_name", ""),
            "guild_description": g.get("guild_description"),
            "faction_name": g.get("faction_name"),
            "faction_id": g.get("guild_faction"),
            "members": members,
        }

    def disband(self, guild_id: int) -> bool:
        try:
            self.db.execute_mutation("SELECT dune.disband_guild(%s)", [guild_id])
            return True
        except Exception:
            return False

    def remove_member(self, guild_id: int, player_id: int, reason: int = 0) -> bool:
        try:
            self.db.execute_mutation(
                "DELETE FROM dune.guild_members WHERE guild_id = %s AND player_id = %s",
                [guild_id, player_id],
            )
            return True
        except Exception:
            return False

    def promote(self, guild_id: int, player_id: int, role_id: int) -> bool:
        try:
            self.db.execute_mutation(
                "UPDATE dune.guild_members SET role_id = %s WHERE guild_id = %s AND player_id = %s",
                [role_id, guild_id, player_id],
            )
            return True
        except Exception:
            return False
