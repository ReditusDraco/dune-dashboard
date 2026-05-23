# Economy service — items, currency, vitals, vendors.

import logging
from typing import Any

from app.models import Inventory, Item, CurrencyBalance, Vitals
from app.services.database import DatabaseService

logger = logging.getLogger(__name__)

ALLOWED_ITEM_FIELDS = {"stack_size", "quality_level", "is_new", "durability", "max_durability", "ammo"}


class EconomyService:
    def __init__(self, db: DatabaseService):
        self.db = db

    # ── Inventory ─────────────────────────────────────────────────

    def get_inventory(self, account_id: int) -> list[Inventory]:
        return PlayerService(self.db)._get_inventory(account_id)

    def add_item(self, inventory_id: int, template_id: str, stack_size: int = 1, quality_level: int = 0) -> int:
        rows = self.db.call_function("add_item", [inventory_id, template_id, stack_size, quality_level])
        if rows and rows[0].get("id"):
            return rows[0]["id"]
        raise ValueError("Item add failed: no ID returned")

    def delete_item(self, item_id: int) -> bool:
        self.db.call_procedure("delete_item", [item_id])
        return True

    def delete_inventory_item(self, item_id: int, count: int) -> bool:
        self.db.call_procedure("delete_inventory_item", [item_id, count])
        return True

    # ── Item Editing (DB-ONLY direct UPDATE — validated) ──────────

    def edit_item_field(self, item_id: int, field: str, value: Any) -> bool:
        if field not in ALLOWED_ITEM_FIELDS:
            raise ValueError(f"Invalid field. Allowed: {', '.join(sorted(ALLOWED_ITEM_FIELDS))}")

        if field == "is_new":
            self.db.execute_mutation(
                "UPDATE dune.items SET is_new = %s WHERE id = %s",
                [bool(value), item_id],
            )
        elif field in ("durability", "max_durability", "ammo"):
            stats_path = {
                "durability": "{FItemStackAndDurabilityStats,CurrentDurability}",
                "max_durability": "{FItemStackAndDurabilityStats,DecayedMaxDurability}",
                "ammo": "{FWeaponItemStats,CurrentAmmo}",
            }[field]
            self.db.execute_mutation(
                "UPDATE dune.items SET stats = jsonb_set(stats, %s, to_jsonb(%s::text), true) WHERE id = %s",
                [stats_path.split(","), str(value), item_id],
            )
        else:
            self.db.execute_mutation(
                f"UPDATE dune.items SET {field} = %s WHERE id = %s",
                [int(value), item_id],
            )
        return True

    # ── Currency ──────────────────────────────────────────────────

    def get_currency(self, controller_id: int) -> list[CurrencyBalance]:
        rows = self.db.call_function("get_player_virtual_currency_balances", [controller_id])
        labels = {0: "Solari Credits", 1: "House Script", 2: "Spice"}
        return [CurrencyBalance(
            currency_id=r["currency_id"],
            currency_label=labels.get(r["currency_id"], f"Currency {r['currency_id']}"),
            balance=r.get("balance", 0),
        ) for r in rows]

    def adjust_currency(self, controller_id: int, currency_id: int, delta: int) -> int:
        rows = self.db.call_function("adjust_player_virtual_currency_balance", [controller_id, currency_id, delta])
        if rows and len(rows) > 0:
            return rows[0].get("balance", 0)
        raise ValueError("Currency adjustment failed")

    def set_currency(self, controller_id: int, currency_id: int, balance: int) -> bool:
        # DB-ONLY direct UPSERT — validated
        if balance < 0:
            raise ValueError("Balance cannot be negative")
        self.db.execute_mutation(
            """INSERT INTO dune.player_virtual_currency_balances (player_controller_id, currency_id, balance)
               VALUES (%s, %s, %s)
               ON CONFLICT (player_controller_id, currency_id) DO UPDATE SET balance = EXCLUDED.balance""",
            [controller_id, currency_id, balance],
        )
        return True

    # ── Vitals (DB-ONLY direct UPDATE — validated + offline check) ─

    def get_vitals(self, pawn_id: int) -> Vitals:
        rows = self.db.call_function("admin_get_character_details", [pawn_id])
        if not rows:
            return Vitals()
        # Character details returns by account_id, but we need pawn data
        # Fallback to actors query for vitals
        actor_rows = self.db.execute_readonly(
            """SELECT properties, gas_attributes FROM dune.actors WHERE id = %s""",
            [pawn_id],
        )
        if not actor_rows:
            return Vitals()
        row = actor_rows[0]
        props = row.get("properties") or {}
        gas = row.get("gas_attributes") or {}
        dmg = props.get("DamageableActorComponent") or {}
        hyd = gas.get("DuneHydrationAttributeSet") or {}
        spc = gas.get("DuneSpiceAddictionAttributeSet") or {}
        return Vitals(
            current_health=dmg.get("m_CurrentMaxHealth"),
            max_health=dmg.get("m_TotalMaxHealth"),
            current_hydration=(hyd.get("CurrentHydration") or {}).get("CurrentValue"),
            dehydration_penalty=(hyd.get("DehydrationPenalty") or {}).get("CurrentValue"),
            current_spice=(spc.get("CurrentSpice") or {}).get("CurrentValue"),
            spice_addiction_level=(spc.get("SpiceAddictionLevel") or {}).get("CurrentValue"),
            spice_tolerance=(spc.get("SpiceTolerance") or {}).get("CurrentValue"),
        )

    def set_vitals(self, pawn_id: int, health: float | None, max_health: float | None,
                   hydration: float, spice: float) -> bool:
        # DB-ONLY: Validate player is offline
        offline_check = self.db.execute_readonly(
            """SELECT 1 FROM dune.player_state
               WHERE player_pawn_id = %s AND online_status::text = 'Online'""",
            [pawn_id],
        )
        if offline_check:
            raise ValueError("Player must be offline to edit vitals")

        if health is not None and health < 0:
            raise ValueError("Health cannot be negative")
        if max_health is not None and max_health < 0:
            raise ValueError("Max health cannot be negative")
        if hydration < 0:
            raise ValueError("Hydration cannot be negative")
        if spice < 0:
            raise ValueError("Spice cannot be negative")

        if health is not None:
            self.db.execute_mutation(
                """UPDATE dune.actors SET properties = jsonb_set(
                    properties, '{DamageableActorComponent,m_CurrentMaxHealth}', to_jsonb(%s::float)
                ) WHERE id = %s""",
                [health, pawn_id],
            )
        if max_health is not None:
            self.db.execute_mutation(
                """UPDATE dune.actors SET properties = jsonb_set(
                    properties, '{DamageableActorComponent,m_TotalMaxHealth}', to_jsonb(%s::float)
                ) WHERE id = %s""",
                [max_health, pawn_id],
            )

        self.db.execute_mutation(
            """UPDATE dune.actors SET gas_attributes = jsonb_set(
                jsonb_set(jsonb_set(jsonb_set(gas_attributes,
                    '{DuneHydrationAttributeSet,CurrentHydration,CurrentValue}', to_jsonb(%s::float)),
                    '{DuneHydrationAttributeSet,CurrentHydration,BaseValue}', to_jsonb(%s::float)),
                    '{DuneSpiceAddictionAttributeSet,CurrentSpice,CurrentValue}', to_jsonb(%s::float)),
                '{DuneSpiceAddictionAttributeSet,CurrentSpice,BaseValue}', to_jsonb(%s::float)
            ) WHERE id = %s""",
            [hydration, hydration, spice, spice, pawn_id],
        )
        return True

    # ── Vendors ───────────────────────────────────────────────────

    def clean_vendor_stock(self, player_id: int) -> bool:
        self.db.call_procedure("clean_stock_for_player", [player_id])
        return True

    def get_tax_invoices(self, player_id: int) -> list[dict]:
        return self.db.call_function("taxation_get_all_invoices_for_player", [player_id])


# Import here to avoid circular dependency at module load time
from app.services.player import PlayerService
