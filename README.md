# Dune Awakening Dashboard

A comprehensive web-based management dashboard for Dune: Awakening private servers. Provides real-time monitoring, player management, chat logging, file browsing, and server administration tools.

## Branching Strategy

This repo follows a git-flow inspired strategy. Here's the breakdown:

- **main** - Current beta release. It's stable enough to use, but things still break occasionally. I'm working toward a proper stable release, but we're not there yet. Don't use main as a reference for "production-ready" code - it's more "production-adjacent."

- **nightly** - The cutting edge. Updated automatically from main with the latest changes. Might have shiny new features, might have shiny new bugs. Generally works but don't be surprised if something catches fire.

- **experimental** - Where ideas go to become features or crash spectacularly. This is where new features are tested, questionable UI decisions are made, and code is written that might make future-me weep. Expect bugs. Expect weirdness. Expect things to break in creative new ways.

> "This seemed like a great idea at 3am" - every experimental commit ever

**Workflow:** Features → experimental → testing → nightly → main (eventually)

If you're testing this project, grab builds from nightly for the latest features, or main for something more stable. Experimental is where I break things on purpose to see what sticks.

## Quick Start

### Windows
1. Double-click `launcher.bat` (or run `.\launcher.ps1` in PowerShell)
2. Select option **2** to run Setup on first use
3. Select option **1** to Start Dashboard

> **Tip**: The launcher automatically finds your SSH key from the Dune Awakening server installation at `%LOCALAPPDATA%\DuneAwakeningServer\sshKey`.
>
> **Note**: If PowerShell blocks running scripts due to execution policy (`launcher.ps1` won't run), use `launcher.bat` instead — it bypasses the restriction automatically. You can also run `powershell.exe -ExecutionPolicy Bypass -File .\launcher.ps1` directly from Command Prompt.

## Features

- **Map Features**: Interactive maps with real-world coordinate calibration for Hagga Basin and The Deep Desert. Default view centers on Hagga Basin at 15% zoom. Zoom range: 15%–100%.
- **Player Management**: View, search, and filter players. Track online status, factions, guilds, and locations. Rich detail view with vitals, currency, inventory, vehicles, buildings, landclaims, specialization, keystones, and faction reputation.
- **Chat Logs**: Parsed from text-router pod logs with channel filtering and auto-refresh.
- **Director Controls**: Live battlegroup stats, world state management, and server transfer controls.
- **File Browser**: Secure SSH-based file browser for server configuration and logs.
- **Shell Access**: Interactive VM and Kubernetes pod shells directly in the browser.
- **Admin Tools**: Ban management, IP detection, kick/unban functionality, player history, item/currency/vitals editing, and raw SQL query interface.
- **Firewall Security**: Block unauthenticated game server ports (File Browser, Director) from external internet access. Applied via iptables on the game server VM across INPUT, FORWARD, and mangle PREROUTING chains to cover both host services and Kubernetes NodePort traffic. Configurable per-port during setup or from the Server page.
- **Vehicles & Buildings**: Track owned vehicles, modules, and player structures.
- **Auto-Update**: Background checker polls GitHub for new commits. Safe file replacement preserves your settings, logs, and SSH keys. One-click update from the dashboard.
- **Remote Access**: Built-in support for HTTPS and binding to `0.0.0.0` for secure remote management.
- **Let's Encrypt**: Optionally set up publicly trusted SSL certs during setup with automatic renewal via certbot.
- **Settings Migration**: Automatically adds new configuration options to `settings.yaml` when updating, so you never miss a feature.
- **Cross-Platform**: Works on Windows (`.bat`/`.ps1`) and Linux/macOS (`.sh`).
- **Organized Logging**: Launcher logs are automatically categorized by type (SSH, K8s, database, etc.) with sensitive data redacted. Old logs are cleaned up after 30 days, oversized files are truncated at 10 MB.
- **Debug Mode**: Enable verbose debug logging via launcher (option 6) or the Server page UI. Logs detailed information about all HTTP requests/responses, SSH commands, database queries, Kubernetes operations, and service health checks. All sensitive data (passwords, tokens, keys) is automatically sanitized before writing to log files. Debug logs are written to `logs/debug.log`.

## License

This project is **Source Available** under the [Dune Dashboard Source License (DDSL)](LICENSE).
- Source code is available for inspection and security auditing.
- **No redistribution** (modified or unmodified).
- **No claiming of credit** or authorship.
- Personal, non-commercial use only.

## Requirements

- Python 3.8+
- Node.js 18+ (for frontend development/build)
- OpenSSH client
- `kubectl` access to the Dune: Awakening Kubernetes cluster
- SSH access to the game server VM

## Setup

### Windows

1. **Run the Launcher**
    ```powershell
    .\launcher.ps1
    ```

2. **Choose an option from the menu:**
    - **[1] Start Dashboard** — Launch the dashboard web interface
    - **[2] Run Setup** — Configure the dashboard for the first time (or reconfigure)
    - **[3] Run Diagnostics** — Check your system for common issues
    - **[4] Install CA Certificate** — Install the local CA into Windows Trusted Root store (removes browser SSL warnings)
    - **[5] Clean & Reinstall CA Certificate** — Remove old CA certificates and install a fresh one
    - **[6] Start Dashboard (Debug Mode)** — Launch with full debug logging enabled
    - **[7] Start New Dashboard (React + ChakraUI)** — Launch the modern React dashboard with auto-installed dependencies
    - **[8] Reset to Factory Defaults** — Wipe all data (settings, logs, certs, cache, node_modules) and return to a clean state
    - **[9] Repair Game Database** — Fix dashboard schema ownership so game updates won't break servers
    - **[10] Clean up Old Dashboard Schema** — Drop the old `dashboard` schema from the game database (after migration)
    - **[Q] Quit** — Exit the launcher

3. **First-time Setup** (option 2)

    The setup script will:
    - Install Python dependencies
    - Find your SSH key (automatically detects the Dune Awakening server key)
    - Auto-detect your VM IP from Hyper-V or SSH history
    - Generate SSL certificates (local CA or Let's Encrypt)
    - Configure firewall rules and security hardening

    During setup you'll be prompted for:
    - **VM External IP** — the IP you SSH into (e.g., `<YOUR_VM_IP>`)
    - **Host External IP** — the public IP for SSL certificate SANs (e.g., `<YOUR_HOST_IP>`)
    - **Let's Encrypt** — optionally set up a publicly trusted SSL cert with auto-renewal via certbot
    - **Firewall rules** — only prompted if no `DuneDashboard` rule exists yet

    > **Note**: Setup will retry SSH up to 12 times (60 seconds) to accommodate fresh VM boot times. If SSH isn't ready yet, you can still continue and enter your Kubernetes namespace manually.

4. **Start Dashboard** (option 1)

    The launcher will:
    - Establish an SSH tunnel to your game server
    - Set up database and Director port-forwards via kubectl
    - Scale up the BGD deployment if needed
    - Launch the dashboard web interface

### Linux / macOS

1. **Start Dashboard**
    ```bash
    chmod +x start.sh
    ./start.sh
    ```
    The launcher will prompt you to run setup if `settings.yaml` is missing.

## Configuration

All settings are stored in `settings.yaml`. The setup script generates this automatically. Key settings include:

- `server.host`: Game server VM IP
- `server.ssh_key`: Path to your SSH private key
- `kubernetes.namespace`: Auto-detected K8s namespace
- `database.port`: Local port for database tunnel
- `auth.username` / `auth.password_hash`: Dashboard login credentials (password_hash is Argon2 hash, generated by setup)

### Remote Access

During setup, answer **y** to "Enable remote access?" to:
- Bind to `0.0.0.0` (accessible from other machines)
- Auto-generate SSL certificates for HTTPS
- Enable secure remote connections via `https://YOUR_IP:5050`

**Firewall rules** are created automatically during setup. On subsequent starts, `start.ps1`/`start.sh` will only prompt if the `DuneDashboard` rule is missing.

You can also manually edit `settings.yaml` later:
```yaml
dashboard:
  host: 0.0.0.0
  ssl_cert: ssl/cert.pem
  ssl_key: ssl/key.pem
```

### Let's Encrypt (Publicly Trusted Certs)

During setup, answer **y** when asked to enable Let's Encrypt. The setup script will:
1. Install `certbot` (tries `winget`, `pip`, and `python -m` fallbacks on Windows)
2. Run `certbot certonly --standalone` to validate your domain
3. Configure auto-renewal via Windows Scheduled Task or Linux cron
4. Point the dashboard to the Let's Encrypt cert paths

> **Note**: Port 80 must be free during certbot validation. The dashboard's HTTP redirect server will release port 80 temporarily for this.

### Local CA Utilities (Windows)

Available from the launcher menu (`.\launcher.ps1`):
- **Option 4: Install CA Certificate** — Installs the local CA (`ssl/ca.pem`) into Windows Trusted Root store. Run as Administrator. Removes browser warnings.
- **Option 5: Clean & Reinstall CA Certificate** — Removes all old Dune Dashboard CA certificates from Windows Trusted Root store and installs a fresh one. Use if you have duplicate or expired CA certificates.

### SSL Configuration

The dashboard supports both self-signed and CA-signed certificates.

**Local CA (auto-generated during setup):**
- A local Certificate Authority (`ssl/ca.pem`) is created during setup
- Server certificates are signed by this CA
- Server certs include SAN for the server IP + `127.0.0.1` + `localhost`
- Valid for 365 days

**Remove browser warnings (Windows):**
1. Run `.\launcher.ps1` and select option **4** (Install CA Certificate)
2. Restart your browser
3. Access `https://localhost:5050` — no more warnings

**Remove browser warnings (Linux):**
```bash
sudo cp ssl/ca.pem /usr/local/share/ca-certificates/dune-dashboard-ca.crt
sudo update-ca-certificates
```

**Let's Encrypt or custom CA:**
```yaml
dashboard:
  host: 0.0.0.0
  ssl_cert: /etc/letsencrypt/live/yourdomain.com/fullchain.pem
  ssl_key: /etc/letsencrypt/live/yourdomain.com/privkey.pem
```

When SSL is enabled:
- Session cookies are marked `Secure` (sent only over HTTPS)
- HTTP-to-HTTPS redirect runs on port+1 (e.g., `http://localhost:5051` → `https://localhost:5050`)
- Certificate expiry is checked at startup (warning if < 30 days)

**Regenerate certificates:**
Delete `ssl/cert.pem`, `ssl/key.pem`, and `ssl/ca*.pem`, then re-run setup.

### Auto-Renewal

SSL certificates are automatically regenerated when they approach expiry:
- A background thread checks the certificate every 24 hours (configurable)
- If the certificate expires within 30 days (configurable), a new one is generated
- The server does **not** need to restart — Flask-SocketIO picks up the new cert on the next connection
- Configure thresholds in `settings.yaml` under the `ssl:` section

## Project Structure

```
DuneDashboard/
├── backend/             # New Flask backend (API + services)
│   ├── app/
│   │   ├── routes/      # HTTP route handlers (API, auth, health, server, files, director, chat)
│   │   ├── services/    # Business logic (DB, SSH, K8s, BGD, RMQ, player, economy, guild, world, etc.)
│   │   ├── models/      # Pydantic v2 models
│   │   ├── websocket/   # Socket.IO shell handler
│   │   ├── config.py    # Settings loader
│   │   └── factory.py   # App factory (services, blueprints, security)
│   ├── run.py           # Entry point
│   └── requirements.txt # Python dependencies
│
├── frontend/            # New React SPA (Vite + TypeScript + Tailwind)
│   ├── src/
│   │   ├── components/  # Pages (overview, players, guilds, vehicles, buildings, map, accounts, server, admin, chat, shell, files, director, settings)
│   │   ├── api/         # Axios client
│   │   ├── stores/      # React Context (app state, auth, theme)
│   │   ├── hooks/       # Custom hooks (realtime, debounce)
│   │   └── styles/      # Tailwind + 14 Dune themes
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   └── tsconfig.json
│
├── app/                 # Legacy Flask/Jinja2 dashboard (untouched, still functional)
│   ├── routes/
│   ├── services/
│   ├── utils/
│   └── websocket/
├── templates/           # Legacy Jinja2 HTML templates
├── static/              # Legacy CSS and frontend assets
├── scripts/             # Pre-flight utilities (db_check.py)
├── launcher.ps1         # Unified launcher (setup, start, diagnostics, CA tools)
├── start.sh             # Linux/macOS entry point
├── settings.yaml        # Configuration (gitignored)
└── settings.yaml.example # Reference configuration
```

> **Note**: The legacy `app/`, `templates/`, and `static/` directories remain untouched and functional. The new system lives in `backend/` and `frontend/`. Both can coexist during migration.

## Architecture

### Frontend
- **React 18** with TypeScript
- **Vite** for fast builds and HMR
- **Tailwind CSS** for styling with 14 Dune house themes
- **SWR** for server state caching and revalidation
- **Axios** for HTTP requests with 401 redirect handling
- **Socket.IO Client** for the remote terminal
- **xterm.js** for the in-browser shell

### Backend
- **Flask 3** with Blueprint-based routing
- **Pydantic v2** for request/response validation
- **psycopg3** with connection pooling for PostgreSQL
- **Flask-SocketIO** for the interactive shell
- **Flask-Login** for session-based authentication (Argon2 password hashing)
- **Flask-Limiter** for rate limiting
- **SSE (Server-Sent Events)** for real-time updates (battlegroup, chat, metrics)

### Services
- `DatabaseService` — psycopg3 pool, stored procedure executor, audit table DDL
- `SSHService` — paramiko SSH client for tunneling and remote commands
- `K8sService` — kubectl-over-SSH for pod/deployment management
- `BgDirectorService` — HTTP client for the Battlegroup Director API
- `RmqAdminService` — RabbitMQ Management HTTP API client
- `RmqGameService` — RabbitMQ Game HTTP API client (broadcasts, chat intercept)
- `RealtimeService` — SSE broadcaster with background polling loops
- `PlayerService` / `EconomyService` / `GuildService` / `WorldService` / `ProgressionService` / `CharacterService` — DB-function-only domain services
- `AuditService` — persistent PostgreSQL audit logging
- `ChatService` — chat history + pod log catch-up

## Security Notes

- Never commit `settings.yaml` to version control.
- SSH keys are copied to `%TEMP%` with restricted permissions during startup.
- All database queries use parameterized statements to prevent SQL injection.
- Dashboard authentication is required by default.
- Raw SQL query endpoint (`/api/query`) is **read-only SELECT** — INSERT/UPDATE/DELETE/DROP/CREATE/ALTER/GRANT/TRUNCATE are blocked.
- All mutations are audited to PostgreSQL.
- CSP, HSTS, X-Frame-Options, and other security headers are enforced in production mode.

## Logging

The launcher automatically organizes and sanitizes logs to protect sensitive information.

### Log Categories

```
logs/
├── launcher/
│   ├── general/        # General launcher events
│   ├── ssh/            # SSH tunnel and connection logs
│   ├── k8s/            # Kubernetes operations
│   ├── database/       # Database port-forward and connections
│   ├── dashboard/      # Dashboard startup and runtime
│   ├── setup/          # Setup wizard logs
│   └── diagnostics/    # Diagnostic tool output
├── app.log             # Python application log (rotating, 10 MB max, 5 backups)
└── audit.log           # Security audit log (rotating, 10 MB max, 5 backups)
```

### Sensitive Data Redaction

All launcher log files are automatically sanitized before writing. The following are redacted:
- IP addresses → `<IP_REDACTED>`
- JWT tokens → `<JWT_REDACTED>`
- Base64 secrets → `<BASE64_REDACTED>`
- SSH key paths → `<SSH_KEY_PATH_REDACTED>`
- K8s namespaces → `<NAMESPACE_REDACTED>`
- Host IDs → `<HOST_ID_REDACTED>`
- Passwords/tokens → `<REDACTED>`
- Funcom IDs → `<FUNCOM_ID_REDACTED>`

Console output is **not** sanitized so you can see full details during operation.

### Automatic Cleanup

- Log files older than **30 days** are deleted
- Files exceeding **10 MB** are truncated (keeps last 5000 lines)
- Empty category directories are removed
- Cleanup runs automatically on every launcher start

## Development

### Frontend Development

```bash
cd frontend
npm install
npm run dev        # Vite dev server with API proxy to localhost:5050
npm run build      # Production build to frontend/dist/
```

### Backend Development

```bash
cd backend
pip install -r requirements.txt
python run.py      # Or: flask --app run:app run
```

### Themes

The dashboard supports 14 Dune house themes. Switch via the theme picker in the top-right nav bar:
Classic Dune, House Atreides, House Harkonnen, Fremen, Bene Gesserit, Spacing Guild, Emperor, House Corrino, Mentat, Sardaukar, Bene Tleilax, House Ordos, Ix, CHOAM.

Themes are implemented via CSS custom properties (`var(--primary)`, `var(--bg)`, etc.) and switched by setting `data-theme` on the `<html>` element.
