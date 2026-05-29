"""API routes - server actions, player management, debug endpoints"""

import json
import logging
import os
import re
import shlex
import time
from datetime import datetime
from flask import Blueprint, request, jsonify
from flask_login import login_required
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from app.utils.constants import NAV_PAGES

logger = logging.getLogger(__name__)

K8S_NAME_RE = re.compile(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")


def require_k8s_name(value, label):
    """Validate that a value is a valid Kubernetes resource name."""
    value = str(value or "").strip()
    if not value or not K8S_NAME_RE.fullmatch(value):
        raise ValueError(f"Invalid {label}")
    return value


def quote_remote(value):
    """Shell-quote a value for safe use in remote commands."""
    return shlex.quote(str(value))


def register_api_routes(app, services, settings):
    db = services['db']
    ssh = services['ssh']
    k8s = services['k8s']
    chat_svc = services['chat']
    admin_svc = services['admin']
    vehicle_svc = services['vehicle']
    audit_svc = services.get('audit')

# Get or create rate limiter - use existing one from factory if available
    if not hasattr(app, 'limiter'):
        limiter = Limiter(
            app=app,
            key_func=get_remote_address,
            default_limits=[],  # Disabled
            storage_uri="memory://",
        )
    else:
        limiter = app.limiter

    # Only require login if auth is enabled
    auth_req = login_required if settings.get('auth', {}).get('enabled', True) else lambda f: f

    # Server actions
    @app.route('/server/action', methods=['POST'])
    @auth_req
    @limiter.limit("500 per hour")
    def server_action():
        deployment = request.form.get('deployment', '')
        action = request.form.get('action', '')
        if not deployment or not action:
            return jsonify({'success': False, 'output': 'Missing deployment or action'})
        try:
            deployment = require_k8s_name(deployment, 'deployment')
        except ValueError as e:
            return jsonify({'success': False, 'output': str(e)})

        actions = {
            'restart': f'rollout restart deployment/{deployment}',
            'status': f'rollout status deployment/{deployment}',
            'scale_0': f'scale deployment/{deployment} --replicas=0',
            'scale_1': f'scale deployment/{deployment} --replicas=1',
            'describe': f'describe deployment/{deployment}',
        }
        cmd = actions.get(action)
        if not cmd:
            return jsonify({'success': False, 'output': f'Unknown action: {action}'})

        out, err, rc = k8s.run(cmd)
        
        # Audit logging for server actions
        if audit_svc and action in ['restart', 'scale_0', 'scale_1']:
            severity = 'warning' if action in ['restart', 'scale_0'] else 'info'
            audit_svc.log(f'server_{action}', {'deployment': deployment, 'result': rc}, user='admin', severity=severity)
        
        return jsonify({'success': rc == 0, 'output': out + '\n' + err})

    @app.route('/server/pods')
    @auth_req
    def server_pods():
        out, err, rc = k8s.run('get pods -o wide')
        if rc != 0:
            return jsonify({'success': False, 'output': err})
        return jsonify({'success': True, 'output': out})

    @app.route('/server/metrics')
    @auth_req
    def server_metrics():
        metrics = k8s.get_node_metrics()
        if metrics:
            return jsonify(metrics)
        return jsonify({'cpu': 'N/A', 'memory': 'N/A'})

    # Battlegroup
    @app.route('/server/battlegroup/status')
    @auth_req
    def battlegroup_status():
        bg_script = settings['kubernetes']['battlegroup_script']
        out, err, rc = ssh.run(f'{bg_script} status', timeout=30)
        return jsonify({'success': rc == 0, 'output': out + err if out or err else 'No output'})

    @app.route('/server/battlegroup/action', methods=['POST'])
    @auth_req
    @limiter.limit("500 per hour")
    def battlegroup_action():
        action = request.form.get('action', '')
        if action not in ('start', 'stop', 'restart'):
            return jsonify({'success': False, 'output': f'Unknown action: {action}'})
        bg_script = settings['kubernetes']['battlegroup_script']
        out, err, rc = ssh.run(f'{bg_script} {action}', timeout=120)
        return jsonify({'success': rc == 0, 'output': out + err if out or err else 'No output'})

    @app.route('/server/battlegroup/update', methods=['POST'])
    @auth_req
    @limiter.limit("1000 per hour")
    def battlegroup_update():
        bg_script = settings['kubernetes']['battlegroup_script']
        out, err, rc = ssh.run(f'{bg_script} update', timeout=600)
        return jsonify({'success': rc == 0, 'output': out + err if out or err else 'No output'})

    # Firewall management
    def _get_bgd_nodeport():
        """Resolve the current BGD service NodePort from K8s."""
        ns = settings.get('kubernetes', {}).get('namespace', '')
        if not ns:
            return None
        out, _, rc = k8s.run(f'get svc -n {ns} -o wide')
        if rc != 0 or not out:
            return None
        for line in out.split('\n'):
            if '-bgd-svc' in line and 'NodePort' in line:
                parts = line.split()
                for p in parts:
                    if ':' in p and p[0].isdigit():
                        port_str = p.split(':')[1].split('/')[0]
                        try:
                            return int(port_str)
                        except ValueError:
                            continue
        return None

    @app.route('/server/firewall')
    @auth_req
    def firewall_status():
        bgd_port = _get_bgd_nodeport()
        port_map = {
            'filebrowser': {'port': 18888, 'name': 'File Browser'},
        }
        if bgd_port:
            port_map['director'] = {'port': bgd_port, 'name': 'Battlegroup Director'}
        else:
            port_map['director'] = {'port': None, 'name': 'Battlegroup Director (not running)'}

        active_ports = [str(p['port']) for p in port_map.values() if p['port']]
        all_ports_re = '|'.join(active_ports) if active_ports else 'NONE'
        out, _, _ = ssh.run(f'sudo iptables -L INPUT -n 2>/dev/null | grep -E "dpt:({all_ports_re})"; sudo iptables -L FORWARD -n 2>/dev/null | grep -E "dpt:({all_ports_re})"; sudo iptables -t mangle -L PREROUTING -n 2>/dev/null | grep -E "dpt:({all_ports_re})"', timeout=15)

        blocked_ports = set()
        rules = {}
        port_strs = [str(p['port']) for p in port_map.values()]
        for line in out.split('\n'):
            for port in port_strs:
                if f'dpt:{port}' in line and 'DROP' in line:
                    blocked_ports.add(port)
                    rules[port] = line.strip()

        blocked = []
        available = []
        for key, info in port_map.items():
            port_str = str(info['port'])
            if port_str in blocked_ports:
                blocked.append(info)
            else:
                available.append(info)

        return jsonify({
            'success': True,
            'blocked': blocked,
            'available': available,
            'iptables_rules': rules,
        })

    @app.route('/server/firewall/block', methods=['POST'])
    @auth_req
    @limiter.limit("500 per hour")
    def firewall_block():
        port = request.form.get('port', type=int)
        bgd_port = _get_bgd_nodeport()
        allowed_ports = {18888}
        if bgd_port:
            allowed_ports.add(bgd_port)
        if port not in allowed_ports:
            return jsonify({'success': False, 'output': f'Invalid port. Allowed: {", ".join(str(p) for p in sorted(allowed_ports))}'})

        cmd = (
            f'sudo iptables -I INPUT 1 -p tcp --dport {port} -s 127.0.0.1 -j ACCEPT && '
            f'sudo iptables -I INPUT 2 -p tcp --dport {port} -j DROP && '
            f'sudo iptables -I FORWARD 1 -p tcp --dport {port} -s 127.0.0.1 -j ACCEPT && '
            f'sudo iptables -I FORWARD 2 -p tcp --dport {port} -j DROP && '
            f'sudo iptables -t mangle -I PREROUTING 1 -p tcp --dport {port} -s 127.0.0.1 -j ACCEPT && '
            f'sudo iptables -t mangle -I PREROUTING 2 -p tcp --dport {port} -j DROP'
        )
        out, err, rc = ssh.run(cmd, timeout=20)
        if rc != 0 and 'already exists' not in (out + err):
            return jsonify({'success': False, 'output': err})

        port_key = None
        if port == 18888:
            port_key = 'block_filebrowser'
        elif port == bgd_port:
            port_key = 'block_director'
        if port_key:
            settings.setdefault('firewall', {})[port_key] = True
            import yaml
            settings_path = None
            for p in ['settings.yaml', 'settings.yml']:
                import os
                if os.path.exists(p):
                    settings_path = p
                    break
            if settings_path:
                with open(settings_path, 'w') as f:
                    yaml.dump(dict(settings), f)

        return jsonify({'success': True, 'output': f'Port {port} blocked (localhost allowed)'})

    @app.route('/server/firewall/unblock', methods=['POST'])
    @auth_req
    @limiter.limit("500 per hour")
    def firewall_unblock():
        port = request.form.get('port', type=int)
        bgd_port = _get_bgd_nodeport()
        allowed_ports = {18888}
        if bgd_port:
            allowed_ports.add(bgd_port)
        if port not in allowed_ports:
            return jsonify({'success': False, 'output': f'Invalid port. Allowed: {", ".join(str(p) for p in sorted(allowed_ports))}'})

        cmd = (
            f'sudo iptables -D INPUT -p tcp --dport {port} -j DROP 2>/dev/null; '
            f'sudo iptables -D INPUT -p tcp --dport {port} -s 127.0.0.1 -j ACCEPT 2>/dev/null; '
            f'sudo iptables -D FORWARD -p tcp --dport {port} -j DROP 2>/dev/null; '
            f'sudo iptables -D FORWARD -p tcp --dport {port} -s 127.0.0.1 -j ACCEPT 2>/dev/null; '
            f'sudo iptables -t mangle -D PREROUTING -p tcp --dport {port} -j DROP 2>/dev/null; '
            f'sudo iptables -t mangle -D PREROUTING -p tcp --dport {port} -s 127.0.0.1 -j ACCEPT 2>/dev/null; '
            f'echo DONE'
        )
        out, err, rc = ssh.run(cmd, timeout=20)
        combined = (out + err).strip()
        all_ok = 'DONE' in out or rc == 0

        port_key = None
        if port == 18888:
            port_key = 'block_filebrowser'
        elif port == bgd_port:
            port_key = 'block_director'
        if port_key:
            settings.setdefault('firewall', {})[port_key] = False
            import yaml
            settings_path = None
            for p in ['settings.yaml', 'settings.yml']:
                import os
                if os.path.exists(p):
                    settings_path = p
                    break
            if settings_path:
                with open(settings_path, 'w') as f:
                    yaml.dump(dict(settings), f)

        return jsonify({'success': all_ok, 'output': 'Port unblocked' if all_ok else combined})

    # Chat API
    @app.route('/api/chat_logs')
    @auth_req
    def api_chat_logs():
        try:
            chat_svc.ensure_history_table()

            db_messages = chat_svc.get_history(1)
            if not db_messages or len(db_messages) < 10:
                chat_svc.catch_up(settings['kubernetes']['namespace'])

            db_messages = chat_svc.get_history(200)
            messages = []
            for row in db_messages:
                ts = row.get('timestamp')
                messages.append({
                    'channel': row.get('channel', ''),
                    'sender': row.get('sender', ''),
                    'message': row.get('message', ''),
                    'timestamp': ts.isoformat() if ts else '',
                    'location': {'X': row.get('location_x', 0), 'Y': row.get('location_y', 0), 'Z': row.get('location_z', 0)},
                    'target': row.get('target', ''),
                    'is_admin': row.get('is_admin', False),
                })

            note = None
            if not messages:
                note = "Chat messages are not available in this server version. The text-router pod does not expose chat logs via kubectl."

            return jsonify({'success': True, 'messages': messages, 'count': len(messages), 'note': note})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    # Player IP management
    @app.route('/api/set_player_ip', methods=['POST'])
    @auth_req
    def api_set_player_ip():
        try:
            player_id = request.form.get('player_id', type=int)
            ip_address = request.form.get('ip_address', '').strip()
            if not player_id:
                return jsonify({'success': False, 'error': 'Missing player_id'})
            if not ip_address:
                return jsonify({'success': False, 'error': 'Missing ip_address'})

            if admin_svc.set_player_ip(player_id, ip_address):
                return jsonify({'success': True, 'message': f'IP {ip_address} set for player {player_id}'})
            return jsonify({'success': False, 'error': 'Failed to set IP'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/api/detect_player_ips', methods=['POST'])
    @auth_req
    def api_detect_player_ips():
        try:
            success, message = admin_svc.detect_player_ips(settings['kubernetes']['namespace'])
            return jsonify({'success': success, 'message': message})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    # Ban management
    @app.route('/api/ban_player', methods=['POST'])
    @auth_req
    @limiter.limit("1000 per hour")
    def api_ban_player():
        try:
            player_id = request.form.get('player_id', type=int)
            duration = request.form.get('duration', '0')
            reason = request.form.get('reason', '')
            note = request.form.get('note', '')

            if not player_id:
                return jsonify({'success': False, 'error': 'Missing player_id'})

            success, message = admin_svc.ban_player(player_id, duration, reason, note)
            return jsonify({'success': success, 'message': message})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/api/get_player_ban', methods=['POST'])
    @auth_req
    def api_get_player_ban():
        try:
            player_id = request.form.get('player_id', type=int)
            if not player_id:
                return jsonify({'success': False, 'error': 'Missing player_id'})

            ban = admin_svc.get_player_ban(player_id)
            if ban:
                return jsonify({
                    'success': True, 'banned': True,
                    'reason': ban.get('reason', ''),
                    'note': ban.get('note', ''),
                    'duration': ban.get('duration', 0),
                    'banned_at': ban.get('banned_at').isoformat() if ban.get('banned_at') else '',
                    'expires_at': ban.get('expires_at').isoformat() if ban.get('expires_at') else 'Permanent'
                })
            return jsonify({'success': True, 'banned': False})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/api/get_player_history', methods=['POST'])
    @auth_req
    def api_get_player_history():
        try:
            player_id = request.form.get('player_id', type=int)
            if not player_id:
                return jsonify({'success': False, 'error': 'Missing player_id'})

            actions = admin_svc.get_player_history(player_id)
            history = []
            for a in actions:
                history.append({
                    'action': a.get('action_type', ''),
                    'reason': a.get('reason', ''),
                    'note': a.get('note', ''),
                    'duration': a.get('duration_minutes', 0),
                    'ip': a.get('ip_address', ''),
                    'created_at': a.get('created_at').isoformat() if a.get('created_at') else ''
                })
            return jsonify({'success': True, 'history': history})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/api/unban_player', methods=['POST'])
    @auth_req
    @limiter.limit("1000 per hour")
    def api_unban_player():
        try:
            player_id = request.form.get('player_id', type=int)
            if not player_id:
                return jsonify({'success': False, 'error': 'Missing player_id'})

            success, message = admin_svc.unban_player(player_id)
            return jsonify({'success': success, 'message': message})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/api/emergency_unban', methods=['POST'])
    @auth_req
    def api_emergency_unban():
        try:
            ip = request.form.get('ip', '').strip()
            if not ip:
                return jsonify({'success': False, 'error': 'Missing IP'})
            success, message = admin_svc.emergency_unban(ip)
            return jsonify({'success': success, 'message': message})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/api/kick_player', methods=['POST'])
    @auth_req
    @limiter.limit("500 per hour")
    def api_kick_player():
        try:
            player_id = request.form.get('player_id', type=int)
            if not player_id:
                return jsonify({'success': False, 'error': 'Missing player_id'})

            success, message = admin_svc.kick_player(player_id)
            return jsonify({'success': success, 'message': message})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    # Vitals editing
    @app.route('/api/edit_vitals', methods=['POST'])
    @auth_req
    @limiter.limit("500 per hour")
    def api_edit_vitals():
        try:
            pawn_id = request.form.get('pawn_id', type=int)
            current_health = request.form.get('current_health', type=float)
            max_health = request.form.get('max_health', type=float)
            current_hydration = request.form.get('current_hydration', type=float)
            current_spice = request.form.get('current_spice', type=float)

            success, result = admin_svc.edit_vitals(pawn_id, current_health, max_health, current_hydration, current_spice)
            if success:
                return jsonify({'success': True, **result})
            return jsonify({'success': False, 'error': result})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    # Player editing endpoints
    @app.route('/api/edit_faction', methods=['POST'])
    @auth_req
    def api_edit_faction():
        try:
            player_controller_id = request.form.get('player_controller_id', type=int)
            faction_id = request.form.get('faction_id', type=int)
            if not player_controller_id:
                return jsonify({'success': False, 'error': 'Missing player_controller_id'})
            if faction_id is None:
                return jsonify({'success': False, 'error': 'Missing faction_id'})

            success, result = admin_svc.edit_faction(player_controller_id, faction_id)
            if success:
                return jsonify({'success': True, 'message': f'Faction changed to {result["faction_id"]}'})
            return jsonify({'success': False, 'error': result})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/api/edit_xp', methods=['POST'])
    @auth_req
    def api_edit_xp():
        try:
            player_id = request.form.get('player_id', type=int)
            track_type = request.form.get('track_type', '').strip()
            xp_amount = request.form.get('xp_amount', type=float)
            level = request.form.get('level', type=float)

            if not player_id or not track_type or xp_amount is None:
                return jsonify({'success': False, 'error': 'Missing required parameters'})

            success, result = admin_svc.edit_xp(player_id, track_type, xp_amount, level)
            if success:
                return jsonify({'success': True, 'message': f'XP updated for {track_type}'})
            return jsonify({'success': False, 'error': result})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/api/edit_tech_knowledge', methods=['POST'])
    @auth_req
    def api_edit_tech_knowledge():
        try:
            player_id = request.form.get('player_id', type=int)
            xp_points = request.form.get('xp_points', type=int)

            if not player_id or xp_points is None:
                return jsonify({'success': False, 'error': 'Missing required parameters'})

            success, result = admin_svc.edit_tech_knowledge(player_id, xp_points)
            if success:
                return jsonify({'success': True, 'message': 'Tech knowledge updated'})
            return jsonify({'success': False, 'error': result})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/api/edit_currency', methods=['POST'])
    @auth_req
    def api_edit_currency():
        try:
            player_controller_id = request.form.get('player_controller_id', type=int)
            currency_id = request.form.get('currency_id', type=int)
            new_balance = request.form.get('new_balance', type=int)

            if not player_controller_id or currency_id is None or new_balance is None:
                return jsonify({'success': False, 'error': 'Missing required parameters'})

            success, result = admin_svc.edit_currency(player_controller_id, currency_id, new_balance)
            if success:
                return jsonify({'success': True, 'message': 'Currency updated', 'new_balance': result['new_balance']})
            return jsonify({'success': False, 'error': result})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/api/edit_item', methods=['POST'])
    @auth_req
    def api_edit_item():
        try:
            item_id = request.form.get('item_id', type=int)
            field = request.form.get('field', '').strip()
            value = request.form.get('value', '').strip()

            if not item_id or not field or value == '':
                return jsonify({'success': False, 'error': 'Missing required parameters'})

            success, result = admin_svc.edit_item(item_id, field, value)
            if success:
                return jsonify({'success': True, 'value': result['value']})
            return jsonify({'success': False, 'error': result})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/api/delete_item', methods=['POST'])
    @auth_req
    def api_delete_item():
        try:
            item_id = request.form.get('item_id', type=int)
            if not item_id:
                return jsonify({'success': False, 'error': 'Missing item_id'})

            success, result = admin_svc.delete_item(item_id)
            if success:
                return jsonify({'success': True, 'message': f'Item {result["template_id"]} deleted'})
            return jsonify({'success': False, 'error': result})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/api/add_item', methods=['POST'])
    @auth_req
    def api_add_item():
        try:
            inventory_id = request.form.get('inventory_id', type=int)
            template_id = request.form.get('template_id', '').strip()
            stack_size = request.form.get('stack_size', type=int, default=1)
            quality_level = request.form.get('quality_level', type=int, default=0)

            if not inventory_id or not template_id:
                return jsonify({'success': False, 'error': 'Missing inventory_id or template_id'})

            success, result = admin_svc.add_item(inventory_id, template_id, stack_size, quality_level)
            if success:
                return jsonify({'success': True, 'message': 'Item added', 'item_id': result['item_id']})
            return jsonify({'success': False, 'error': result})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    # Maintenance
    @app.route('/api/maintenance/create_indexes', methods=['POST'])
    @auth_req
    def api_create_indexes():
        try:
            success, created, error = admin_svc.create_indexes()
            if success:
                return jsonify({'success': True, 'created': created, 'count': len(created)})
            return jsonify({'success': False, 'error': error})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    # Delete vehicle
    
        if success:
            return jsonify({'success': True, 'message': message})
        return jsonify({'success': False, 'error': message}), 404 if 'not found' in message.lower() else 500

    # Debug endpoints (should be restricted in production)
    @app.route('/api/debug/vehicle_properties/<int:vehicle_id>')
    @auth_req
    def debug_vehicle_properties(vehicle_id):
        try:
            vehicle = db.query("""
                SELECT a.id, a.class, a.properties
                FROM dune.actors a JOIN dune.vehicles v ON a.id = v.id WHERE a.id = %s
            """, [vehicle_id], one=True)
            if not vehicle:
                return jsonify({'error': 'Vehicle not found'}), 404

            props = vehicle.get('properties', {})
            keys = list(props.keys()) if props else []
            damageable = props.get('DamageableActorComponent', {})
            damageable_keys = list(damageable.keys()) if damageable else []
            weapon_comp = props.get('WeaponActorComponent', {})
            weapon_keys = list(weapon_comp.keys()) if weapon_comp else []

            class_key = [k for k in keys if k.startswith('BP_')][0] if [k for k in keys if k.startswith('BP_')] else None
            vehicle_bp = props.get(class_key, {}) if class_key else {}

            def extract_all_keys(d, prefix='', max_depth=3, depth=0):
                if depth >= max_depth:
                    return []
                result = []
                if isinstance(d, dict):
                    for k, v in d.items():
                        result.append(prefix + k)
                        if isinstance(v, dict):
                            result.extend(extract_all_keys(v, prefix + k + '.', max_depth, depth + 1))
                        elif isinstance(v, list) and v and isinstance(v[0], dict):
                            result.append(prefix + k + '[]')
                            result.extend(extract_all_keys(v[0], prefix + k + '[0].', max_depth, depth + 1))
                return result

            all_keys = extract_all_keys(props)[:100]
            relevant = [k for k in all_keys if any(x in k.lower() for x in ['health', 'damage', 'part', 'module', 'component', 'hit', 'armor', 'slot', 'fuel', 'gas', 'energy', 'resource'])]

            return jsonify({
                'id': vehicle_id, 'class': vehicle['class'],
                'all_keys_sample': all_keys[:50], 'relevant_keys': relevant[:30]
            })
        except Exception as e:
            logger.exception("Error fetching vehicle properties")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/debug/vehicle_children/<int:vehicle_id>/')
    @auth_req
    def debug_vehicle_children(vehicle_id):
        try:
            children = db.query("""
                SELECT a.id, a.class, a.map, a.properties
                FROM dune.actors a
                WHERE a.properties::text LIKE %s LIMIT 50
            """, [f'!!act#{vehicle_id}']) or []

            results = []
            for c in children:
                props = c.get('properties', {})
                results.append({
                    'id': c['id'], 'class': c['class'], 'map': c['map'],
                    'keys': list(props.keys())[:15] if props else []
                })
            return jsonify({'vehicle_id': vehicle_id, 'found_children': len(results), 'children': results})
        except Exception as e:
            logger.exception("Error fetching vehicle children")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/debug/vehicle_parts/<int:vehicle_id>')
    @auth_req
    def debug_vehicle_parts(vehicle_id):
        try:
            parts = db.query("""
                SELECT a.id, a.class, a.properties FROM dune.actors
                WHERE a.properties::text LIKE %s LIMIT 100
            """, [f'%!!act#{vehicle_id}%']) or []

            results = []
            for p in parts:
                props = p.get('properties', {})
                current_health = props.get('DamageableActorComponent', {}).get('m_CurrentMaxHealth')
                max_health = props.get('DamageableActorComponent', {}).get('m_TotalMaxHealth')
                results.append({
                    'id': p['id'],
                    'class': p['class'][:100] if p.get('class') else '',
                    'current_health': current_health, 'max_health': max_health
                })

            vehicle = db.query("""
                SELECT a.id, a.class, a.properties FROM dune.actors a
                JOIN dune.vehicles v ON a.id = v.id WHERE a.id = %s
            """, [vehicle_id], one=True)

            return jsonify({
                'vehicle_id': vehicle_id,
                'vehicle_class': vehicle.get('class', '') if vehicle else '',
                'keys': list(vehicle.get('properties', {}).keys()) if vehicle else [],
                'bp_keys': list(vehicle.get('properties', {}).get('BP_MediumOrnithopter_CHOAM_C', {}).keys()) if vehicle else []
            })
        except Exception as e:
            logger.exception("Error fetching vehicle parts")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/debug/list_tables')
    @auth_req
    def list_tables():
        try:
            tables = db.query("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'dune' ORDER BY table_name
            """) or []
            return jsonify({'tables': [t.get('table_name', '') for t in tables]})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/debug/vehicle_modules/<int:vehicle_id>')
    @auth_req
    def debug_vehicle_modules(vehicle_id):
        try:
            vehicle_modules = db.query("SELECT * FROM dune.vehicle_modules WHERE vehicle_id = %s LIMIT 50", [vehicle_id]) or []
            return jsonify({'vehicle_id': vehicle_id, 'found': len(vehicle_modules), 'modules': vehicle_modules})
        except Exception as e:
            logger.exception("Error fetching vehicle modules")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/debug/vmi/<int:vehicle_id>')
    @auth_req
    def debug_vmi(vehicle_id):
        try:
            invs = db.query("SELECT * FROM dune.vehicle_module_inventories WHERE vehicle_id = %s LIMIT 10", [vehicle_id])
            return jsonify({'data': invs})
        except Exception as e:
            return jsonify({'error': str(e)[:100]})

    @app.route('/api/debug/vm_schema')
    @auth_req
    def debug_vm_schema():
        try:
            cols = db.query("""
                SELECT column_name, data_type FROM information_schema.columns
                WHERE table_name = 'vehicle_modules' AND table_schema = 'dune'
                ORDER BY ordinal_position
            """) or []
            return jsonify({'columns': cols})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/debug/vm_stats/<int:vehicle_id>')
    @auth_req
    def debug_vm_stats(vehicle_id):
        try:
            modules = db.query("SELECT id, template_id, stats FROM dune.vehicle_modules WHERE vehicle_id = %s", [vehicle_id]) or []
            results = []
            for m in modules:
                stats = m.get('stats', {})
                durability = stats.get('FVehicleModuleDurabilityStats', [{}])[1] if stats.get('FVehicleModuleDurabilityStats') else {}
                results.append({
                    'id': m['id'], 'template': m['template_id'],
                    'durability_keys': list(durability.keys()) if durability else [],
                    'durability': durability
                })
            return jsonify({'vehicle_id': vehicle_id, 'modules': results})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/debug/vehicle_row/<int:vehicle_id>')
    @auth_req
    def debug_vehicle_row(vehicle_id):
        try:
            v = db.query("SELECT * FROM dune.vehicles WHERE id = %s", [vehicle_id], one=True)
            return jsonify({'vehicle': v})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/debug/module_tables')
    @auth_req
    def debug_module_tables():
        try:
            tables = db.query("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'dune' AND (table_name LIKE '%module%' OR table_name LIKE '%vehicle%')
                ORDER BY table_name
            """) or []
            return jsonify({'tables': [t.get('table_name', '') for t in tables]})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    # File browser
    FILEBROWSER_BASE_PATH = '/srv'

    def _validate_fb_path(path):
        """Validate filebrowser path is within allowed directory."""
        import posixpath
        path_str = str(path or "").lstrip("/")
        if '..' in path_str or '\x00' in path_str:
            return False
        normalized = posixpath.normpath("/" + path_str)
        return normalized == FILEBROWSER_BASE_PATH or normalized.startswith(FILEBROWSER_BASE_PATH + "/")

    def _get_fb_pod():
        """Get the FileBrowser pod name dynamically."""
        pod = k8s.find_pod_by_pattern('fb-deploy')
        return pod

    def _fb_exec(command, timeout=10):
        """Execute kubectl exec in the FileBrowser pod with correct namespace placement."""
        pod = _get_fb_pod()
        if not pod:
            return '', 'FileBrowser pod not found', 1
        full_cmd = f'sudo kubectl exec {pod} -n {k8s.namespace} -- {command}'
        return k8s.ssh.run(full_cmd, timeout=timeout)

    @app.route('/api/files/list', methods=['POST'])
    @auth_req
    def api_files_list():
        path = request.form.get('path', '/srv')
        if not _validate_fb_path(path):
            return jsonify({'success': False, 'error': 'Invalid path: access denied'})
        safe_path = quote_remote(path)
        out, err, rc = _fb_exec(f'ls -la {safe_path}', timeout=10)
        if rc != 0:
            return jsonify({'success': False, 'error': err or 'Failed to list directory'})

        files = []
        for line in out.strip().split('\n')[1:]:
            parts = line.split(None, 8)
            if len(parts) >= 9:
                perms = parts[0]
                size = parts[4]
                date = ' '.join(parts[5:8])
                name = parts[8]
                if name in ('.', '..'):
                    continue
                files.append({
                    'name': name,
                    'is_dir': perms.startswith('d'),
                    'size': size if not perms.startswith('d') else '',
                    'perms': perms,
                    'date': date,
                })
        return jsonify({'success': True, 'files': files})

    @app.route('/api/files/view')
    @auth_req
    def api_files_view():
        path = request.args.get('path', '')
        if not path:
            return jsonify({'success': False, 'error': 'Missing path'})
        if not _validate_fb_path(path):
            return jsonify({'success': False, 'error': 'Invalid path: access denied'})
        safe_path = quote_remote(path)
        out, err, rc = _fb_exec(f'head -c 100000 {safe_path}', timeout=10)
        if rc != 0:
            return jsonify({'success': False, 'error': err or 'Failed to read file'})
        return jsonify({'success': True, 'content': out, 'path': path})

    @app.route('/api/files/save', methods=['POST'])
    @auth_req
    @limiter.limit("50 per hour")
    def api_files_save():
        path = request.form.get('path', '')
        content = request.form.get('content', '')
        if not path:
            return jsonify({'success': False, 'error': 'Missing path'})
        if not _validate_fb_path(path):
            return jsonify({'success': False, 'error': 'Invalid path: access denied'})
        import base64
        content_b64 = base64.b64encode(content.encode()).decode()
        safe_path = quote_remote(path)
        save_script = quote_remote(f"base64 -d > {safe_path}")
        out, err, rc = _fb_exec(f"sh -c {save_script}", timeout=15)
        if rc != 0:
            return jsonify({'success': False, 'error': err or 'Failed to save file'})
        return jsonify({'success': True})

    director_svc = services.get('director')
    director_port = settings.get('director', {}).get('port', 32479)

    # Director API proxy
    @app.route('/api/director/battlegroup')
    @auth_req
    def director_battlegroup():
        try:
            if not director_svc:
                return jsonify({'success': False, 'error': 'Director service not available'}), 503
            logger.info("Director request: %s/v0/battlegroup", director_svc.base_url)
            data = director_svc.get_battlegroup()
            return data, 200, {'Content-Type': 'application/json'}
        except Exception as e:
            error_msg = str(e)
            logger.error("Director battlegroup error: %s", e)
            if 'refused' in error_msg.lower() or 'closed' in error_msg.lower() or 'aborted' in error_msg.lower():
                return jsonify({
                    'success': False,
                    'error': 'Director unavailable',
                    'detail': 'The Battlegroup Director service is not responding. This usually means the BGD pod is starting up or has crashed due to RabbitMQ/database connectivity issues.',
                    'hint': 'Check the BGD pod logs on the server: sudo kubectl logs -n <namespace> -l app=<namespace>-bgd-deploy --tail=50'
                }), 503
            return jsonify({'success': False, 'error': error_msg}), 500

    @app.route('/api/director/update_config', methods=['POST'])
    @auth_req
    def director_update_config():
        try:
            if not director_svc:
                return jsonify({'success': False, 'error': 'Director service not available'}), 503
            config = request.get_json()
            map_name = config.get('MapName', '')
            result = director_svc.update_server_config(config)

            if map_name:
                kv = director_svc.extract_server_config_kv(config)
                if kv:
                    if not director_svc.update_ini_section(map_name, kv):
                        logger.warning("ConfigMap update failed for map %s (director API call succeeded)", map_name)

            return result, 200, {'Content-Type': 'application/json'}
        except Exception as e:
            if 'refused' in str(e).lower() or 'closed' in str(e).lower() or 'aborted' in str(e).lower():
                return jsonify({'success': False, 'error': 'Director unavailable. The BGD service is not responding.'}), 503
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/director/clear_config', methods=['POST'])
    @auth_req
    def director_clear_config():
        try:
            if not director_svc:
                return jsonify({'success': False, 'error': 'Director service not available'}), 503
            map_name = request.get_data(as_text=True).strip()
            result = director_svc.clear_map_config(map_name)
            if map_name:
                director_svc.update_ini_section(map_name, {}, remove_section=True)
            return result, 200, {'Content-Type': 'application/json'}
        except Exception as e:
            if 'refused' in str(e).lower() or 'closed' in str(e).lower() or 'aborted' in str(e).lower():
                return jsonify({'success': False, 'error': 'Director unavailable. The BGD service is not responding.'}), 503
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/director/character_transfer', methods=['GET'])
    @auth_req
    def director_character_transfer_get():
        try:
            if not director_svc:
                return jsonify({'success': False, 'error': 'Director service not available'}), 503
            data = director_svc.fetch_character_transfer_rules()
            return data, 200, {'Content-Type': 'application/json'}
        except Exception as e:
            if 'refused' in str(e).lower() or 'closed' in str(e).lower() or 'aborted' in str(e).lower():
                return jsonify({'success': False, 'error': 'Director unavailable. The BGD service is not responding.'}), 503
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/director/character_transfer', methods=['POST'])
    @auth_req
    def director_character_transfer_update():
        try:
            if not director_svc:
                return jsonify({'success': False, 'error': 'Director service not available'}), 503
            config = request.get_json()
            result = director_svc.update_character_transfer(config)

            kv = director_svc.extract_character_transfer_kv(config)
            if kv:
                director_svc.update_ini_section('CharacterTransfers', kv)

            return result, 200, {'Content-Type': 'application/json'}
        except Exception as e:
            if 'refused' in str(e).lower() or 'closed' in str(e).lower() or 'aborted' in str(e).lower():
                return jsonify({'success': False, 'error': 'Director unavailable. The BGD service is not responding.'}), 503
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/director/character_transfer_clear', methods=['POST'])
    @auth_req
    def director_character_transfer_clear():
        try:
            if not director_svc:
                return jsonify({'success': False, 'error': 'Director service not available'}), 503
            result = director_svc.clear_character_transfer_overrides()
            director_svc.update_ini_section('CharacterTransfers', {}, remove_section=True)
            return result, 200, {'Content-Type': 'application/json'}
        except Exception as e:
            if 'refused' in str(e).lower() or 'closed' in str(e).lower() or 'aborted' in str(e).lower():
                return jsonify({'success': False, 'error': 'Director unavailable. The BGD service is not responding.'}), 503
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/director/server_set_scale/<map_name>')
    @auth_req
    def director_server_set_scale_get(map_name):
        try:
            if not director_svc:
                return jsonify({'success': False, 'error': 'Director service not available'}), 503
            scale = director_svc.get_server_set_scale(map_name)
            if scale is None:
                return jsonify({'replicas': 0, 'partitions': []})
            spec = scale.get('spec', {})
            return jsonify({
                'replicas': spec.get('replicas', 0),
                'partitions': [p for p in spec.get('partitions', []) if p is not None],
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/director/server_set_scale/<map_name>', methods=['POST'])
    @auth_req
    def director_server_set_scale_patch(map_name):
        try:
            if not director_svc:
                return jsonify({'success': False, 'error': 'Director service not available'}), 503
            config = request.get_json()
            replicas = int(config.get('replicas', 1))
            partitions_raw = config.get('partitions', [])
            partitions = [int(p) for p in partitions_raw if p is not None]
            if replicas > len(partitions):
                return jsonify({'success': False, 'error': 'replicas cannot exceed partition count'}), 400
            if not director_svc.patch_server_set_scale(map_name, replicas, partitions):
                return jsonify({'success': False, 'error': 'Failed to patch ServerSetScale'}), 500
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    # Update management
    @app.route('/api/update/status')
    @auth_req
    def api_update_status():
        updater = services.get('updater')
        if not updater:
            return jsonify({'available': False})
        return jsonify({
            'available': updater.update_available,
            'status': updater.update_status,
        })

    @app.route('/api/update/apply', methods=['POST'])
    @auth_req
    def api_update_apply():
        updater = services.get('updater')
        if not updater:
            return jsonify({'success': False, 'error': 'Updater not available'})
        success, message = updater.apply_update()
        return jsonify({'success': success, 'message': message})

    @app.route('/api/update/test', methods=['POST'])
    @auth_req
    def api_update_test():
        """Force show update banner for testing."""
        updater = services.get('updater')
        if updater:
            updater._update_available = True
            return jsonify({'success': True, 'message': 'Update banner triggered'})
        return jsonify({'success': False, 'error': 'Updater not available'})

    @app.route('/api/update/check', methods=['POST'])
    @auth_req
    def api_update_check():
        """Force a fresh check against GitHub."""
        updater = services.get('updater')
        if not updater:
            return jsonify({'success': False, 'error': 'Updater not available'})
        updater.check_for_updates()
        return jsonify({
            'available': updater.update_available,
            'status': updater.update_status,
            'local_version': updater._current_sha,
            'remote_version': updater._latest_sha,
        })

    # Audit logs
    from app.services.audit import AuditService
    audit_svc = AuditService()

    @app.route('/api/audit/logs', methods=['GET'])
    @auth_req
    def api_audit_logs():
        """Get audit logs."""
        action = request.args.get('action')
        user = request.args.get('user')
        limit = int(request.args.get('limit', 100))
        offset = int(request.args.get('offset', 0))
        logs = audit_svc.get_logs(action=action, user=user, limit=limit, offset=offset)
        return jsonify({'success': True, 'logs': logs})

    @app.route('/api/audit/stats', methods=['GET'])
    @auth_req
    def api_audit_stats():
        """Get audit log statistics."""
        stats = audit_svc.get_stats()
        return jsonify({'success': True, 'stats': stats})

    # Health check endpoint (no auth required for monitoring systems)
    @app.route('/api/health')
    def api_health():
        """Health check for monitoring systems."""
        health = {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'checks': {}
        }
        
        # Debug logging for connection status checks
        debug_mode = settings.get('logging', {}).get('debug_enabled', False)
        
        # Check database
        try:
            db.execute('SELECT 1')
            health['checks']['database'] = {'status': 'ok'}
            if debug_mode:
                logger.debug("Health check: Database connection OK")
        except Exception as e:
            health['checks']['database'] = {'status': 'error', 'message': str(e)}
            health['status'] = 'degraded'
            logger.warning(f"Health check: Database connection FAILED - {e}")
        
        # Check SSH
        try:
            out, err, rc = ssh.run('echo OK')
            if rc == 0 and 'OK' in out:
                health['checks']['ssh'] = {'status': 'ok'}
                if debug_mode:
                    logger.debug(f"Health check: SSH connection OK to {ssh.host}")
            else:
                health['checks']['ssh'] = {'status': 'error', 'message': 'SSH command failed'}
                health['status'] = 'degraded'
                logger.warning(f"Health check: SSH command failed (rc={rc})")
        except Exception as e:
            health['checks']['ssh'] = {'status': 'error', 'message': str(e)}
            health['status'] = 'degraded'
            logger.warning(f"Health check: SSH connection FAILED - {e}")
        
        # Check Kubernetes
        try:
            out, err, rc = k8s.run('get nodes')
            if rc == 0:
                health['checks']['kubernetes'] = {'status': 'ok'}
                if debug_mode:
                    node_count = len(out.split('\n')) - 1 if out else 0
                    logger.debug(f"Health check: Kubernetes OK - {node_count} nodes")
            else:
                health['checks']['kubernetes'] = {'status': 'error', 'message': 'kubectl failed'}
                health['status'] = 'degraded'
                logger.warning(f"Health check: kubectl failed - {err[:100]}")
        except Exception as e:
            health['checks']['kubernetes'] = {'status': 'error', 'message': str(e)}
            health['status'] = 'degraded'
            logger.warning(f"Health check: Kubernetes FAILED - {e}")
        
        # Check BGD (Battlegroup Director) pod
        try:
            ns = settings.get('kubernetes', {}).get('namespace', '')
            bgd_out, bgd_err, bgd_rc = k8s.run(f"get pods -n {ns} -l app={ns}-bgd-deploy -o jsonpath='{{.items[*].status.phase}}'")
            if bgd_rc == 0 and bgd_out:
                pod_status = bgd_out.strip()
                if 'Running' in pod_status:
                    health['checks']['bgd'] = {'status': 'ok', 'phase': pod_status}
                    if debug_mode:
                        logger.debug(f"Health check: BGD pod {pod_status}")
                else:
                    health['checks']['bgd'] = {'status': 'degraded', 'phase': pod_status}
                    logger.warning(f"Health check: BGD pod not running - {pod_status}")
            else:
                health['checks']['bgd'] = {'status': 'unavailable'}
                logger.warning("Health check: BGD pod not found")
        except Exception as e:
            health['checks']['bgd'] = {'status': 'error', 'message': str(e)}
            logger.warning(f"Health check: BGD check FAILED - {e}")
        
        # Check RabbitMQ (if accessible)
        try:
            mq_out, mq_err, mq_rc = k8s.run(f"get pods -n {ns} -l app=rabbitmq -o jsonpath='{{.items[*].status.phase}}'")
            if mq_rc == 0 and mq_out:
                mq_status = mq_out.strip()
                if 'Running' in mq_status:
                    health['checks']['rabbitmq'] = {'status': 'ok', 'phase': mq_status}
                    if debug_mode:
                        logger.debug(f"Health check: RabbitMQ pod {mq_status}")
                else:
                    health['checks']['rabbitmq'] = {'status': 'degraded', 'phase': mq_status}
                    logger.warning(f"Health check: RabbitMQ not running - {mq_status}")
        except Exception as e:
            health['checks']['rabbitmq'] = {'status': 'unavailable', 'message': 'RabbitMQ check skipped'}
        
        # Add dashboard uptime
        start_time = getattr(app, '_start_time', None)
        if start_time:
            health['uptime_seconds'] = int(time.time() - start_time)
        
        status_code = 200 if health['status'] == 'healthy' else 503
        return jsonify(health), status_code

    # Settings API - get and update dashboard settings
    @app.route('/api/settings', methods=['GET'])
    @login_required
    def get_settings():
        """Get current dashboard settings (filtered)."""
        try:
            from app.config import get_settings
            current_settings = get_settings()
            
            # Filter out sensitive values
            safe_settings = {
                'logging': {
                    'level': current_settings.get('logging', {}).get('level', 'INFO'),
                    'debug_enabled': current_settings.get('logging', {}).get('debug_enabled', False),
                },
                'shell_enabled': current_settings.get('shell', {}).get('shell_enabled', True),
            }
            return jsonify({'success': True, 'settings': safe_settings})
        except Exception as e:
            logger.error(f"Failed to get settings: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/settings/debug', methods=['POST'])
    @login_required
    def toggle_debug():
        """Toggle debug logging on/off."""
        try:
            from app.config import get_settings, save_settings
            current_settings = get_settings()
            data = request.get_json() or {}
            
            debug_enabled = data.get('enabled', False)
            
            if 'logging' not in current_settings:
                current_settings['logging'] = {}
            current_settings['logging']['debug_enabled'] = debug_enabled
            
            save_settings(current_settings)
            
            # Apply the change to the running logger
            if debug_enabled:
                logging.getLogger().setLevel(logging.DEBUG)
                logger.info("Debug logging enabled via API")
            else:
                logging.getLogger().setLevel(logging.INFO)
                logger.info("Debug logging disabled via API")
            
            return jsonify({
                'success': True, 
                'debug_enabled': debug_enabled,
                'message': f"Debug logging {'enabled' if debug_enabled else 'disabled'}"
            })
        except Exception as e:
            logger.error(f"Failed to toggle debug: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    # ── Admin Experimental: Broadcast ─────────────────────────────────
    @app.route('/api/admin-experimental/broadcast', methods=['POST'])
    @auth_req
    @limiter.limit("100 per hour")
    def admin_broadcast():
        data = request.get_json() or {}
        title = (data.get('title') or '').strip()
        message = (data.get('message') or '').strip()
        try:
            duration = int(data.get('duration', 30))
        except (ValueError, TypeError):
            duration = 30
        if not title or not message:
            return jsonify({'success': False, 'error': 'Title and message are required'})
        success, result = admin_svc.send_global_broadcast(title, message, duration)
        return jsonify({'success': success, 'output': result})

    # ── Admin Experimental: Query Database ────────────────────────────
    @app.route('/api/admin-experimental/query', methods=['POST'])
    @auth_req
    @limiter.limit("300 per hour")
    def admin_query():
        data = request.get_json() or {}
        sql = (data.get('sql') or '').strip()
        if not sql:
            return jsonify({'success': False, 'error': 'SQL is required'})
        lower = sql.strip().lower()
        if not any(lower.startswith(w) for w in ('select', 'with', 'show', 'explain')):
            return jsonify({'success': False, 'error': 'Only SELECT/WITH queries allowed'})
        result = admin_svc.admin_db_query(sql)
        return jsonify({'success': True, 'rows': result or []})

    # ── Admin Experimental: Search Players ────────────────────────────
    @app.route('/api/admin-experimental/search-players', methods=['POST'])
    @auth_req
    def admin_search_players():
        data = request.get_json() or {}
        term = (data.get('term') or '').strip()
        if not term:
            return jsonify({'success': False, 'error': 'Search term required'})
        try:
            results = admin_svc.search_players(term)
            return jsonify({'success': True, 'players': results})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    # ── Admin Experimental: Online Players ─────────────────────────────
    @app.route('/api/admin-experimental/online-players', methods=['GET'])
    @auth_req
    def admin_online_players():
        try:
            players = admin_svc.get_online_players()
            return jsonify({'success': True, 'players': players})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    # ── Admin Experimental: Adjust Currency ───────────────────────────
    @app.route('/api/admin-experimental/adjust-currency', methods=['POST'])
    @auth_req
    @limiter.limit("200 per hour")
    def admin_adjust_currency():
        data = request.get_json() or {}
        pid = data.get('player_controller_id')
        cid = data.get('currency_id')
        delta = data.get('delta')
        if pid is None or cid is None or delta is None:
            return jsonify({'success': False, 'error': 'player_controller_id, currency_id, and delta required'})
        success, result = admin_svc.adjust_currency(pid, int(cid), int(delta))
        return jsonify({'success': success, 'output': result})

    # ── Admin Experimental: Change Faction ────────────────────────────
    @app.route('/api/admin-experimental/change-faction', methods=['POST'])
    @auth_req
    @limiter.limit("100 per hour")
    def admin_change_faction():
        data = request.get_json() or {}
        pid = data.get('player_id')
        fid = data.get('faction_id')
        if pid is None or fid is None:
            return jsonify({'success': False, 'error': 'player_id and faction_id required'})
        success, result = admin_svc.change_faction(pid, int(fid))
        return jsonify({'success': success, 'output': result})

    # ── Admin Experimental: Battlegroup Info ──────────────────────────
    @app.route('/api/admin-experimental/battlegroup', methods=['GET'])
    @auth_req
    def admin_battlegroup():
        try:
            out, err, rc = ssh.run("wget -qO- http://10.43.135.0:11717/v0/battlegroup", timeout=15)
            if rc != 0 or not out:
                return jsonify({'success': False, 'error': f'BGD unreachable: {err}'})
            parsed = json.loads(out)
            return jsonify({'success': True, 'data': parsed})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    # ── Admin Experimental: View Currency Balances ────────────────────
    @app.route('/api/admin-experimental/currency-balances', methods=['POST'])
    @auth_req
    def admin_currency_balances():
        data = request.get_json() or {}
        pcid = data.get('player_controller_id')
        if not pcid:
            return jsonify({'success': False, 'error': 'player_controller_id required'})
        try:
            result = admin_svc.get_currency_balances(pcid)
            return jsonify({'success': True, 'balances': result})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    # ── Admin Experimental: Teleport Player ───────────────────────────
    @app.route('/api/admin-experimental/teleport', methods=['POST'])
    @auth_req
    @limiter.limit("100 per hour")
    def admin_teleport():
        data = request.get_json() or {}
        fls_id = data.get('fls_id')
        partition_id = data.get('partition_id')
        x = data.get('x', 0)
        y = data.get('y', 0)
        z = data.get('z', 0)
        if not fls_id or not partition_id:
            return jsonify({'success': False, 'error': 'fls_id and partition_id required'})
        try:
            success, msg = admin_svc.teleport_player(fls_id, int(partition_id), float(x), float(y), float(z))
            return jsonify({'success': success, 'output': msg})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/api/admin-experimental/partitions', methods=['GET'])
    @auth_req
    def admin_partitions():
        try:
            partitions = admin_svc.get_partitions()
            return jsonify({'success': True, 'partitions': partitions})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    # ── Admin Experimental: Faction Reputation ────────────────────────
    @app.route('/api/admin-experimental/faction-reputation', methods=['POST'])
    @auth_req
    def admin_faction_reputation():
        data = request.get_json() or {}
        actor_id = data.get('actor_id')
        if not actor_id:
            return jsonify({'success': False, 'error': 'actor_id required'})
        try:
            # GET mode
            if 'set' not in data:
                result = admin_svc.get_faction_reputation(actor_id)
                return jsonify({'success': True, 'reputation': result})
            else:
                success, msg = admin_svc.set_faction_reputation(actor_id, int(data['faction_id']), int(data['amount']))
                return jsonify({'success': success, 'output': msg})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    # ── Admin Experimental: Inventory Lookup ──────────────────────────
    @app.route('/api/admin-experimental/inventory', methods=['POST'])
    @auth_req
    def admin_inventory():
        data = request.get_json() or {}
        account_id = data.get('account_id')
        if not account_id:
            return jsonify({'success': False, 'error': 'account_id required'})
        try:
            inv = admin_svc.get_inventory(account_id)
            pawn = admin_svc.get_player_pawn(account_id)
            return jsonify({'success': True, 'inventory': inv, 'pawn': pawn})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    # ── Admin Experimental: Guild Tools ────────────────────────────────
    @app.route('/api/admin-experimental/guilds', methods=['GET'])
    @auth_req
    def admin_guilds():
        try:
            guilds = admin_svc.get_all_guilds()
            return jsonify({'success': True, 'guilds': guilds})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/api/admin-experimental/guild-data', methods=['POST'])
    @auth_req
    def admin_guild_data():
        data = request.get_json() or {}
        guild_id = data.get('guild_id')
        if not guild_id:
            return jsonify({'success': False, 'error': 'guild_id required'})
        try:
            guild = admin_svc.get_guild_data(guild_id)
            return jsonify({'success': True, 'guild': guild})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/api/admin-experimental/disband-guild', methods=['POST'])
    @auth_req
    @limiter.limit("50 per hour")
    def admin_disband_guild():
        data = request.get_json() or {}
        guild_id = data.get('guild_id')
        if not guild_id:
            return jsonify({'success': False, 'error': 'guild_id required'})
        try:
            success, msg = admin_svc.disband_guild(guild_id)
            return jsonify({'success': success, 'output': msg})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/api/admin-experimental/remove-guild-member', methods=['POST'])
    @auth_req
    @limiter.limit("100 per hour")
    def admin_remove_guild_member():
        data = request.get_json() or {}
        guild_id = data.get('guild_id')
        player_id = data.get('player_id')
        if not guild_id or not player_id:
            return jsonify({'success': False, 'error': 'guild_id and player_id required'})
        try:
            success, msg = admin_svc.remove_guild_member(guild_id, player_id)
            return jsonify({'success': success, 'output': msg})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    # ── Admin Experimental: Player Tags ────────────────────────────────
    @app.route('/api/admin-experimental/player-tags', methods=['POST'])
    @auth_req
    def admin_player_tags():
        data = request.get_json() or {}
        account_id = data.get('account_id')
        if not account_id:
            return jsonify({'success': False, 'error': 'account_id required'})
        try:
            if 'tags_to_add' in data or 'tags_to_remove' in data:
                success, msg = admin_svc.update_player_tags(account_id, data.get('tags_to_add', []), data.get('tags_to_remove', []))
                return jsonify({'success': success, 'output': msg})
            else:
                tags = admin_svc.get_player_tags(account_id)
                return jsonify({'success': True, 'tags': tags})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/api/admin-experimental/flag-cheater', methods=['POST'])
    @auth_req
    @limiter.limit("50 per hour")
    def admin_flag_cheater():
        data = request.get_json() or {}
        account_id = data.get('account_id')
        cheat_type = data.get('cheat_type', 'manual')
        if not account_id:
            return jsonify({'success': False, 'error': 'account_id required'})
        try:
            success, msg = admin_svc.flag_cheater(account_id, cheat_type)
            return jsonify({'success': success, 'output': msg})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    # ── Admin Experimental: Player Vehicles ───────────────────────────
    @app.route('/api/admin-experimental/player-vehicles', methods=['POST'])
    @auth_req
    def admin_player_vehicles():
        data = request.get_json() or {}
        player_id = data.get('player_id')
        account_id = data.get('account_id')
        if not player_id or not account_id:
            return jsonify({'success': False, 'error': 'player_id and account_id required'})
        try:
            vehicles = admin_svc.get_player_vehicles(player_id, account_id)
            return jsonify({'success': True, 'vehicles': vehicles})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    # ── Admin Experimental: Player Stats ──────────────────────────────
    @app.route('/api/admin-experimental/player-stats', methods=['POST'])
    @auth_req
    def admin_player_stats():
        data = request.get_json() or {}
        pcid = data.get('player_controller_id')
        if not pcid:
            return jsonify({'success': False, 'error': 'player_controller_id required'})
        try:
            stats = admin_svc.get_player_stats(pcid)
            return jsonify({'success': True, 'stats': stats})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    # ── Admin Experimental: Character Management ──────────────────────
    @app.route('/api/admin-experimental/set-character-name', methods=['POST'])
    @auth_req
    def admin_set_character_name():
        data = request.get_json() or {}
        account_id = data.get('account_id')
        name = data.get('name', '').strip()
        if not account_id or not name:
            return jsonify({'success': False, 'error': 'account_id and name required'})
        try:
            success, msg = admin_svc.set_character_name(account_id, name)
            return jsonify({'success': success, 'output': msg})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/api/admin-experimental/delete-character', methods=['POST'])
    @auth_req
    @limiter.limit("20 per hour")
    def admin_delete_character():
        data = request.get_json() or {}
        actor_id = data.get('actor_id')
        if not actor_id:
            return jsonify({'success': False, 'error': 'actor_id required'})
        try:
            success, msg = admin_svc.delete_character(actor_id)
            return jsonify({'success': success, 'output': msg})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/api/admin-experimental/delete-account', methods=['POST'])
    @auth_req
    @limiter.limit("10 per hour")
    def admin_delete_account():
        data = request.get_json() or {}
        user_id = data.get('user_id')
        reason = data.get('reason', 'admin')
        if not user_id:
            return jsonify({'success': False, 'error': 'user_id required'})
        try:
            success, msg = admin_svc.delete_account(user_id, reason)
            return jsonify({'success': success, 'output': msg})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/api/admin-experimental/set-demo-state', methods=['POST'])
    @auth_req
    def admin_set_demo_state():
        data = request.get_json() or {}
        user_id = data.get('user_id')
        demo_state = data.get('demo_state', 'none')
        if not user_id:
            return jsonify({'success': False, 'error': 'user_id required'})
        try:
            success, msg = admin_svc.set_demo_state(user_id, demo_state)
            return jsonify({'success': success, 'output': msg})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    # ── Admin Experimental: Journey / Progression ─────────────────────
    @app.route('/api/admin-experimental/journey', methods=['POST'])
    @auth_req
    def admin_journey():
        data = request.get_json() or {}
        account_id = data.get('account_id')
        node_ids = data.get('node_ids', [])
        action = data.get('action', 'complete')
        if not account_id or not node_ids:
            return jsonify({'success': False, 'error': 'account_id and node_ids required'})
        try:
            if action == 'complete':
                success, msg = admin_svc.complete_journey_nodes(account_id, node_ids)
            elif action == 'reveal':
                success, msg = admin_svc.reveal_journey_nodes(account_id, node_ids)
            elif action == 'reset':
                success, msg = admin_svc.reset_journey_nodes(account_id, node_ids)
            else:
                return jsonify({'success': False, 'error': 'Invalid action'})
            return jsonify({'success': success, 'output': msg})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/api/admin-experimental/specialization', methods=['POST'])
    @auth_req
    def admin_specialization():
        data = request.get_json() or {}
        player_id = data.get('player_id')
        if not player_id:
            return jsonify({'success': False, 'error': 'player_id required'})
        try:
            if 'reset' in data:
                success, msg = admin_svc.reset_specialization(player_id)
            else:
                track = data.get('track_type', 'combat')
                xp = data.get('xp', 0)
                level = data.get('level', 1)
                success, msg = admin_svc.set_specialization(player_id, track, xp, level)
            return jsonify({'success': success, 'output': msg})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    # ── Admin Experimental: Guild Roster ──────────────────────────────
    @app.route('/api/admin-experimental/guild-members', methods=['POST'])
    @auth_req
    def admin_guild_members():
        data = request.get_json() or {}
        guild_id = data.get('guild_id')
        if not guild_id:
            return jsonify({'success': False, 'error': 'guild_id required'})
        try:
            if 'promote' in data:
                success, msg = admin_svc.promote_guild_member(guild_id, data['player_id'], data['new_role'])
                return jsonify({'success': success, 'output': msg})
            else:
                members = admin_svc.get_guild_members(guild_id)
                return jsonify({'success': True, 'members': members})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    # ── Admin Experimental: Economy ───────────────────────────────────
    @app.route('/api/admin-experimental/clean-vendor-stock', methods=['POST'])
    @auth_req
    def admin_clean_vendor_stock():
        data = request.get_json() or {}
        player_id = data.get('player_id')
        if not player_id:
            return jsonify({'success': False, 'error': 'player_id required'})
        try:
            success, msg = admin_svc.clean_player_vendor_stock(player_id)
            return jsonify({'success': success, 'output': msg})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/api/admin-experimental/tax-invoices', methods=['POST'])
    @auth_req
    def admin_tax_invoices():
        data = request.get_json() or {}
        player_id = data.get('player_id')
        if not player_id:
            return jsonify({'success': False, 'error': 'player_id required'})
        try:
            invoices = admin_svc.get_player_tax_invoices(player_id)
            return jsonify({'success': True, 'invoices': invoices})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    # ── Admin Experimental: Spice Fields ──────────────────────────────
    @app.route('/api/admin-experimental/spice', methods=['POST'])
    @auth_req
    @limiter.limit("30 per hour")
    def admin_spice():
        data = request.get_json() or {}
        try:
            if data.get('action') == 'reset':
                success, msg = admin_svc.reset_spice_state(data['map_name'], data.get('dimension_index', 0))
            else:
                success, msg = admin_svc.force_spice_spawn(data['server_id'], data['spicefield_type_id'])
            return jsonify({'success': success, 'output': msg})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    # ── Admin Experimental: Server Tools ──────────────────────────────
    @app.route('/api/admin-experimental/server-tools', methods=['POST'])
    @auth_req
    @limiter.limit("30 per hour")
    def admin_server_tools():
        data = request.get_json() or {}
        try:
            if data.get('action') == 'set_offline':
                success, msg = admin_svc.set_players_offline(data.get('server_ids', []))
            elif data.get('action') == 'cleanup_orphans':
                success, msg = admin_svc.cleanup_orphaned()
            else:
                return jsonify({'success': False, 'error': 'Invalid action'})
            return jsonify({'success': success, 'output': msg})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    # ── Admin Experimental: Permissions ──────────────────────────────
    @app.route('/api/admin-experimental/permissions', methods=['POST'])
    @auth_req
    def admin_permissions():
        data = request.get_json() or {}
        try:
            if 'set_rank' in data:
                success, msg = admin_svc.set_player_rank(data['actor_id'], data['player_id'], data['rank'], data.get('map_id', ''))
                return jsonify({'success': success, 'output': msg})
            elif data.get('actor_id'):
                perms = admin_svc.get_actor_permissions(data['actor_id'])
                return jsonify({'success': True, 'permissions': perms})
            else:
                return jsonify({'success': False, 'error': 'actor_id required'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    # ── Admin Experimental: Function Explorer ─────────────────────────
    @app.route('/api/admin-experimental/functions', methods=['GET'])
    @auth_req
    def admin_list_functions():
        try:
            funcs = admin_svc.list_all_functions()
            return jsonify({'success': True, 'functions': funcs})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/api/admin-experimental/functions/<name>', methods=['GET'])
    @auth_req
    def admin_function_details(name):
        try:
            detail = admin_svc.get_function_details(name)
            if not detail:
                return jsonify({'success': False, 'error': 'Function not found'})
            return jsonify({'success': True, 'function': detail})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/api/admin-experimental/functions/<name>/execute', methods=['POST'])
    @auth_req
    @limiter.limit("200 per hour")
    def admin_execute_function(name):
        data = request.get_json() or {}
        params = data.get('params', [])
        try:
            success, result, error = admin_svc.execute_function(name, params)
            if success:
                return jsonify({'success': True, 'result': result})
            else:
                return jsonify({'success': False, 'error': error})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    # ── Admin Experimental: SQL Execute (admin functions) ─────────────
    @app.route('/api/admin-experimental/execute', methods=['POST'])
    @auth_req
    @limiter.limit("200 per hour")
    def admin_execute():
        data = request.get_json() or {}
        sql = (data.get('sql') or '').strip()
        if not sql:
            return jsonify({'success': False, 'error': 'SQL is required'})
        lower = sql.strip().lower()
        allowed_prefixes = ('select', 'with', 'insert', 'update', 'delete', 'call', 'show', 'explain')
        if not any(lower.startswith(w) for w in allowed_prefixes):
            return jsonify({'success': False, 'error': 'SQL prefix not allowed'})
        success, result = admin_svc.admin_db_execute(sql)
        return jsonify({'success': success, 'result': result if success else str(result)})
