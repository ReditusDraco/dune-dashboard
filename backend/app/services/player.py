# Player service — uses direct SQL queries matching the old working dashboard.

import logging
from typing import List, Any

from app.services.database import DatabaseService

logger = logging.getLogger(__name__)

LIKE_PC = '%DunePlayerCharacter_C'


class PlayerService:
    def __init__(self, db: DatabaseService):
        self.db = db

    def search(self, term: str, limit: int = 50) -> list[dict]:
        where = "a.class LIKE %s"
        params: list[Any] = [LIKE_PC]
        if term:
            where += """ AND (
                ps.character_name ILIKE %s
                OR acc.funcom_id ILIKE %s
                OR ea.user ILIKE %s
            )"""
            params.extend([f'%{term}%'] * 3)

        sql = f"""
            SELECT
                ps.player_controller_id, ps.character_name, ps.online_status::text as online_status,
                ps.life_state, acc.funcom_id, ps.account_id,
                a.map, a.id as actor_id,
                pf.faction_id, f.name as faction_name,
                acc.last_login as last_login_time
            FROM dune.actors a
            JOIN dune.player_state ps ON (a.properties->>'m_PlayerControllerId')::bigint = ps.player_controller_id
            LEFT JOIN dune.actor_faction af ON a.id = af.actor_id
            LEFT JOIN dune.factions f ON af.faction_id = f.id
            LEFT JOIN dune.player_faction pf ON ps.player_controller_id = pf.player_controller_id
            LEFT JOIN dune.entity_actors ea ON a.owner_id = ea.id
            LEFT JOIN dune.accounts acc ON ea.id = acc.id
            WHERE {where}
            ORDER BY ps.character_name
            LIMIT %s
        """
        params.append(limit)
        try:
            return self.db.execute_readonly(sql, params)
        except Exception as e:
            logger.warning(f"Player search via actor join failed: {e}, trying fallback")
            return self._search_fallback(term, limit)

    def _search_fallback(self, term: str, limit: int = 50) -> list[dict]:
        """Fallback using only player_state and accounts."""
        where = "1=1"
        params: list[Any] = []
        if term:
            where = """(
                ps.character_name ILIKE %s
                OR acc.funcom_id ILIKE %s
            )"""
            params = [f'%{term}%', f'%{term}%']
        sql = f"""
            SELECT
                ps.player_controller_id, ps.character_name, ps.online_status::text as online_status,
                ps.life_state, acc.funcom_id, ps.account_id,
                NULL as map, NULL as actor_id,
                NULL as faction_id, NULL as faction_name,
                NULL as last_login_time
            FROM dune.player_state ps
            LEFT JOIN dune.accounts acc ON ps.account_id = acc.id
            WHERE {where}
            ORDER BY ps.character_name
            LIMIT %s
        """
        params.append(limit)
        try:
            return self.db.execute_readonly(sql, params)
        except Exception as e:
            logger.exception("Player search fallback failed")
            return []

    def get_detail(self, account_id: int) -> dict | None:
        sql = """
            SELECT
                ps.player_controller_id, ps.player_pawn_id, ps.character_name,
                ps.online_status::text as online_status, ps.life_state,
                ps.account_id, acc.funcom_id, acc.email as account_email,
                a.map, a.id as actor_id,
                f.name as faction_name, pf.faction_id,
                acc.last_login as last_login_time,
                ps.current_health, ps.max_health,
                ps.current_stamina, ps.max_stamina,
                ps.current_water, ps.max_water,
                ps.current_oxygen, ps.max_oxygen,
                ps.xp, ps.tech_knowledge
            FROM dune.player_state ps
            LEFT JOIN dune.accounts acc ON ps.account_id = acc.id
            LEFT JOIN dune.actors a ON (a.properties->>'m_PlayerControllerId')::bigint = ps.player_controller_id
            LEFT JOIN dune.player_faction pf ON ps.player_controller_id = pf.player_controller_id
            LEFT JOIN dune.factions f ON pf.faction_id = f.id
            WHERE ps.account_id = %s
            LIMIT 1
        """
        try:
            rows = self.db.execute_readonly(sql, [account_id])
            return rows[0] if rows else None
        except Exception as e:
            logger.warning(f"Player detail via actor failed: {e}, trying fallback")
            return self._get_detail_fallback(account_id)

    def _get_detail_fallback(self, account_id: int) -> dict | None:
        sql = """
            SELECT
                ps.player_controller_id, ps.player_pawn_id, ps.character_name,
                ps.online_status::text as online_status, ps.life_state,
                ps.account_id, acc.funcom_id, acc.email as account_email,
                NULL as map, NULL as actor_id,
                NULL as faction_name, NULL as faction_id,
                NULL as last_login_time,
                NULL as current_health, NULL as max_health,
                NULL as current_stamina, NULL as max_stamina,
                NULL as current_water, NULL as max_water,
                NULL as current_oxygen, NULL as max_oxygen,
                NULL as xp, NULL as tech_knowledge
            FROM dune.player_state ps
            LEFT JOIN dune.accounts acc ON ps.account_id = acc.id
            WHERE ps.account_id = %s
            LIMIT 1
        """
        try:
            rows = self.db.execute_readonly(sql, [account_id])
            return rows[0] if rows else None
        except Exception:
            return None

    def get_inventory(self, account_id: int) -> list[dict]:
        """Get player inventory items."""
        sql = """
            SELECT it.id, it.item_name, it.quantity, it.durability
            FROM dune.inventory_items it
            WHERE it.account_id = %s
            ORDER BY it.item_name
        """
        try:
            return self.db.execute_readonly(sql, [account_id])
        except Exception:
            return []

    def get_currency(self, player_id: int) -> list[dict]:
        """Get player currency balances."""
        sql = """
            SELECT currency_id, balance
            FROM dune.player_currency
            WHERE player_controller_id = %s
        """
        try:
            return self.db.execute_readonly(sql, [player_id])
        except Exception:
            return []

    def get_vitals(self, player_id: int) -> dict | None:
        """Get player vitals."""
        sql = """
            SELECT current_health, max_health, current_stamina, max_stamina,
                   current_water, max_water, current_oxygen, max_oxygen
            FROM dune.player_state
            WHERE player_controller_id = %s
            LIMIT 1
        """
        try:
            rows = self.db.execute_readonly(sql, [player_id])
            return rows[0] if rows else None
        except Exception:
            return None

    def get_landsraad(self, player_id: int) -> dict | None:
        return None

    def get_faction_reputation(self, player_id: int) -> list[dict]:
        return []

    def get_vehicles(self, player_id: int) -> list[dict]:
        try:
            sql = """
                SELECT a.id, a.class, a.map
                FROM dune.actors a
                JOIN dune.vehicle_instances vi ON a.id = vi.actor_id
                WHERE vi.owner_id = %s
            """
            return self.db.execute_readonly(sql, [player_id])
        except Exception:
            return []

    def get_buildings(self, pawn_id: int) -> list[dict]:
        try:
            sql = """
                SELECT a.id, a.class, a.map,
                       a.properties->>'m_bIsPowered' as is_powered,
                       a.properties->>'m_PowerLevel' as power_level
                FROM dune.actors a
                JOIN dune.buildings b ON a.id = b.id
                WHERE b.owner_id = %s
            """
            return self.db.execute_readonly(sql, [pawn_id])
        except Exception:
            return []

    def get_landclaims(self, account_id: int) -> list[dict]:
        return []

    def get_specialization(self, player_id: int) -> dict | None:
        return None

    def get_keystones(self, player_id: int) -> dict | None:
        return None

    def get_tags(self, account_id: int) -> list[str]:
        return []

    def is_online(self, player_id: int) -> bool:
        try:
            sql = """
                SELECT 1 FROM dune.player_state
                WHERE player_controller_id = %s AND online_status::text = 'Online'
                LIMIT 1
            """
            rows = self.db.execute_readonly(sql, [player_id])
            return len(rows) > 0
        except Exception:
            return False
