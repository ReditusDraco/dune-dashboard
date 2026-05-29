"""Player service - player queries and operations"""

import logging

logger = logging.getLogger(__name__)

LIKE_PC = '%DunePlayerCharacter_C'


def _build_player_filters(search='', faction_id='', guild_id='', map_filter='', online_filter=''):
    """Build WHERE clause and params for player queries.

    Returns (where_clause, params) tuple.
    """
    where = ["a.class LIKE %s"]
    params = [LIKE_PC]

    if search:
        where.append("""(
            ps.character_name ILIKE %s
            OR acc.funcom_id ILIKE %s
            OR ea.user ILIKE %s
            OR a.properties::text ILIKE %s
        )""")
        params.extend([f'%{search}%'] * 4)
    if faction_id:
        where.append("pf.faction_id = %s")
        params.append(faction_id)
    if guild_id:
        where.append("gm.guild_id = %s")
        params.append(guild_id)
    if map_filter:
        where.append("a.map = %s")
        params.append(map_filter)
    if online_filter == 'online':
        where.append("ps.online_status::text = 'Online'")
    elif online_filter == 'offline':
        where.append("ps.online_status::text = 'Offline'")

    return ' AND '.join(where), params


class PlayerService:
    def __init__(self, db_service, dash_db=None):
        self.db = db_service
        self.dash_db = dash_db

    def is_online(self, player_controller_id):
        result = self.db.query(
            "SELECT 1 FROM dune.player_state WHERE player_controller_id = %s AND online_status::text = 'Online' LIMIT 1",
            [player_controller_id],
            one=True
        )
        return bool(result)

    def get_overview_counts(self):
        return self.db.query("""
            SELECT
                (SELECT COUNT(*) FROM dune.accounts) as account_count,
                (SELECT COUNT(*) FROM dune.player_state) as player_count,
                (SELECT COUNT(*) FROM dune.vehicles) as vehicle_count,
                (SELECT COUNT(*) FROM dune.buildings) as building_count,
                (SELECT COUNT(*) FROM dune.guilds) as guild_count,
                (SELECT COUNT(*) FROM dune.actors) as actor_count,
                (SELECT COUNT(*) FROM dune.player_state WHERE online_status::text = 'Online') as online_count
        """, one=True)

    def get_faction_distribution(self):
        return self.db.query("""
            SELECT f.name, COUNT(pf.actor_id)::int count
            FROM dune.player_faction pf
            JOIN dune.factions f ON pf.faction_id = f.id
            GROUP BY f.name
            ORDER BY count DESC
        """)

    def get_players_per_map(self):
        return self.db.query("""
            SELECT a.map, COUNT(*)::int as count
            FROM dune.player_state ps
            JOIN dune.actors a ON ps.player_pawn_id = a.id
            WHERE a.class LIKE %s AND a.map IS NOT NULL
            GROUP BY a.map
            ORDER BY count DESC
        """, [LIKE_PC])

    def get_players_online(self):
        return self.db.query("""
            SELECT ps.character_name, ps.player_pawn_id as pawn_id, a.map,
                   ps.online_status::text as online_status
            FROM dune.player_state ps
            JOIN dune.actors a ON ps.player_pawn_id = a.id
            WHERE ps.online_status::text = 'Online'
            ORDER BY ps.character_name
        """)

    def get_players_list(self, search='', faction_id='', guild_id='', map_filter='',
                         online_filter='', limit=200, offset=0):
        where = ["a.class LIKE %s"]
        params = [LIKE_PC]

        if search:
            where.append("""(
                ps.character_name ILIKE %s
                OR acc.funcom_id ILIKE %s
                OR ea.user ILIKE %s
                OR a.properties::text ILIKE %s
            )""")
            params.extend([f'%{search}%'] * 4)
        if faction_id:
            where.append("pf.faction_id = %s")
            params.append(faction_id)
        if guild_id:
            where.append("gm.guild_id = %s")
            params.append(guild_id)
        if map_filter:
            where.append("a.map = %s")
            params.append(map_filter)
        if online_filter == 'online':
            where.append("ps.online_status::text = 'Online'")
        elif online_filter == 'offline':
            where.append("ps.online_status::text = 'Offline'")

        where_clause = ' AND '.join(where)
        players = self.db.query(f"""
            SELECT a.id, a.class, a.map, a.transform::text as transform_text,
                COALESCE(NULLIF(ps.character_name, ''), NULLIF(acc.funcom_id, ''), 'Character ' || a.id::text) as player_name,
                ps.online_status::text as online_status,
                ps.life_state::text as life_state,
                ps.last_login_time,
                ps.last_avatar_activity,
                ea.id as account_id, ea.user as account_email,
                acc.funcom_id,
                ps.player_controller_id,
                f.name as faction_name, g.guild_name
            FROM dune.actors a
            JOIN dune.encrypted_accounts ea ON a.owner_account_id = ea.id
            LEFT JOIN dune.accounts acc ON ea.id = acc.id
            LEFT JOIN dune.player_state ps ON a.owner_account_id = ps.account_id AND a.id = ps.player_pawn_id
            LEFT JOIN dune.player_faction pf ON ps.player_controller_id = pf.actor_id
            LEFT JOIN dune.factions f ON pf.faction_id = f.id
            LEFT JOIN dune.guild_members gm ON ps.player_controller_id = gm.player_id
            LEFT JOIN dune.guilds g ON gm.guild_id = g.guild_id
            WHERE {where_clause}
            ORDER BY player_name
            LIMIT %s OFFSET %s
        """, params + [limit, offset])

        if not players:
            return []

        player_ids = [p.get('player_controller_id') for p in players if p.get('player_controller_id')]

        # Fetch IPs from the dashboard database separately and merge
        ip_map = {}
        if self.dash_db and player_ids:
            placeholders = ','.join(['%s'] * len(player_ids))
            ip_rows = self.dash_db.query(
                f"SELECT player_id, ip_address FROM player_ips WHERE player_id IN ({placeholders})",
                player_ids
            ) or []
            ip_map = {r['player_id']: r['ip_address'] for r in ip_rows if r.get('player_id')}
        for p in players:
            pid = p.get('player_controller_id')
            if pid and pid in ip_map:
                p['ip_address'] = ip_map[pid]
            else:
                p['ip_address'] = None
        actor_ids = [p.get('id') for p in players if p.get('id')]

        vehicle_counts = {}
        if player_ids:
            vc = self.db.query("""
                SELECT par.player_id, COUNT(DISTINCT par.permission_actor_id)::int as cnt
                FROM dune.permission_actor_rank par
                JOIN dune.vehicles v ON par.permission_actor_id = v.id
                WHERE par.rank = 1 AND par.player_id = ANY(%s)
                GROUP BY par.player_id
            """, [player_ids])
            vehicle_counts = {r['player_id']: r['cnt'] for r in (vc or []) if r.get('player_id')}

        building_counts = {}
        if actor_ids:
            bc = self.db.query("""
                SELECT owner_id, COUNT(*)::int as cnt
                FROM dune.buildings
                WHERE owner_id = ANY(%s)
                GROUP BY owner_id
            """, [actor_ids])
            building_counts = {r['owner_id']: r['cnt'] for r in (bc or []) if r.get('owner_id')}

        for p in players:
            pid = p.get('player_controller_id') or p.get('id')
            p['vehicle_count'] = vehicle_counts.get(pid, 0)
            p['building_count'] = building_counts.get(p.get('id'), 0)

        return players

    def get_player_detail(self, player_id):
        player = self.db.query("""
            SELECT a.*, a.transform::text as transform_text,
                ea.id as account_id, ea.user as account_email, ea.platform_id,
                acc.funcom_id,
                COALESCE(NULLIF(ps.character_name, ''), NULLIF(acc.funcom_id, ''), 'Character ' || a.id::text) as player_name,
                ps.online_status::text as online_status,
                ps.life_state::text as life_state,
                ps.last_login_time,
                ps.last_avatar_activity,
                ps.player_controller_id,
                ps.player_pawn_id as state_pawn_id,
                f.name as faction_name, pf.faction_id, pf.utc_time_faction_change
            FROM dune.actors a
            JOIN dune.encrypted_accounts ea ON a.owner_account_id = ea.id
            LEFT JOIN dune.accounts acc ON ea.id = acc.id
            LEFT JOIN dune.player_state ps ON a.owner_account_id = ps.account_id AND a.id = ps.player_pawn_id
            LEFT JOIN dune.player_faction pf ON ps.player_controller_id = pf.actor_id
            LEFT JOIN dune.factions f ON pf.faction_id = f.id
            WHERE a.id = %s AND a.class LIKE %s
        """, [player_id, LIKE_PC], one=True)
        return player

    def get_player_vitals(self, state_pawn_id):
        if not state_pawn_id:
            return {}
        try:
            return self.db.query("""
                SELECT
                    (properties->'DamageableActorComponent'->>'m_CurrentMaxHealth')::float as current_health,
                    (properties->'DamageableActorComponent'->>'m_TotalMaxHealth')::float as max_health,
                    (gas_attributes->'DuneHydrationAttributeSet'->'CurrentHydration'->>'CurrentValue')::float as current_hydration,
                    (gas_attributes->'DuneHydrationAttributeSet'->'DehydrationPenalty'->>'CurrentValue')::float as dehydration_penalty,
                    (gas_attributes->'DuneSpiceAddictionAttributeSet'->'CurrentSpice'->>'CurrentValue')::float as current_spice,
                    (gas_attributes->'DuneSpiceAddictionAttributeSet'->'SpiceAddictionLevel'->'CurrentValue'->>'Value')::float as spice_addiction_level,
                    (gas_attributes->'DuneSpiceAddictionAttributeSet'->'SpiceTolerance'->'CurrentValue'->>'Value')::float as spice_tolerance
                FROM dune.actors WHERE id = %s
            """, [state_pawn_id], one=True) or {}
        except Exception as e:
            logger.warning(f"Failed to get vitals: {e}")
            return {}

    def get_player_guild(self, player_controller_id):
        return self.db.query("""
            SELECT g.guild_id, g.guild_name, g.guild_description, f.name as faction_name, gm.role_id
            FROM dune.guild_members gm
            JOIN dune.guilds g ON gm.guild_id = g.guild_id
            LEFT JOIN dune.factions f ON g.guild_faction = f.id
            WHERE gm.player_id = %s
        """, [player_controller_id], one=True)

    def get_player_vehicles(self, player_controller_id):
        if not player_controller_id:
            return []
        return self.db.query("""
            SELECT v_a.id, v_a.class, v_a.map, v_a.transform::text as transform_text,
                pa.actor_name,
                par.rank as ownership_rank
            FROM dune.permission_actor_rank par
            JOIN dune.vehicles v ON par.permission_actor_id = v.id
            JOIN dune.actors v_a ON v.id = v_a.id
            LEFT JOIN dune.permission_actor pa ON v.id = pa.actor_id AND pa.is_child = FALSE
            WHERE par.player_id = %s
            ORDER BY v_a.class
        """, [player_controller_id]) or []

    def get_player_buildings(self, player_id):
        try:
            return self.db.query("""
                SELECT a.id, a.class, a.map, a.transform::text as transform_text,
                    (SELECT COUNT(*)::int FROM dune.building_instances bi WHERE bi.building_id = b.id) as instance_count
                FROM dune.buildings b
                JOIN dune.actors a ON b.id = a.id
                JOIN LATERAL (
                    SELECT DISTINCT afe_totem.actor_id as totem_actor_id
                    FROM dune.building_instances bi
                    JOIN dune.actor_fgl_entities afe_totem ON afe_totem.entity_id = bi.owner_entity_id
                    WHERE bi.building_id = b.id
                    LIMIT 1
                ) totem ON true
                JOIN LATERAL (
                    SELECT pawn.id as pawn_id
                    FROM dune.actors pawn
                    WHERE pawn.id BETWEEN totem.totem_actor_id - 6 AND totem.totem_actor_id - 1
                      AND pawn.class LIKE %s
                    ORDER BY totem.totem_actor_id - pawn.id
                    LIMIT 1
                ) owner ON true
                WHERE owner.pawn_id = %s
                ORDER BY a.map
            """, [LIKE_PC, player_id]) or []
        except Exception:
            return []

    def get_player_currency(self, player_controller_id):
        if not player_controller_id:
            return []
        try:
            return self.db.query(
                "SELECT pvcb.currency_id, pvcb.balance FROM dune.player_virtual_currency_balances pvcb WHERE pvcb.player_controller_id = %s",
                [player_controller_id]
            ) or []
        except Exception:
            return []

    def get_player_inventories(self, player_id):
        try:
            inventories = self.db.query("""
                SELECT i.id, i.actor_id, i.inventory_type, i.max_item_count, i.max_item_volume,
                    COALESCE(json_agg(
                        json_build_object(
                            'id', items.id,
                            'template_id', items.template_id,
                            'stack_size', items.stack_size,
                            'quality_level', items.quality_level,
                            'is_new', items.is_new,
                            'position_index', items.position_index,
                            'stats_text', items.stats::text
                        ) ORDER BY items.position_index
                    ) FILTER (WHERE items.id IS NOT NULL), '[]') as item_list
                FROM dune.inventories i
                LEFT JOIN dune.items ON i.id = items.inventory_id
                WHERE i.actor_id = %s
                GROUP BY i.id, i.actor_id, i.inventory_type, i.max_item_count, i.max_item_volume
                ORDER BY i.inventory_type
            """, [player_id]) or []
            for inv in inventories:
                if not isinstance(inv, dict):
                    logger.warning(f"Inventory row is not a dict: {type(inv)}")
                    continue
                raw_items = inv.get('item_list', []) or []
                if isinstance(raw_items, str):
                    try:
                        import json
                        raw_items = json.loads(raw_items)
                    except (json.JSONDecodeError, TypeError):
                        raw_items = []
                parsed_items = []
                for item in raw_items:
                    if not isinstance(item, dict):
                        logger.warning(f"Item is not a dict: {type(item)}, value: {repr(item)[:100]}")
                        continue
                    new_item = dict(item)
                    stats_text = new_item.pop('stats_text', None)
                    stats = {}
                    if stats_text:
                        try:
                            import json
                            stats = json.loads(stats_text)
                        except (json.JSONDecodeError, TypeError):
                            stats = {}
                    new_item['stats'] = stats
                    dur_stats = stats.get('FItemStackAndDurabilityStats')
                    if isinstance(dur_stats, dict):
                        new_item['durability'] = dur_stats.get('CurrentDurability')
                        new_item['max_durability'] = dur_stats.get('DecayedMaxDurability')
                    elif isinstance(dur_stats, list) and dur_stats:
                        new_item['durability'] = dur_stats[0].get('CurrentDurability') if isinstance(dur_stats[0], dict) else None
                        new_item['max_durability'] = dur_stats[0].get('DecayedMaxDurability') if isinstance(dur_stats[0], dict) else None
                    else:
                        new_item['durability'] = None
                        new_item['max_durability'] = None
                    weapon_stats = stats.get('FWeaponItemStats')
                    if isinstance(weapon_stats, dict):
                        new_item['ammo'] = weapon_stats.get('CurrentAmmo')
                    elif isinstance(weapon_stats, list) and weapon_stats:
                        new_item['ammo'] = weapon_stats[0].get('CurrentAmmo') if isinstance(weapon_stats[0], dict) else None
                    else:
                        new_item['ammo'] = None
                    parsed_items.append(new_item)
                inv['item_list'] = parsed_items
            return inventories
        except Exception as e:
            logger.warning(f"Failed to get inventories: {e}")
            import traceback
            logger.warning(traceback.format_exc())
            inventories = self.db.query(
                "SELECT i.* FROM dune.inventories i WHERE i.actor_id = %s ORDER BY i.inventory_type",
                [player_id]
            ) or []
            for inv in inventories:
                inv['item_list'] = []
            return inventories

    def get_player_landclaims(self, owner_account_id):
        try:
            return self.db.query("""
                SELECT DISTINCT a.id, a.class, a.map, a.transform::text as transform_text
                FROM dune.landclaim_segments lcs
                JOIN dune.actors a ON lcs.totem_id = a.id
                WHERE a.owner_account_id = %s
            """, [owner_account_id]) or []
        except Exception:
            return []

    def get_player_specialization(self, player_controller_id):
        if not player_controller_id:
            return []
        try:
            return self.db.query(
                "SELECT track_type, xp_amount, level FROM dune.specialization_tracks WHERE player_id = %s",
                [player_controller_id]
            ) or []
        except Exception:
            return []

    def get_player_tech_knowledge(self, player_id):
        try:
            tech_row = self.db.query(
                "SELECT (properties->'TechKnowledgePlayerComponent'->>'m_TechKnowledgePoints')::int as xp_points FROM dune.actors WHERE id = %s",
                [player_id], one=True
            )
            return tech_row['xp_points'] if tech_row else None
        except Exception:
            return None

    def get_player_keystones(self, player_controller_id):
        if not player_controller_id:
            return []
        try:
            return self.db.query(
                "SELECT ks.id, ks.name FROM dune.purchased_specialization_keystones psk JOIN dune.specialization_keystones_map ks ON psk.keystone_id = ks.id WHERE psk.player_id = %s ORDER BY ks.id",
                [player_controller_id]
            ) or []
        except Exception:
            return []

    def get_player_faction_reputation(self, player_controller_id):
        if not player_controller_id:
            return []
        try:
            return self.db.query(
                "SELECT pfr.faction_id, f.name as faction_name, pfr.reputation_amount FROM dune.player_faction_reputation pfr JOIN dune.factions f ON pfr.faction_id = f.id WHERE pfr.actor_id = %s ORDER BY pfr.faction_id",
                [player_controller_id]
            ) or []
        except Exception:
            return []

    def get_player_landsraad(self, player_controller_id):
        if not player_controller_id:
            return {}
        try:
            return self.db.query(
                "SELECT (properties->'LandsraadCharacterComponent'->>'m_DailyRewardCharges')::int as daily_reward_charges, "
                "(properties->'LandsraadCharacterComponent'->>'m_LastViewedLandsraadTermId')::int as last_viewed_term_id, "
                "(properties->'LandsraadCharacterComponent'->>'m_DailyRewardLastProcessedTimestamp')::bigint as daily_reward_last_processed "
                "FROM dune.actors WHERE id = %s",
                [player_controller_id], one=True
            ) or {}
        except Exception:
            return {}
