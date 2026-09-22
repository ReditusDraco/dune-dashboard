#!/bin/bash
# Dune Awakening Dashboard - Cross-Platform Setup
# Configures settings.yaml and installs dependencies.

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_ROOT"

# ── Helpers ──────────────────────────────────────────────────────────────

find_python() {
    if command -v python3 &>/dev/null; then echo "python3"
    elif command -v python &>/dev/null; then echo "python"
    else echo ""; fi
}

find_ssh_key() {
    local paths=(
        "$1"
        "$HOME/.ssh/dune-dashboard-key"
        "$HOME/.ssh/id_ed25519"
        "$HOME/.ssh/id_rsa"
        "$HOME/.ssh/id_ecdsa"
    )
    for kp in "${paths[@]}"; do
        if [ -n "$kp" ] && [ -f "$kp" ]; then
            echo "$kp"
            return 0
        fi
    done
    return 1
}

test_ssh() {
    local key="$1" host="$2" user="${3:-dune}"
    if [ -z "$key" ] || [ -z "$host" ]; then return 1; fi
    ssh -i "$key" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 -o BatchMode=yes "${user}@${host}" "echo ok" 2>/dev/null | grep -q "ok"
}

get_public_ip() {
    curl -s --connect-timeout 5 https://api.ipify.org 2>/dev/null || echo ""
}

# ── Main ─────────────────────────────────────────────────────────────────

echo ""
echo "============================================================"
echo "  Dune Awakening Dashboard - Setup"
echo "============================================================"
echo ""

# Warn about re-run
IS_RERUN=false
[ -f "$PROJECT_ROOT/settings.yaml" ] && IS_RERUN=true
[ -d "$PROJECT_ROOT/logs" ] && IS_RERUN=true
[ -d "$PROJECT_ROOT/instance" ] && IS_RERUN=true
[ -d "$PROJECT_ROOT/ssl" ] && IS_RERUN=true

if $IS_RERUN; then
    echo "  [WARNING] Existing dashboard data detected!"
    echo ""
    echo "  This will WIPE the following:"
    echo "    - settings.yaml"
    echo "    - logs/, instance/, ssl/"
    echo ""
    read -rp "  Continue? (y/N): " confirm
    if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
        echo ""
        echo "  Setup cancelled."
        exit 0
    fi

    echo ""
    echo "  Cleaning existing data..."
    rm -f "$PROJECT_ROOT/settings.yaml"
    rm -rf "$PROJECT_ROOT/logs" "$PROJECT_ROOT/instance" "$PROJECT_ROOT/ssl" 2>/dev/null || true
    find "$PROJECT_ROOT" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
    echo "  Clean complete!"
    echo ""
fi

# [1/5] Check Python
echo "[1/5] Checking Python..."
PYTHON=$(find_python)
if [ -z "$PYTHON" ]; then
    echo "  [ERROR] Python 3.8+ not found."
    echo ""
    echo "  Install Python:"
    echo "    macOS:   brew install python3"
    echo "    Ubuntu:  sudo apt install python3 python3-pip"
    echo "    Fedora:  sudo dnf install python3 python3-pip"
    exit 1
fi
echo "  Found: $($PYTHON --version)"

# [2/5] Install Python dependencies
echo ""
echo "[2/5] Installing Python dependencies..."
$PYTHON -m pip install --quiet --upgrade pip 2>/dev/null || true
$PYTHON -m pip install --quiet -r "$PROJECT_ROOT/requirements.txt" 2>/dev/null || {
    echo "  [WARN] Some packages failed. Continuing anyway..."
}
$PYTHON -m pip install --quiet "psycopg[binary]" 2>/dev/null || true
echo "  Dependencies installed"

# [3/5] Find SSH key
echo ""
echo "[3/5] Configuring SSH key..."
echo ""
echo "  The dashboard needs SSH access to your game server VM."
echo "  Enter the path to your private SSH key (or leave blank to auto-detect):"

SSH_KEY=""
read -rp "  SSH key path: " ssh_path
SSH_KEY=$(find_ssh_key "$ssh_path")
if [ -n "$SSH_KEY" ]; then
    echo "  Found: $SSH_KEY"
else
    echo ""
    echo "  No SSH key found at common locations."
    echo "  Common paths:"
    echo "    - ~/.ssh/id_ed25519"
    echo "    - ~/.ssh/id_rsa"
    echo "    - ~/.ssh/dune-dashboard-key"
    echo ""
    read -rp "  Enter full path to your SSH key: " SSH_KEY
    if [ ! -f "$SSH_KEY" ]; then
        echo "  [ERROR] Key not found at: $SSH_KEY"
        echo "  Setup will continue but you'll need to fix this in settings.yaml"
        SSH_KEY=""
    fi
fi

# [4/5] Server settings
echo ""
echo "[4/5] Server settings..."
echo ""

# VM host
echo "  Game Server IP (for SSH connection)"
read -rp "  VM Host [YOUR_SERVER_IP]: " VM_HOST
VM_HOST="${VM_HOST:-YOUR_SERVER_IP}"

# SSH user
read -rp "  SSH Username [dune]: " SSH_USER
SSH_USER="${SSH_USER:-dune}"

# Dashboard port
read -rp "  Dashboard Port [5050]: " DASH_PORT
DASH_PORT="${DASH_PORT:-5050}"

# DB port
read -rp "  Database Port [15433]: " DB_PORT
DB_PORT="${DB_PORT:-15433}"

# Director port
read -rp "  BG Director Port [32479]: " DIR_PORT
DIR_PORT="${DIR_PORT:-32479}"

# Kubernetes namespace
echo ""
echo "  Kubernetes Namespace (auto-detecting via SSH if possible)..."

K8S_NAMESPACE=""
if [ -n "$SSH_KEY" ] && [ "$VM_HOST" != "YOUR_SERVER_IP" ]; then
    echo "  Testing SSH connection..."
    if test_ssh "$SSH_KEY" "$VM_HOST" "$SSH_USER"; then
        echo "  SSH connected! Detecting namespace..."
        NAMESPACES=$(ssh -i "$SSH_KEY" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 "${SSH_USER}@${VM_HOST}" "sudo kubectl get namespaces -o name" 2>/dev/null)
        if [ -n "$NAMESPACES" ]; then
            K8S_NAMESPACE=$(echo "$NAMESPACES" | grep 'funcom-seabass-' | head -1 | sed 's|namespace/||')
            if [ -n "$K8S_NAMESPACE" ]; then
                echo "  Auto-detected: $K8S_NAMESPACE"
            fi
        fi
    else
        echo "  SSH connection failed. You can enter the namespace manually."
    fi
fi

if [ -z "$K8S_NAMESPACE" ]; then
    echo "  (Find it with: ssh dune@IP 'sudo kubectl get namespaces')"
    read -rp "  Kubernetes Namespace: " K8S_NAMESPACE
fi

# Auth
echo ""
echo "  Dashboard login credentials"
read -rp "  Admin Username [admin]: " AUTH_USER
AUTH_USER="${AUTH_USER:-admin}"
read -rsp "  Admin Password: " AUTH_PASS
echo ""

# RMQ tunnel ports
echo ""
echo "  RabbitMQ tunnel ports (local forwards to the game server)"
read -rp "  RMQ Admin Port [30325]: " RMQ_ADMIN_PORT
RMQ_ADMIN_PORT="${RMQ_ADMIN_PORT:-30325}"
read -rp "  RMQ Game Port [32716]: " RMQ_GAME_PORT
RMQ_GAME_PORT="${RMQ_GAME_PORT:-32716}"

# Remote access
echo ""
echo "  Remote access:"
echo "    Local only (n) - access from this machine only (recommended)"
echo "    Remote (y)     - access from other devices on your network"
read -rp "  Enable remote access? (y/N): " ENABLE_REMOTE
DASH_HOST="127.0.0.1"
SSL_CERT="null"
SSL_KEY="null"
SSL_DOMAIN="null"
SSL_EMAIL="null"
HTTP_REDIRECT="false"
if [ "$ENABLE_REMOTE" = "y" ] || [ "$ENABLE_REMOTE" = "Y" ]; then
    DASH_HOST="0.0.0.0"
    echo ""
    echo "  Remote access needs HTTPS. You can use a domain with Let's Encrypt"
    echo "  or fall back to a self-signed certificate (browser warning)."
    read -rp "  Domain name (leave blank to use a self-signed certificate): " SSL_DOMAIN_IN
    if [ -n "$SSL_DOMAIN_IN" ]; then
        read -rp "  Email address (required by Let's Encrypt): " SSL_EMAIL_IN
        if command -v certbot &>/dev/null && [ -n "$SSL_EMAIL_IN" ]; then
            echo "  Requesting Let's Encrypt certificate for $SSL_DOMAIN_IN..."
            if sudo certbot certonly --standalone --non-interactive --agree-tos -m "$SSL_EMAIL_IN" -d "$SSL_DOMAIN_IN" 2>/dev/null; then
                SSL_CERT="/etc/letsencrypt/live/${SSL_DOMAIN_IN}/fullchain.pem"
                SSL_KEY="/etc/letsencrypt/live/${SSL_DOMAIN_IN}/privkey.pem"
                SSL_DOMAIN="$SSL_DOMAIN_IN"
                SSL_EMAIL="$SSL_EMAIL_IN"
                echo "  Let's Encrypt certificate issued."
            else
                echo "  [WARN] Let's Encrypt failed (port 80 must be reachable). Falling back to self-signed."
            fi
        else
            echo "  [WARN] certbot not found or no email given. Falling back to self-signed."
            echo "  Install with: sudo apt install certbot  (Ubuntu/Debian)"
        fi
    fi
    if [ "$SSL_CERT" = "null" ]; then
        echo ""
        read -rp "  This machine's IP for the certificate [127.0.0.1]: " HOST_IP
        HOST_IP="${HOST_IP:-127.0.0.1}"
        mkdir -p "$PROJECT_ROOT/ssl"
        if $PYTHON -c "
import sys
sys.path.insert(0, '$PROJECT_ROOT')
from app.utils.ssl import generate_cert
generate_cert('$PROJECT_ROOT/ssl/cert.pem', '$PROJECT_ROOT/ssl/key.pem', common_name='$HOST_IP', san_ips=['$HOST_IP', '127.0.0.1'], san_dns=['localhost'])
" 2>/dev/null; then
            SSL_CERT="$PROJECT_ROOT/ssl/cert.pem"
            SSL_KEY="$PROJECT_ROOT/ssl/key.pem"
        else
            echo "  [WARN] Could not generate a certificate. Remote access will be HTTP only."
        fi
    fi
    if [ "$SSL_CERT" != "null" ]; then
        echo ""
        echo "  Optional: redirect plain http://HOST to https automatically."
        echo "  Requires TCP port 80 to be free."
        read -rp "  Enable HTTP redirect on port 80? (y/N): " HTTP_REDIRECT_IN
        if [ "$HTTP_REDIRECT_IN" = "y" ] || [ "$HTTP_REDIRECT_IN" = "Y" ]; then
            HTTP_REDIRECT="true"
        fi
    fi
fi

# [5/5] Generate settings
echo ""
echo "[5/5] Generating settings.yaml..."
echo ""

# Hash password
PASS_HASH=""
if [ -n "$AUTH_PASS" ]; then
    PASS_HASH=$($PYTHON -c "
from argon2 import PasswordHasher
ph = PasswordHasher(time_cost=3, memory_cost=65536)
print(ph.hash('${AUTH_PASS//\'/\'\"\'\"\'}'))
" 2>/dev/null)
    if [ -z "$PASS_HASH" ]; then
        echo "  [WARN] argon2-cffi not installed — password stored as plaintext."
        echo "  Install with: pip install argon2-cffi"
        PASS_HASH=""
    fi
fi

SECRET_KEY=$($PYTHON -c "import secrets; print(secrets.token_hex(32))" 2>/dev/null || echo "change-me-in-production")

# Normalize SSH key path for YAML
SSH_KEY_YAML="$SSH_KEY"
if [ -n "$SSH_KEY_YAML" ]; then
    SSH_KEY_YAML=$(echo "$SSH_KEY_YAML" | sed 's|\\|/|g')
fi

cat > "$PROJECT_ROOT/settings.yaml" << YAML_EOF
server:
  host: ${VM_HOST}
  user: ${SSH_USER}
  ssh_key: ${SSH_KEY_YAML}

dashboard:
  host: ${DASH_HOST}
  port: ${DASH_PORT}
  debug: false
  secret_key: ${SECRET_KEY}
  ssl_cert: ${SSL_CERT}
  ssl_key: ${SSL_KEY}
  ssl_domain: ${SSL_DOMAIN}
  ssl_email: ${SSL_EMAIL}
  http_redirect: ${HTTP_REDIRECT}
  http_redirect_port: 80

database:
  host: 127.0.0.1
  port: ${DB_PORT}
  user: postgres
  password: null
  name: dune
  schema: dune

kubernetes:
  namespace: ${K8S_NAMESPACE}
  battlegroup_script: /home/dune/.dune/bin/battlegroup

director:
  port: ${DIR_PORT}

filebrowser:
  port: 18888

firewall:
  block_filebrowser: true
  block_director: true

cache:
  chat_pod_ttl: 60
  chat_messages_ttl: 10
  static_data_ttl: 300

auth:
  enabled: true
  username: ${AUTH_USER}
  password_hash: ${PASS_HASH}

logging:
  level: INFO
  file: logs/dashboard.log
  max_bytes: 10485760
  backup_count: 5

rabbitmq:
  admin_port: ${RMQ_ADMIN_PORT}
  game_port: ${RMQ_GAME_PORT}
  username: dashboard_admin
  password: null
YAML_EOF

echo "  settings.yaml created!"

# Create logs directory
mkdir -p "$PROJECT_ROOT/logs"

# Test database connection
if [ -n "$SSH_KEY" ] && [ "$VM_HOST" != "YOUR_SERVER_IP" ]; then
    echo ""
    echo "  Testing database connection via SSH tunnel..."
    echo "  (Start the dashboard with option 1 or 7 first to set up tunnels)"
fi

if [ "$DASH_HOST" = "0.0.0.0" ] && command -v ufw &>/dev/null; then
    echo ""
    echo "  Remote access is on. This machine's firewall may block port ${DASH_PORT}."
    read -rp "  Allow TCP port ${DASH_PORT} through ufw now? (requires sudo) (y/N): " UFW_ALLOW
    if [ "$UFW_ALLOW" = "y" ] || [ "$UFW_ALLOW" = "Y" ]; then
        sudo ufw allow "${DASH_PORT}/tcp" 2>/dev/null && echo "  Firewall rule added." || echo "  [WARN] Could not add firewall rule."
    else
        echo "  Skipped. If remote access fails, run: sudo ufw allow ${DASH_PORT}/tcp"
    fi
fi

echo ""
echo "============================================================"
echo "  Setup Complete!"
echo "============================================================"
echo ""
echo "  Next steps:"
echo "    1. Start the dashboard: bash start.sh -> option 1"
echo ""
if [ "$SSL_CERT" != "null" ]; then
    echo "    2. Open https://localhost:${DASH_PORT} in your browser (or your domain/IP)"
else
    echo "    2. Open http://localhost:${DASH_PORT} in your browser"
fi
echo ""
echo "  Username: ${AUTH_USER}"
echo "  Password: (what you entered)"
echo ""
