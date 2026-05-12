"""Admin service - ban, kick, unban, vitals, IP detection"""

import re
import time
import threading
import logging

logger = logging.getLogger(__name__)


class AdminService:
    def __init__(self, db_service, ssh_service):
        self.db = db_service
        self.ssh = ssh_service

    def ban_player(self, player_id, duration=0, reason='', note=''):
        try:
            duration_int = int(duration) if duration else 0
        except (ValueError, TypeError):
            duration_int = 0

        player_row = self.db.query(
            "SELECT ps.account_id, ps.character_name FROM dune.player_state ps WHERE ps.player_controller_id = %s",
            [player_id], one=True
        )

        account_id = player_row.get('account_id') if player_row else None
        player_name = player_row.get('character_name', 'Unknown') if player_row else 'Unknown'

        conn = self.db.get_connection()
        if not conn:
            return False, "Database connection failed"
        cur = None
        try:
            cur = conn.cursor()

            if account_id:
                if duration_int == 0:
                    cur.execute("""
                        INSERT INTO dune.bans (player_id, account_id, reason, note, duration, banned_at, expires_at, active)
                        VALUES (%s, %s, %s, %s, %s, NOW(), NULL, TRUE)
                        ON CONFLICT (player_id) DO UPDATE SET
                            account_id = EXCLUDED.account_id, reason = EXCLUDED.reason,
                            note = EXCLUDED.note, duration = EXCLUDED.duration,
                            banned_at = NOW(), expires_at = NULL, active = TRUE
                    """, [player_id, account_id, reason, note, duration_int])
                else:
                    cur.execute("""
                        INSERT INTO dune.bans (player_id, account_id, reason, note, duration, banned_at, expires_at, active)
                        VALUES (%s, %s, %s, %s, %s, NOW(), NOW() + INTERVAL '1 minute' * %s, TRUE)
                        ON CONFLICT (player_id) DO UPDATE SET
                            account_id = EXCLUDED.account_id, reason = EXCLUDED.reason,
                            note = EXCLUDED.note, duration = EXCLUDED.duration,
                            banned_at = NOW(), expires_at = NOW() + INTERVAL '1 minute' * %s, active = TRUE
                    """, [player_id, account_id, reason, note, duration_int, duration_int, duration_int])
            else:
                if duration_int == 0:
                    cur.execute("""
                        INSERT INTO dune.bans (player_id, reason, note, duration, banned_at, expires_at, active)
                        VALUES (%s, %s, %s, %s, NOW(), NULL, TRUE)
                        ON CONFLICT (player_id) DO UPDATE SET
                            reason = EXCLUDED.reason, note = EXCLUDED.note,
                            duration = EXCLUDED.duration, banned_at = NOW(),
                            expires_at = NULL, active = TRUE
                    """, [player_id, reason, note, duration_int])
                else:
                    cur.execute("""
                        INSERT INTO dune.bans (player_id, reason, note, duration, banned_at, expires_at, active)
                        VALUES (%s, %s, %s, %s, NOW(), NOW() + INTERVAL '1 minute' * %s, TRUE)
                        ON CONFLICT (player_id) DO UPDATE SET
                            reason = EXCLUDED.reason, note = EXCLUDED.note,
                            duration = EXCLUDED.duration, banned_at = NOW(),
                            expires_at = NOW() + INTERVAL '1 minute' * %s, active = TRUE
                    """, [player_id, reason, note, duration_int, duration_int, duration_int])

            conn.commit()
            return True, f"Player {player_name} banned for {duration_int} minutes"
        except Exception as e:
            logger.error(f"Failed to ban player {player_id}: {e}")
            if conn:
                conn.rollback()
            return False, str(e)
        finally:
            if cur:
                cur.close()
            self.db.return_connection(conn)

    def unban_player(self, player_id):
        conn = self.db.get_connection()
        if not conn:
            return False, "Database connection failed"
        cur = None
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM dune.bans WHERE player_id = %s", [player_id])
            conn.commit()

            cur.execute("SELECT ps.account_id FROM dune.player_state ps WHERE ps.player_controller_id = %s", [player_id])
            account_row = cur.fetchone()
            account_id = account_row[0] if account_row else None

            ips_to_unblock = []
            if account_id:
                all_ips = self.db.query("""
                    SELECT ip_address FROM dune.player_ips
                    WHERE player_id IN (SELECT player_controller_id FROM dune.player_state WHERE account_id = %s)
                """, [account_id]) or []
                ips_to_unblock = [r.get('ip_address') for r in all_ips if r.get('ip_address')]
            else:
                ip_row = self.db.query("SELECT ip_address FROM dune.player_ips WHERE player_id = %s", [player_id], one=True)
                if ip_row and ip_row.get('ip_address'):
                    ips_to_unblock.append(ip_row.get('ip_address'))

            cur.execute("INSERT INTO dune.player_actions (player_id, action_type, reason, duration_minutes) VALUES (%s, 'unban', 'Manual unban', 0)", [player_id])
            conn.commit()

            for ip in ips_to_unblock:
                self.ssh.run(f'sudo iptables -D INPUT -s {ip} -j DROP 2>/dev/null')
                self.ssh.run(f'sudo iptables -D OUTPUT -d {ip} -j DROP 2>/dev/null')

            return True, f"Player unbanned. Cleared {len(ips_to_unblock)} IP block(s)."
        except Exception as e:
            logger.error(f"Failed to unban player {player_id}: {e}")
            if conn:
                conn.rollback()
            return False, str(e)
        finally:
            if cur:
                cur.close()
            self.db.return_connection(conn)

    def kick_player(self, player_id):
        player = self.db.query("""
            SELECT ps.character_name, a.map FROM dune.player_state ps
            JOIN dune.actors a ON ps.player_pawn_id = a.id
            WHERE ps.player_controller_id = %s
        """, [player_id], one=True)

        if not player:
            return False, "Player not found"

        player_name = player.get('character_name', 'Unknown')
        ip_row = self.db.query("SELECT ip_address FROM dune.player_ips WHERE player_id = %s", [player_id], one=True)
        player_ip = ip_row.get('ip_address') if ip_row else None

        if not player_ip:
            return False, "Player IP not known. Detect IPs first."

        def temporary_block(ip):
            self.ssh.run(f'sudo iptables -I INPUT -s {ip} -j DROP')
            self.ssh.run(f'sudo iptables -I OUTPUT -d {ip} -j DROP')
            time.sleep(60)
            self.ssh.run(f'sudo iptables -D INPUT -s {ip} -j DROP')
            self.ssh.run(f'sudo iptables -D OUTPUT -d {ip} -j DROP')

        thread = threading.Thread(target=temporary_block, args=(player_ip,), daemon=True)
        thread.start()

        self.db.execute("INSERT INTO dune.player_actions (player_id, action_type, reason, duration_minutes, ip_address) VALUES (%s, 'kick', 'Temporary kick', 1, %s)", [player_id, player_ip])

        return True, f"Player {player_name} kicked (IP {player_ip} blocked for 60 seconds)"

    def edit_vitals(self, pawn_id, current_health=None, max_health=None, current_hydration=None, current_spice=None):
        if pawn_id is None or current_hydration is None or current_spice is None:
            return False, "Missing parameters"

        controller_row = self.db.query(
            "SELECT player_controller_id FROM dune.player_state WHERE player_pawn_id = %s LIMIT 1",
            [pawn_id], one=True
        )
        if controller_row:
            from app.services.player import PlayerService
            ps = PlayerService(self.db)
            if ps.is_online(controller_row['player_controller_id']):
                return False, "Player must be offline to edit vitals. Log out first."

        health = max(0.0, float(current_health)) if current_health is not None else None
        max_h = max(0.0, float(max_health)) if max_health is not None else None
        hydration = max(0.0, float(current_hydration))
        spice = max(0.0, float(current_spice))

        conn = self.db.get_connection()
        if not conn:
            return False, "Database connection failed"
        cur = None
        try:
            cur = conn.cursor()
            if health is not None:
                cur.execute(
                    "UPDATE dune.actors SET properties = jsonb_set(properties, '{DamageableActorComponent,m_CurrentMaxHealth}', to_jsonb(%s::float)) WHERE id = %s",
                    [health, pawn_id]
                )
            if max_h is not None:
                cur.execute(
                    "UPDATE dune.actors SET properties = jsonb_set(properties, '{DamageableActorComponent,m_TotalMaxHealth}', to_jsonb(%s::float)) WHERE id = %s",
                    [max_h, pawn_id]
                )
            cur.execute(
                "UPDATE dune.actors SET gas_attributes = jsonb_set("
                "  jsonb_set(jsonb_set(jsonb_set(gas_attributes, "
                "    '{DuneHydrationAttributeSet,CurrentHydration,CurrentValue}', to_jsonb(%s::float)), "
                "    '{DuneHydrationAttributeSet,CurrentHydration,BaseValue}', to_jsonb(%s::float)), "
                "    '{DuneSpiceAddictionAttributeSet,CurrentSpice,CurrentValue}', to_jsonb(%s::float)), "
                "  '{DuneSpiceAddictionAttributeSet,CurrentSpice,BaseValue}', to_jsonb(%s::float)) "
                "WHERE id = %s",
                [hydration, hydration, spice, spice, pawn_id]
            )
            conn.commit()
            return True, {"health": health, "max_health": max_h, "hydration": hydration, "spice": spice}
        except Exception as e:
            logger.error(f"Failed to edit vitals for pawn {pawn_id}: {e}")
            if conn:
                conn.rollback()
            return False, str(e)
        finally:
            if cur:
                cur.close()
            self.db.return_connection(conn)

    def detect_player_ips(self, namespace):
        out, err, rc = self.ssh.run(f'sudo kubectl get pods -n {namespace} -o name 2>/dev/null')
        if rc != 0 or not out:
            return False, "Failed to list pods"

        game_pods = []
        for line in out.strip().split('\n'):
            pod = line.replace('pod/', '').strip()
            if '-sg-' in pod and '-pod-' in pod:
                map_name = pod.split('-sg-')[-1].split('-pod-')[0] if '-sg-' in pod else 'Unknown'
                game_pods.append((pod, map_name))

        if not game_pods:
            return False, "No game server pods found"

        conn = self.db.get_connection()
        if not conn:
            return False, "Database connection failed"
        cur = None
        updated = 0
        try:
            cur = conn.cursor()

            for pod_name, map_name in game_pods:
                cmd = f'sudo kubectl exec -n {namespace} {pod_name} -- find /home/dune -name "*.log" -path "*/Logs/*" 2>/dev/null | head -5'
                out_logs, err_logs, rc_logs = self.ssh.run(cmd)
                if not out_logs:
                    continue

                log_files = [l.strip() for l in out_logs.strip().split('\n') if l.strip()]
                for log_file in log_files:
                    cat_cmd = f'sudo kubectl exec -n {namespace} {pod_name} -- cat "{log_file}" 2>/dev/null'
                    out, err, rc = self.ssh.run(cat_cmd)
                    if not out:
                        continue

                    ip_to_player = {}
                    current_ip = None

                    for line in out.split('\n'):
                        ip_match = re.search(r'RemoteAddr:\s*([0-9.]+):(\d+)', line)
                        if ip_match:
                            current_ip = ip_match.group(1)
                            continue

                        if 'Login request:' in line and current_ip:
                            name_match = re.search(r'Name=([^?#]+)', line)
                            if name_match:
                                current_player = name_match.group(1).split('#')[0]
                                if current_player and current_ip and current_ip != 'YOUR_SERVER_IP':
                                    ip_to_player[current_ip] = current_player
                            current_ip = None

                    if ip_to_player:
                        for ip, name in ip_to_player.items():
                            cur.execute("""
                                SELECT ps.player_controller_id, ps.account_id
                                FROM dune.player_state ps
                                JOIN dune.accounts a ON ps.account_id = a.id
                                WHERE a.funcom_id = %s OR ps.character_name = %s
                                LIMIT 1
                            """, [name, name])
                            row = cur.fetchone()
                            if row:
                                pid = row[0]
                                account_id = row[1]
                                cur.execute("""
                                    INSERT INTO dune.player_ips (player_id, ip_address, updated_at)
                                    VALUES (%s, %s, NOW())
                                    ON CONFLICT (player_id) DO UPDATE SET ip_address = EXCLUDED.ip_address, updated_at = NOW()
                                """, [pid, ip])
                                updated += 1

                                ban_check = self.db.query("""
                                    SELECT player_id FROM dune.bans
                                    WHERE (player_id = %s OR account_id = %s) AND (active = TRUE OR active IS NULL)
                                    LIMIT 1
                                """, [pid, account_id], one=True)

                                if ban_check:
                                    self.ssh.run(f'sudo iptables -I INPUT -s {ip} -j DROP')
                                    self.ssh.run(f'sudo iptables -I OUTPUT -d {ip} -j DROP')

            conn.commit()
            return True, f"Updated {updated} player IPs from game logs"
        except Exception as e:
            logger.error(f"Failed to detect player IPs: {e}")
            if conn:
                conn.rollback()
            return False, str(e)
        finally:
            if cur:
                cur.close()
            self.db.return_connection(conn)

    def set_player_ip(self, player_id, ip_address):
        return self.db.execute("""
            INSERT INTO dune.player_ips (player_id, ip_address, updated_at)
            VALUES (%s, %s, NOW())
            ON CONFLICT (player_id) DO UPDATE SET ip_address = EXCLUDED.ip_address, updated_at = NOW()
        """, [player_id, ip_address])

    def emergency_unban(self, ip):
        self.ssh.run(f'sudo iptables -D INPUT -s {ip} -j DROP 2>/dev/null')
        self.ssh.run(f'sudo iptables -D OUTPUT -d {ip} -j DROP 2>/dev/null')
        return True, f"Unblocked {ip}"

    def get_bans(self, limit=50):
        return self.db.query("""
            SELECT b.id, b.player_id, b.reason, b.active, b.banned_at, b.expires_at, ps.character_name
            FROM dune.bans b
            LEFT JOIN dune.player_state ps ON b.player_id = ps.player_controller_id
            ORDER BY b.banned_at DESC
            LIMIT %s
        """, [limit]) or []

    def get_player_ban(self, player_id):
        return self.db.query("SELECT reason, note, duration, banned_at, expires_at FROM dune.bans WHERE player_id = %s", [player_id], one=True)

    def get_player_history(self, player_id, limit=20):
        return self.db.query("""
            SELECT action_type, reason, note, duration_minutes, created_at, ip_address
            FROM dune.player_actions
            WHERE player_id = %s
            ORDER BY created_at DESC
            LIMIT %s
        """, [player_id, limit]) or []

    def create_indexes(self):
        indexes = [
            ("idx_actors_class", "CREATE INDEX IF NOT EXISTS idx_actors_class ON dune.actors (class)"),
            ("idx_actors_map", "CREATE INDEX IF NOT EXISTS idx_actors_map ON dune.actors (map)"),
            ("idx_actors_owner_account", "CREATE INDEX IF NOT EXISTS idx_actors_owner_account ON dune.actors (owner_account_id)"),
            ("idx_player_state_controller", "CREATE INDEX IF NOT EXISTS idx_player_state_controller ON dune.player_state (player_controller_id)"),
            ("idx_player_state_pawn", "CREATE INDEX IF NOT EXISTS idx_player_state_pawn ON dune.player_state (player_pawn_id)"),
            ("idx_player_state_account", "CREATE INDEX IF NOT EXISTS idx_player_state_account ON dune.player_state (account_id)"),
            ("idx_player_state_online", "CREATE INDEX IF NOT EXISTS idx_player_state_online ON dune.player_state (online_status)"),
            ("idx_guild_members_player", "CREATE INDEX IF NOT EXISTS idx_guild_members_player ON dune.guild_members (player_id)"),
            ("idx_guild_members_guild", "CREATE INDEX IF NOT EXISTS idx_guild_members_guild ON dune.guild_members (guild_id)"),
            ("idx_player_faction_actor", "CREATE INDEX IF NOT EXISTS idx_player_faction_actor ON dune.player_faction (actor_id)"),
            ("idx_permission_actor_rank_player", "CREATE INDEX IF NOT EXISTS idx_permission_actor_rank_player ON dune.permission_actor_rank (player_id)"),
            ("idx_permission_actor_rank_actor", "CREATE INDEX IF NOT EXISTS idx_permission_actor_rank_actor ON dune.permission_actor_rank (permission_actor_id)"),
            ("idx_buildings_owner", "CREATE INDEX IF NOT EXISTS idx_buildings_owner ON dune.buildings (owner_id)"),
            ("idx_inventories_actor", "CREATE INDEX IF NOT EXISTS idx_inventories_actor ON dune.inventories (actor_id)"),
            ("idx_items_inventory", "CREATE INDEX IF NOT EXISTS idx_items_inventory ON dune.items (inventory_id)"),
            ("idx_specialization_tracks_player", "CREATE INDEX IF NOT EXISTS idx_specialization_tracks_player ON dune.specialization_tracks (player_id)"),
            ("idx_player_faction_reputation_actor", "CREATE INDEX IF NOT EXISTS idx_player_faction_reputation_actor ON dune.player_faction_reputation (actor_id)"),
            ("idx_player_virtual_currency_controller", "CREATE INDEX IF NOT EXISTS idx_player_virtual_currency_controller ON dune.player_virtual_currency_balances (player_controller_id)"),
        ]

        created = []
        conn = self.db.get_connection()
        if not conn:
            return False, [], "Database connection failed"
        cur = None
        try:
            cur = conn.cursor()
            for name, sql in indexes:
                try:
                    cur.execute(sql)
                    created.append(name)
                except Exception as e:
                    logger.warning(f"Index {name} failed: {e}")
            conn.commit()
            return True, created, None
        except Exception as e:
            logger.error(f"Failed to create indexes: {e}")
            if conn:
                conn.rollback()
            return False, [], str(e)
        finally:
            if cur:
                cur.close()
            self.db.return_connection(conn)
