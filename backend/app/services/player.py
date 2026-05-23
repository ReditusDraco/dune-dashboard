# Player service — player queries using DB functions only.

import logging
from typing import List

from app.models import PlayerDetail, PlayerSummary, Vitals, Inventory, Item
from app.models import CurrencyBalance, SpecializationTrack, Keystone
from app.models import FactionReputation, LandsraadInfo
from app.models import VehicleSummary, BuildingSummary, Landclaim
from app.services.database import DatabaseService

logger = logging.getLogger(__name__)


class PlayerService:
    def __init__(self, db: DatabaseService):
        self.db = db

    # ── Search & List ─────────────────────────────────────────────

    def search(self, term: str, limit: int = 50) -> list[PlayerSummary]:
        rows = self.db.call_function("admin_get_character_ids", [f"%{term}%"])
        if not rows:
            return []

        account_ids = [r.get("id") for r in rows if r.get("id")]
        if not account_ids:
            return []

        return self._resolve_accounts(account_ids)

    def _resolve_accounts(self, account_ids: list[int]) -> list[PlayerSummary]:
        summaries = []
        for account_id in account_ids:
            detail = self.db.call_function("admin_get_character_details", [account_id])
            if detail:
                row = detail[0]
                summaries.append(PlayerSummary(
                    player_controller_id=row.get("player_controller_id"),
                    character_name=row.get("character_name") or "Unknown",
                    account_email=row.get("account_email"),
                    funcom_id=row.get("funcom_id"),
                    faction_name=row.get("faction_name"),
                    faction_id=row.get("faction_id"),
                    map=row.get("map"),
                    online_status=row.get("online_status") or "Unknown",
                    life_state=row.get("life_state"),
                    last_login_time=row.get("last_login_time"),
                    last_avatar_activity=row.get("last_avatar_activity"),
                ))
        return summaries

    # ── Detail ──────────────────────────────────────────────────────

    def get_detail(self, account_id: int) -> PlayerDetail | None:
        char_rows = self.db.call_function("admin_get_character_details", [account_id])
        if not char_rows:
            return None
        row = char_rows[0]

        controller_id = row.get("player_controller_id")
        pawn_id = row.get("player_pawn_id")

        vitals = self._extract_vitals(row)
        currency = self._get_currency(controller_id)
        inventories = self._get_inventory(account_id)
        vehicles = self._get_vehicles(controller_id, account_id)
        buildings = self._get_buildings(pawn_id)
        landclaims = self._get_landclaims(account_id)
        spec = self._get_specialization(controller_id)
        keystones = self._get_keystones(controller_id)
        faction_rep = self._get_faction_reputation(controller_id)
        landsraad = self._get_landsraad(controller_id)
        tags = self._get_tags(account_id)
        is_online = self._check_online(controller_id)

        return PlayerDetail(
            id=row.get("id"),
            account_id=account_id,
            player_controller_id=controller_id,
            player_pawn_id=pawn_id,
            character_name=row.get("character_name") or "Unknown",
            account_email=row.get("account_email"),
            funcom_id=row.get("funcom_id"),
            faction_name=row.get("faction_name"),
            faction_id=row.get("faction_id"),
            map=row.get("map"),
            online_status=row.get("online_status") or "Unknown",
            life_state=row.get("life_state"),
            last_login_time=row.get("last_login_time"),
            last_avatar_activity=row.get("last_avatar_activity"),
            vitals=vitals,
            currency=currency,
            inventories=inventories,
            vehicles=vehicles,
            buildings=buildings,
            landclaims=landclaims,
            specialization=spec,
            keystones=keystones,
            faction_reputation=faction_rep,
            landsraad=landsraad,
            tags=tags,
            is_online=is_online,
        )

    def _extract_vitals(self, row: dict) -> Vitals:
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

    def _get_currency(self, controller_id: int | None) -> list[CurrencyBalance]:
        if not controller_id:
            return []
        rows = self.db.call_function("get_player_virtual_currency_balances", [controller_id])
        labels = {0: "Solari Credits", 1: "House Script", 2: "Spice"}
        return [CurrencyBalance(
            currency_id=r["currency_id"],
            currency_label=labels.get(r["currency_id"], f"Currency {r['currency_id']}"),
            balance=r.get("balance", 0),
        ) for r in rows]

    def _get_inventory(self, account_id: int) -> list[Inventory]:
        rows = self.db.call_function("admin_get_inventory_details", [account_id])
        if not rows:
            return []

        from app.utils.constants import INVENTORY_TYPE_LABELS
        inventories = {}
        for r in rows:
            inv_id = r.get("inventory_id")
            if inv_id not in inventories:
                inv_type = r.get("inventory_type", 0)
                inventories[inv_id] = Inventory(
                    inventory_id=inv_id,
                    actor_id=r.get("actor_id"),
                    inventory_type=inv_type,
                    inventory_type_label=INVENTORY_TYPE_LABELS.get(inv_type, f"Type {inv_type}"),
                    max_item_count=r.get("max_item_count"),
                    max_item_volume=r.get("max_item_volume"),
                    items=[],
                )
            stats = r.get("stats") or {}
            dur = stats.get("FItemStackAndDurabilityStats") or {}
            wpn = stats.get("FWeaponItemStats") or {}
            inventories[inv_id].items.append(Item(
                id=r.get("item_id"),
                template_id=r.get("template_id", ""),
                stack_size=r.get("count", 1),
                quality_level=r.get("quality_level", 0),
                is_new=r.get("is_new", False),
                position_index=r.get("position_index", 0),
                stats=stats,
                durability=dur.get("CurrentDurability") if isinstance(dur, dict) else None,
                max_durability=dur.get("DecayedMaxDurability") if isinstance(dur, dict) else None,
                ammo=wpn.get("CurrentAmmo") if isinstance(wpn, dict) else None,
            ))
        return list(inventories.values())

    def _get_vehicles(self, controller_id: int | None, account_id: int) -> list[VehicleSummary]:
        if not controller_id:
            return []
        rows = self.db.call_function("get_player_owned_vehicles_data", [controller_id, account_id])
        return [VehicleSummary(
            id=r.get("vehicle_id"),
            class_name=r.get("class", ""),
            display_name=self._vehicle_display_name(r.get("class", "")),
            map=r.get("map"),
        ) for r in rows]

    def _get_buildings(self, player_id: int | None) -> list[BuildingSummary]:
        if not player_id:
            return []
        # DB-READ: no function for buildings-by-owner
        rows = self.db.execute_readonly(
            """SELECT a.id, a.class, a.map, a.properties->>'m_bIsPowered' as is_powered,
                      a.properties->>'m_PowerLevel' as power_level
               FROM dune.buildings b JOIN dune.actors a ON b.id = a.id
               WHERE b.owner_id = %s ORDER BY a.map""",
            [player_id],
        )
        return [BuildingSummary(
            id=r["id"],
            class_name=r["class"],
            map=r["map"],
            owner_name="",  # known from context
            instance_count=0,
            is_powered=r.get("is_powered") == "True",
            power_level=r.get("power_level"),
        ) for r in rows]

    def _get_landclaims(self, account_id: int) -> list[Landclaim]:
        rows = self.db.execute_readonly(
            """SELECT DISTINCT a.id, a.class, a.map
               FROM dune.landclaim_segments lcs
               JOIN dune.actors a ON lcs.totem_id = a.id
               WHERE a.owner_account_id = %s""",
            [account_id],
        )
        return [Landclaim(id=r["id"], class_name=r["class"], map=r["map"]) for r in rows]

    def _get_specialization(self, controller_id: int | None) -> list[SpecializationTrack]:
        if not controller_id:
            return []
        rows = self.db.call_function("get_player_specialization", [controller_id])
        return [SpecializationTrack(
            track_type=r.get("track_type", ""),
            xp_amount=r.get("xp_amount", 0),
            level=r.get("level", 0),
        ) for r in rows]

    def _get_keystones(self, controller_id: int | None) -> list[Keystone]:
        if not controller_id:
            return []
        rows = self.db.call_function("get_player_keystones", [controller_id])
        return [Keystone(id=r.get("id", 0), name=r.get("name", "")) for r in rows]

    def _get_faction_reputation(self, controller_id: int | None) -> list[FactionReputation]:
        if not controller_id:
            return []
        rows = self.db.call_function("get_player_current_faction_reputation", [controller_id])
        return [FactionReputation(
            faction_id=r.get("out_faction_id"),
            faction_name="",  # resolved later if needed
            reputation_amount=r.get("out_reputation_amount", 0),
        ) for r in rows]

    def _get_landsraad(self, controller_id: int | None) -> LandsraadInfo:
        if not controller_id:
            return LandsraadInfo()
        rows = self.db.call_function("get_player_landsraad", [controller_id])
        if rows:
            r = rows[0]
            return LandsraadInfo(
                daily_reward_charges=r.get("daily_reward_charges"),
                last_viewed_term_id=r.get("last_viewed_term_id"),
                daily_reward_last_processed=r.get("daily_reward_last_processed"),
            )
        return LandsraadInfo()

    def _get_tags(self, account_id: int) -> list[str]:
        rows = self.db.call_function("admin_read_player_tags", [account_id])
        return [r.get("tag", "") for r in rows if r.get("tag")]

    def _check_online(self, controller_id: int | None) -> bool:
        if not controller_id:
            return False
        rows = self.db.call_function("get_player_ids_online_state", [[controller_id]])
        return bool(rows)

    # ── Utilities ─────────────────────────────────────────────────

    @staticmethod
    def _vehicle_display_name(cls: str) -> str:
        if "/" in cls:
            short = cls.split("/")[-1].replace("_C", "")
        else:
            short = cls.replace("_C", "")
        return short.replace("BP_", "").replace("_CHOAM", "").replace("_", " ")
