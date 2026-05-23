# Character service — rename, delete, demo, cheater flags using DB functions.

import logging

from app.services.database import DatabaseService

logger = logging.getLogger(__name__)


class CharacterService:
    def __init__(self, db: DatabaseService):
        self.db = db

    def rename(self, account_id: int, name: str) -> bool:
        self.db.call_procedure("set_character_name", [account_id, name])
        return True

    def delete_character(self, actor_id: int) -> bool:
        self.db.call_procedure("delete_character", [actor_id])
        return True

    def delete_account(self, user_id: str, reason: str = "admin") -> bool:
        self.db.call_procedure("delete_account", [user_id, reason])
        return True

    def set_demo(self, user_id: str, state: str) -> bool:
        self.db.call_procedure("set_demo_state", [user_id, state])
        return True

    def flag_cheater(self, account_id: int, cheat_type: str) -> bool:
        self.db.call_procedure("flag_player_as_cheater", [account_id, cheat_type])
        return True

    def get_tags(self, account_id: int) -> list[str]:
        rows = self.db.call_function("admin_read_player_tags", [account_id])
        return [r.get("tag", "") for r in rows if r.get("tag")]

    def update_tags(self, account_id: int, add: list[str], remove: list[str]) -> bool:
        # DB-ONLY direct SQL — no function exists for tag management
        for tag in add:
            self.db.execute_mutation(
                "INSERT INTO dune.player_tags (account_id, tag) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                [account_id, tag],
            )
        if remove:
            self.db.execute_mutation(
                "DELETE FROM dune.player_tags WHERE account_id = %s AND tag = ANY(%s)",
                [account_id, remove],
            )
        return True
