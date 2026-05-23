# Guild service — guild operations using DB functions only.

import logging

from app.models import GuildDetail, GuildMember, GuildSummary
from app.services.database import DatabaseService

logger = logging.getLogger(__name__)

GUILD_ROLES = {100: "Leader", 90: "Officer", 80: "Officer", 50: "Member", 1: "Member"}


class GuildService:
    def __init__(self, db: DatabaseService):
        self.db = db

    def list_all(self) -> list[GuildSummary]:
        rows = self.db.call_function("get_all_guilds", [])
        return [GuildSummary(
            guild_id=r.get("guild_id", 0),
            guild_name=r.get("guild_name", ""),
            guild_description=r.get("guild_description"),
            faction_name=r.get("faction_name"),
            member_count=r.get("member_count", 0),
            online_count=0,  # requires additional query if needed
        ) for r in rows]

    def get_detail(self, guild_id: int) -> GuildDetail | None:
        guild_rows = self.db.call_function("get_guild_data", [guild_id])
        if not guild_rows:
            return None
        g = guild_rows[0]
        member_rows = self.db.call_function("get_guild_members", [guild_id])
        members = [GuildMember(
            player_id=r.get("player_id", 0),
            role_id=r.get("role_id", 50),
            role_name=GUILD_ROLES.get(r.get("role_id", 50), f"Role {r.get('role_id', 50)}"),
            player_name=r.get("name", "Unknown"),
            online_status=r.get("online_status", "Unknown"),
        ) for r in member_rows]
        return GuildDetail(
            guild_id=g.get("guild_id", guild_id),
            guild_name=g.get("guild_name", ""),
            guild_description=g.get("guild_description"),
            faction_name=g.get("faction_name"),
            faction_id=g.get("guild_faction"),
            members=members,
        )

    def disband(self, guild_id: int) -> bool:
        self.db.call_procedure("disband_guild", [guild_id])
        return True

    def remove_member(self, guild_id: int, player_id: int, reason: int = 0) -> bool:
        self.db.call_procedure("remove_guild_members", [[player_id], guild_id, reason])
        return True

    def promote(self, guild_id: int, player_id: int, role_id: int) -> bool:
        self.db.call_procedure("promote_guild_member", [guild_id, player_id, role_id])
        return True

    def demote(self, guild_id: int, player_id: int, role_id: int) -> bool:
        self.db.call_procedure("demote_guild_member", [guild_id, player_id, role_id])
        return True
