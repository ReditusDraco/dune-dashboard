"""Admin service - ban, kick, unban, vitals, IP detection, broadcast"""
 
import re
import time
import threading
import logging
import ipaddress
import tempfile
import os
import json
import psycopg2.extras

logger = logging.getLogger(__name__)
audit_logger = logging.getLogger('audit')


def _validate_ip(ip):
    """Validate that a string is a valid IPv4 or IPv6 address."""
    try:
        ipaddress.ip_address(ip)
        return True
    except (ValueError, TypeError):
        return False


class AdminService:
    _iptables_lock = threading.Lock()

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
                        INSERT INTO dashboard.bans (player_id, account_id, reason, note, duration, banned_at, expires_at, active)
                        VALUES (%s, %s, %s, %s, %s, NOW(), NULL, TRUE)
                        ON CONFLICT (player_id) DO UPDATE SET
                            account_id = EXCLUDED.account_id, reason = EXCLUDED.reason,
                            note = EXCLUDED.note, duration = EXCLUDED.duration,
                            banned_at = NOW(), expires_at = NULL, active = TRUE
                    """, [player_id, account_id, reason, note, duration_int])
                else:
                    cur.execute("""
                        INSERT INTO dashboard.bans (player_id, account_id, reason, note, duration, banned_at, expires_at, active)
                        VALUES (%s, %s, %s, %s, %s, NOW(), NOW() + INTERVAL '1 minute' * %s, TRUE)
                        ON CONFLICT (player_id) DO UPDATE SET
                            account_id = EXCLUDED.account_id, reason = EXCLUDED.reason,
                            note = EXCLUDED.note, duration = EXCLUDED.duration,
                            banned_at = NOW(), expires_at = NOW() + INTERVAL '1 minute' * %s, active = TRUE
                    """, [player_id, account_id, reason, note, duration_int, duration_int, duration_int])
            else:
                if duration_int == 0:
                    cur.execute("""
                        INSERT INTO dashboard.bans (player_id, reason, note, duration, banned_at, expires_at, active)
                        VALUES (%s, %s, %s, %s, NOW(), NULL, TRUE)
                        ON CONFLICT (player_id) DO UPDATE SET
                            reason = EXCLUDED.reason, note = EXCLUDED.note,
                            duration = EXCLUDED.duration, banned_at = NOW(),
                            expires_at = NULL, active = TRUE
                    """, [player_id, reason, note, duration_int])
                else:
                    cur.execute("""
                        INSERT INTO dashboard.bans (player_id, reason, note, duration, banned_at, expires_at, active)
                        VALUES (%s, %s, %s, %s, NOW(), NOW() + INTERVAL '1 minute' * %s, TRUE)
                        ON CONFLICT (player_id) DO UPDATE SET
                            reason = EXCLUDED.reason, note = EXCLUDED.note,
                            duration = EXCLUDED.duration, banned_at = NOW(),
                            expires_at = NOW() + INTERVAL '1 minute' * %s, active = TRUE
                    """, [player_id, reason, note, duration_int, duration_int, duration_int])

            conn.commit()
            audit_logger.info(f"BAN: player_id={player_id} player_name={player_name} duration={duration_int}min reason={reason}")
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
            cur.execute("DELETE FROM dashboard.bans WHERE player_id = %s", [player_id])
            conn.commit()

            cur.execute("SELECT ps.account_id FROM dune.player_state ps WHERE ps.player_controller_id = %s", [player_id])
            account_row = cur.fetchone()
            account_id = account_row[0] if account_row and isinstance(account_row, (tuple, list)) else (account_row.get('account_id') if account_row else None)

            ips_to_unblock = []
            if account_id:
                all_ips = self.db.query("""
                    SELECT ip_address FROM dashboard.player_ips
                    WHERE player_id IN (SELECT player_controller_id FROM dune.player_state WHERE account_id = %s)
                """, [account_id]) or []
                ips_to_unblock = [r.get('ip_address') for r in all_ips if r.get('ip_address')]
            else:
                ip_row = self.db.query("SELECT ip_address FROM dashboard.player_ips WHERE player_id = %s", [player_id], one=True)
                if ip_row and ip_row.get('ip_address'):
                    ips_to_unblock.append(ip_row.get('ip_address'))

            cur.execute("INSERT INTO dashboard.player_actions (player_id, action_type, reason, duration_minutes) VALUES (%s, 'unban', 'Manual unban', 0)", [player_id])
            conn.commit()

            with self._iptables_lock:
                for ip in ips_to_unblock:
                    if not _validate_ip(ip):
                        logger.warning(f"Skipping invalid IP in unban: {ip}")
                        continue
                    self.ssh.run(f'sudo iptables -D INPUT -s {ip} -j DROP 2>/dev/null')
                    self.ssh.run(f'sudo iptables -D OUTPUT -d {ip} -j DROP 2>/dev/null')

            audit_logger.info(f"UNBAN: player_id={player_id} ips_cleared={len(ips_to_unblock)}")
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
        ip_row = self.db.query("SELECT ip_address FROM dashboard.player_ips WHERE player_id = %s", [player_id], one=True)
        player_ip = ip_row.get('ip_address') if ip_row else None

        if not player_ip:
            return False, "Player IP not known. Detect IPs first."

        def temporary_block(ip):
            if not _validate_ip(ip):
                logger.error(f"Invalid IP address for kick: {ip}")
                return
            with self._iptables_lock:
                self.ssh.run(f'sudo iptables -I INPUT -s {ip} -j DROP')
                self.ssh.run(f'sudo iptables -I OUTPUT -d {ip} -j DROP')
            time.sleep(60)
            with self._iptables_lock:
                self.ssh.run(f'sudo iptables -D INPUT -s {ip} -j DROP')
                self.ssh.run(f'sudo iptables -D OUTPUT -d {ip} -j DROP')

        thread = threading.Thread(target=temporary_block, args=(player_ip,), daemon=True)
        thread.start()

        self.db.execute("INSERT INTO dashboard.player_actions (player_id, action_type, reason, duration_minutes, ip_address) VALUES (%s, 'kick', 'Temporary kick', 1, %s)", [player_id, player_ip])
        audit_logger.info(f"KICK: player_id={player_id} player_name={player_name} ip={player_ip}")

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
            audit_logger.info(f"EDIT_VITALS: pawn_id={pawn_id} health={health} max_health={max_h} hydration={hydration} spice={spice}")
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
                                pid = row[0] if isinstance(row, (tuple, list)) else row.get('funcom_id')
                                account_id = row[1] if isinstance(row, (tuple, list)) else row.get('account_id')
                                cur.execute("""
                                    INSERT INTO dashboard.player_ips (player_id, ip_address, updated_at)
                                    VALUES (%s, %s, NOW())
                                    ON CONFLICT (player_id) DO UPDATE SET ip_address = EXCLUDED.ip_address, updated_at = NOW()
                                """, [pid, ip])
                                updated += 1

                                ban_check = self.db.query("""
                                    SELECT player_id FROM dashboard.bans
                                    WHERE (player_id = %s OR account_id = %s) AND (active = TRUE OR active IS NULL)
                                    LIMIT 1
                                """, [pid, account_id], one=True)

                                if ban_check:
                                    if _validate_ip(ip):
                                        with self._iptables_lock:
                                            self.ssh.run(f'sudo iptables -I INPUT -s {ip} -j DROP')
                                            self.ssh.run(f'sudo iptables -I OUTPUT -d {ip} -j DROP')
                                    else:
                                        logger.warning(f"Skipping invalid IP for ban block: {ip}")

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
            INSERT INTO dashboard.player_ips (player_id, ip_address, updated_at)
            VALUES (%s, %s, NOW())
            ON CONFLICT (player_id) DO UPDATE SET ip_address = EXCLUDED.ip_address, updated_at = NOW()
        """, [player_id, ip_address])

    def emergency_unban(self, ip):
        if not _validate_ip(ip):
            return False, f"Invalid IP address: {ip}"
        with self._iptables_lock:
            self.ssh.run(f'sudo iptables -D INPUT -s {ip} -j DROP 2>/dev/null')
            self.ssh.run(f'sudo iptables -D OUTPUT -d {ip} -j DROP 2>/dev/null')
        audit_logger.info(f"EMERGENCY_UNBAN: ip={ip}")
        return True, f"Unblocked {ip}"

    def get_bans(self, limit=50):
        return self.db.query("""
            SELECT b.id, b.player_id, b.reason, b.active, b.banned_at, b.expires_at, ps.character_name
            FROM dashboard.bans b
            LEFT JOIN dune.player_state ps ON b.player_id = ps.player_controller_id
            ORDER BY b.banned_at DESC
            LIMIT %s
        """, [limit]) or []

    def get_player_ban(self, player_id):
        return self.db.query("SELECT reason, note, duration, banned_at, expires_at FROM dashboard.bans WHERE player_id = %s", [player_id], one=True)

    def get_player_history(self, player_id, limit=20):
        return self.db.query("""
            SELECT action_type, reason, note, duration_minutes, created_at, ip_address
            FROM dashboard.player_actions
            WHERE player_id = %s
            ORDER BY created_at DESC
            LIMIT %s
        """, [player_id, limit]) or []

    def create_indexes(self):
        indexes = [
            ("idx_actors_class", "CREATE INDEX IF NOT EXISTS idx_actors_class ON dune.actors (class)"),
            ("idx_actors_map", "CREATE INDEX IF NOT EXISTS idx_actors_map ON dune.actors (map)"),
            ("idx_actors_owner_account", "CREATE INDEX IF NOT EXISTS idx_actors_owner_account ON dune.actors (owner_account_id)"),
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
                    conn.commit()
                    created.append(name)
                except Exception as e:
                    logger.warning(f"Index {name} failed: {e}")
                    try:
                        conn.rollback()
                    except Exception:
                        pass
            return True, created, None
        except Exception as e:
            logger.error(f"Failed to create indexes: {e}")
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            return False, [], str(e)
        finally:
            if cur:
                cur.close()
            self.db.return_connection(conn)

    def reapply_firewall_rules(self, settings, k8s_service):
        """Re-apply iptables firewall rules based on settings after VM reboot.
        Checks current iptables state first to avoid duplicate rules.
        Returns (success, applied_ports, skipped_ports, error).
        """
        firewall_cfg = settings.get('firewall', {})
        if not firewall_cfg:
            return True, [], [], None

        # Resolve BGD NodePort
        bgd_port = None
        try:
            ns = settings.get('kubernetes', {}).get('namespace', '')
            if ns and k8s_service:
                out, _, rc = k8s_service.run(f'get svc -n {ns} -o wide')
                if rc == 0 and out:
                    for line in out.split('\n'):
                        if '-bgd-svc' in line and 'NodePort' in line:
                            parts = line.split()
                            for p in parts:
                                if ':' in p and p[0].isdigit():
                                    port_str = p.split(':')[1].split('/')[0]
                                    bgd_port = int(port_str)
                                    break
        except Exception as e:
            logger.warning(f"Firewall reapply: failed to resolve BGD NodePort: {e}")

        # Build port map: port -> (setting_key, should_block)
        port_map = {}
        port_map[18888] = ('block_filebrowser', firewall_cfg.get('block_filebrowser', False))
        if bgd_port:
            port_map[bgd_port] = ('block_director', firewall_cfg.get('block_director', False))

        # Check current iptables state
        active_ports = [str(p) for p in port_map.keys()]
        all_ports_re = '|'.join(active_ports) if active_ports else 'NONE'
        try:
            out, _, _ = self.ssh.run(
                f'sudo iptables -L INPUT -n 2>/dev/null | grep -E "dpt:({all_ports_re})"; '
                f'sudo iptables -L FORWARD -n 2>/dev/null | grep -E "dpt:({all_ports_re})"; '
                f'sudo iptables -t mangle -L PREROUTING -n 2>/dev/null | grep -E "dpt:({all_ports_re})"',
                timeout=15
            )
        except Exception as e:
            return False, [], [], f"SSH command failed: {e}"

        blocked_ports = set()
        for line in out.split('\n'):
            for port_str in active_ports:
                if f'dpt:{port_str}' in line and 'DROP' in line:
                    blocked_ports.add(int(port_str))

        # Apply rules for ports that should be blocked but aren't
        applied = []
        skipped = []
        for port, (key, should_block) in port_map.items():
            if not should_block:
                skipped.append(f"{port} (setting=False)")
                continue
            if port in blocked_ports:
                skipped.append(f"{port} (already blocked)")
                continue

            cmd = (
                f'sudo iptables -I INPUT 1 -p tcp --dport {port} -s 127.0.0.1 -j ACCEPT && '
                f'sudo iptables -I INPUT 2 -p tcp --dport {port} -j DROP && '
                f'sudo iptables -I FORWARD 1 -p tcp --dport {port} -s 127.0.0.1 -j ACCEPT && '
                f'sudo iptables -I FORWARD 2 -p tcp --dport {port} -j DROP && '
                f'sudo iptables -t mangle -I PREROUTING 1 -p tcp --dport {port} -s 127.0.0.1 -j ACCEPT && '
                f'sudo iptables -t mangle -I PREROUTING 2 -p tcp --dport {port} -j DROP'
            )
            try:
                out, err, rc = self.ssh.run(cmd, timeout=20)
                if rc != 0 and 'already exists' not in (out + err):
                    logger.warning(f"Firewall reapply: failed to block port {port}: {err}")
                    skipped.append(f"{port} (failed: {err.strip()})")
                else:
                    applied.append(port)
                    logger.info(f"Firewall reapply: blocked port {port}")
            except Exception as e:
                logger.warning(f"Firewall reapply: SSH error for port {port}: {e}")
                skipped.append(f"{port} (SSH error: {e})")

        if applied:
            logger.info(f"Firewall reapply: applied rules for ports {applied}")
        return True, applied, skipped, None

    def edit_faction(self, player_controller_id, faction_id):
        if player_controller_id is None or faction_id is None:
            return False, "Missing parameters"
        faction_id = int(faction_id)
        if faction_id not in (1, 2, 3, 4):
            return False, "Invalid faction ID. Must be 1 (Atreides), 2 (Harkonnen), 3 (None), or 4 (Smuggler)"

        conn = self.db.get_connection()
        if not conn:
            return False, "Database connection failed"
        cur = None
        try:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO dune.player_faction (actor_id, faction_id, utc_time_faction_change)
                VALUES (%s, %s, NOW())
                ON CONFLICT (actor_id) DO UPDATE SET
                    faction_id = EXCLUDED.faction_id,
                    utc_time_faction_change = EXCLUDED.utc_time_faction_change
            """, [player_controller_id, faction_id])
            conn.commit()
            audit_logger.info(f"EDIT_FACTION: player_controller_id={player_controller_id} faction_id={faction_id}")
            return True, {"faction_id": faction_id}
        except Exception as e:
            logger.error(f"Failed to edit faction for player {player_controller_id}: {e}")
            if conn:
                conn.rollback()
            return False, str(e)
        finally:
            if cur:
                cur.close()
            self.db.return_connection(conn)

    def edit_xp(self, player_controller_id, track_type, xp_amount, level=None):
        if player_controller_id is None or track_type is None or xp_amount is None:
            return False, "Missing parameters"
        try:
            xp_amount = float(xp_amount)
        except (ValueError, TypeError):
            return False, "Invalid XP amount"
        if level is not None:
            try:
                level = float(level)
            except (ValueError, TypeError):
                return False, "Invalid level"

        conn = self.db.get_connection()
        if not conn:
            return False, "Database connection failed"
        cur = None
        try:
            cur = conn.cursor()
            if level is not None:
                cur.execute("""
                    INSERT INTO dune.specialization_tracks (player_id, track_type, xp_amount, level)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (player_id, track_type) DO UPDATE SET
                        xp_amount = EXCLUDED.xp_amount,
                        level = EXCLUDED.level
                """, [player_controller_id, track_type, xp_amount, level])
            else:
                cur.execute("""
                    INSERT INTO dune.specialization_tracks (player_id, track_type, xp_amount)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (player_id, track_type) DO UPDATE SET
                        xp_amount = EXCLUDED.xp_amount
                """, [player_controller_id, track_type, xp_amount])
            conn.commit()
            audit_logger.info(f"EDIT_XP: player_controller_id={player_controller_id} track={track_type} xp={xp_amount} level={level}")
            return True, {"track_type": track_type, "xp_amount": xp_amount, "level": level}
        except Exception as e:
            logger.error(f"Failed to edit XP for player {player_controller_id}: {e}")
            if conn:
                conn.rollback()
            return False, str(e)
        finally:
            if cur:
                cur.close()
            self.db.return_connection(conn)

    def edit_tech_knowledge(self, player_id, xp_points):
        if player_id is None or xp_points is None:
            return False, "Missing parameters"
        try:
            xp_points = int(xp_points)
        except (ValueError, TypeError):
            return False, "Invalid XP points value"

        conn = self.db.get_connection()
        if not conn:
            return False, "Database connection failed"
        cur = None
        try:
            cur = conn.cursor()
            cur.execute("""
                UPDATE dune.actors SET properties = jsonb_set(
                    properties,
                    '{TechKnowledgePlayerComponent,m_TechKnowledgePoints}',
                    to_jsonb(%s::int)
                ) WHERE id = %s
            """, [xp_points, player_id])
            conn.commit()
            audit_logger.info(f"EDIT_TECH_KNOWLEDGE: player_id={player_id} xp_points={xp_points}")
            return True, {"xp_points": xp_points}
        except Exception as e:
            logger.error(f"Failed to edit tech knowledge for player {player_id}: {e}")
            if conn:
                conn.rollback()
            return False, str(e)
        finally:
            if cur:
                cur.close()
            self.db.return_connection(conn)

    def edit_currency(self, player_controller_id, currency_id, new_balance):
        if player_controller_id is None or currency_id is None or new_balance is None:
            return False, "Missing parameters"
        try:
            new_balance = int(new_balance)
        except (ValueError, TypeError):
            return False, "Invalid balance value"

        conn = self.db.get_connection()
        if not conn:
            return False, "Database connection failed"
        cur = None
        try:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO dune.player_virtual_currency_balances (player_controller_id, currency_id, balance)
                VALUES (%s, %s, %s)
                ON CONFLICT (player_controller_id, currency_id) DO UPDATE SET
                    balance = EXCLUDED.balance
                RETURNING balance
            """, [player_controller_id, currency_id, new_balance])
            cur.fetchone()
            conn.commit()
            audit_logger.info(f"EDIT_CURRENCY: player_controller_id={player_controller_id} currency={currency_id} new_balance={new_balance}")
            return True, {"currency_id": currency_id, "new_balance": new_balance}
        except Exception as e:
            logger.error(f"Failed to edit currency for player {player_controller_id}: {e}")
            if conn:
                conn.rollback()
            return False, str(e)
        finally:
            if cur:
                cur.close()
            self.db.return_connection(conn)

    def edit_item(self, item_id, field, value):
        if item_id is None or field is None or value is None:
            return False, "Missing parameters"
        allowed_fields = ('stack_size', 'quality_level', 'is_new', 'durability', 'max_durability', 'ammo')
        if field not in allowed_fields:
            return False, f"Invalid field. Allowed: {', '.join(allowed_fields)}"

        conn = self.db.get_connection()
        if not conn:
            return False, "Database connection failed"
        cur = None
        try:
            cur = conn.cursor()
            if field == 'is_new':
                cur.execute(
                    "UPDATE dune.items SET is_new = %s WHERE id = %s RETURNING id, stack_size, quality_level, is_new",
                    [bool(value), item_id]
                )
            elif field in ('durability', 'max_durability', 'ammo'):
                stats_path = {
                    'durability': '{FItemStackAndDurabilityStats,CurrentDurability}',
                    'max_durability': '{FItemStackAndDurabilityStats,DecayedMaxDurability}',
                    'ammo': '{FWeaponItemStats,CurrentAmmo}',
                }[field]
                cur.execute(
                    "UPDATE dune.items SET stats = jsonb_set(stats, %s, %s::jsonb, true) WHERE id = %s RETURNING id",
                    [stats_path.split(','), str(value), item_id]
                )
                row = cur.fetchone()
                if not row:
                    conn.rollback()
                    return False, "Item not found"
                conn.commit()
                audit_logger.info(f"EDIT_ITEM: item_id={item_id} field={field} value={value}")
                return True, {"item_id": item_id, "field": field, "value": value}
            else:
                cur.execute(
                    "UPDATE dune.items SET {} = %s WHERE id = %s RETURNING id, stack_size, quality_level, is_new".format(field),
                    [int(value), item_id]
                )
            row = cur.fetchone()
            if not row:
                conn.rollback()
                return False, "Item not found"
            conn.commit()
            if isinstance(row, dict):
                value_result = row.get(field)
            else:
                field_index = {'id': 0, 'stack_size': 1, 'quality_level': 2, 'is_new': 3}.get(field, 0)
                value_result = row[field_index]
            audit_logger.info(f"EDIT_ITEM: item_id={item_id} field={field} value={value}")
            return True, {"item_id": item_id, "field": field, "value": value_result}
        except Exception as e:
            logger.error(f"Failed to edit item {item_id}: {e}")
            if conn:
                conn.rollback()
            return False, str(e)
        finally:
            if cur:
                cur.close()
            self.db.return_connection(conn)

    def delete_item(self, item_id):
        if item_id is None:
            return False, "Missing item_id"

        conn = self.db.get_connection()
        if not conn:
            return False, "Database connection failed"
        cur = None
        try:
            cur = conn.cursor()
            cur.execute("SELECT template_id FROM dune.items WHERE id = %s", [item_id])
            row = cur.fetchone()
            if not row:
                conn.rollback()
                return False, "Item not found"
            template_name = row[0] if isinstance(row, (tuple, list)) else row.get('template_id')
            cur.execute("DELETE FROM dune.items WHERE id = %s", [item_id])
            conn.commit()
            audit_logger.info(f"DELETE_ITEM: item_id={item_id} template={template_name}")
            return True, {"item_id": item_id, "template_id": template_name}
        except Exception as e:
            logger.error(f"Failed to delete item {item_id}: {e}")
            if conn:
                conn.rollback()
            return False, str(e)
        finally:
            if cur:
                cur.close()
            self.db.return_connection(conn)

    def add_item(self, inventory_id, template_id, stack_size=1, quality_level=0):
        if inventory_id is None or template_id is None:
            return False, "Missing inventory_id or template_id"
        try:
            stack_size = int(stack_size)
        except (ValueError, TypeError):
            stack_size = 1
        try:
            quality_level = int(quality_level)
        except (ValueError, TypeError):
            quality_level = 0

        conn = self.db.get_connection()
        if not conn:
            return False, "Database connection failed"
        cur = None
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM dune.inventories WHERE id = %s", [inventory_id])
            row = cur.fetchone()
            if not row or (isinstance(row, dict) and not row.get('id')):
                conn.rollback()
                return False, "Inventory not found"

            cur.execute("""
                INSERT INTO dune.items (inventory_id, template_id, stack_size, quality_level, is_new, position_index, stats)
                VALUES (%s, %s, %s, %s, FALSE, (SELECT COALESCE(MAX(position_index), 0) + 1 FROM dune.items WHERE inventory_id = %s), '{}')
                RETURNING id
            """, [inventory_id, template_id, stack_size, quality_level, inventory_id])
            row = cur.fetchone()
            conn.commit()
            if row:
                new_item_id = row[0] if isinstance(row, (tuple, list)) else row.get('id')
            else:
                new_item_id = None
            audit_logger.info(f"ADD_ITEM: inventory_id={inventory_id} template={template_id} stack={stack_size} quality={quality_level} new_item_id={new_item_id}")
            return True, {"item_id": new_item_id, "template_id": template_id}
        except Exception as e:
            logger.error(f"Failed to add item to inventory {inventory_id}: {e}")
            if conn:
                conn.rollback()
            return False, str(e)
        finally:
            if cur:
                cur.close()
            self.db.return_connection(conn)

    def send_global_broadcast(self, title, message, duration=30):
        """Send an in-game broadcast via RabbitMQ rabbitmqctl eval on the VM."""
        try:
            import base64
            import json as _json
            title_json = _json.dumps(title)[1:-1]
            message_json = _json.dumps(message)[1:-1]

            erl = (
                f'Title = unicode:characters_to_binary(<<"{title_json}">>, utf8), '
                f'Body = unicode:characters_to_binary(<<"{message_json}">>, utf8), '
                f'Duration = {duration}, '
                'EntryEn = #{<<"Key">> => <<"en">>, <<"Title">> => Title, <<"Body">> => Body}, '
                'EntryEnUs = #{<<"Key">> => <<"en-US">>, <<"Title">> => Title, <<"Body">> => Body}, '
                'Inner = iolist_to_binary(rabbit_json:encode(#{<<"ServerCommand">> => <<"ServiceBroadcast">>, <<"BroadcastType">> => <<"Generic">>, <<"BroadcastPayload">> => #{<<"BroadcastDuration">> => Duration, <<"LocalizedText">> => [EntryEn, EntryEnUs]}})), '
                'Outer = iolist_to_binary(rabbit_json:encode(#{<<"Version">> => 2, <<"AuthToken">> => <<"Nu6VmPWUMvdPMeB7qErr">>, <<"MessageContent">> => Inner})), '
                'XName = rabbit_misc:r(<<"/">>, exchange, <<"heartbeats">>), '
                'X = rabbit_exchange:lookup_or_die(XName), '
                'MsgId = list_to_binary("manual-service-broadcast-" ++ integer_to_list(erlang:system_time(millisecond))), '
                'P = {list_to_atom("P_basic"), <<"Content">>, undefined, [], undefined, undefined, undefined, undefined, undefined, MsgId, undefined, undefined, <<"fls">>, <<"fls_backend">>, undefined}, '
                'Content = rabbit_basic:build_content(P, Outer), '
                '{ok, Msg} = rabbit_basic:message(XName, <<"notifications">>, Content), '
                'Result = rabbit_queue_type:publish_at_most_once(X, Msg), '
                'io:format("broadcast=~p duration=~p~n", [Result, Duration]).'
            )

            ns = self._detect_namespace()
            pod_name = ns.replace('funcom-seabass-', '') + '-mq-game-sts-0'
            b64 = base64.b64encode(erl.encode()).decode()

            # Write erl on VM host, then pipe it into the pod via kubectl exec -i
            wcmd = f"echo {b64} | base64 -d | sudo tee /tmp/dune_bc.erl > /dev/null"
            wout, werr, wrc = self.ssh.run(wcmd)
            if wrc != 0:
                return False, f"write failed: {werr}"

            # Cat the host file and pipe into kubectl exec -i to write inside the pod
            ecmd = (
                f"cat /tmp/dune_bc.erl | sudo kubectl exec -i -n {ns} {pod_name} -- sh -lc '"
                "cat > /tmp/dune_bc.erl; "
                "export PATH=/opt/rabbitmq/sbin:/opt/erlang/lib/erlang/bin:/opt/erlang/lib/erlang/erts-14.2.5.12/bin:/bin:/usr/bin:/usr/local/bin:$PATH; "
                'rabbitmqctl eval "$(cat /tmp/dune_bc.erl)"; '
                "rm -f /tmp/dune_bc.erl'"
            )
            out, err, rc = self.ssh.run(ecmd)

            self.ssh.run("rm -f /tmp/dune_bc.erl")

            if rc != 0:
                return False, f"Broadcast failed (rc={rc}): {err}"

            audit_logger.info(f"BROADCAST: title={title} message={message} duration={duration}")
            return True, "Broadcast sent successfully"
        except Exception as e:
            logger.error(f"Broadcast error: {e}")
            try:
                self.ssh.run("rm -f /tmp/dune_bc.erl")
            except Exception:
                pass
            return False, str(e)

    def admin_db_query(self, sql, params=None):
        """Execute a read-only SQL query and return results."""
        return self.db.query(sql, params)

    def admin_db_execute(self, sql, params=None):
        """Execute a SQL statement (insert/update/delete/call) and commit."""
        conn = self.db.get_connection()
        if not conn:
            return False, "DB connection failed"
        cur = None
        try:
            cur = conn.cursor()
            cur.execute(sql, params or [])
            conn.commit()
            if cur.description:
                rows = cur.fetchall()
                if rows and isinstance(rows[0], dict):
                    return True, rows
                cols = [d.name for d in cur.description]
                return True, [dict(zip(cols, r)) for r in rows]
            return True, f"Executed, rows affected: {cur.rowcount}"
        except Exception as e:
            conn.rollback()
            return False, str(e)
        finally:
            if cur:
                cur.close()
            self.db.return_connection(conn)

    def search_players(self, term):
        """Search characters by name."""
        like = f'%{term}%'
        result = self.db.query("""
            SELECT ea.id, ea.user,
                   COALESCE(NULLIF(ps.character_name, ''), 'Unknown') as character_name
            FROM dune.encrypted_accounts ea
            LEFT JOIN dune.player_state ps ON ea.id = ps.account_id
            WHERE lower(ea.user) LIKE lower(%s)
               OR lower(ps.character_name) LIKE lower(%s)
            ORDER BY ea.user
            LIMIT 50
        """, [like, like])
        return result or []

    def get_online_players(self):
        """Get all online or recently disconnected players."""
        result = self.db.query("""
            SELECT a.id as player_controller_id,
                   COALESCE(NULLIF(ps.character_name, ''), 'Unknown') as character_name,
                   a.map,
                   ps.online_status,
                   ps.last_avatar_activity
            FROM dune.actors a
            JOIN dune.player_state ps ON ps.player_controller_id = a.id
            WHERE ps.online_status = 'Online'
               OR ps.last_avatar_activity > NOW() - INTERVAL '1 minute'
            ORDER BY ps.character_name
        """)
        return result or []

    def adjust_currency(self, player_controller_id, currency_id, delta):
        """Add/remove virtual currency from a player."""
        try:
            conn = self.db.get_connection()
            if not conn:
                return False, "DB connection failed"
            cur = None
            try:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO dune.player_virtual_currency_balances (player_controller_id, currency_id, balance)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (player_controller_id, currency_id) DO UPDATE SET balance = (dune.player_virtual_currency_balances.balance + %s)
                    RETURNING balance
                """, [player_controller_id, currency_id, delta, delta])
                new_balance = cur.fetchone()[0]
                conn.commit()
                audit_logger.info(f"CURRENCY_ADJUST: player={player_controller_id} currency={currency_id} delta={delta} new_balance={new_balance}")
                return True, f"Currency {currency_id} adjusted by {delta}. New balance: {new_balance}"
            except Exception as e:
                conn.rollback()
                return False, str(e)
            finally:
                if cur:
                    cur.close()
                self.db.return_connection(conn)
        except Exception as e:
            return False, str(e)

    def change_faction(self, player_id, faction_id):
        """Change a player's faction."""
        try:
            conn = self.db.get_connection()
            if not conn:
                return False, "DB connection failed"
            cur = None
            try:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO dune.player_faction (actor_id, faction_id, utc_time_faction_change)
                    VALUES (%s, %s, NOW())
                    ON CONFLICT (actor_id) DO UPDATE SET faction_id = %s, utc_time_faction_change = NOW()
                """, [player_id, faction_id, faction_id])
                conn.commit()
                audit_logger.info(f"FACTION_CHANGE: player={player_id} faction={faction_id}")
                return True, f"Faction changed to {faction_id}"
            except Exception as e:
                conn.rollback()
                return False, str(e)
            finally:
                if cur:
                    cur.close()
                self.db.return_connection(conn)
        except Exception as e:
            return False, str(e)

    # ── View Currency Balances ─────────────────────────────────────────
    def get_currency_balances(self, player_controller_id):
        """Get virtual currency balances for a player."""
        result = self.db.query(
            "SELECT currency_id, balance FROM dune.player_virtual_currency_balances WHERE player_controller_id = %s ORDER BY currency_id",
            [player_controller_id]
        )
        return result or []

    # ── Teleport Player ────────────────────────────────────────────────
    def teleport_player(self, fls_id, partition_id, x, y, z):
        """Teleport an offline player to a partition using direct SQL."""
        conn = self.db.get_connection()
        if not conn:
            return False, "DB connection failed"
        cur = None
        try:
            cur = conn.cursor()
            # Set search_path so unqualified references in the function resolve
            cur.execute("SET search_path TO dune, public")
            cur.execute("""
                SELECT dune.admin_move_offline_player_to_partition(
                    %s, %s, ROW(%s, %s, %s)::dune.vector
                )
            """, [fls_id, int(partition_id), float(x), float(y), float(z)])
            conn.commit()
            audit_logger.info(f"TELEPORT: fls_id={fls_id} partition={partition_id} loc=({x},{y},{z})")
            return True, f"Teleported to partition {partition_id}"
        except Exception as e:
            conn.rollback()
            return False, str(e)
        finally:
            if cur: cur.close()
            self.db.return_connection(conn)

    def get_partitions(self):
        """List all available partitions."""
        result = self.db.query("""
            SELECT partition_id as id, map, dimension_index, label, partition_definition::text
            FROM dune.world_partition
            ORDER BY map, dimension_index, partition_id
            LIMIT 100
        """)
        return result or []

    # ── Faction Reputation (direct SQL) ────────────────────────────────
    def get_faction_reputation(self, actor_id):
        """Get faction reputation for a player."""
        result = self.db.query("""
            SELECT pf.faction_id, COALESCE(pfr.reputation_amount, 0) as reputation_amount
            FROM dune.player_faction pf
            LEFT JOIN dune.player_faction_reputation pfr ON pfr.actor_id = pf.actor_id AND pfr.faction_id = pf.faction_id
            WHERE pf.actor_id = %s
            LIMIT 1
        """, [actor_id])
        return result or []

    def set_faction_reputation(self, actor_id, faction_id, amount):
        """Set faction reputation for a player."""
        try:
            conn = self.db.get_connection()
            if not conn:
                return False, "DB connection failed"
            cur = None
            try:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO dune.player_faction_reputation (actor_id, faction_id, reputation_amount)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (actor_id, faction_id) DO UPDATE SET reputation_amount = %s
                """, [actor_id, faction_id, amount, amount])
                conn.commit()
                audit_logger.info(f"FACTION_REP: actor={actor_id} faction={faction_id} amount={amount}")
                return True, f"Reputation set to {amount}"
            except Exception as e:
                conn.rollback()
                return False, str(e)
            finally:
                if cur: cur.close()
                self.db.return_connection(conn)
        except Exception as e:
            return False, str(e)

    # ── Inventory Lookup (direct SQL) ─────────────────────────────────
    def get_inventory(self, account_id):
        """Get inventory details for an account."""
        result = self.db.query("""
            SELECT inv.id as inventory_id, inv.actor_id, i.id as item_id, i.template_id, i.stack_size as count, i.position_index
            FROM dune.inventories inv
            JOIN dune.items i ON i.inventory_id = inv.id
            WHERE inv.actor_id IN (SELECT id FROM dune.actors WHERE owner_account_id = %s)
            ORDER BY inv.id, i.position_index
            LIMIT 200
        """, [account_id])
        return result or []

    def get_player_pawn(self, account_id):
        """Get player pawn info by account id."""
        result = self.db.query("""
            SELECT a.id, a.class, a.map, a.owner_account_id as account_id
            FROM dune.actors a
            WHERE a.owner_account_id = %s AND a.class LIKE '%%PlayerPawn_C%%'
            LIMIT 5
        """, [account_id])
        return result or []

    # ── Guild Tools (direct SQL) ───────────────────────────────────────
    def get_guild_data(self, guild_id):
        """Get guild data."""
        result = self.db.query("""
            SELECT g.*, 
                (SELECT COUNT(*) FROM dune.guild_members gm WHERE gm.guild_id = g.id) as member_count
            FROM dune.guilds g WHERE g.id = %s
        """, [guild_id])
        return result or []

    def get_all_guilds(self):
        """Get all guilds."""
        result = self.db.query("""
            SELECT g.*, 
                (SELECT COUNT(*) FROM dune.guild_members gm WHERE gm.guild_id = g.id) as member_count
            FROM dune.guilds g
            ORDER BY g.id
        """)
        return result or []

    def disband_guild(self, guild_id):
        """Disband a guild via function."""
        try:
            conn = self.db.get_connection()
            if not conn:
                return False, "DB connection failed"
            cur = None
            try:
                cur = conn.cursor()
                cur.execute("SELECT dune.disband_guild(%s)", [guild_id])
                conn.commit()
                audit_logger.info(f"GUILD_DISBAND: guild_id={guild_id}")
                return True, f"Guild {guild_id} disbanded"
            except Exception as e:
                conn.rollback()
                return False, str(e)
            finally:
                if cur: cur.close()
                self.db.return_connection(conn)
        except Exception as e:
            return False, str(e)

    def remove_guild_member(self, guild_id, player_id):
        """Remove a member from a guild."""
        try:
            conn = self.db.get_connection()
            if not conn:
                return False, "DB connection failed"
            cur = None
            try:
                cur = conn.cursor()
                cur.execute("DELETE FROM dune.guild_members WHERE guild_id = %s AND player_id = %s", [guild_id, player_id])
                conn.commit()
                audit_logger.info(f"GUILD_KICK: guild={guild_id} player={player_id}")
                return True, f"Player {player_id} removed from guild"
            except Exception as e:
                conn.rollback()
                return False, str(e)
            finally:
                if cur: cur.close()
                self.db.return_connection(conn)
        except Exception as e:
            return False, str(e)

    # ── Player Tags (direct SQL) ───────────────────────────────────────
    def get_player_tags(self, account_id):
        """Read player tags."""
        result = self.db.query(
            "SELECT tag FROM dune.player_tags WHERE account_id = %s ORDER BY tag",
            [account_id]
        )
        return result or []

    def update_player_tags(self, account_id, tags_to_add, tags_to_remove):
        """Update player tags."""
        try:
            conn = self.db.get_connection()
            if not conn:
                return False, "DB connection failed"
            cur = None
            try:
                cur = conn.cursor()
                for tag in tags_to_add:
                    cur.execute(
                        "INSERT INTO dune.player_tags (account_id, tag) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                        [account_id, tag]
                    )
                if tags_to_remove:
                    cur.execute(
                        "DELETE FROM dune.player_tags WHERE account_id = %s AND tag = ANY(%s)",
                        [account_id, tags_to_remove]
                    )
                conn.commit()
                audit_logger.info(f"TAGS_UPDATE: account={account_id} add={tags_to_add} remove={tags_to_remove}")
                return True, "Tags updated"
            except Exception as e:
                conn.rollback()
                return False, str(e)
            finally:
                if cur: cur.close()
                self.db.return_connection(conn)
        except Exception as e:
            return False, str(e)

    def flag_cheater(self, account_id, cheat_type):
        """Flag a player as cheater."""
        try:
            conn = self.db.get_connection()
            if not conn:
                return False, "DB connection failed"
            cur = None
            try:
                cur = conn.cursor()
                # Add cheater tag
                cur.execute(
                    "INSERT INTO dune.player_tags (account_id, tag) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    [account_id, f'cheater_{cheat_type}']
                )
                conn.commit()
                audit_logger.info(f"CHEATER_FLAG: account={account_id} type={cheat_type}")
                return True, f"Flagged as {cheat_type}"
            except Exception as e:
                conn.rollback()
                return False, str(e)
            finally:
                if cur: cur.close()
                self.db.return_connection(conn)
        except Exception as e:
            return False, str(e)

    # ── Vehicles (direct SQL) ─────────────────────────────────────────
    def get_player_vehicles(self, player_id, account_id):
        """Get vehicles owned by a player."""
        result = self.db.query("""
            SELECT v.id as vehicle_id, v.actor_id, a.class, a.map, a.owner_account_id as account_id
            FROM dune.vehicles v
            JOIN dune.actors a ON a.id = v.actor_id
            WHERE a.owner_account_id = %s
            ORDER BY v.id
            LIMIT 50
        """, [account_id])
        return result or []

    # ── Character Management ───────────────────────────────────────────
    def set_character_name(self, account_id, new_name):
        """Rename a character."""
        try:
            conn = self.db.get_connection()
            if not conn: return False, "DB connection failed"
            cur = None
            try:
                cur = conn.cursor()
                cur.execute("UPDATE dune.player_state SET character_name = %s WHERE account_id = %s", [new_name, account_id])
                conn.commit()
                audit_logger.info(f"RENAME: account={account_id} new_name={new_name}")
                return True, f"Renamed to {new_name}"
            except Exception as e:
                conn.rollback(); return False, str(e)
            finally:
                if cur: cur.close(); self.db.return_connection(conn)
        except Exception as e: return False, str(e)

    def delete_character(self, actor_id):
        """Delete a character."""
        try:
            conn = self.db.get_connection()
            if not conn: return False, "DB connection failed"
            cur = None
            try:
                cur = conn.cursor()
                cur.execute("SELECT dune.delete_character(%s)", [actor_id])
                conn.commit()
                audit_logger.info(f"DELETE_CHAR: actor_id={actor_id}")
                return True, f"Character {actor_id} deleted"
            except Exception as e:
                conn.rollback(); return False, str(e)
            finally:
                if cur: cur.close(); self.db.return_connection(conn)
        except Exception as e: return False, str(e)

    def delete_account(self, user_id, reason='admin'):
        """Delete an account."""
        try:
            conn = self.db.get_connection()
            if not conn: return False, "DB connection failed"
            cur = None
            try:
                cur = conn.cursor()
                cur.execute("SELECT dune.delete_account(%s, %s)", [user_id, reason])
                conn.commit()
                audit_logger.info(f"DELETE_ACCOUNT: user={user_id} reason={reason}")
                return True, f"Account {user_id} deleted"
            except Exception as e:
                conn.rollback(); return False, str(e)
            finally:
                if cur: cur.close(); self.db.return_connection(conn)
        except Exception as e: return False, str(e)

    def set_demo_state(self, user_id, demo_state):
        """Set demo state for an account."""
        try:
            conn = self.db.get_connection()
            if not conn: return False, "DB connection failed"
            cur = None
            try:
                cur = conn.cursor()
                cur.execute("SELECT dune.set_demo_state(%s, %s::dune.demostate)", [user_id, demo_state])
                conn.commit()
                audit_logger.info(f"DEMO: user={user_id} state={demo_state}")
                return True, f"Demo state set to {demo_state}"
            except Exception as e:
                conn.rollback(); return False, str(e)
            finally:
                if cur: cur.close(); self.db.return_connection(conn)
        except Exception as e: return False, str(e)

    # ── Journey / Progression ─────────────────────────────────────────
    def complete_journey_nodes(self, account_id, node_ids):
        """Complete journey story nodes for a player."""
        try:
            conn = self.db.get_connection()
            if not conn: return False, "DB connection failed"
            cur = None
            try:
                cur = conn.cursor()
                cur.execute("SELECT dune.complete_journey_story_nodes_for_player(%s, %s)", [str(account_id), node_ids])
                conn.commit()
                audit_logger.info(f"JOURNEY_COMPLETE: account={account_id} nodes={node_ids}")
                return True, f"Completed {len(node_ids)} nodes"
            except Exception as e:
                conn.rollback(); return False, str(e)
            finally:
                if cur: cur.close(); self.db.return_connection(conn)
        except Exception as e: return False, str(e)

    def reveal_journey_nodes(self, account_id, node_ids):
        """Reveal journey story nodes for a player."""
        try:
            conn = self.db.get_connection()
            if not conn: return False, "DB connection failed"
            cur = None
            try:
                cur = conn.cursor()
                cur.execute("SELECT dune.reveal_journey_story_nodes_for_player(%s, %s)", [str(account_id), node_ids])
                conn.commit()
                audit_logger.info(f"JOURNEY_REVEAL: account={account_id} nodes={node_ids}")
                return True, f"Revealed {len(node_ids)} nodes"
            except Exception as e:
                conn.rollback(); return False, str(e)
            finally:
                if cur: cur.close(); self.db.return_connection(conn)
        except Exception as e: return False, str(e)

    def reset_journey_nodes(self, account_id, node_ids):
        """Reset journey story nodes for a player."""
        try:
            conn = self.db.get_connection()
            if not conn: return False, "DB connection failed"
            cur = None
            try:
                cur = conn.cursor()
                cur.execute("SELECT dune.reset_journey_story_nodes_for_player(%s, %s)", [str(account_id), node_ids])
                conn.commit()
                audit_logger.info(f"JOURNEY_RESET: account={account_id} nodes={node_ids}")
                return True, f"Reset {len(node_ids)} nodes"
            except Exception as e:
                conn.rollback(); return False, str(e)
            finally:
                if cur: cur.close(); self.db.return_connection(conn)
        except Exception as e: return False, str(e)

    def set_specialization(self, player_id, track_type, xp, level):
        """Set specialization XP and level."""
        try:
            conn = self.db.get_connection()
            if not conn: return False, "DB connection failed"
            cur = None
            try:
                cur = conn.cursor()
                # track_type is a dune.specializationtracktype enum
                cur.execute(
                    "SELECT dune.set_specialization_xp_and_level(%s, %s::dune.specializationtracktype, %s, %s)",
                    [player_id, track_type, xp, level]
                )
                conn.commit()
                audit_logger.info(f"SPEC_SET: player={player_id} track={track_type} xp={xp} level={level}")
                return True, f"Specialization {track_type} set to level {level}"
            except Exception as e:
                conn.rollback(); return False, str(e)
            finally:
                if cur: cur.close(); self.db.return_connection(conn)
        except Exception as e: return False, str(e)

    def reset_specialization(self, player_id):
        """Reset all specialization tracks for a player."""
        try:
            conn = self.db.get_connection()
            if not conn: return False, "DB connection failed"
            cur = None
            try:
                cur = conn.cursor()
                cur.execute("SELECT dune.reset_specialization_tracks(%s)", [player_id])
                conn.commit()
                audit_logger.info(f"SPEC_RESET: player={player_id}")
                return True, "Specialization tracks reset"
            except Exception as e:
                conn.rollback(); return False, str(e)
            finally:
                if cur: cur.close(); self.db.return_connection(conn)
        except Exception as e: return False, str(e)

    # ── Guild Roster ───────────────────────────────────────────────────
    def get_guild_members(self, guild_id):
        """Get all members of a guild."""
        result = self.db.query("""
            SELECT gm.player_id, gm.role_id, COALESCE(NULLIF(ps.character_name, ''), 'Unknown') as name
            FROM dune.guild_members gm
            LEFT JOIN dune.player_state ps ON ps.player_controller_id = gm.player_id
            WHERE gm.guild_id = %s
            ORDER BY gm.role_id, ps.character_name
        """, [guild_id])
        return result or []

    def promote_guild_member(self, guild_id, player_id, new_role):
        """Promote/demote a guild member."""
        try:
            conn = self.db.get_connection()
            if not conn: return False, "DB connection failed"
            cur = None
            try:
                cur = conn.cursor()
                cur.execute("SELECT dune.promote_guild_member(%s, %s, %s)", [guild_id, player_id, new_role])
                conn.commit()
                audit_logger.info(f"GUILD_PROMOTE: guild={guild_id} player={player_id} role={new_role}")
                return True, f"Player {player_id} now role {new_role}"
            except Exception as e:
                conn.rollback(); return False, str(e)
            finally:
                if cur: cur.close(); self.db.return_connection(conn)
        except Exception as e: return False, str(e)

    # ── Economy / Vendors ──────────────────────────────────────────────
    def clean_player_vendor_stock(self, player_id):
        """Reset vendor buy limits for a player."""
        try:
            conn = self.db.get_connection()
            if not conn: return False, "DB connection failed"
            cur = None
            try:
                cur = conn.cursor()
                cur.execute("SELECT dune.clean_stock_for_player(%s)", [player_id])
                conn.commit()
                audit_logger.info(f"VENDOR_CLEAN: player={player_id}")
                return True, f"Vendor stock reset for player {player_id}"
            except Exception as e:
                conn.rollback(); return False, str(e)
            finally:
                if cur: cur.close(); self.db.return_connection(conn)
        except Exception as e: return False, str(e)

    def get_player_tax_invoices(self, player_id):
        """Get tax invoices for a player."""
        result = self.db.query(
            "SELECT * FROM dune.taxation_get_all_invoices_for_player(%s)",
            [player_id]
        )
        return result or []

    # ── Spice Fields ───────────────────────────────────────────────────
    def force_spice_spawn(self, server_id, spicefield_type_id):
        """Request a spice field spawn."""
        try:
            conn = self.db.get_connection()
            if not conn: return False, "DB connection failed"
            cur = None
            try:
                cur = conn.cursor()
                cur.execute("SELECT dune.request_spawn_spice_field(%s, %s)", [server_id, spicefield_type_id])
                conn.commit()
                audit_logger.info(f"SPICE_SPAWN: server={server_id} type={spicefield_type_id}")
                return True, f"Spice field spawn requested on {server_id}"
            except Exception as e:
                conn.rollback(); return False, str(e)
            finally:
                if cur: cur.close(); self.db.return_connection(conn)
        except Exception as e: return False, str(e)

    def reset_spice_state(self, map_name, dimension_index):
        """Reset global spice field state."""
        try:
            conn = self.db.get_connection()
            if not conn: return False, "DB connection failed"
            cur = None
            try:
                cur = conn.cursor()
                cur.execute("SELECT dune.reset_global_spice_field_state(%s, %s)", [map_name, dimension_index])
                conn.commit()
                audit_logger.info(f"SPICE_RESET: map={map_name} dim={dimension_index}")
                return True, f"Spice state reset on {map_name}"
            except Exception as e:
                conn.rollback(); return False, str(e)
            finally:
                if cur: cur.close(); self.db.return_connection(conn)
        except Exception as e: return False, str(e)

    # ── Server Tools ───────────────────────────────────────────────────
    def set_players_offline(self, server_ids):
        """Set all players on given servers to offline."""
        try:
            conn = self.db.get_connection()
            if not conn: return False, "DB connection failed"
            cur = None
            try:
                cur = conn.cursor()
                cur.execute("SELECT dune.set_players_from_server_ids_offline(%s)", [server_ids])
                conn.commit()
                audit_logger.info(f"SET_OFFLINE: servers={server_ids}")
                return True, f"Players set offline on {len(server_ids)} servers"
            except Exception as e:
                conn.rollback(); return False, str(e)
            finally:
                if cur: cur.close(); self.db.return_connection(conn)
        except Exception as e: return False, str(e)

    def cleanup_orphaned(self):
        """Clean up orphaned entities in the database."""
        try:
            conn = self.db.get_connection()
            if not conn: return False, "DB connection failed"
            cur = None
            try:
                cur = conn.cursor()
                cur.execute("SELECT dune.cleanup_orphaned_entities()")
                conn.commit()
                audit_logger.info("CLEANUP_ORPHANS")
                return True, "Orphaned entities cleaned up"
            except Exception as e:
                conn.rollback(); return False, str(e)
            finally:
                if cur: cur.close(); self.db.return_connection(conn)
        except Exception as e: return False, str(e)

    # ── Permission Management ─────────────────────────────────────────
    def get_actor_permissions(self, actor_id):
        """Get permissions for an actor."""
        result = self.db.query(
            "SELECT * FROM dune.get_permission_for_actor(%s)",
            [actor_id]
        )
        return result or []

    def set_player_rank(self, actor_id, player_id, rank, map_id=''):
        """Set a player's rank on an actor."""
        try:
            conn = self.db.get_connection()
            if not conn: return False, "DB connection failed"
            cur = None
            try:
                cur = conn.cursor()
                cur.execute("SELECT dune.permission_set_player_rank(%s, %s, %s, %s)", [actor_id, player_id, rank, map_id])
                conn.commit()
                audit_logger.info(f"RANK_SET: actor={actor_id} player={player_id} rank={rank}")
                return True, f"Rank {rank} set for player {player_id}"
            except Exception as e:
                conn.rollback(); return False, str(e)
            finally:
                if cur: cur.close(); self.db.return_connection(conn)
        except Exception as e: return False, str(e)

    # ── Player Stats (from actors.properties JSONB) ───────────────────
    def get_player_stats(self, player_controller_id):
        """Get player health and stats from actor properties."""
        result = self.db.query("""
            WITH pawn AS (
                SELECT id, properties FROM dune.actors
                WHERE id = (SELECT player_pawn_id FROM dune.player_state WHERE player_controller_id = %s)
            ),
            ctrl AS (
                SELECT properties FROM dune.actors WHERE id = %s
            )
            SELECT
                pawn.id as pawn_id,
                pawn.properties::text as pawn_props,
                ctrl.properties::text as ctrl_props
            FROM pawn, ctrl
        """, [player_controller_id, player_controller_id])
        if not result:
            return None
        row = result[0]
        import json
        pawn = json.loads(row.get('pawn_props') or '{}')
        ctrl = json.loads(row.get('ctrl_props') or '{}')
        stats = {'pawn_id': row['pawn_id']}

        # Health
        dmg = pawn.get('DamageableActorComponent', {})
        stats['health'] = {'current': dmg.get('m_CurrentMaxHealth'), 'max': dmg.get('m_TotalMaxHealth')}

        # Character stats
        char = pawn.get('BP_DunePlayerCharacter_C', {})
        stats['eyes_of_ibad'] = char.get('m_EyesOfIbadValue')
        stats['heatstroke'] = char.get('m_bHeatstroke')
        stats['is_driving'] = char.get('m_bIsDriving')

        # Journey / Spice exposure
        journey = ctrl.get('BP_JourneyComponent_C', {})
        stats['spice_exposure_level'] = journey.get('CurrentSpiceExposureThresholdLevel')

        # Landsraad
        landsraad = ctrl.get('LandsraadCharacterComponent', {})
        stats['daily_reward_charges'] = landsraad.get('m_DailyRewardCharges')
        stats['last_viewed_term'] = landsraad.get('m_LastViewedLandsraadTermId')

        return stats

    # ── Dynamic Function Explorer ─────────────────────────────────────
    def list_all_functions(self):
        """List all dune schema functions with signatures."""
        result = self.db.query("""
            SELECT p.proname as name,
                   pg_get_function_identity_arguments(p.oid) as args,
                   l.lanname as language,
                   p.prokind as kind
            FROM pg_proc p
            JOIN pg_namespace n ON n.oid = p.pronamespace
            JOIN pg_language l ON l.oid = p.prolang
            WHERE n.nspname = 'dune' AND p.prokind = 'f'
            ORDER BY p.proname
        """)
        return result or []

    def execute_function(self, function_name, params):
        """Execute any dune schema function dynamically."""
        try:
            param_placeholders = ','.join(['%s'] * len(params))
            sql = f"SELECT * FROM dune.{function_name}({param_placeholders})"
            result = self.db.query(sql, params)
            audit_logger.info(f"EXEC_FUNC: {function_name}({params})")
            return True, result, None
        except Exception as e:
            return False, None, str(e)

    def get_function_details(self, function_name):
        """Get full definition of a function."""
        result = self.db.query("""
            SELECT pg_get_functiondef(p.oid) as definition,
                   p.proname as name,
                   pg_get_function_identity_arguments(p.oid) as args
            FROM pg_proc p
            JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = 'dune' AND p.proname = %s AND p.prokind = 'f'
        """, [function_name])
        return result[0] if result else None

    def _detect_namespace(self):
        out, err, rc = self.ssh.run(
            "sudo kubectl get pods -A --no-headers -o custom-columns=NS:.metadata.namespace,NAME:.metadata.name "
            "| awk '$1 ~ /^funcom-seabass-/ && $2 ~ /-mq-game-sts-0$/ { print $1 }' | sort -u"
        )
        if out:
            ns = out.strip().split('\n')[0]
            if ns:
                return ns
        return "funcom-seabass-sh-b17a5f036d1f7882-ccdijf"
