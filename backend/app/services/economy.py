# Economy service — items, currency, vitals, vendors. Uses direct SQL.

import logging
from typing import Any

from app.services.database import DatabaseService

logger = logging.getLogger(__name__)


class EconomyService:
    def __init__(self, db: DatabaseService):
        self.db = db

    def get_inventory(self, account_id: int) -> list[dict]:
        try:
            return self.db.execute_readonly(
                """SELECT it.id, it.item_name, it.quantity, it.durability
                   FROM dune.inventory_items it
                   WHERE it.account_id = %s
                   ORDER BY it.item_name""",
                [account_id],
            )
        except Exception:
            return []

    def get_currency(self, player_id: int) -> list[dict]:
        try:
            return self.db.execute_readonly(
                """SELECT currency_id, balance
                   FROM dune.player_currency
                   WHERE player_controller_id = %s""",
                [player_id],
            )
        except Exception:
            return []

    def get_vitals(self, pawn_id: int) -> dict | None:
        try:
            rows = self.db.execute_readonly(
                """SELECT current_health, max_health, current_stamina,
                          max_stamina, current_water, max_water,
                          current_oxygen, max_oxygen
                   FROM dune.player_state
                   WHERE player_pawn_id = %s
                   LIMIT 1""",
                [pawn_id],
            )
            return rows[0] if rows else None
        except Exception:
            return None

    def add_item(self, inventory_id: int, template_id: str, stack_size: int = 1, quality_level: int = 0) -> int:
        sql = """INSERT INTO dune.inventory_items (inventory_id, template_id, quantity, quality_level)
                 VALUES (%s, %s, %s, %s) RETURNING id"""
        rows = self.db.execute_mutation(sql, [inventory_id, template_id, stack_size, quality_level])
        if rows and rows[0].get("id"):
            return rows[0]["id"]
        raise ValueError("Item add failed")

    def delete_item(self, item_id: int) -> bool:
        self.db.execute_mutation("DELETE FROM dune.inventory_items WHERE id = %s", [item_id])
        return True

    def edit_item_field(self, item_id: int, field: str, value: Any) -> bool:
        allowed = {"stack_size", "quality_level", "is_new", "durability", "max_durability", "ammo"}
        if field not in allowed:
            raise ValueError(f"Invalid field. Allowed: {', '.join(sorted(allowed))}")
        self.db.execute_mutation(
            f"UPDATE dune.items SET {field} = %s WHERE id = %s",
            [value, item_id],
        )
        return True
