#!/bin/bash
# Dune Awakening Dashboard - Unified Launcher (Linux/macOS)
# This script handles both setup and starting the dashboard.
# Run this script and choose what you want to do.

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_ROOT"

# ── Helper Functions ──────────────────────────────────────────────────

show_banner() {
    echo ""
    echo "============================================================"
    echo "  Dune Awakening Dashboard"
    echo "============================================================"
    echo ""
}

show_menu() {
    echo "  What would you like to do?"
    echo ""
    echo "  [1] Start Dashboard"
    echo "      Launch the classic dashboard web interface."
    echo ""
    echo "  [2] Run Setup"
    echo "      Configure the dashboard for the first time, or reconfigure."
    echo "      WARNING: Re-running setup will wipe your current settings."
    echo ""
    echo "  [3] Run Diagnostics"
    echo "      Check your system for common issues that could block the dashboard."
    echo ""
    echo "  [4] Start Dashboard (Debug Mode)"
    echo "      Start with verbose debug logging. Only use when troubleshooting."
    echo ""
    echo "  [5] Reset to Factory Defaults"
    echo "      Wipe settings, logs, SSL files and cached keys. You must run setup again."
    echo ""
    echo "  [6] Repair Game Database"
    echo "      Fix dashboard schema ownership (fixes game servers not starting)."
    echo ""
    echo "  [7] Clean Up Old Dashboard Schema"
    echo "      Drop the legacy dashboard schema from the game database."
    echo ""
    echo "  [8] Rotate SSH Key"
    echo "      Find the newest SSH key on this machine and sync it into the project."
    echo ""
    echo "  [9] Trust Server Certificate"
    echo "      Install/remove the dashboard's self-signed cert in the system store."
    echo ""
    echo "  [Q] Quit"
    echo ""
}

determine_python() {
    PYTHON=""
    if command -v python3 &>/dev/null; then
        PYTHON="python3"
    elif command -v python &>/dev/null; then
        PYTHON="python"
    else
        echo "  Python: NOT FOUND"
        echo ""
        echo "  Python is required but not found on your system."
        echo "  Please install Python 3.8 or later."
        echo ""
        echo "  On Ubuntu/Debian: sudo apt install python3 python3-pip"
        echo "  On Fedora: sudo dnf install python3 python3-pip"
        echo "  On macOS: brew install python3"
        echo ""
        return 1
    fi
    echo "  Python: $($PYTHON --version)"
    return 0
}

test_dependencies() {
    echo "  Checking Python dependencies..."
    $PYTHON -c "import flask, flask_socketio, yaml, flask_login, flask_wtf, flask_limiter, paramiko, argon2, cryptography, cheroot" 2>/dev/null
    if [ $? -ne 0 ]; then
        echo "  Installing dependencies..."
        $PYTHON -m pip install -r "$PROJECT_ROOT/requirements.txt" --quiet 2>/dev/null && echo "  Dependencies installed." || echo "  [WARN] Some packages may have failed."
    else
        echo "  All dependencies installed."
    fi
}

test_ssh_key() {
    local settings_file="$PROJECT_ROOT/settings.yaml"
    local ssh_key_src=""

    if [ -f "$settings_file" ]; then
        ssh_key_src=$($PYTHON -c "
import yaml
with open('$settings_file') as f:
    s = yaml.safe_load(f) or {}
k = s.get('server', {}).get('ssh_key', '')
if k and k != 'null':
    print(k)
" 2>/dev/null)
    fi

    local key_paths=(
        "$ssh_key_src"
        "$HOME/.ssh/dune-dashboard-key"
        "$PROJECT_ROOT/internal-scripts/ssh/sshKey"
        "/tmp/dune-tunnel-key"
        "$HOME/.ssh/id_ed25519"
        "$HOME/.ssh/id_rsa"
    )

    for kp in "${key_paths[@]}"; do
        if [ -n "$kp" ] && [ -f "$kp" ]; then
            # Status goes to stderr so command substitution callers get a clean path on stdout.
            echo "  SSH Key: Found at $kp" >&2
            echo "$kp"
            return 0
        fi
    done

    echo "  SSH Key: NOT FOUND"
    echo ""
    echo "  No SSH key was found. The dashboard needs an SSH key to connect to your game server."
    echo ""
    echo "  Where to find your SSH key:"
    echo "    - If you used the Dune Awakening server setup, check ~/.ssh/"
    echo "    - If you generated your own key, it's wherever you saved it."
    echo ""
    echo "  To fix this:"
    echo "    1. Locate your SSH private key file"
    echo "    2. Copy it to: $PROJECT_ROOT/internal-scripts/ssh/sshKey"
    echo "    3. Or run setup again and provide the path when prompted"
    echo ""
    return 1
}

test_ssh_connection() {
    local ssh_key="$1"
    local server_host="$2"
    local server_user="$3"

    if [ -z "$ssh_key" ] || [ -z "$server_host" ] || [ "$server_host" = "YOUR_SERVER_IP" ]; then
        echo "  SSH Connection: SKIPPED (server not configured)"
        return 1
    fi

    echo "  Testing SSH connection to $server_user@$server_host..."
    if ssh -i "$ssh_key" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 -o BatchMode=yes "${server_user}@${server_host}" "echo ok" &>/dev/null; then
        echo "  SSH Connection: OK"
        return 0
    else
        echo "  SSH Connection: FAILED"
        echo ""
        echo "  Could not connect to the game server via SSH."
        echo ""
        echo "  Common causes:"
        echo "    1. The game server VM is not running"
        echo "       Fix: Start your VM or ensure the remote server is online."
        echo ""
        echo "    2. The SSH key is incorrect or doesn't match the server"
        echo "       Fix: Verify the key in settings.yaml matches the key authorized on the VM."
        echo ""
        echo "    3. The server IP in settings.yaml is wrong"
        echo "       Fix: Edit settings.yaml and update server.host to the correct IP."
        echo ""
        echo "    4. A firewall is blocking SSH (port 22)"
        echo "       Fix: Check your network/firewall settings."
        echo ""
        return 1
    fi
}

test_port_available() {
    local port="$1"
    local name="$2"

    if command -v ss &>/dev/null; then
        if ss -tln | grep -q ":${port} "; then
            echo "  Port $port ($name): IN USE"
            return 1
        fi
    elif command -v netstat &>/dev/null; then
        if netstat -tln | grep -q ":${port} "; then
            echo "  Port $port ($name): IN USE"
            return 1
        fi
    fi
    echo "  Port $port ($name): Available"
    return 0
}

show_port_forward_guide() {
    echo ""
    echo "============================================================"
    echo "  Port Forwarding & Firewall Guide"
    echo "============================================================"
    echo ""
    echo "  If you want to access the dashboard from another device on your network"
    echo "  or from the internet, you need to open/forward the dashboard port."
    echo ""
    echo "  -- Home Network (Router Port Forwarding) -------------------"
    echo ""
    echo "  1. Find this computer's local IP address:"
    echo "     Run: ip addr show  (Linux) or ifconfig (macOS)"
    echo "     Look for your active network adapter's IP (e.g., 192.168.1.XXX)"
    echo ""
    echo "  2. Log into your router's admin page:"
    echo "     Open a browser and go to your router's IP (usually 192.168.1.1)"
    echo "     Look for 'Port Forwarding', 'Virtual Server', or 'NAT' settings."
    echo ""
    echo "  3. Create a port forwarding rule:"
    echo "     - External Port: 5050 (or your dashboard port)"
    echo "     - Internal Port: 5050 (or your dashboard port)"
    echo "     - Protocol: TCP"
    echo "     - Internal IP: The local IP from step 1"
    echo ""
    echo "  4. Find your public IP address:"
    echo "     Visit https://api.ipify.org in your browser"
    echo "     Your public IP is what others use: https://YOUR_PUBLIC_IP:5050"
    echo ""
    echo "  -- Linux Firewall (ufw) ------------------------------------"
    echo ""
    echo "  If using ufw (Uncomplicated Firewall):"
    echo "    sudo ufw allow 5050/tcp"
    echo ""
    echo "  -- Linux Firewall (firewalld) ------------------------------"
    echo ""
    echo "  If using firewalld:"
    echo "    sudo firewall-cmd --permanent --add-port=5050/tcp"
    echo "    sudo firewall-cmd --reload"
    echo ""
    echo "  -- Linux Firewall (iptables) -------------------------------"
    echo ""
    echo "  If using iptables directly:"
    echo "    sudo iptables -A INPUT -p tcp --dport 5050 -j ACCEPT"
    echo ""
    echo "  -- Cloud Server (AWS, Azure, Hetzner, etc.) ---------------"
    echo ""
    echo "  If your dashboard is on a cloud server, open the port"
    echo "  in the cloud provider's firewall/security group:"
    echo ""
    echo "    - AWS: Edit Security Group -> Add Inbound Rule -> TCP 5050"
    echo "    - Azure: Edit NSG -> Add Inbound Rule -> TCP 5050"
    echo "    - Hetzner: Edit Firewall -> Add Rule -> TCP 5050"
    echo "    - DigitalOcean: Edit Firewall -> Add Inbound Rule -> TCP 5050"
    echo ""
    echo "  -- Common Ports Used by the Dashboard ----------------------"
    echo ""
    echo "    Port 5050  - Dashboard web interface (main port)"
    echo "    Port 80    - HTTP to HTTPS redirect (optional)"
    echo "    Port 443   - HTTPS (if you change the dashboard port to 443)"
    echo ""
    echo "  -- Testing Your Connection ---------------------------------"
    echo ""
    echo "  From another device on the same network:"
    echo "    Open browser -> https://THIS_COMPUTER_IP:5050"
    echo ""
    echo "  From the internet:"
    echo "    Open browser -> https://YOUR_PUBLIC_IP:5050"
    echo ""
    echo "  If it doesn't work:"
    echo "    1. Check your firewall (see above)"
    echo "    2. Check router port forwarding (see above)"
    echo "    3. Check cloud provider firewall (see above)"
    echo "    4. Make sure the dashboard is bound to 0.0.0.0 (not 127.0.0.1)"
    echo "       Check settings.yaml -> dashboard.host should be 0.0.0.0 for remote access"
    echo ""
}

run_diagnostics() {
    show_banner
    echo "  Running Diagnostics..."
    echo ""

    issues=0

    # Python
    echo "[1/6] Checking Python..."
    if ! determine_python; then ((++issues)); fi
    echo ""

    # Dependencies
    echo "[2/6] Checking Dependencies..."
    test_dependencies
    echo ""

    # Settings
    settings_file="$PROJECT_ROOT/settings.yaml"
    echo "[3/6] Checking Settings..."
    if [ -f "$settings_file" ]; then
        echo "  settings.yaml: FOUND"
        server_host=$($PYTHON -c "
import yaml
with open('$settings_file') as f:
    s = yaml.safe_load(f) or {}
print(s.get('server', {}).get('host', 'NOT SET'))
" 2>/dev/null)
        if [ "$server_host" != "NOT SET" ] && [ "$server_host" != "YOUR_SERVER_IP" ]; then
            echo "  Server Host: $server_host"
        else
            echo "  Server Host: NOT CONFIGURED (edit settings.yaml)"
            ((++issues))
        fi
        dash_info=$($PYTHON -c "
import yaml
with open('$settings_file') as f:
    s = yaml.safe_load(f) or {}
d = s.get('dashboard', {})
print(f\"{d.get('host', 'N/A')}:{d.get('port', 'N/A')}\")
" 2>/dev/null)
        echo "  Dashboard: $dash_info"
    else
        echo "  settings.yaml: NOT FOUND - Run setup first"
        ((++issues))
    fi
    echo ""

    # SSH Key
    echo "[4/6] Checking SSH Key..."
    ssh_key=$(test_ssh_key) || ((issues++))
    echo ""

    # SSH Connection (only when a key file was actually found, otherwise the
    # missing key above is the single issue worth reporting).
    echo "[5/6] Checking SSH Connection..."
    if [ -f "$settings_file" ]; then
        server_user=$($PYTHON -c "
import yaml
with open('$settings_file') as f:
    s = yaml.safe_load(f) or {}
print(s.get('server', {}).get('user', 'dune'))
" 2>/dev/null)
        if [ -f "$ssh_key" ]; then
            test_ssh_connection "$ssh_key" "$server_host" "$server_user" || ((issues++))
        else
            echo "  SSH Connection: SKIPPED (no working key)"
        fi
    else
        echo "  SSH Connection: SKIPPED (settings not available)"
    fi
    echo ""

    # Port Availability
    echo "[6/6] Checking Port Availability..."
    dashboard_port=5050
    if [ -f "$settings_file" ]; then
        dashboard_port=$($PYTHON -c "
import yaml
with open('$settings_file') as f:
    s = yaml.safe_load(f) or {}
print(s.get('dashboard', {}).get('port', 5050))
" 2>/dev/null)
    fi
    test_port_available "$dashboard_port" "Dashboard" || ((issues++))
    echo ""

    # Summary
    echo "============================================================"
    if [ $issues -eq 0 ]; then
        echo "  All local checks passed!"
    else
        echo "  Found $issues local issue(s) that may prevent the dashboard from working."
        echo "  Review the messages above for details on how to fix each issue."
    fi
    echo ""

    # Server-side diagnostics
    if [ -f "$settings_file" ]; then
        server_host_check=$($PYTHON -c "
import yaml
with open('$settings_file') as f:
    s = yaml.safe_load(f) or {}
print(s.get('server', {}).get('host', 'NOT SET'))
" 2>/dev/null)
        if [ "$server_host_check" != "NOT SET" ] && [ "$server_host_check" != "YOUR_SERVER_IP" ]; then
            echo "  Running server-side diagnostics..."
            echo ""
            $PYTHON "$PROJECT_ROOT/scripts/diagnostic.py" "$settings_file"
            echo ""
        fi
    fi

    # Offer port forward guide
    echo "  Would you like to see the Port Forwarding & Firewall guide? (y/N)"
    read -r show_guide || true
    if [ "$show_guide" = "y" ] || [ "$show_guide" = "Y" ]; then
        show_port_forward_guide
    fi

    echo "  Press Enter to return to the main menu..."
    read -r || true
}

run_setup() {
    echo ""
    echo "  Starting setup..."
    echo ""

    if [ -f "$PROJECT_ROOT/setup.sh" ]; then
        chmod +x "$PROJECT_ROOT/setup.sh"
        bash "$PROJECT_ROOT/setup.sh"
    else
        echo "  [ERROR] setup.sh not found."
    fi

    echo ""
    echo "  Press Enter to return to the main menu..."
    read -r || true
}

start_dashboard() {
    echo ""
    echo "  Starting dashboard..."
    echo ""

    # Check Python
    if ! determine_python; then
        echo "  Cannot start without Python. Please install Python 3.8+ first."
        return
    fi

    # Check dependencies
    test_dependencies

    # Check settings
    settings_file="$PROJECT_ROOT/settings.yaml"
    if [ ! -f "$settings_file" ]; then
        echo ""
        echo "  [ERROR] settings.yaml not found. You need to run setup first."
        echo ""
        echo "  Run setup to configure the dashboard before starting it."
        return
    fi

    # Normal start runs with debug logging off (debug entry point sets PRESERVE_DEBUG).
    if [ -z "$PRESERVE_DEBUG" ]; then
        $PYTHON -c "
import yaml
p = '$settings_file'
s = yaml.safe_load(open(p)) or {}
lg = s.setdefault('logging', {})
if lg.get('debug_enabled') is True:
    lg['debug_enabled'] = False
    lg['level'] = 'INFO'
    yaml.safe_dump(s, open(p, 'w'), default_flow_style=False, sort_keys=False)
    print('  Debug logging: disabled for normal start')
" 2>/dev/null
    fi

    # Read settings
    server_host=$($PYTHON -c "import yaml; s=yaml.safe_load(open('$settings_file')); print(s['server']['host'])" 2>/dev/null)
    ssh_user=$($PYTHON -c "import yaml; s=yaml.safe_load(open('$settings_file')); print(s['server']['user'])" 2>/dev/null)
    local_port=$($PYTHON -c "import yaml; s=yaml.safe_load(open('$settings_file')); print(s['database']['port'])" 2>/dev/null)
    namespace=$($PYTHON -c "import yaml; s=yaml.safe_load(open('$settings_file')); print(s['kubernetes']['namespace'])" 2>/dev/null)
    dashboard_port=$($PYTHON -c "import yaml; s=yaml.safe_load(open('$settings_file')); print(s['dashboard']['port'])" 2>/dev/null)
    director_port=$($PYTHON -c "import yaml; s=yaml.safe_load(open('$settings_file')); print(s['director']['port'])" 2>/dev/null)
    rmq_admin_port=$($PYTHON -c "import yaml; s=yaml.safe_load(open('$settings_file')); print(s.get('rabbitmq',{}).get('admin_port',30325))" 2>/dev/null)
    rmq_game_port=$($PYTHON -c "import yaml; s=yaml.safe_load(open('$settings_file')); print(s.get('rabbitmq',{}).get('game_port',32716))" 2>/dev/null)
    [ -z "$rmq_admin_port" ] && rmq_admin_port=30325
    [ -z "$rmq_game_port" ] && rmq_game_port=32716

    # Find SSH key
    ssh_key_src=$($PYTHON -c "
import yaml
with open('$settings_file') as f:
    s = yaml.safe_load(f) or {}
k = s.get('server', {}).get('ssh_key', '')
if k and k != 'null':
    print(k)
" 2>/dev/null)

    ssh_key=""
    key_paths=(
        "$ssh_key_src"
        "$HOME/.ssh/dune-dashboard-key"
        "$PROJECT_ROOT/internal-scripts/ssh/sshKey"
        "/tmp/dune-tunnel-key"
        "$HOME/.ssh/id_ed25519"
        "$HOME/.ssh/id_rsa"
    )

    for kp in "${key_paths[@]}"; do
        if [ -n "$kp" ] && [ -f "$kp" ]; then
            if ssh -i "$kp" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=5 -o BatchMode=yes "${ssh_user}@${server_host}" "echo ok" &>/dev/null; then
                ssh_key="$kp"
                echo "  SSH Key: Found working key at $kp"
                break
            fi
        fi
    done

    if [ -z "$ssh_key" ]; then
        echo ""
        echo "  [ERROR] No working SSH key found."
        echo ""
        echo "  The dashboard needs an SSH key to connect to your game server."
        echo "  Place a valid key in one of these locations:"
        echo "    - $PROJECT_ROOT/internal-scripts/ssh/sshKey"
        echo "    - ~/.ssh/dune-dashboard-key"
        echo "    - ~/.ssh/id_ed25519"
        echo ""
        echo "  Or update the ssh_key path in settings.yaml."
        return
    fi

    # Copy SSH key to temp with restricted permissions
    ssh_key_tmp="/tmp/dune-tunnel-key"
    cp "$ssh_key" "$ssh_key_tmp" 2>/dev/null
    chmod 600 "$ssh_key_tmp"

    echo ""
    echo "============================================================"
    echo "  Dune Awakening Dashboard"
    echo "============================================================"
    echo ""

    # Kill existing SSH tunnels on the DB/Director/RMQ ports.
    # Each kill is guarded so an empty port can never widen the pattern
    # into matching unrelated SSH processes.
    [ -n "$local_port" ] && pkill -f "ssh.*-L.*${local_port}" 2>/dev/null || true
    [ -n "$director_port" ] && pkill -f "ssh.*-L.*${director_port}" 2>/dev/null || true
    [ -n "$rmq_admin_port" ] && pkill -f "ssh.*-L.*${rmq_admin_port}" 2>/dev/null || true
    [ -n "$rmq_game_port" ] && pkill -f "ssh.*-L.*${rmq_game_port}" 2>/dev/null || true
    sleep 1

    # [1/4] SSH Tunnel
    echo "[1/4] Starting SSH tunnel (localhost:$local_port -> VM)..."
    ssh -i "$ssh_key_tmp" -o StrictHostKeyChecking=accept-new -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -L "${local_port}:localhost:${local_port}" -L "${director_port}:localhost:${director_port}" -L "${rmq_admin_port}:localhost:${rmq_admin_port}" -L "${rmq_game_port}:localhost:${rmq_game_port}" -N "${ssh_user}@${server_host}" &
    ssh_tunnel_pid=$!

    connected=false
    for i in $(seq 1 30); do
        sleep 1
        if ! kill -0 $ssh_tunnel_pid 2>/dev/null; then
            echo "[ERROR] SSH tunnel exited unexpectedly."
            echo ""
            echo "  Troubleshooting:"
            echo "    1. Make sure the game server VM is running"
            echo "    2. Check that the server IP in settings.yaml is correct: $server_host"
            echo "    3. Verify your SSH key is authorized on the VM"
            echo "    4. Try connecting manually: ssh -i $ssh_key ${ssh_user}@${server_host}"
            echo ""
            return
        fi
        if ($PYTHON -c "import socket; s=socket.socket(); s.settimeout(1); s.connect(('127.0.0.1', $local_port)); s.close()" 2>/dev/null); then
            connected=true
            break
        fi
    done

    if [ "$connected" = false ]; then
        echo "[ERROR] SSH tunnel did not connect within 30 seconds"
        echo ""
        echo "  Troubleshooting:"
        echo "    1. Check that your game server VM is running"
        echo "    2. Verify network connectivity: ping $server_host"
        echo "    3. Check if port $local_port is blocked by a firewall"
        echo "    4. Try connecting manually: ssh -i $ssh_key ${ssh_user}@${server_host}"
        echo ""
        kill $ssh_tunnel_pid 2>/dev/null
        return
    fi
    echo "[OK]   SSH tunnel up on localhost:$local_port (DB), localhost:$director_port (Director), localhost:$rmq_admin_port (RMQ Admin), localhost:$rmq_game_port (RMQ Game)"

    # [2/4] DB Port-Forward
    echo "[2/4] Starting DB port-forward on VM..."

    if [ -z "$namespace" ] || [ "$namespace" = "" ]; then
        echo "[ERROR] Kubernetes namespace is empty."
        echo ""
        echo "  To find your namespace:"
        echo "    1. SSH into your game server: ssh -i $ssh_key ${ssh_user}@${server_host}"
        echo "    2. Run: sudo kubectl get namespaces"
        echo "    3. Look for a namespace starting with 'funcom-seabass-'"
        echo "    4. Edit settings.yaml and set kubernetes.namespace to that value"
        echo ""
        kill $ssh_tunnel_pid 2>/dev/null
        return
    fi

    db_svc="${namespace}-db-dbdepl-svc"

    ssh -i "$ssh_key_tmp" -o StrictHostKeyChecking=accept-new -o ServerAliveInterval=30 "${ssh_user}@${server_host}" "sudo pkill -9 -f port-forward 2>/dev/null; sleep 2" 2>/dev/null
    sleep 2

    ssh -i "$ssh_key_tmp" -o StrictHostKeyChecking=accept-new -o ServerAliveInterval=30 "${ssh_user}@${server_host}" "nohup sudo kubectl port-forward -n ${namespace} svc/${db_svc} ${local_port}:${local_port} > /tmp/pf.log 2>&1 &" 2>/dev/null

    bgd_svc="${namespace}-bgd-svc"

    # Check if BGD deployment is running, scale up if needed
    bgd_deploy="${namespace}-bgd-deploy"
    bgd_ready=$(ssh -i "$ssh_key_tmp" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 "${ssh_user}@${server_host}" "sudo kubectl get deployment $bgd_deploy -n $namespace -o jsonpath='{.status.readyReplicas}'" 2>/dev/null)
    if [ -z "$bgd_ready" ] || [ "$bgd_ready" = "0" ]; then
        echo "  BGD deployment is scaled down, starting..."
        ssh -i "$ssh_key_tmp" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=30 "${ssh_user}@${server_host}" "sudo kubectl scale deployment $bgd_deploy -n $namespace --replicas=1" 2>/dev/null
        echo "  Waiting for BGD pod to be ready..."
        sleep 15
    fi

    ssh -i "$ssh_key_tmp" -o StrictHostKeyChecking=accept-new -o ServerAliveInterval=30 "${ssh_user}@${server_host}" "nohup sudo kubectl port-forward -n ${namespace} svc/${bgd_svc} ${director_port}:11717 > /tmp/director_pf.log 2>&1 &" 2>/dev/null

    sleep 3

    # [3/4] Database Check
    echo "[3/4] Checking database..."
    db_test=false
    for i in $(seq 1 15); do
        if $PYTHON "$PROJECT_ROOT/scripts/db_check.py" "$local_port" 2>/dev/null | grep -q "ok"; then
            db_test=true
            break
        fi
        sleep 1
    done

    if [ "$db_test" = false ]; then
        echo "[ERROR] Database connection failed."
        echo ""
        echo "  Troubleshooting:"
        echo "    1. Check the port-forward log on the VM:"
        pf_log=$(ssh -i "$ssh_key_tmp" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 "${ssh_user}@${server_host}" "cat /tmp/pf.log" 2>/dev/null)
        if [ -n "$pf_log" ]; then
            echo "       $pf_log"
        else
            echo "       Log empty or unreadable."
        fi
        echo ""
        echo "    2. Verify the DB service exists on the VM:"
        echo "       ssh -i $ssh_key ${ssh_user}@${server_host} 'sudo kubectl get svc -n $namespace'"
        echo ""
        echo "    3. Check that the database port in settings.yaml is correct: $local_port"
        echo ""
        kill $ssh_tunnel_pid 2>/dev/null
        return
    fi
    echo "[OK]   Database connected"

    # [4/4] Start Dashboard
    echo "[4/4] Starting dashboard..."
    echo ""

    # Determine access URLs
    protocol="http"
    ssl_cert=$($PYTHON -c "import yaml; s=yaml.safe_load(open('$settings_file')); c=s.get('dashboard',{}).get('ssl_cert',''); print(c if c and c!='null' else '')" 2>/dev/null)
    ssl_key=$($PYTHON -c "import yaml; s=yaml.safe_load(open('$settings_file')); k=s.get('dashboard',{}).get('ssl_key',''); print(k if k and k!='null' else '')" 2>/dev/null)
    if [ -n "$ssl_cert" ] && [ -n "$ssl_key" ] && [ -f "$ssl_cert" ] && [ -f "$ssl_key" ]; then
        protocol="https"
    fi

    dash_host=$($PYTHON -c "import yaml; s=yaml.safe_load(open('$settings_file')); print(s.get('dashboard',{}).get('host','127.0.0.1'))" 2>/dev/null)
    if [ "$dash_host" = "0.0.0.0" ]; then
        echo "  Dashboard is accessible at:"
        echo "    Local:    $protocol://localhost:$dashboard_port"
        echo "    Local:    $protocol://127.0.0.1:$dashboard_port"
        echo "    Network:  $protocol://<this-computer-ip>:$dashboard_port"
        echo "    Internet: $protocol://<your-public-ip>:$dashboard_port"
    else
        echo "  Dashboard is accessible at:"
        echo "    $protocol://$dash_host:$dashboard_port"
    fi
    echo ""
    echo "  Press Ctrl+C to stop the dashboard."
    echo ""

    cd "$PROJECT_ROOT"
    # Exit code 42 = watchdog tripped (dashboard wedged) - restart it
    # automatically, tunnels stay up. Anything else shuts down normally.
    watchdog_restarts=0
    while true; do
        $PYTHON run.py
        code=$?
        if [ "$code" -eq 42 ] && [ "$watchdog_restarts" -lt 5 ]; then
            watchdog_restarts=$((watchdog_restarts + 1))
            echo ""
            echo "  [WARN] Dashboard stopped responding (watchdog) - restarting ($watchdog_restarts/5)..."
            sleep 5
        else
            if [ "$code" -eq 42 ]; then
                echo ""
                echo "  [ERROR] Dashboard keeps freezing - giving up auto-restart. Check the setup and start manually."
            fi
            break
        fi
    done

    echo ""
    echo "Stopping tunnels..."
    kill $ssh_tunnel_pid 2>/dev/null
    ssh -i "$ssh_key_tmp" -o StrictHostKeyChecking=accept-new "${ssh_user}@${server_host}" "pkill -f kubectl-port-forward" 2>/dev/null || true
}


# ── Shared Server Helpers ───────────────────────────────────────────────

# Load server connection details from settings.yaml.
# Sets: server_host ssh_user namespace ssh_key. Returns non-zero on error.
load_server_settings() {
    settings_file="$PROJECT_ROOT/settings.yaml"
    if [ ! -f "$settings_file" ]; then
        echo "  [ERROR] settings.yaml not found. Run setup first."
        return 1
    fi
    server_host=$($PYTHON -c "import yaml; s=yaml.safe_load(open('$settings_file')) or {}; print(s.get('server',{}).get('host',''))" 2>/dev/null)
    ssh_user=$($PYTHON -c "import yaml; s=yaml.safe_load(open('$settings_file')) or {}; print(s.get('server',{}).get('user','dune'))" 2>/dev/null)
    namespace=$($PYTHON -c "import yaml; s=yaml.safe_load(open('$settings_file')) or {}; print(s.get('kubernetes',{}).get('namespace',''))" 2>/dev/null)
    ssh_key=$($PYTHON -c "import yaml; s=yaml.safe_load(open('$settings_file')) or {}; k=s.get('server',{}).get('ssh_key',''); print(k if k and k!='null' else '')" 2>/dev/null)
    if [ -z "$ssh_key" ] || [ ! -f "$ssh_key" ]; then
        ssh_key=""
        for kp in "$HOME/.ssh/dune-dashboard-key" "$PROJECT_ROOT/internal-scripts/ssh/sshKey" "$HOME/.ssh/id_ed25519" "$HOME/.ssh/id_rsa"; do
            if [ -f "$kp" ]; then ssh_key="$kp"; break; fi
        done
    fi
    if [ -z "$server_host" ] || [ "$server_host" = "YOUR_SERVER_IP" ]; then
        echo "  [ERROR] Server IP not configured in settings.yaml."
        return 1
    fi
    if [ -z "$namespace" ]; then
        echo "  [ERROR] Kubernetes namespace not configured."
        return 1
    fi
    if [ ! -f "$ssh_key" ]; then
        echo "  [ERROR] SSH key not found."
        return 1
    fi
    return 0
}

start_dashboard_debug() {
    echo ""
    echo "  ============================================================"
    echo "  Starting Dashboard with DEBUG LOGGING enabled"
    echo "  ============================================================"
    echo ""
    echo "  WARNING: Debug logging can significantly impact performance!"
    echo "     - Logs every HTTP request/response"
    echo "     - Logs all SSH commands and results"
    echo "     - Logs all database queries"
    echo "     - Only use this when troubleshooting, not for regular use"
    echo ""
    read -rp "  Continue with debug mode? (y/N) " confirm
    if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
        echo "  Cancelled."
        return
    fi
    settings_file="$PROJECT_ROOT/settings.yaml"
    if [ ! -f "$settings_file" ]; then
        echo "  [ERROR] settings.yaml not found. Run setup first."
        return
    fi
    $PYTHON -c "
import yaml
p = '$settings_file'
s = yaml.safe_load(open(p)) or {}
s.setdefault('logging', {})['debug_enabled'] = True
yaml.safe_dump(s, open(p, 'w'), default_flow_style=False, sort_keys=False)
" 2>/dev/null
    echo "  Debug logging enabled for this run."
    echo ""
    PRESERVE_DEBUG=1 start_dashboard
}

reset_to_factory() {
    echo ""
    echo "  Reset to Factory Defaults"
    echo ""
    echo "  WARNING: This will permanently delete the following:"
    echo "    - settings.yaml (all configuration)"
    echo "    - logs/, app/logs/ (log files)"
    echo "    - instance/ (local data)"
    echo "    - ssl/ (SSL certificates)"
    echo "    - internal-scripts/ssh/ (copied SSH key)"
    echo "    - Python __pycache__ directories"
    echo ""
    echo "  This cannot be undone. You will need to run setup again."
    echo ""
    read -rp "  Type 'yes' to confirm: " confirmation
    if [ "$confirmation" != "yes" ]; then
        echo ""
        echo "  Reset cancelled. No changes made."
        return
    fi
    echo ""
    echo "  Wiping all dashboard data..."
    echo ""
    count=0
    [ -f "$PROJECT_ROOT/settings.yaml" ] && rm -f "$PROJECT_ROOT/settings.yaml" && echo "    Deleted settings.yaml" && count=$((count + 1))
    [ -d "$PROJECT_ROOT/instance" ] && rm -rf "$PROJECT_ROOT/instance" && echo "    Deleted instance/" && count=$((count + 1))
    [ -d "$PROJECT_ROOT/ssl" ] && rm -rf "$PROJECT_ROOT/ssl" && echo "    Deleted ssl/" && count=$((count + 1))
    [ -d "$PROJECT_ROOT/logs" ] && rm -rf "$PROJECT_ROOT/logs" && echo "    Deleted logs/" && count=$((count + 1))
    [ -d "$PROJECT_ROOT/app/logs" ] && rm -rf "$PROJECT_ROOT/app/logs" && echo "    Deleted app/logs/" && count=$((count + 1))
    [ -d "$PROJECT_ROOT/internal-scripts/ssh" ] && rm -rf "$PROJECT_ROOT/internal-scripts/ssh" && echo "    Deleted internal-scripts/ssh/" && count=$((count + 1))
    find "$PROJECT_ROOT/app" -type d -name "__pycache__" -prune -exec rm -rf {} + 2>/dev/null
    echo "    Cleaned Python caches"
    echo ""
    echo "  Reset complete ($count items removed). Run setup (option 2) to start over."
    echo ""
    read -rp "  Press Enter to return to the main menu..." || true
}

repair_game_database() {
    echo ""
    echo "  Game Database Repair"
    echo "  ====================="
    echo ""
    if ! load_server_settings; then
        echo ""
        read -rp "  Press Enter to return..." || true
        return
    fi
    echo "  Server: $server_host"
    echo "  Namespace: $namespace"
    echo ""
    read -rp "  This will transfer dashboard schema ownership to the dune user. Continue? (y/N) " confirm
    if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
        echo "  Cancelled."
        return
    fi
    echo ""
    echo "[1/4] Finding database pod..."
    db_pod=$(ssh -i "$ssh_key" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 "${ssh_user}@${server_host}" "sudo kubectl get pods -n $namespace -l app=${namespace}-db-dbdepl-sts -o jsonpath='{.items[0].metadata.name}'" 2>/dev/null)
    if [ -z "$db_pod" ]; then
        echo "[ERROR] Could not find database pod."
        return
    fi
    echo "  [OK]   Database pod: $db_pod"
    echo "[2/4] Running ownership fix..."
    ssh -i "$ssh_key" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 "${ssh_user}@${server_host}" "cat > /tmp/repair.sql <<'REPAIR_EOF'
ALTER SCHEMA dashboard OWNER TO dune;
DO \$\$DECLARE r RECORD; BEGIN FOR r IN SELECT tablename FROM pg_tables WHERE schemaname = 'dashboard' LOOP EXECUTE 'ALTER TABLE dashboard.' || quote_ident(r.tablename) || ' OWNER TO dune'; END LOOP; END\$\$;
DO \$\$DECLARE r RECORD; BEGIN FOR r IN SELECT sequencename FROM pg_sequences WHERE schemaname = 'dashboard' LOOP EXECUTE 'ALTER SEQUENCE dashboard.' || quote_ident(r.sequencename) || ' OWNER TO dune'; END LOOP; END\$\$;
ALTER DEFAULT PRIVILEGES IN SCHEMA dashboard GRANT ALL ON TABLES TO dune;
ALTER DEFAULT PRIVILEGES IN SCHEMA dashboard GRANT ALL ON SEQUENCES TO dune;
REPAIR_EOF
cat /tmp/repair.sql | sudo kubectl exec -n $namespace -i $db_pod -- psql -U postgres -p 15432 -d dune
printf 'CREATE SCHEMA IF NOT EXISTS dashboard;\nGRANT ALL PRIVILEGES ON SCHEMA dashboard TO dune;\n' | sudo kubectl exec -n $namespace -i $db_pod -- psql -U postgres -p 15432 -d template1" 2>&1
    echo "  [OK]   Ownership fix applied"
    echo "[3/4] Cleaning up failed utility pods..."
    deleted=$(ssh -i "$ssh_key" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 "${ssh_user}@${server_host}" "sudo kubectl get pods -n $namespace | grep 'db.*util' | grep -v Running | awk '{print \$1}' | xargs -r sudo kubectl delete pod -n $namespace --wait=false" 2>/dev/null)
    if [ -n "$deleted" ]; then
        echo "$deleted"
        echo "  [OK]   Failed util pods deleted"
    else
        echo "  [OK]   No failed util pods found"
    fi
    echo "[4/4] Done!"
    echo ""
    echo "  If game servers still show errors, restart the battlegroup,"
    echo "  wait for all pods to come back healthy, then start the dashboard."
    echo "  The dashboard also auto-fixes ownership on every startup."
    echo ""
    read -rp "  Press Enter to return to the menu..." || true
}

cleanup_old_dashboard_schema() {
    echo ""
    echo "  Clean Up Old Dashboard Schema"
    echo "  ==============================="
    echo ""
    if ! load_server_settings; then
        echo ""
        read -rp "  Press Enter to return..." || true
        return
    fi
    db_pod=$(ssh -i "$ssh_key" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 "${ssh_user}@${server_host}" "sudo kubectl get pods -n $namespace -l app=${namespace}-db-dbdepl-sts -o jsonpath='{.items[0].metadata.name}'" 2>/dev/null)
    if [ -z "$db_pod" ]; then
        echo "[ERROR] Could not find database pod."
        return
    fi
    has_old=$(ssh -i "$ssh_key" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 "${ssh_user}@${server_host}" "sudo kubectl exec -n $namespace -i $db_pod -- psql -U postgres -p 15432 -d dune -t -c \"SELECT count(*) FROM information_schema.schemata WHERE schema_name = 'dashboard'\" 2>&1" 2>/dev/null | tr -d '[:space:]')
    if [ "$has_old" = "0" ] || [ -z "$has_old" ]; then
        echo "  [OK]   No old dashboard schema found - nothing to clean up."
        echo ""
        read -rp "  Press Enter to return..." || true
        return
    fi
    echo "  [WARN] Old dashboard schema found in the game database."
    echo ""
    echo "  This drops: dashboard.audit_log, dashboard.bans, dashboard.player_ips,"
    echo "               dashboard.player_actions, dashboard.chat_history, dashboard.settings"
    echo ""
    echo "  Make sure the dashboard has migrated this data first"
    echo "  (it does this automatically on next startup)."
    echo ""
    read -rp "  Type 'yes' to drop the old dashboard schema: " confirm
    if [ "$confirm" != "yes" ]; then
        echo "  Cancelled."
        return
    fi
    read -rp "  REALLY drop? This cannot be undone. Type 'yes' again: " confirm2
    if [ "$confirm2" != "yes" ]; then
        echo "  Cancelled."
        return
    fi
    echo ""
    echo "  Dropping old dashboard schema..."
    ssh -i "$ssh_key" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 "${ssh_user}@${server_host}" "sudo kubectl exec -n $namespace -i $db_pod -- psql -U postgres -p 15432 -d dune -c \"DROP SCHEMA IF EXISTS dashboard CASCADE\" 2>&1" 2>&1
    echo "  [OK]   Old dashboard schema dropped."
    echo ""
    read -rp "  Press Enter to return..." || true
}

trust_server_cert() {
    echo ""
    echo "  Trust Server Certificate"
    echo "  ========================"
    echo ""
    echo "  Installs the dashboard's self-signed certificate into this"
    echo "  machine's system trust store so browsers stop warning about it."
    echo "  Only do this on machines you own, for your own dashboard."
    echo ""
    settings_file="$PROJECT_ROOT/settings.yaml"
    cert=""
    if [ -f "$settings_file" ]; then
        cert=$($PYTHON -c "import yaml; s=yaml.safe_load(open('$settings_file')) or {}; c=s.get('dashboard',{}).get('ssl_cert',''); print(c if c and c!='null' else '')" 2>/dev/null)
    fi
    if { [ -z "$cert" ] || [ ! -f "$cert" ]; } && [ -f "$PROJECT_ROOT/ssl/cert.pem" ]; then
        cert="$PROJECT_ROOT/ssl/cert.pem"
    fi
    if [ -z "$cert" ] || [ ! -f "$cert" ]; then
        echo "  [ERROR] No server certificate found."
        echo "  Run setup with remote access enabled to generate one (ssl/cert.pem)."
        echo ""
        read -rp "  Press Enter to return..." || true
        return
    fi
    echo "  Certificate: $cert"
    echo ""
    if command -v update-ca-certificates &>/dev/null; then
        # Debian / Ubuntu
        dest="/usr/local/share/ca-certificates/dune-dashboard.crt"
        if [ -f "$dest" ]; then
            read -rp "  Already trusted. Remove it instead? (y/N): " remove
            if [ "$remove" = "y" ] || [ "$remove" = "Y" ]; then
                sudo rm -f "$dest" && sudo update-ca-certificates --fresh >/dev/null 2>&1
                echo "  [OK]   Certificate removed from system store."
            else
                echo "  Cancelled."
            fi
        else
            read -rp "  Install into system store? (requires sudo) (y/N): " confirm
            if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
                if sudo cp "$cert" "$dest" && sudo update-ca-certificates >/dev/null 2>&1; then
                    echo "  [OK]   Certificate trusted. Restart your browser."
                else
                    echo "  [ERROR] Install failed."
                fi
            else
                echo "  Cancelled."
            fi
        fi
    elif command -v update-ca-trust &>/dev/null; then
        # Fedora / RHEL
        dest="/etc/pki/ca-trust/source/anchors/dune-dashboard.crt"
        if [ -f "$dest" ]; then
            read -rp "  Already trusted. Remove it instead? (y/N): " remove
            if [ "$remove" = "y" ] || [ "$remove" = "Y" ]; then
                sudo rm -f "$dest" && sudo update-ca-trust >/dev/null 2>&1
                echo "  [OK]   Certificate removed from system store."
            else
                echo "  Cancelled."
            fi
        else
            read -rp "  Install into system store? (requires sudo) (y/N): " confirm
            if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
                if sudo cp "$cert" "$dest" && sudo update-ca-trust >/dev/null 2>&1; then
                    echo "  [OK]   Certificate trusted. Restart your browser."
                else
                    echo "  [ERROR] Install failed."
                fi
            else
                echo "  Cancelled."
            fi
        fi
    elif [ "$(uname)" = "Darwin" ]; then
        # macOS: install only; removal via Keychain Access.
        read -rp "  Install into System keychain? (requires sudo) (y/N): " confirm
        if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
            if sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain "$cert" 2>/dev/null; then
                echo "  [OK]   Certificate trusted. Restart your browser."
                echo "  To remove later, delete it from Keychain Access (System keychain)."
            else
                echo "  [ERROR] Install failed."
            fi
        else
            echo "  Cancelled."
        fi
    else
        echo "  [ERROR] No supported trust store tool found."
        echo "  Need one of: update-ca-certificates (Debian/Ubuntu),"
        echo "  update-ca-trust (Fedora/RHEL), or macOS security."
    fi
    echo ""
    read -rp "  Press Enter to return..." || true
}

rotate_ssh_key() {
    echo ""
    echo "  Rotate SSH Key"
    echo "  ==============="
    echo ""
    target_key="$PROJECT_ROOT/internal-scripts/ssh/sshKey"
    parent_key="$(dirname "$PROJECT_ROOT")/internal-scripts/ssh/sshKey"
    echo "  Scanning for SSH keys..."
    if [ -f "$target_key" ]; then
        echo "    Current: $target_key (modified $(stat -c '%y' "$target_key" 2>/dev/null || stat -f '%Sm' "$target_key" 2>/dev/null))"
    fi
    newest=""
    newest_mtime=0
    for kp in "$HOME/.ssh/dune-dashboard-key" "/tmp/dune-tunnel-key" "$parent_key" "$HOME/.ssh/id_ed25519" "$HOME/.ssh/id_rsa" "$HOME/.ssh/id_ecdsa"; do
        if [ -f "$kp" ]; then
            mtime=$(stat -c '%Y' "$kp" 2>/dev/null || stat -f '%m' "$kp" 2>/dev/null || echo 0)
            echo "    Found:   $kp"
            if [ "$mtime" -gt "$newest_mtime" ] 2>/dev/null; then
                newest_mtime=$mtime
                newest=$kp
            fi
        fi
    done
    if [ -z "$newest" ]; then
        echo ""
        echo "  No SSH keys found in any search location."
        echo ""
        read -rp "  Press Enter to return..." || true
        return
    fi
    mkdir -p "$(dirname "$target_key")"
    if [ "$newest" = "$target_key" ]; then
        echo ""
        echo "  The newest key is already at the target location."
        echo "  No rotation needed."
    else
        cp "$newest" "$target_key"
        chmod 600 "$target_key"
        echo ""
        echo "  [OK]   Synced newest key ($newest) to $target_key"
    fi
    echo ""
    read -rp "  Press Enter to return..." || true
}

# ── Main Loop ───────────────────────────────────────────────────────────

# --auto-start skips the menu and starts the dashboard straight away
# (used after self-updates so the panel comes back up unattended).
if [ "$1" = "--auto-start" ] || [ "$1" = "--autostart" ]; then
    start_dashboard
    exit $?
fi

show_banner

while true; do
    show_menu
    read -rp "  Enter your choice: " choice || { echo ""; echo "  Goodbye!"; echo ""; exit 0; }

    case "$choice" in
        1) start_dashboard ;;
        2) run_setup ;;
        3) run_diagnostics ;;
        4) start_dashboard_debug ;;
        5) reset_to_factory ;;
        6) repair_game_database ;;
        7) cleanup_old_dashboard_schema ;;
        8) rotate_ssh_key ;;
        9) trust_server_cert ;;
        [Qq]) echo ""; echo "  Goodbye!"; echo ""; exit 0 ;;
        *) echo ""; echo "  Invalid choice. Please enter 1-9 or Q."; echo "" ;;
    esac

    echo ""
done
