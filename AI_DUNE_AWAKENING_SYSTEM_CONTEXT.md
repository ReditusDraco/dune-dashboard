# Dune Awakening — Full System Context for AI Continuation

> **Last updated:** 2026-05-22 (production VPS at 65.21.198.100, cluster fully running)
> **VM Hostname:** `duneawakening` (Alpine Linux 3.23.4, K3s single-node)
> **Server IP:** `65.21.198.100`
> **Dashboard repo:** `C:\Users\Reditus\OneDrive\Documents\GitHub\dune-dashboard-private`
> **This doc path:** `C:\Users\Reditus\Downloads\DUNE_AWAKENING_SYSTEM_CONTEXT.md`
> **⚠️ SECURITY: NEVER commit this doc or any credentials to GitHub.**

---

## ⚠️ YOUR MISSION (read this first)

You are continuing work on a **Dune Awakening private game server**. Your job is to help access and configure admin settings on the game server. Everything you need is in this document.

### What to do
1. **Read this entire document** — it contains the full architecture, credentials, connection methods, and what's been tried.
2. **Connect to the VM** via SSH (see section 1), run kubectl commands, explore the cluster.
3. **Continue from section 12** ("What's Still Unknown / Next Steps") — that's the active work queue.
4. **Update this document** with any new findings, credentials discovered, or progress made.
5. **Ask the user** only when you genuinely need a decision or something is blocked. Otherwise, just do it.

### How to work
- All kubectl commands need `sudo` on the VM.
- PowerShell has tricky quoting — use script files piped via SSH for complex commands (`tr -d '\r'` to strip CRLF).
- The SSH tunnel for the dashboard (localhost:15433 → DB, localhost:32479 → BGD) may need restarting if down.
- When you find new credentials or endpoints, **add them to this document immediately**.
- **NEVER commit or push to GitHub.** The doc lives in Downloads for a reason.

### Current priorities
- ✅ **DONE:** DB schema migration succeeded — cluster is fully running. See finding #19.
- ✅ **DONE:** RMQ Management UI accessible with `admin:admin123`. See finding #20.
- ✅ **DONE:** `send-dune-broadcast` tested and working on live server. See finding #21.
- **High:** Add custom broadcast title/identity (e.g., "Dune Admin" instead of hardcoded FLS backend)
- **Medium:** Integrate broadcast functionality into the dashboard admin panel.
- **Medium:** Scale operators back up (currently scaled to 0).

---

## 1. HOW TO CONNECT

### SSH to VM
```powershell
ssh -i "$env:LOCALAPPDATA\DuneAwakeningServer\sshKey" -o StrictHostKeyChecking=accept-new dune@65.21.198.100
```
**Note:** Production VPS at `65.21.198.100`. Hostname: `duneawakening`, Alpine Linux 3.23.4, K3s single-node. No longer a local Hyper-V VM.

**Installed tools on VM (2026-05-22):** `curl`, `python3`, `py3-pip` (via `apk add`)

**⚠️ SCP does not work on this VM** (no `sftp-server`). Use pipe method instead:
```powershell
Get-Content -Raw script.sh | ssh -i "<key>" dune@65.21.198.100 "cat > /tmp/script.sh && tr -d '\r' < /tmp/script.sh > /tmp/script_clean.sh && mv /tmp/script_clean.sh /tmp/script.sh && chmod +x /tmp/script.sh && bash /tmp/script.sh"
```

### SSH Tunnel (maintained by dashboard launcher, PID 31172)
| Local Port | Forwards To | Purpose |
|-----------|-------------|---------|
| `localhost:15433` | VM:DB cluster IP (15432) | PostgreSQL |
| `localhost:32479` | VM:BGD NodePort 31403 | BGD Director API |

### Kubectl on VM
```bash
# All commands need sudo
sudo kubectl get pods -A
sudo kubectl get svc -A
sudo kubectl get secrets -A
sudo kubectl logs -n <namespace> <pod>
sudo kubectl exec -n <namespace> <pod> -- <command>
```

### BGD Web UI
- `http://192.168.0.101:31403/` — web dashboard with player stats
- `http://10.43.173.27:11717/` — via cluster IP (from inside VM)

---

## 2. ARCHITECTURE OVERVIEW

```
Windows Host                          Hyper-V VM (192.168.0.101 / dune-awakening)
┌────────────────────┐                ┌─────────────────────────────────────────────┐
│  Dashboard         │                │  K3s Cluster (single node)                  │
│  (Flask/SocketIO)  │ ───SSH─────→   │                                             │
│  Port 5050         │    tunnel      │  ┌──────────────────────────────────────┐   │
│                    │                │  │ funcom-seabass-{WORLD_ID}-whxlri     │   │
│  RabbitMQ UI:      │                │  │                                      │   │
│  192.168.0.101:    │                │  │  mq-admin-sts (RabbitMQ admin)       │   │
│   32253 (admin)    │                │  │  mq-game-sts  (RabbitMQ game)        │   │
│   31745 (game)     │                │  │  tr-deploy    (Text Router / Auth)   │   │
│                    │                │  │  bgd-deploy   (Battlegroup Director) │   │
│                    │                │  │  sgw-deploy   (Server Gateway)       │   │
│                    │                │  │  db-dbdepl    (PostgreSQL)            │   │
│                    │                │  │  sg-overmap   (Overmap game server)   │   │
│                    │                │  │  sg-survival-1 (Pending - unsched)   │   │
│                    │                │  │  fb-deploy    (File Browser)         │   │
│                    │                │  │                                      │   │
│                    │                │  │ funcom-operators namespace:          │   │
│                    │                │  │  battlegroupoperator                 │   │
│                    │                │  │  databaseoperator                    │   │
│                    │                │  │  serveroperator                      │   │
│                    │                │  │  utilitiesoperator                   │   │
│                    │                │  └──────────────────────────────────────┘   │
│                    │                │                                             │
│                    │                │  VM Scripts: /home/dune/.dune/download/     │
│                    │                │    scripts/{battlegroup.sh, bg-util, ...}   │
│                    │                │    images/battlegroup/*.tar (Docker images) │
│                    │                └─────────────────────────────────────────────┘
```

---

## 3. ALL EXPOSED SERVICES (NodePort on 65.21.198.100)

| Service | Type | ClusterIP | NodePort | Internal Ports | Purpose |
|---------|------|-----------|----------|---------------|---------|
| bgd-svc | NodePort | 10.43.92.250 | **30553** | 11717 | BGD Director web UI + API |
| mq-admin-svc | NodePort | 10.43.78.227 | **30325** | 15672 (HTTP) | RMQ Admin Management UI ✅ |
| mq-admin-svc | NodePort | 10.43.78.227 | **32729** | 5672 (AMQP) | RMQ Admin AMQP (TLS) |
| mq-game-svc | NodePort | 10.43.79.0 | **32716** | 15672 (HTTP) | RMQ Game Management UI ✅ |
| mq-game-svc | NodePort | 10.43.79.0 | **31982** | 5672 (AMQP) | RMQ Game AMQP (TLS) |
| db-dbdepl-svc | ClusterIP | 10.43.14.243 | - | 15432 | PostgreSQL |
| tr-svc | ClusterIP | 10.43.40.75 | - | 5059 | Text Router (RMQ auth) |

**Note:** NodePorts are dynamically assigned and change on each install. Always check with `sudo kubectl get svc -n <namespace>`.

**Current (2026-05-22 production):** RMQ Admin UI at `http://65.21.198.100:30325`, RMQ Game UI at `http://65.21.198.100:32716`. Both accessible from outside the server.

---

## 4. CREDENTIALS FOUND

### RMQ HTTP Token Auth Secret (SIGNING KEY — NOT a password)
```
gZQbpwOA6ow190HgLKDfxy9zZoRWejTJ1Trp+fnMQkNapY7TEdQ6RIXbLUVAlpPtbaz9pGLW8M8LWnjOfsCTKQ==
```
- Base64-decoded: 64 bytes
- Used by: TR (Text Router) service to validate RMQ authentication tokens
- Stored in: `rmq-game-secret` Kubernetes secret
- Also present as env var in: BGD pod, SGW pod, TR pod, mq-admin pod, mq-game pod

### FuncomLiveServices Service Auth Token (JWT)
```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJIb3N0SWQiOiJCMTdBNUYwMzZEMUY3ODgyIiwiVG9rZW5JbmRleCI6IjEiLCJTZXJ2aWNlQXV0aEtleSI6IjI4RVVGOFMyM2dnQXdNWjQwUjRCQUZ1TTVFbkswM3RHeDZLY1h3Q0Vkc3FEcmVoUExxWFhGS0ZNcUIyYlNCUmYiLCJTZXJ2aWNlSG9zdFR5cGUiOiIyIiwibmJmIjoxNzc5MzE4MjQ1LCJleHAiOjE4MTA4NTQyNDUsImlhdCI6MTc3OTMxODI0NX0.yNenOJVmshIg1OcTEt0UeEmdUBnTQn2Gov098znvHMg
```
**Decoded payload:**
```json
{
  "HostId": "B17A5F036D1F7882",
  "TokenIndex": "1",
  "ServiceAuthKey": "28EUGFS2M23ggAWMjQ0jR4BAFuM5VEbKsM3tGd6KYXh7CFKcsDqchPLxxXFGKFNqB2bNCBRf",
  "ServiceHostType": "2",
  "nbf": 1779318245,
  "exp": 1810854245,
  "iat": 1779318245
}
```
- Used by: BGD, SGW, TR for service-to-service authentication
- Expires: 2027-05-15

### Database Password
- **User:** `dune`
- **Password:** `qEJ1xJUedRJCv5qnAPJEnFnR`
- **Superuser:** `postgres` (no password needed from inside cluster)
- **Database:** `dune`
- **Schema:** `dune` (main game data), `ext` (extensions), `public`
- **Note:** Database is essentially empty (0 players, fresh install)

### RabbitMQ Users (from RMQ logs — user format: `{service}.{world}.{token}.{role}`)
| User | Purpose | Pod |
|------|---------|-----|
| `sg.{WORLD}.wlP+pNNSRYeatInPivYEjw.admin` | Server Gateway admin | on mq-admin |
| `sg.{WORLD}.wlP+pNNSRYeatInPivYEjw.game` | Server Gateway game | on mq-game |
| `bgd.{WORLD}.Y_WL2MEd406KLEg5Lu+Bpw.admin` | BGD Director admin | on mq-admin |
| `bgd.{WORLD}.Y_WL2MEd406KLEg5Lu+Bpw.game` | BGD Director game | on mq-game |
| `tr.{POD}.iKkgMO91kEOlvCGqBwT3dg` | Text Router | on mq-game |

### FLS API Key
- **Value:** `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` (masked/placeholder)
- Stored as `fls-apikey` in server-gateway-secret

### RabbitMQ Management UI Credentials (RESOLVED 2026-05-22)
- **Username:** `admin`
- **Password:** `admin123`
- **Admin UI:** `http://65.21.198.100:30325` — ✅ Working
- **Game UI:** `http://65.21.198.100:32716` — ✅ Working
- **How it was done (new approach, 2026-05-22 production):**
  1. Scaled down all 4 operators to 0 replicas (prevents ConfigMap reconciliation)
  2. Modified `mq-admin-cm` and `mq-game-cm` ConfigMaps: changed `auth_backends.1 = $(RMQ_AUTH_BACKEND_1)` to `auth_backends.1 = internal` + `auth_backends.2 = $(RMQ_AUTH_BACKEND_1)`
  3. Restarted RMQ StatefulSet pods (they pick up new config)
  4. Created admin users on both mq-admin and mq-game via `rabbitmqctl add_user admin admin123`
  5. Set `administrator` tag and full permissions on both
- **Key difference from old approach:** Kept HTTP auth plugin enabled (needed for game services), just added `internal` as primary auth backend so the admin user is checked first. Game service tokens still authenticate via HTTP→TR fallback.
- **Note:** Admin users are LOST on pod restart (PV doesn't persist user data reliably). Must recreate via `rabbitmqctl` after each restart.

---

## 5. RABBITMQ AUTHENTICATION ARCHITECTURE

### How RMQ Auth Works
1. RabbitMQ is configured with `rabbitmq_auth_backend_http` + `rabbitmq_auth_backend_cache`
2. When a client connects via AMQP, RabbitMQ makes an HTTP POST to the TR service
3. **TR endpoint:** `POST /v0/auth/user` with `username` and `password` form params
4. TR validates the password as a structured/signed token using `RMQ_HTTP_TOKEN_AUTH_SECRET`
5. Returns `allow` or `deny`

### TR Service Details
- **Pod:** `{WORLD}-tr-deploy`
- **Image:** `seabass-server-text-router`
- **Port:** 5059
- **Type:** .NET 8 ASP.NET Core application (112MB binary at `/Tools/Battlegroups/TextRouter/TextRouter`)
- **Auth endpoints:** `/v0/auth/user` (GetUserAuth), `/v0/auth/vhost`, `/v0/auth/resource`, `/v0/auth/topic`
- **Config:** Minimal — `appsettings.json` only has Serilog settings

### AMQP is TLS-only
Both mq-admin and mq-game are configured with:
```
listeners.tcp = none
listeners.ssl.default = 5672
```
All AMQP connections use TLS. The Management UI (port 15672) is plain HTTP.

### Token Format (from TR logs)
The TR extracts a "token" from the password and parses it as:
- **Created** (DateTime, 8 bytes) — was `01/01/0001` for invalid tokens
- **TTL** (duration) — was `00:00:00` for invalid tokens

The token is validated using `RMQ_HTTP_TOKEN_AUTH_SECRET` as the HMAC signing key.
The 16-byte tokens in the usernames (`wlP+pNNSRYeatInPivYEjw` decoded) are too short and don't contain proper timestamp data.

### Management UI Login
- URL: `http://192.168.0.101:32253` (admin) or `http://192.168.0.101:31745` (game)
- Uses HTTP Basic Auth
- **Status:** ✅ RESOLVED — Use `admin:admin123` (see section 4)
- The default HTTP auth backend (TR service) intercepts all login attempts. Internal RMQ users bypass this.

---

## 6. BGD DIRECTOR API

### Web UI
The BGD has a Bootstrap web UI at its root (`/`) with:
- Player count (total, online, in-transit, grace period)
- Links to API endpoints

### API Endpoints Found
| Endpoint | Method | Response |
|----------|--------|----------|
| `/` | GET | HTML web UI |
| `/v0/players` | GET | `[]` (empty array) |
| `/v0/players/online` | GET | `[]` |
| `/v0/players/intransit` | GET | `[]` |
| `/v0/players/graceperiod` | GET | `[]` |
| Everything else | ANY | 404 Not Found |

### BGD Pod
- **Args:** `--RMQGameHostname`, `--RMQGamePort`, `--RMQAdminHostname`, `--RMQAdminPort`
- **Env:** Has `FuncomLiveServices__ServiceAuthToken` (JWT) and `RMQ_HTTP_TOKEN_AUTH_SECRET`
- The BGD connects to both mq-admin and mq-game via AMQP internally

---

## 6.5. SEND-DUNE-BROADCAST UTILITY (DISCOVERED 2026-05-22)

### Location
- **File:** `F:\Downloads\send-dune-broadcast`
- **Type:** Bash script (177 lines)
- **Purpose:** Sends in-game broadcast notifications to all connected players via RabbitMQ

### How It Works
The script publishes a message directly to the **`heartbeats` exchange** on the **mq-game** RabbitMQ instance using `rabbitmqctl eval` (Erlang code executed inside the RMQ pod).

**Message structure:**
```erlang
Outer = #{
    <<"Version">> => 2,
    <<"AuthToken">> => <<"Nu6VmPWUMvdPMeB7qErr">>,  %% ⚠️ HARDCODED TOKEN
    <<"MessageContent">> => Inner
}

Inner = #{
    <<"ServerCommand">> => <<"ServiceBroadcast">>,
    <<"BroadcastType">> => <<"Generic">>,
    <<"BroadcastPayload">> => #{
        <<"BroadcastDuration">> => Duration,
        <<"LocalizedText">> => [
            #{<<"Key">> => <<"en">>, <<"Title">> => Title, <<"Body">> => Body},
            #{<<"Key">> => <<"en-US">>, <<"Title">> => Title, <<"Body">> => Body}
        ]
    }
}
```

**Publishing details:**
- **Exchange:** `heartbeats`
- **Routing key:** `notifications`
- **App ID:** `fls`
- **User ID:** `fls_backend`
- **Message ID:** `manual-service-broadcast-{timestamp}`

### Usage
```bash
send-dune-broadcast --title "Server Notice" --message "Maintenance in 10 minutes" --duration 60
# or positional:
send-dune-broadcast "Server Notice" "Maintenance in 10 minutes" 60
```

### Key Findings
1. **Hardcoded AuthToken:** `Nu6VmPWUMvdPMeB7qErr` — this is the FLS (Funcom Live Services) backend auth token used to authenticate broadcast messages
2. **Direct RMQ access:** Bypasses the TR auth entirely by executing Erlang code inside the RMQ pod via `rabbitmqctl eval`
3. **No AMQP connection needed:** Uses RMQ's internal APIs (`rabbit_exchange:lookup_or_die`, `rabbit_queue_type:publish_at_most_once`)
4. **Localized text:** Supports multiple locales (en, en-US) — could be extended
5. **BroadcastType:** Currently hardcoded as `Generic` — there may be other types

### How to Run on Our Server
```bash
# Copy script to VM
scp -i "$env:LOCALAPPDATA\DuneAwakeningServer\sshKey" F:\Downloads\send-dune-broadcast dune@192.168.0.101:/home/dune/

# Make executable and run
ssh -i "$env:LOCALAPPDATA\DuneAwakeningServer\sshKey" dune@192.168.0.101 'chmod +x /home/dune/send-dune-broadcast && /home/dune/send-dune-broadcast --title "Test" --message "Hello from admin!" --duration 30'
```

### Potential Uses
- **Server announcements** (maintenance, events, restarts)
- **Emergency alerts** (crashes, rollbacks)
- **Welcome messages** for new players
- **Event notifications** (sandstorms, landsraad votes, etc.)
- **Integration with dashboard** — add a broadcast UI to the admin panel

### Integration with Dashboard
The dashboard's `send_global_broadcast()` in `app/services/admin.py:668` currently only publishes to SocketIO (dashboard clients). This script shows how to reach **actual game clients** via RMQ. We can:
1. Port the Erlang logic to Python using `pika` or `aio-pika`
2. Or wrap this script and call it via SSH from the dashboard
3. Add a broadcast UI to the admin panel with title/message/duration fields

### ⚠️ Important Notes
- The `heartbeats` exchange may not exist on our RMQ instance (it's created dynamically when the message is published)
- The AuthToken `Nu6VmPWUMvdPMeB7qErr` may need to match what the game clients expect
- This script requires `python3` on the VM for JSON escaping (already installed)
- The script uses `rabbitmqctl eval` which requires root/sudo access to the RMQ pod

---

## 7. TEXT ROUTER (TR) POD DETAILS

### Env Vars
```
FuncomLiveServices__RmqTlsEnabled=true
FuncomLiveServices__ServiceAuthToken=<JWT>
RMQ_HTTP_TOKEN_AUTH_SECRET=<signing-key>
Database_address={WORLD}-db-dbdepl-svc:15432
Database_name=dune
Database_password=qEJ1xJUedRJCv5qnAPJEnFnR
Database_user=dune
```

### Args
```
--RMQAdminHostname={WORLD}-mq-admin-svc --RMQAdminPort=5672
--RMQGameHostname={WORLD}-mq-game-svc --RMQGamePort=5672
```
The TR itself connects to RabbitMQ. It uses the JWT (or signed tokens) to authenticate.

---

## 8. DASHBOARD REPO CODE REFERENCES

| File | Key Content |
|------|-------------|
| `app/services/director.py` | BGD Director integration |
| `app/services/k8s.py` | `get_rabbitmq_pod()` — finds `mq-admin`/`mq-game` |
| `app/services/admin.py:668` | `send_global_broadcast()` — "simulates the administrative `send-dune-broadcast` utility" |
| `app/routes/api.py` | Health checks (RabbitMQ pod status) |
| `app/utils/event_manager.py` | SocketIO event publishing |
| `launcher.ps1:81` | Redacts `RMQ_HTTP_TOKEN_AUTH_SECRET` from logs |
| `settings.yaml.example` | Config template with SSH, DB, K8s settings |

**Note:** `send_global_broadcast()` is defined but NOT called by any route, websocket handler, or template — it's backend scaffolding.

---

## 9. VM SCRIPTS

| File | Location | Purpose |
|------|----------|---------|
| `setup.sh` | `/home/dune/.dune/download/scripts/` | Full setup orchestration |
| `battlegroup.sh` | Same dir | Battlegroup management CLI |
| `bg-util` | Same dir | 7MB Go binary (interactive, needs TTY) |
| `setup/helper.sh` | Same dir | Shared bash helpers |
| `setup/templates/world-template.yaml` | Same dir | Funcom CRD `BattleGroup` template |
| `setup/config/User*.ini` | Same dir | Default game user settings |

### battlegroup.sh Commands
`list`, `status`, `start`, `restart`, `stop`, `edit`, `edit-advanced`, `update`, `update-from-downloads`, `backup`, `import`, `logs-export`, `operator-logs-export`, `apply-default-usersettings`, `enable-experimental-swap`

### bg-util
- Interactive Go binary for editing battlegroup resources
- Requires a `world-template.yaml` path as argument
- Needs TTY (`error: could not open a new TTY` when run via SSH without `-t`)

---

## 10. DATABASE SCHEMA

### Schemas
- `dune` — Main game data (~160 tables)
- `ext` — Extensions
- `public` — Default schema
- `dashboard` — Dashboard's own tables (not yet created in this fresh install)

### Notable Tables (all empty on fresh install)
- `accounts`, `actors`, `buildings`, `items`, `vehicles`, `player_state`
- `guilds`, `factions`, `parties`
- `landsraad_decrees`, `landsraad_tasks` (with data: 11 decrees, 25 tasks)
- `event_log*` (partitioned — empty)
- `world_partition` (30 rows — server config)
- `dune_exchanges` (1 row — exchange config)

### Database Roles
| Role | Superuser | Login |
|------|-----------|-------|
| `dune` | No | Yes |
| `postgres` | Yes | Yes |

---

## 11. INTERESTING LOG ENTRIES

### RMQ mq-admin Errors
```
operation basic.publish caused a channel exception not_found:
no exchange 'completions' in vhost '/'
```
This occurs when the BGD or SGW tries to publish to a `completions` exchange that doesn't exist yet. Likely an initialization race condition or config issue.

### TR Malformed Token
```
Malformed token for user sg...wlP+pNNSRYeatInPivYEjw.game:
  wlP+pNNSRYeatInPivYEjw: created: 01/01/0001 00:00:00, TTL: 00:00:00
```
Indicates the token in the username is NOT a valid signed credential. The SGW/BGD must be using something else as the actual password (probably the JWT).

---

## 12. WHAT'S STILL UNKNOWN / NEXT STEPS

### ✅ Completed
1. **DB Schema Migration Failure** — ✅ **RESOLVED** (happened automatically between installs or was unrelated to current cluster)
2. **RMQ Management UI credentials** — ✅ **RESOLVED** — `admin:admin123` working on both admin (30325) and game (32716) UIs
3. **`send-dune-broadcast`** — ✅ **TESTED AND WORKING** on live production server

### Next Steps
1. **Scale operators back up** — Currently scaled to 0. They need to be restored:
   - `for op in battlegroupoperator databaseoperator serveroperator utilitiesoperator; do sudo kubectl scale deployment -n funcom-operators $op-controller-manager --replicas=1; done`
   - **Risk:** Operators will reconcile ConfigMaps back to defaults, reverting the `auth_backends` change. May need to:
     a. Leave operators at 0 (manual management only)
     b. Or accept that RMQ admin UI access breaks after reconciliation (recreate admin users on each RMQ restart)

2. **Custom broadcast identity** — Currently broadcasts appear as `fls_backend`. Want to change title to "Dune Admin" or similar. Modify the hardcoded values in the script or change the message structure.

3. **Integrate broadcast into dashboard** — Add a broadcast UI to the dashboard admin panel (title/message/duration fields) that calls the script via SSH.

4. **BGD API expansion** — Currently only player endpoints. Check if there are undocumented endpoints or if the dashboard's director.py adds functionality.

5. **Database backup/import** — `battlegroup.sh backup` and `import` commands exist.

6. **`completions` exchange** — RMQ error that may be benign or indicate a missing exchange declaration.

7. **SG Overmap pod** — Check TLS connection issues.

### New Findings (2026-05-22)
8. **Installed tools on VM:** `curl`, `python3`, `py3-pip` added to Alpine VM for easier debugging
9. **TR Binary analysis:** Extracted from `server-text-router.tar` Docker image. Found classes: `RmqHttpTokenAuthApi`, `RmqHttpTokenGenerator`, `ShaTokenGenerator` with `TimeSkew` config. Token validation uses HMAC with the signing key.
10. **Battlegroup Operator behavior:** All 4 operators continuously reconcile ConfigMaps. To make config changes, must scale operators to 0 replicas first, then restore after changes.
11. **World namespace:** `funcom-seabass-sh-b17a5f036d1f7882-ooaeyc` (3rd install). Changes on each install — auto-detect with: `kubectl get pods -A --no-headers | grep mq-game-sts-0 | awk '{print $1}'`
12. **BGD Map Config:** BGD manages 50+ maps/instances including Survival, Story, Challenge Rooms, CB (Combat Block), DLC content, and test gyms
13. **send-dune-broadcast utility:** Found at `F:\Downloads\send-dune-broadcast`. Sends in-game announcements via RMQ `heartbeats` exchange using `rabbitmqctl eval`. Uses hardcoded AuthToken `Nu6VmPWUMvdPMeB7qErr`. See section 6.5 for full analysis.
14. **RMQ admin user persistence:** Admin users created via `rabbitmqctl add_user` are lost when RMQ pods restart. The PV may not be persisting user data, or the StatefulSet may be using a fresh volume each time. Need to investigate PV configuration.
15. **CRITICAL — RMQ TLS config missing on fresh install:** The default RMQ ConfigMaps on a fresh install are **missing TLS configuration**. Game services connect via TLS (`-RMQGameTlsEnabled=true`) but RMQ only listens on plain TCP, causing `{bad_header,<<22,3,1...>>}` errors and immediate connection drops. **Fix:** Add TLS config to both `mq-admin-cm` and `mq-game-cm` ConfigMaps:
```yaml
system.conf: |
  listeners.tcp = none
  listeners.ssl.default = 5672
  ssl_options.cacertfile = /etc/rabbitmq/cacert.pem
  ssl_options.certfile   = /etc/rabbitmq/cert.pem
  ssl_options.keyfile    = /etc/rabbitmq/key.pem
  ssl_options.verify     = verify_none
  ssl_options.fail_if_no_peer_cert = false
  auth_backends.1 = internal
  auth_backends.2 = $(RMQ_AUTH_BACKEND_1)
  # ... rest of auth config
```
16. **Fresh install details (2026-05-22 #2):** VM IP `192.168.0.102`. World namespace: `funcom-seabass-sh-b17a5f036d1f7882-vvgcmr`. All pods running including survival. NodePorts: BGD 30086, RMQ admin 32560, RMQ game 31834.
17. **Fresh install details (2026-05-22 #3):** VM IP `192.168.0.103`. World namespace: `funcom-seabass-sh-b17a5f036d1f7882-ooaeyc`. **CRITICAL ISSUE:** Game servers not starting — DB schema migration failing.
    - **Error:** `Failed to apply schema 1968181-0-shipping` — database operator keeps retrying
    - **Root cause:** DB util pods (`db-dbdepl-util-*`) hang during schema migration. They connect to DB but never complete.
    - **Effect:** BattleGroup stuck in `Stopped` phase, ServerGroup stuck in `Starting`, no game server pods (bgd, sg-overmap, sg-survival, sgw, tr) are created
    - **Server operator logs:** `Cannot execute pod creation since database sh-b17a5f036d1f7882-ooaeyc-db is not ready to receive connections`
    - **DB pod itself is Running** — the issue is specifically with the schema migration util pods
    - **DB password:** `IgNybVaa7xbtBYz7kCvf7LbF` (changes each install)
    - **DB util image:** `seabass-server-db-utils:1968181-0-shipping`
    - **Workaround needed:** Investigate why schema migration hangs. May need to check DB connectivity, schema files, or manually apply schema.

### New Findings (2026-05-22 — Production VPS Session)
18. **Server is a production VPS, not local Hyper-V:** IP `65.21.198.100`, hostname `duneawakening`, Alpine Linux 3.23.4. K3s single-node cluster is fully running with all game servers operational (overmap, survival-1, deepdesert-1, arrakeen, harkovillage, bgd, sgw, tr, fb, db). Schema migration eventually succeeded.
    - **World namespace:** `funcom-seabass-sh-b17a5f036d1f7882-ccdijf` (different from the failed #3 install)
    - **SSH key:** `$env:LOCALAPPDATA\DuneAwakeningServer\sshKey`
    - **⚠️ SCP doesn't work** (no `sftp-server`). Use pipe method with `tr -d '\r'` to strip CRLF.
19. **RMQ ConfigMap auth fix applied:**
    - Operators scaled to 0 (still at 0 as of end of session)
    - Changed both `mq-admin-cm` and `mq-game-cm`: `auth_backends.1 = internal`, `auth_backends.2 = $(RMQ_AUTH_BACKEND_1)`
    - RMQ pods restarted, admin users `admin:admin123` created with full permissions on both instances
    - **RMQ Admin UI:** `http://65.21.198.100:30325` ✅
    - **RMQ Game UI:** `http://65.21.198.100:32716` ✅
    - **Note:** The game ConfigMap also needed the fix applied separately (first run only got admin, not game)
20. **`send-dune-broadcast` tested and confirmed working on live server:**
    - Script copied to `/tmp/send-dune-broadcast` on the VM
    - `python3` was not pre-installed — had to `apk add python3 py3-pip` first
    - Test 1: `--title Notice --message Test --duration 30` → ✅ Success
    - Test 2: `--title "YEY got it working!" --message "How are ya?" --duration 30` → ✅ Success
    - Messages appear in-game as expected with hardcoded `fls_backend` identity
    - The `heartbeats` exchange exists and accepts messages from `rabbitmqctl eval`
21. **No GitHub commits/pushes made — security enforced.**
22. **"Admin Experimental" dashboard tab created:**
    - New nav entry at end of NAV_PAGES in `constants.py`
    - Route `/admin-experimental` added in `main.py`
    - Template `templates/admin_experimental.html` with broadcast form
    - API endpoint `POST /api/admin-experimental/broadcast` in `api.py`
    - `send_global_broadcast()` method added to `AdminService` in `admin.py`
    - Uses base64 encoding to write Erlang script on VM host, then pipes via `cat | kubectl exec -i` into the pod
    - **Note:** The original approach using heredoc failed through paramiko. Final working approach: write erl file on VM host via base64 decode, then `cat file | kubectl exec -i pod -- sh -lc 'cat > /tmp/pod.erl && rabbitmqctl eval "$(cat /tmp/pod.erl)"'`
23. **RMQ Game Exchanges discovered (via RMQ Management API at :32716):**
    - `heartbeats` (direct) — broadcasts
    - `rpc` (direct) — server RPC (no bindings currently)
    - `notifications` (topic) — notifications
    - `chat.faction.1-4` (fanout) — faction chat
    - `chat.guild.*` (fanout) — guild chat
    - `chat.intercept` (topic) — chat intercept
    - `chat.proximity`, `chat.whispers`, `chat.map` (direct) — chat channels
    - `login_grant`, `login_request`, `login_response` (direct) — auth flow
    - `status.*` (fanout) — per-map status (Overmap, Survival_1, DeepDesert_1, SH_Arrakeen, SH_HarkoVillage, CB_*, DLC_*, Story_*)
    - `travel_queue_status` (topic) — travel queue
    - `director_respawned` (fanout) — respawn events
24. **RMQ Admin Exchanges discovered (via RMQ Management API at :30325):**
    - `completions` (direct) — 723 messages published (completion events)
    - `response` (direct) — 64K+ messages published (response routing)
    - `settingsUpdate` (fanout) — 71 messages published (server settings updates)
    - `travel` (topic) — travel messages
    - `travelQueueStatus` (fanout) — 1K+ messages published
    - `grant` (direct) — grant messages
    - `heartbeats` (direct) — 2K+ messages published
    - `rpc` (direct) — RPC messages
    - `director_respawned` (fanout) — respawn events
25. **RMQ Game Queues discovered:**
    - `B17A5F036D1F7882_queue` — host-specific queue
    - `bgdRpc` — BGD RPC queue (1 consumer)
    - `loginRequests` — login requests (1 consumer)
    - `queue.intercept` — intercept queue (1 consumer)
    - `queue.server.*` (5 queues) — server-specific queues (1 consumer each)
26. **BGD API Full Discovery:**
    - `/v0/battlegroup` — **Full battlegroup JSON** with all server/player data (dimension maps, servers, configs, player counts, gameplay settings)
    - `/v0/players` — returns `["B17A5F036D1F7882"]` (FLS IDs)
    - `/v0/players/online` — online FLS IDs
    - `/v0/players/intransit`, `/v0/graceperiod`, `/v0/completion`, `/v0/queued` — player status endpoints
    - `/v0/BattlegroupFetchFlsReportSettings` — FLS report config
    - `/v0/BattlegroupUpdateFlsReportSettings` — POST to update FLS settings
    - `/v0/BattlegroupClearFlsReportOverrides` — POST to clear overrides
    - BGD Web UI at `/` shows: player stats, FLS settings, character transfer settings, per-map server overview with player counts/queue/status, per-server settings (force lock, caps), instance scaling config
    - `/v0/battlegroup` JSON contains: `dimensionMaps[]`, `singleServerMaps[]`, `instancedMaps[]` with per-server `partition`, `ip`, `gamePort`, `numPlayers*`, `status`, `cfg`, `lastServerState` (includes `serverGameplaySettings`: hydration, sandstorm, sandworm, PvP, security zones, mining multiplier, durability, etc.)
27. **PostgreSQL Database Admin Functions discovered (517 total in `dune` schema):**
    - `_add_item_delete_log(in_item_id bigint, in_inventory_id bigint, in_template_id text)`
    - `_add_item_trace_log(in_function_name dune.itemtrackingfunctiontype, in_item_locations dune.inventoryitemlocation[])`
    - `_add_item_trace_log(in_function_name dune.itemtrackingfunctiontype, in_item_id bigint, in_inventory_id bigint, in_template_id text, in_position_index bigint)`
    - `_building_validate_totem_owner_id(in_totem_owner_id bigint)`
    - `_character_transfer_allocate_id(kind dune._charactertransferentrykind, data jsonb)`
    - `_character_transfer_create_data_table()`
    - `_character_transfer_data_filter(id text, removed text[], VARIADIC refs dune._charactertransferdatafilterref[])`
    - `_character_transfer_data_table_load(entries jsonb)`
    - `_character_transfer_data_table_save()`
    - `_character_transfer_ensure_player_is_owner_of_vbt_vehicle(in_vehicle_id bigint[])`
    - `_character_transfer_get_filter(kind dune._charactertransferentrykind)`
    - `_character_transfer_get_patches_checksum()`
    - `_character_transfer_pre_export_validation(in_fls_id text)`
    - `_character_transfer_property_not_exported_is_expected(path text)`
    - `_character_transfer_replace_local_id_with_transfer_id(data text, path text)`
    - `_character_transfer_replace_local_id_with_transfer_id_in_json(data jsonb, path text)`
    - `_character_transfer_replace_transfer_id_with_local_id(data text, path text)`
    - `_character_transfer_replace_transfer_id_with_local_id_in_json(data jsonb, path text)`
    - `_character_transfer_store_in_world_owned_vehicles_into_recovery(in_player_id bigint)`
    - `_character_transfer_top_level_export(in_kind dune._charactertransferentrykind, data jsonb)`
    - `_character_transfer_top_level_import(in_kind dune._charactertransferentrykind, data jsonb, in_id bigint)`
    - `_placeable_validate_totem_owner_id(in_totem_owner_id bigint)`
    - `_user_data_encryption_initially_encrypt_existing_data()`
    - `_user_data_encryption_setup_enabled(key_hash bytea)`
    - `_user_data_encryption_setup_tainted()`
    - `accept_guild_invite(in_invite_id bigint, in_role_id smallint, in_max_guild_count_per_player integer, in_max_members_per_guild integer, in_neutral_faction_id smallint)`
    - `accept_party_invite(in_invite_id bigint, in_platform_session_id text, in_max_party_member_count integer)`
    - `add_actor_audit(in_id bigint, in_class text)`
    - `add_event_log_data(in_game_event_owner bigint, in_universe_time bigint, in_map_name text, in_partition_id bigint, in_event_type integer, in_x_location double precisio...)`
    - `add_event_log_data_batched(in_data dune.eventlogbulkentrydata[])`
    - `add_guild_invite(in_player_id bigint, in_guild_id bigint, in_sender_player_id bigint, in_invite_sent_timespan bigint, in_max_guild_invites_per_guild integer)`
    - `add_guild_member(in_player_id bigint, in_guild_id bigint, in_role_id smallint, in_max_guild_count_per_player integer, in_max_members_per_guild integer, in_neutral_f...)`
    - `add_landclaim_segment(in_totem_id bigint, in_grid_location_x bigint, in_grid_location_y bigint)`
    - `add_map_areas_surveyed_items(in_account_id bigint, in_area_id smallint, in_survey_point_marker_id bigint, in_surveyed_items_target jsonb, in_surveyed_items_progress jsonb, in_m...)`
    - `add_map_areas_time_discovered(in_account_id bigint, in_area_id smallint, in_time_discovered timestamp without time zone, in_map_name text)`
    - `add_map_areas_time_first_entered(in_account_id bigint, in_area_id smallint, in_time_first_entered timestamp without time zone, in_map_name text)`
    - `add_partition_unique(in_map text, in_definition jsonb, in_dimension bigint, in_label text)`
    - `add_party_invite(in_sender_player_id bigint, in_sender_platform_name text, in_sender_platform_session_id text, in_player_id bigint, in_max_party_member_count intege...)`
    - `adjust_player_virtual_currency_balance(in_controller_id bigint, in_currency_id smallint, in_delta bigint)`
    - `admin_get_character_details(in_account_id bigint)`
    - `admin_get_character_ids(in_search_term text)`
    - `admin_get_inventory_details(in_account_id bigint)`
    - `admin_get_journey_details(in_player_id text, in_story_node_id text)`
    - `admin_get_mnemonic_recall_details(in_account_id bigint)`
    - `admin_get_partitions()`
    - `admin_move_offline_player(in_fls_id text, in_target_partition_name text, in_target_location dune.vector)`
    - `admin_move_offline_player_to_partition(in_fls_id text, in_target_partition_id bigint, in_target_location dune.vector)`
    - `admin_read_player_tags(in_account_id bigint)`
    - `advance_items_id_sequencer(count bigint)`
    - `assign_actor_id(in_class text)`
    - `base_backup_delete(in_base_backup_id bigint)`
    - `base_backup_find_totems_from_player_owner(in_player_id bigint)`
    - `base_backup_finish_placing(in_base_backup_id bigint)`
    - `base_backup_get_actors_to_spawn(in_base_backup_id bigint)`
    - `base_backup_get_available_backups(in_player_id bigint)`
    - `base_backup_get_buildable_data(in_base_backup_id bigint)`
    - `base_backup_get_data(in_base_backup_id bigint)`
    - `base_backup_get_totem_data(in_base_backup_id bigint)`
    - `base_backup_get_totem_data_from_totem_id(in_totem_id bigint)`
    - `base_backup_get_totem_id(backup_id bigint)`
    - `base_backup_recycle(in_base_backup_id bigint, in_target_inventory_id bigint)`
    - `base_backup_save(in_player_actor_id bigint, in_base_backup_name text, in_building_pieces_to_link dune.basebackupbuildingitem[], in_placeables_to_link bigint[], in_p...)`
    - `base_backup_save_all_totems_from_player_owner(in_player_id bigint)`
    - `base_backup_save_from_totem(in_player_id bigint, totem_id bigint)`
    - `break_guild_allegiance(in_guild_id bigint, in_neutral_faction_id smallint)`
    - `can_takeover_account(in_user_id text)`
    - `change_player_faction(in_player_id bigint, in_faction_id smallint, neutral_faction_id smallint, in_utc_time_faction_change timestamp without time zone)`
    - `character_migration_export(in_fls_id text)`
    - `character_migration_import(in_data jsonb, in_fls_id text, in_character_name text)`
    - `character_transfer_export(in_fls_id text)`
    - `character_transfer_get_unsaved_counts(in_fls_id text)`
    - `character_transfer_import(in_data jsonb, in_fls_id text, in_character_name text)`
    - `clean_expired_party_invites(in_invite_expire_seconds integer)`
    - `clean_guild_invites_with_incompatible_faction(in_player_id bigint, in_faction_id smallint, neutral_faction_id smallint)`
    - `clean_old_guild_invites(in_cutoff_timespan bigint)`
    - `clean_stock_for_player(in_player_id bigint)`
    - `clean_stock_for_vendors(in_vendor_ids text[])`
    - `clean_vendors_older_than_timestamp(in_reference_timestamp bigint)`
    - `cleanup_account_log_and_orphaned_actors()`
    - `cleanup_accounts_marked_for_deletion_in_fls(in_account_ids text[])`
    - `cleanup_orphaned_entities()`
    - `clear_map_areas_data_for_player(in_id bigint)`
    - `complete_journey_nodes_where_prerequisite_nodes_are_complete(story_ids_to_complete text[], prerequisite_completed_story_ids text[])`
    - `complete_journey_story_nodes_for_player(in_player_id text, in_story_node_ids text[])`
    - `corilis_cleanup_map(in_server_info dune.serverinfo, in_map_info dune.coriolismapinfo)`
    - `coriolis_cleanup_farm(in_server_info dune.serverinfo, in_map_info dune.coriolismapinfo)`
    - `coriolis_cleanup_partition(in_server_info dune.serverinfo, in_map_info dune.coriolismapinfo)`
    - `coriolis_update_seed(in_server_info dune.serverinfo, in_new_coriolis_seed integer, in_map_info dune.coriolismapinfo)`
    - `create_event_log_partition()`
    - `create_guild(in_player_id bigint, in_neutral_faction smallint, in_guild_name text, in_guild_desc text, in_max_guild_count_per_player integer, OUT out_guild_id b...)`
    - `create_or_update_tutorial_entry(in_player_id bigint, in_tutorial_id smallint, in_tutorial_state smallint)`
    - `create_server_player_access_codes(in_account_id bigint, in_access_code integer, in_access_code_type integer, in_is_resettable boolean)`
    - `create_sinkchart_for_map_area_id(in_item_id bigint, in_creator_id bigint, in_map_name text, in_area_id smallint)`
    - `debug_add_test_table_data(in_entry text)`
    - `debug_collect_test_table_data()`
    - `debug_echo(in_text text, in_notices text[])`
    - `debug_get_coriolis_seeds()`
    - `debug_raise_exception(in_exception text, in_notices text[])`
    - `debug_raise_notices(in_notices text[])`
    - `debug_reset_test_table()`
    - `debug_set_farm_seed(in_new_coriolis_seed integer)`
    - `debug_set_map_seed(in_map text, in_new_coriolis_seed integer)`
    - `debug_set_partition_seed(in_partition_id bigint, in_new_coriolis_seed integer)`
    - `decrypt_user_data(in_encrypted_data bytea)`
    - `delete_account(in_user_id text, in_reason text)`
    - `delete_actor_states_travel(in_actor_id bigint)`
    - `delete_actors(in_ids bigint[])`
    - `delete_actors_and_respawns_on_server(in_server_info dune.serverinfo, in_vehicle_classes_spawned_on_map text[], in_allow_vehicle_recovery boolean)`
    - `delete_all_dungeon_completions(in_dungeon_id text)`
    - `delete_all_dungeon_completions_by_player(in_dungeon_id text, in_player_id bigint, in_keep_completion_for_other_players boolean)`
    - `delete_all_dungeon_completions_for_all_dungeons_by_player(in_player_id bigint, in_keep_completion_for_other_players boolean)`
    - `delete_all_inactive_farms()`
    - `delete_all_journey_story_nodes(in_account_id bigint)`
    - `delete_all_static_shifting_sand()`
    - `delete_all_tutorial_entries(in_player_id bigint)`
    - `delete_building_blueprint(in_building_item_id bigint)`
    - `delete_character(in_actor_id bigint)`
    - `delete_crafted_map(in_item_id bigint)`
    - `delete_dialogue_data(in_player_controller_id bigint)`
    - `delete_inventory_item(in_item_id bigint, in_count bigint)`
    - `delete_item(in_id bigint)`
    - `delete_items(in_ids bigint[])`
    - `delete_items_from_actor(in_actor_id bigint)`
    - `delete_journey_story_ids(story_ids text[])`
    - `delete_journey_story_node(in_account_id bigint, in_story_node_id text)`
    - `delete_journey_story_nodes_for_group_for_player(in_account_id bigint, in_reset_group dune.journeystoryresetgroup)`
    - `delete_journey_story_nodes_for_player(in_player_id text, in_story_node_ids text[])`
    - `delete_journey_story_nodes_for_player_account(in_account_id bigint, in_story_node_ids text[])`
    - `delete_map_markers(in_dimension_index integer, in_map_name text, in_player_marker_data dune.deleteplayermarkerdata[])`
    - `delete_markers_by_id(in_marker_ids integer[])`
    - `delete_markers_by_static_location_key(p_location_key text)`
    - `delete_markers_for_all_players(in_marker_types_to_keep text[], in_map text)`
    - `delete_markers_return_actor_ids(in_dimension_index integer, in_map_name text, in_marker_ids integer[])`
    - `delete_mnemonic_recall_lesson(in_account_id bigint, in_lesson_id text)`
    - `delete_mnemonic_recall_lesson_all(in_account_id bigint)`
    - `delete_server_player_access_codes(in_account_id bigint, in_access_code integer, in_access_code_type integer)`
    - `delete_spawner(in_map text, in_name text, in_dimension_index integer)`
    - `delete_static_location_markers(p_location_keys text[])`
    - `delete_world_partition_by_map_id(in_map_id text)`
    - `demote_guild_member(in_guild_id bigint, in_player_id bigint, in_new_role smallint)`
    - `determine_partition_label(in_map text, in_dimension_index integer, in_label text, in_allow_overwrite boolean, in_partition_id bigint)`
    - `determine_partition_label_trigger()`
    - `disband_guild(in_guild_id bigint)`
    - `disband_party(in_party_id bigint)`
    - `downgrade_map_name(in_map_name text)`
    - `drain_item_tracking_data()`
    - `dune_exchange_add_sell_order(in_exchange_id bigint, in_access_point_id bigint, in_owner_id bigint, in_max_orders_per_player integer, in_expiration_time bigint, in_item_id bigin...)`
    - `dune_exchange_cancel_order(in_order_id bigint, in_purge_time bigint, in_completion_type integer)`
    - `dune_exchange_expire_orders(in_exchange_id bigint, in_current_time bigint, in_purge_time bigint, in_expired_completion_type integer)`
    - `dune_exchange_fulfill_sell_order(in_exchange_id bigint, in_max_orders_per_player integer, in_purchased_completion_type integer, in_sold_completion_type integer, in_instigator_id bi...)`
    - `dune_exchange_get_item_price_stats(in_template_ids text[])`
    - `dune_exchange_get_user_id(in_owner_id bigint)`
    - `dune_exchange_modify_user_solari_balance(in_controller_id bigint, in_solari_delta bigint)`
    - `dune_exchange_purge_completed_orders(in_exchange_id bigint, in_current_time bigint)`
    - `dune_exchange_query_storage_item(in_order_id bigint)`
    - `dune_exchange_query_storage_items(in_exchange_id bigint, in_owner_id bigint)`
    - `dune_exchange_relist_order(in_order_id bigint, in_expiration_time bigint, in_item_price bigint, in_wear_normalized_item_price bigint, in_solari_cost bigint)`
    - `dune_exchange_retrieve_solari_balance(in_owner_id bigint)`
    - `dune_exchange_retrieve_solaris_from_item(in_controller_id bigint, in_order_id bigint)`
    - `dune_exchange_retrieve_storage_item(in_exchange_id bigint, in_order_id bigint, in_dst_inventory_id bigint, in_dst_index bigint, in_count bigint)`
    - `dune_exchange_update_recurring_sell_order(in_exchange_id bigint, in_expiration_time bigint, in_access_point_id bigint, in_owner_id bigint, in_item_id bigint, in_increment bigint, in_max_cou...)`
    - `dune_get_account_id_by_user(in_user text)`
    - `edit_guild_description(in_guild_id bigint, in_guild_desc text)`
    - `encrypt_user_data(in_data text)`
    - `fetch_resourcefield_state(in_map text, in_dimension_index integer, in_field_kind_id smallint)`
    - `fetch_server_spice_field_manifest(in_server_id text)`
    - `fetch_spicefie_id_types_with_global_info(in_map_name text, in_dimension_index integer)`
    - `find_actor_by_id(in_id bigint)`
    - `fix_broken_harkonnen_players_due_to_fooled_thufir()`
    - `flag_player_as_cheater(in_account_id bigint, in_cheat_type dune.cheat_type_enum)`
    - `gather_ownerless_actors_on_server(in_server_info dune.serverinfo)`
    - `gather_player_linked_actors(in_player_pawn_id bigint)`
    - `gather_removed_accounts_that_left_orphaned_actors_on_server(in_server_info dune.serverinfo)`
    - `get_account_actor_ids(in_account_id bigint)`
    - `get_active_servers_for_gateway()`
    - `get_actor_server_info(in_id bigint)`
    - `get_actors_location_data_with_permission(in_actor_ids bigint[])`
    - `get_all_demo_players()`
    - `get_all_faction_members()`
    - `get_all_guild_members()`
    - `get_all_online_or_recently_disconnected_player_online_state()`
    - `get_all_parties()`
    - `get_all_party_invites()`
    - `get_all_party_members()`
    - `get_all_player_character_home_dimensions()`
    - `get_all_player_in_guild_online_state(in_guild_id bigint)`
    - `get_all_player_travel_states()`
    - `get_all_tutorial_entries(in_player_id bigint)`
    - `get_all_unresolved_character_imports()`
    - `get_applied_patches()`
    - `get_battlegroup_close_date()`
    - `get_best_dungeon_completion(in_dungeon_id text)`
    - `get_best_dungeons_completions_for_player(in_player_id bigint)`
    - `get_building_blueprint_copy_data(in_building_blueprint_id bigint)`
    - `get_building_favorites(in_account_id bigint)`
    - `get_building_id(in_actor_id bigint, in_class text)`
    - `get_character_import_state(in_fls_id text)`
    - `get_character_transfer_related_items(in_fls_id text)`
    - `get_consumed_lore_pickups(in_actor_id bigint, in_use_temporary boolean)`
    - `get_controller_id_from_platform_id(in_platform_id text)`
    - `get_dune_exchange_accesspoint_id(in_exchange_id bigint, in_name text)`
    - `get_dune_exchange_data(in_exchange_id bigint, in_controller_id bigint)`
    - `get_dune_exchange_id(in_name text)`
    - `get_dune_exchange_used_order_slots(in_controller_id bigint)`
    - `get_exchange_inventory_id(in_exchange_id bigint)`
    - `get_exchange_orders_by_mask(in_mask integer, in_depth smallint)`
    - `get_exchange_sell_orders(in_id bigint, in_exchange_id bigint, in_min_item_price bigint, in_max_item_price bigint, in_template_id text, in_mask integer, in_depth smallint)`
    - `get_exchange_sell_orders_by_item_type(in_exchange_id bigint, in_template_ids text[])`
    - `get_exchange_sell_orders_by_owner(in_exchange_id bigint, in_owner_id bigint)`
    - `get_farm_state()`
    - `get_friends_search(in_player_name text, in_max_players_count integer)`
    - `get_guild_data(in_guild_id bigint)`
    - `get_guild_data_for_player(in_player_id bigint)`
    - `get_guild_for_player(in_player_id bigint)`
    - `get_guild_invites(in_guild_id bigint)`
    - `get_guild_members(in_guild_id bigint)`
    - `get_inventory_data(in_inventory_id bigint)`
    - `get_inventory_id(in_actor_id bigint, in_component_name_hash integer)`
    - `get_items_to_remove(items_to_remove text[])`
    - `get_landclaim_segments(in_totem_id bigint)`
    - `get_learned_building_sets(in_account_id bigint)`
    - `get_learned_new_buildable_pieces(in_account_id bigint)`
    - `get_login_journey_nodes(in_account_id bigint)`
    - `get_login_journey_nodes_cooldown(in_account_id bigint)`
    - `get_mnemonic_recall_lessons(in_account_id bigint)`
    - `get_online_player_controller_ids(in_map text)`
    - `get_online_player_controller_ids_on_farm()`
    - `get_partition_presets()`
    - `get_partitions(in_map text)`
    - `get_party_members(in_party_id bigint)`
    - `get_permission_actors_for_server(in_server_info dune.serverinfo)`
    - `get_permission_for_actor(in_actor_id bigint)`
    - `get_permission_for_actors(in_actor_id bigint[])`
    - `get_permission_for_player_actors(in_player_id bigint, in_min_rank smallint)`
    - `get_placeable_id(in_actor_id bigint, in_class text, in_building_type text)`
    - `get_player_access_codes(in_account_id bigint)`
    - `get_player_current_faction_reputation(in_actor_id bigint, OUT out_faction_id smallint, OUT out_reputation_amount integer)`
    - `get_player_faction(in_player_id bigint, in_neutral_faction_id smallint)`
    - `get_player_faction_name(in_actor_id bigint, OUT player_faction_name text, OUT utc_time_faction_change timestamp without time zone)`
    - `get_player_guild_invites(in_player_id bigint)`
    - `get_player_ids_online_state(in_player_ids bigint[])`
    - `get_player_infos_for_actor_ids(in_actor_ids bigint[])`
    - `get_player_infos_for_character_names(in_character_names text[])`
    - `get_player_infos_for_fls_ids(in_fls_ids text[])`
    - `get_player_infos_for_funcom_ids(in_funcom_ids text[])`
    - `get_player_online_state_within_grace_period_for_each_server()`
    - `get_player_owned_vehicles_data(in_player_id bigint, in_account_id bigint)`
    - `get_player_partition_id(in_fls_id text)`
    - `get_player_pawn(in_account_id bigint)`
    - `get_player_virtual_currency_balances(in_controller_id bigint)`
    - `get_players_demo_data(in_controller_ids bigint[])`
    - `get_recipes_to_remove(recipes_to_remove text[])`
    - `get_registered_spawned_actor(in_spawner_id bigint)`
    - `get_respawn_locations(in_account_id bigint)`
    - `get_schema_version()`
    - `get_solaris_id()`
    - `get_spawner_id(in_map text, in_name text, in_dimension_index integer)`
    - `get_stored_user_data_encryption_key_hash()`
    - `get_stored_user_data_encryption_status()`
    - `get_stored_user_data_encryption_taint_xmax()`
    - `get_sub_inventory_id(in_owner_item_id bigint)`
    - `get_traveling_actor_id_and_types(in_actor_id bigint)`
    - `get_traveling_actor_ids(in_actor_id bigint, in_max_recursion_level integer)`
    - `get_traveling_actors_fls_ids(in_actor_id bigint)`
    - `get_traveling_non_player_actor_ids(in_actor_id bigint)`
    - `get_unbacked_up_vehicle_ids_for_account(in_account_id bigint)`
    - `get_universe_time()`
    - `get_unsaved_base_totem_ids_for_account(in_account_id bigint)`
    - `get_vehicle_id(in_actor_id bigint, in_class text)`
    - `get_vehicle_module_inventory_id(in_vehicle_module_id bigint, in_vehicle_module_inventory_type integer)`
    - `guild_handle_actor_delete(in_player_id bigint)`
    - `guilds_get_exclusive_operation_lock()`
    - `handle_player_faction_guild_effects(in_player_id bigint, in_faction_id smallint, neutral_faction_id smallint)`
    - `igwo_delete_world_partitions(in_partition_ids bigint[])`
    - `igwo_get_partition_id_seq_last_value()`
    - `igwo_get_partition_ids()`
    - `igwo_get_partitions()`
    - `igwo_get_server_details()`
    - `igwo_insert_world_partition(in_partition_id bigint, in_map text, in_partition_definition jsonb, in_dimension_index integer, in_partition_label text)`
    - `igwo_next_partition_id_seq()`
    - `igwo_notify_world_partition_update()`
    - `igwo_restart_partition_id_seq(in_restart_with bigint)`
    - `igwo_update_world_partition(in_map text, in_partition_definition jsonb, in_partition_id bigint, in_dimension_index integer, in_label text)`
    - `init_event_log(in_partition_id bigint)`
    - `initialize_partitions_basic_battlegroup()`
    - `initialize_partitions_basic_survival_1()`
    - `initialize_partitions_development_battlegroup()`
    - `initialize_partitions_editor_default_1x1()`
    - `initialize_partitions_full_battlegroup()`
    - `initialize_partitions_igw_test_small_2x1()`
    - `initialize_partitions_igw_test_small_2x2()`
    - `initialize_partitions_igw_training()`
    - `initialize_specialization_keystones(in_keystones text[])`
    - `initialize_world_partition(in_map_name text, in_num_servers integer, in_dimension_index integer)`
    - `interact_get_vendor_items_bought_from_player(in_vendor_id text, in_player_id bigint, in_current_cycle_start_timestamp bigint)`
    - `internal_add_party_member(in_invite_id bigint, in_party_id bigint, in_player_id bigint, in_platform_session_id text, in_platform_name text, in_max_party_member_count integer)`
    - `internal_create_party(in_invite_id bigint, in_leader_id bigint, in_leader_platform_session_id text, in_leader_platform_name text, in_member_id bigint, in_platform_sessio...)`
    - `is_player_guild_admin(in_player_id bigint, in_guild_id bigint)`
    - `is_player_offline(in_fls_id text)`
    - `is_player_party_leader(in_player_id bigint, in_party_id bigint)`
    - `join_platform_session_party(in_leader_platform_id text, in_player_platform_id text, in_platform_session_id text, in_platform_name text, in_max_party_member_count integer)`
    - `journey_story_node_cooldown_add(in_account_id bigint, in_story_node_id text, in_time_to_expire timestamp without time zone)`
    - `journey_story_node_cooldown_delete_expired(in_time_to_check timestamp without time zone)`
    - `landsraad_cast_vote(in_term_id bigint, in_player_id bigint, in_decree_name text)`
    - `landsraad_change_term_end_time(end_term_id bigint, new_end_time timestamp without time zone, in_test_term boolean)`
    - `landsraad_check_task_completion()`
    - `landsraad_check_term_won()`
    - `landsraad_collect_task_telemetry_for_faction(in_term_id bigint, in_faction_name text)`
    - `landsraad_collect_term_telemetry(in_term_id bigint, in_faction_names text[])`
    - `landsraad_collect_term_telemetry_for_faction(in_term_id bigint, in_faction_name text)`
    - `landsraad_collect_vote_telemetry(in_term_id bigint, in_winning_faction_id integer)`
    - `landsraad_collect_votes(in_term_id bigint)`
    - `landsraad_determine_winner(in_term_id bigint)`
    - `landsraad_force_end_term(end_term_id bigint)`
    - `landsraad_has_term_of_task_ended(in_task_id bigint)`
    - `landsraad_initialize_system(number_of_weeks_term_retention integer, number_of_nominated_decrees integer, in_end_time timestamp without time zone, in_test_term boolean, faction...)`
    - `landsraad_initialize_term(number_of_weeks_term_retention integer, number_of_nominated_decrees integer, in_end_time timestamp without time zone, in_test_term boolean, tasks d...)`
    - `landsraad_insert_task_progress(in_term_id bigint, in_player_id bigint, in_guild_id bigint, in_house_name text, in_faction_progress integer, in_guild_progress real, in_player_prog...)`
    - `landsraad_insert_task_progress_batched(in_term_id bigint, in_task_progress dune.landsraadtaskprogress[])`
    - `landsraad_insert_task_progress_faction(in_term_id bigint, in_faction_name text, in_house_name text, in_faction_progress integer, in_guild_progress real, in_player_progress real)`
    - `landsraad_insert_task_progress_random(in_term_id bigint, in_faction_names text[], in_num_rows integer)`
    - `landsraad_load_current_rotation(in_term_id bigint)`
    - `landsraad_load_current_term()`
    - `landsraad_load_guild_contribution(in_term_id bigint, in_guild_id bigint, in_faction_id bigint)`
    - `landsraad_load_guild_contributions(in_term_id bigint, in_num_guilds integer, in_faction_names text[])`
    - `landsraad_load_guild_vote(in_term_id bigint, in_player_id bigint)`
    - `landsraad_load_house_rewards(in_player_id bigint)`
    - `landsraad_load_player_contributions(in_term_id bigint, in_player_ids bigint[])`
    - `landsraad_load_task_faction_progress(in_term_id bigint)`
    - `landsraad_load_task_faction_reveal_state(in_term_id bigint)`
    - `landsraad_load_term_progress(in_term_id bigint, in_num_guilds integer, in_faction_names text[], in_player_ids bigint[])`
    - `landsraad_notify_house_rewards_changed()`
    - `landsraad_perform_daily_task_reveal(in_term_id bigint, in_faction_names text[], in_house_names_to_reveal text[], in_reveal_day integer)`
    - `landsraad_process_house_rewards()`
    - `landsraad_process_task_progress(max_rows integer)`
    - `landsraad_task_has_been_completed(in_task_id bigint)`
    - `landsraad_update_task_faction_reveal_state(in_term_id bigint, in_task_board_index integer, faction_name text, reveal_state boolean)`
    - `landsraad_withdraw_house_reward(in_player_id bigint, in_house_rewards dune.landsraadplayerhousereward[])`
    - `load_actors(in_actor_ids bigint[], in_actor_state dune.actorstate)`
    - `load_backup_vehicle(in_account_id bigint)`
    - `load_building(in_building_id bigint)`
    - `load_communinet_player_data(in_account_id bigint)`
    - `load_dialogue_data(in_player_controller_id bigint, OUT met_npcs text[], OUT taken_nodes integer[])`
    - `load_dimension_index(in_map text, in_partition_id bigint)`
    - `load_events_log_data_from_player(in_actor_id bigint, in_limit_entries_num integer)`
    - `load_full_actors(in_ids bigint[])`
    - `load_item(in_item_id bigint)`
    - `load_items(in_inventory_id bigint)`
    - `load_map_areas_entries(in_account_id bigint, in_map_name text)`
    - `load_markers(in_player_id bigint, in_dimension_id integer, in_map_name text)`
    - `load_partition_definition_map()`
    - `load_placeable(in_placeable_id bigint)`
    - `load_recovered_vehicles(in_account_id bigint, in_restore_time_limit integer)`
    - `load_static_encounter_name(in_map_name text, in_package_name text, in_actor_name text)`
    - `load_takeoverable_user_ids()`
    - `load_totem(in_id bigint)`
    - `load_travel_return_info(in_player_controller_id bigint)`
    - `load_travel_to_player_info(in_player_controller_id bigint)`
    - `load_vehicle_modules(in_vehicle_id bigint)`
    - `load_world_partition(in_map_name text, in_server_id text, in_desired_dimension_index bigint, in_desired_partition_id bigint)`
    - `log_cheating(in_fls_id text, in_cheat_type dune.cheat_type_enum, in_event_time timestamp with time zone)`
    - `log_event_solaris(in_function_oid oid, in_message dune.logmessagetype, in_controller_id bigint, in_solaris_balance bigint, in_solaris_delta bigint)`
    - `login_account(in_user_id text, in_funcom_id text, in_platform_id text, in_platform_name text, in_minimum_returning_player_time_seconds integer, in_character_name...)`
    - `mark_server_dead(in_server_id text)`
    - `merge_inventory_items(in_item_id bigint, in_dst_inventory_id bigint, in_dst_index bigint, in_count bigint)`
    - `merge_or_move_inventory_item(in_item_id bigint, in_dst_inventory_id bigint, in_dst_index bigint, in_count bigint)`
    - `migrate_character(in_account_id bigint, home_dimension integer, max_solaris_allowed bigint)`
    - `migrate_clamp_max_allow_solaris(in_pawn_id bigint, max_solaris_allowed bigint)`
    - `move_inventory_item(in_item_id bigint, in_dst_inventory_id bigint, in_dst_index bigint, in_count bigint)`
    - `overmap_delete_player_survival_data(in_player_id bigint)`
    - `overmap_load_player_survival_data(in_player_id bigint)`
    - `overmap_save_player_survival_data(in_player_id bigint, in_vehicle_id bigint, in_has_polar_psu boolean, in_overmap_location dune.vector)`
    - `ownership_handle_actor_delete(in_player_id bigint)`
    - `parties_get_exclusive_operation_lock()`
    - `perform_notify_on_character_delete(in_user_id text)`
    - `permission_actor_create_or_update_base_marker(in_actor_id bigint, in_player_id bigint, in_rank smallint)`
    - `permission_actor_destroy(in_actor_id bigint)`
    - `permission_actor_register(in_entry dune.actorpermissionentry, in_owner_rank dune.actorpermissionrankdata)`
    - `permission_actor_takeover(in_entry dune.actorpermissionentry, in_owner_rank dune.actorpermissionrankdata)`
    - `permission_actor_update_marker_location(in_actor_id bigint, in_location_x real, in_location_y real, in_location_z real)`
    - `permission_remove_player_rank(in_actor_id bigint, in_player_id bigint)`
    - `permission_set_access_level(in_actor_id bigint, in_access_level smallint)`
    - `permission_set_name(in_actor_id bigint, in_name text)`
    - `permission_set_player_rank(in_actor_id bigint, in_player_id bigint, in_rank smallint, in_map_id text)`
    - `player_purchased_item_from_vendor(in_vendor_id text, in_player_id bigint, in_template_id text, in_amount_bought integer)`
    - `player_state_update(in_data dune.playerstateupdatedata[])`
    - `pledge_guild_allegiance(in_guild_id bigint, in_guild_leader_player_id bigint, in_neutral_faction_id smallint)`
    - `produce_spicefield_manifest(in_map_name text, in_dimension_index integer)`
    - `promote_guild_member(in_guild_id bigint, in_player_id bigint, in_new_role smallint)`
    - `promote_new_party_leader(in_party_id bigint)`
    - `promote_party_leader_to(in_party_id bigint, in_player_id bigint)`
    - `purchase_specialization_keystone(in_player_id bigint, in_keystone text)`
    - `record_deactivated_spice_field(in_server_id text, in_spicefield_type_id integer)`
    - `record_dungeon_completion(in_dungeon_id text, in_difficulty integer, in_duration_ms integer, players_ids bigint[])`
    - `record_logoff_persistence_end_time(in_player_pawn_id bigint, in_logoff_persistence_end_time timestamp without time zone)`
    - `record_static_shifting_sand(in_id text, in_alpha double precision, in_x double precision, in_y double precision, in_last_modified_time bigint)`
    - `record_unreadied_spice_fields(in_server_id text, in_spicefield_type_id integer, in_num_unreadied integer)`
    - `register_lore_pickup(in_lore_pickup_ids text[])`
    - `register_new_factions(factions text[])`
    - `register_new_tutorials(tutorials text[])`
    - `register_per_player_lore_pickup(in_lore_pickup_ids text[], in_use_temporary boolean)`
    - `register_spawned_actor(in_spawner_id bigint, in_actor_id bigint)`
    - `register_spice_field_server_resources(in_server_id text, in_spicefield_type_ids integer[], in_inactive_fields_of_types integer[])`
    - `register_temporary_lore_pickup(in_lore_pickup_ids text[])`
    - `reject_guild_invite(in_invite_id bigint)`
    - `remove_aborted_authority_transfer_actors(in_partition_id bigint)`
    - `remove_character_transfer_state(in_fls_id text)`
    - `remove_communinet_player_channel(in_account_id bigint, in_channel_name text)`
    - `remove_guild_members(in_player_ids bigint[], in_guild_id bigint, in_remove_reason smallint)`
    - `remove_items(items_to_remove text[])`
    - `remove_items_and_recipes(items_to_remove text[], recipes_to_remove text[])`
    - `remove_items_or_recipes_from_fgl_entities(item_or_recipes text[])`
    - `remove_members_offline_for(in_interval_seconds integer)`
    - `remove_party_invite(in_invite_id bigint, in_remove_reason smallint)`
    - `remove_party_member(in_player_id bigint, in_remove_reason smallint)`
    - `remove_recipes_from_actor_properties(recipes_to_remove text[])`
    - `remove_resourcefield_states(in_map text, in_dimension_index integer, in_field_ids bigint[])`
    - `request_spawn_spice_field(in_server_id text, in_spicefield_type_id integer)`
    - `reset_all_players_from_server_ids_grace_period_and_logoff_timer(in_server_id text, in_reset_time timestamp without time zone)`
    - `reset_global_spice_field_state(in_map_name text, in_dimension_index integer)`
    - `reset_journey_story_nodes_for_player(in_player_id text, in_story_node_ids text[])`
    - `reset_server_all_player_access_codes(in_account_id bigint)`
    - `reset_specialization_keystones(in_player_id bigint)`
    - `reset_specialization_tracks(in_player_id bigint)`
    - `restore_backup_vehicle(in_account_id bigint, in_server_info dune.serverinfo, in_transform dune.transform)`
    - `restore_recovered_vehicle(in_account_id bigint, in_vehicle_id bigint, in_server_info dune.serverinfo, in_transform dune.transform, in_restore_time_limit integer)`
    - `retrieve_all_static_shifting_sand()`
    - `returning_player_award_given(in_account_id bigint)`
    - `reveal_journey_story_nodes_for_player(in_player_id text, in_story_node_ids text[])`
    - `save_aborted_authority_transfer_actors(in_actor_ids bigint[], in_partition_id bigint)`
    - `save_actor_dislocation(in_actor_id bigint, in_current_server_info dune.serverinfo, in_target_location dune.vector, in_target_dimension_index integer)`
    - `save_actors(in_server_info dune.serverinfo, in_actors dune.actordescription[], in_actor_state dune.actorstate)`
    - `save_building(in_building_id bigint, in_data dune.buildingsavedata)`
    - `save_building_blueprint_copy(in_building_item_id bigint, in_building_blueprint_id bigint, in_building_blueprint_building_data dune.buildingblueprintpiecesaveitemcontainer[], in...)`
    - `save_demo_account_time(in_fls_id text, in_demo_playtime_seconds integer)`
    - `save_dialogue_data(in_player_controller_id bigint, in_met_npcs text[], in_taken_nodes integer[])`
    - `save_item(in_item dune.inventoryitem)`
    - `save_journey_story_node(in_account_id bigint, in_story_node_id text, in_override_reward_block boolean, in_has_pending_reward boolean, in_complete_condition_state jsonb, in...)`
    - `save_journey_story_nodes(in_account_id bigint, in_journey_data dune.savejourneydata[])`
    - `save_login_target_dimension(in_fls_id text, in_login_target_dimension_index integer)`
    - `save_markers(in_player_marker_data dune.saveplayermarkerdata[], in_marker_data dune.savemarkerdata[])`
    - `save_mnemonic_recall_lesson(in_account_id bigint, in_lesson_id text, in_lesson_state bigint, in_lesson_progress integer, in_is_new boolean)`
    - `save_placeable(in_placeable_id bigint, in_data dune.placeablesavedata)`
    - `save_player(in_player dune.playerdescription)`
    - `save_player_pawn(in_pawn dune.actordescription, in_server_info dune.serverinfo, in_life_state dune.playerlifestate)`
    - `save_static_encounter_name(in_map_name text, in_package_name text, in_actor_name text, in_encounter_name text)`
    - `save_static_encounter_waiting_for_reset(in_map_name text, in_package_name text, in_actor_name text, in_waiting_for_reset boolean)`
    - `save_totem(in_id bigint, in_data dune.totemsavedata)`
    - `save_tracked_journey_cards(in_player_id bigint, in_tracked_journey_card text, in_tracked_landsraad_card text)`
    - `save_travel_return_info(in_player_controller_id bigint, in_map text, in_transform dune.transform)`
    - `save_vehicle_modules(in_add_list dune.vehiclemodule[], in_delete_list bigint[], in_stat_update dune.itemstatupdate[])`
    - `save_world_partition(in_map_name text, in_server_id text, in_dimension_index bigint, in_partition_definition jsonb, in_blocked boolean, in_label text)`
    - `server_info_match(in_actor dune.actors, in_server_info dune.serverinfo)`
    - `set_account_as_takeoverable(in_user_id text, in_new_user_id text)`
    - `set_all_inactive_players_in_farm_offline()`
    - `set_battlegroup_close_date(in_close_date timestamp without time zone)`
    - `set_character_import_state(in_fls_id text, in_state dune.transferimportstate)`
    - `set_character_name(in_account_id bigint, in_name text)`
    - `set_demo_state(in_user_id text, in_demo_state dune.demostate)`
    - `set_item_tracking_enabled(in_enabled boolean)`
    - `set_player_faction_reputation(in_actor_id bigint, in_faction_id smallint, in_reputation_amount integer)`
    - `set_players_from_server_ids_offline(in_server_ids text[])`
    - `set_specialization_xp_and_level(in_player_id bigint, in_track_type dune.specializationtracktype, in_xp_amount integer, in_level real)`
    - `store_backup_vehicle(in_vehicle_id bigint, in_account_id bigint, in_customization_id text)`
    - `store_recovered_vehicle(in_vehicle_id bigint, in_chassis_durability real, in_customization_id text, in_is_migration boolean)`
    - `store_recovered_vehicles_wiped_before_spawn(in_vehicle_ids bigint[], in_delete_items boolean)`
    - `takeover_account(in_user_to_takeover text, in_current_user text)`
    - `taxation_emit_invoices(new_tax_invoices dune.taxinvoicedata[])`
    - `taxation_get_all_invoices_for_player(in_player_id bigint)`
    - `taxation_get_all_invoices_for_server(map_name text, in_dimension_index integer, in_partition_id bigint)`
    - `taxation_get_all_invoices_for_totem(in_totem_id bigint)`
    - `taxation_pay_invoice(invoice_id bigint, paid_invoice_status smallint)`
    - `taxation_remove_invoices(invoices_to_remove bigint[])`
    - `taxation_remove_invoices_from_totem(totem_actor_id bigint)`
    - `taxation_update_invoice_status(invoices_to_overdue bigint[], invoices_to_defaulted bigint[], overdue_invoice_status smallint, defaulted_invoice_status smallint)`
    - `try_prime_spicefield(in_source_server_id text, in_spicefield_id integer)`
    - `try_restart_spicefield(in_server_id text, in_spicefield_type_id integer)`
    - `try_spawn_spicefield(in_source_server_id text, in_spicefield_id integer)`
    - `try_update_exchange_categories_hash(in_new_hash integer)`
    - `unassign_partition(in_server_id text)`
    - `update_communinet_player_channel(in_account_id bigint, in_channel_name text, in_is_tuned boolean)`
    - `update_communinet_player_data(in_account_id bigint, in_is_active boolean, in_selected_channel_name text)`
    - `update_consumed_per_player_lore(in_actor_id bigint, in_consumed_bit_array bit, in_use_temporary boolean)`
    - `update_coriolis_for_player(in_controller_id bigint, OUT out_was_coriolis_processed boolean)`
    - `update_death_location(in_pawn dune.actordescription, in_server_info dune.serverinfo, in_life_state dune.playerlifestate)`
    - `update_farm_state(in_server_id text, in_outgoing_s2s_connections integer, in_incoming_s2s_connections integer, in_connected_players integer, in_farm_id text, in_igw_...)`
    - `update_global_spice_field_rules(in_max_globally_primed integer, in_max_globally_active integer, in_spicefield_type_id integer)`
    - `update_inventories_data(in_inventory_data_list dune.inventorydata[])`
    - `update_inventory(in_delete_list bigint[], in_stack_update dune.itemstackupdate[], in_quality_update dune.itemqualityupdate[], in_stat_update dune.itemstatupdate[], ...)`
    - `update_item_locations(in_item_locations dune.inventoryitemlocation[])`
    - `update_journey_story_ids(old_story_ids text[], new_story_ids text[])`
    - `update_marker_ids(in_old_ids integer[], in_new_ids integer[])`
    - `update_partition_labels(in_allow_overwrite boolean)`
    - `update_party_platform_session(in_party_id bigint, in_platform_session_id text, in_platform_name text)`
    - `update_player_tags(in_account_id bigint, tags_to_add text[], tags_to_remove text[])`
    - `update_removed_items_and_recipes(items_removed text[], recipes_removed text[])`
    - `update_resourcefield_states(in_map text, in_dimension_index integer, in_field_kind_id smallint, in_field_states dune.resourcefieldstateentry[])`
    - `update_respawn_locations(player_id bigint, respawn_locations dune.respawnlocation[])`
    - `update_returning_player_status(in_user_id text, in_minimum_returning_player_time_seconds integer)`
    - `update_sell_orders_categories(category_update_data dune.exchangecategoryupdatedata[])`
    - `update_server_building_favorites(in_account_id bigint, in_building_types text[])`
    - `update_server_learned_building_sets(in_account_id bigint, in_learned_building_sets text[])`
    - `update_server_learned_new_buildable_pieces(in_account_id bigint, in_new_buildable_pieces text[])`
    - `update_specialization_refund_id(in_player_id bigint, in_refund_id smallint, in_removed_keystones smallint[])`
    - `update_spice_field_spawn_state(in_is_spawning_active boolean, in_spicefield_type_id integer)`
    - `update_traveling_actor_dependencies(in_dep dune.traveldependency[])`
    - `update_traveling_actor_tree(in_actor_id bigint, in_target_transform dune.transform, in_target_map text, in_target_dimension_index integer, in_target_partition_id bigint)`
    - `update_universe_time(in_farm_id text)`
    - `update_vendor_timestamp_for_player(in_vendor_id text, in_player_id bigint, in_timestamp bigint)`
    - `upgrade_location_data_list(in_location_data_list jsonb, in_map_field_name text)`
    - `upgrade_map_name(in_map_name text)`
    - `upgrade_map_value(in_value jsonb)`
    - `upsert_spicefield_types(in_max_globally_active integer[], in_max_globally_primed integer[], in_field_types text[], in_map_name text, in_dimension_index integer)`
    - `use_sinkchart(in_player_id bigint, in_account_id bigint, in_area_id smallint, in_item_id bigint, in_sinkchart_map_name text, in_player_map_name text, in_player_c...)`
    - `verify_item_dup_backup_tool(in_account_id bigint, in_vehicle_id bigint, in_cheat_type dune.cheat_type_enum)`
    - `wipe_old_events_log(in_days_limit integer)`
    - `zero_transform()`

28. **Database table counts (active server):**
    - `encrypted_accounts`: 10 rows, `encrypted_player_state`: 10 rows
    - `actors`: 411 rows, `items`: 1,482, `inventories`: 459
    - `buildings`: 8, `vehicles`: 16, `guilds`: 1 (4 members)
    - `bans`: 0, `factions`: 4 (Atreides, Harkonnen, Fremen, Corrino)
    - `game_events`: 76, `chat_history`: unknown
    - `dashboard.*` tables: `bans`, `chat_history`, `player_actions`, `player_ips`
29. **Dashboard Admin Experimental tab expanded with tools:**
    - Search Players (via `admin_get_character_ids`)
    - Online Players list (via `get_all_online_or_recently_disconnected_player_online_state()`)
    - Adjust Currency (via direct SQL to `player_virtual_currency_balances`)
    - View Currency Balances (via `get_player_virtual_currency_balances`)
    - Change Faction (via direct SQL to `player_faction`)
    - Faction Reputation View/Set (via `get_player_current_faction_reputation` / `set_player_faction_reputation`)
    - Inventory Lookup (via `admin_get_inventory_details`)
    - Teleport Player (via `admin_move_offline_player_to_partition`)
    - Guild Tools: List, View, Disband, Kick Member (via `get_guild_data`, `disband_guild`, `remove_guild_members`)
    - Player Tags: View & Update (via `admin_read_player_tags`, `update_player_tags`)
    - Flag Cheater (via `flag_player_as_cheater`)
    - Player Vehicles (via `get_player_owned_vehicles_data`)
    - Player Stats Viewer (health, spice exposure, etc. from `actors.properties` JSONB)
    - Character Management: rename, delete character, delete account, set demo state
    - Journey & Specialization: complete/reveal/reset story nodes, set/reset specialization tracks
    - Guild Roster: list members, promote/demote
    - Economy: reset vendor stock for player, view tax invoices
    - Spice Fields: force spice spawn, reset spice state
    - Server Tools: set players offline, cleanup orphans
    - Permissions: view actor permissions, set player rank
    - Function Explorer: browse and execute all 517 DB functions dynamically with parameter input
    - Battlegroup Info viewer (via BGD API `/v0/battlegroup`)
    - (Broadcast via RMQ was already done in finding #22)
    - API endpoints in `routes/api.py`:
      - `POST /api/admin-experimental/broadcast`
      - `POST /api/admin-experimental/query` (read-only SQL)
      - `POST /api/admin-experimental/search-players`
      - `GET /api/admin-experimental/online-players`
      - `POST /api/admin-experimental/adjust-currency`
      - `POST /api/admin-experimental/currency-balances`
      - `POST /api/admin-experimental/change-faction`
      - `POST /api/admin-experimental/faction-reputation`
      - `POST /api/admin-experimental/inventory`
      - `POST /api/admin-experimental/teleport`
      - `GET /api/admin-experimental/partitions`
      - `GET /api/admin-experimental/guilds`
      - `POST /api/admin-experimental/guild-data`
      - `POST /api/admin-experimental/disband-guild`
      - `POST /api/admin-experimental/remove-guild-member`
      - `POST /api/admin-experimental/player-tags`
      - `POST /api/admin-experimental/flag-cheater`
      - `POST /api/admin-experimental/player-vehicles`
      - `POST /api/admin-experimental/player-stats`
      - `POST /api/admin-experimental/set-character-name`
      - `POST /api/admin-experimental/delete-character`
      - `POST /api/admin-experimental/delete-account`
      - `POST /api/admin-experimental/set-demo-state`
      - `POST /api/admin-experimental/journey`
      - `POST /api/admin-experimental/specialization`
      - `POST /api/admin-experimental/guild-members`
      - `POST /api/admin-experimental/clean-vendor-stock`
      - `POST /api/admin-experimental/tax-invoices`
      - `POST /api/admin-experimental/spice`
      - `POST /api/admin-experimental/server-tools`
      - `POST /api/admin-experimental/permissions`
      - `GET /api/admin-experimental/functions`
      - `GET /api/admin-experimental/functions/<name>`
      - `POST /api/admin-experimental/functions/<name>/execute`
      - `GET /api/admin-experimental/battlegroup`
      - `POST /api/admin-experimental/execute` (admin functions)
30. **Key insight about kubectl exec from dashboard:** The paramiko SSH `exec_command` doesn't support heredocs well. The working pattern for piping content into pods is:
    - Write content to a temp file on VM host via `echo base64 | base64 -d | sudo tee /tmp/file`
    - Then pipe into pod: `cat /tmp/file | sudo kubectl exec -i -n ns pod -- sh -lc 'cat > /tmp/pod_file && command "$(cat /tmp/pod_file)"'`
    - Clean up both temp files after

31. **`search_path` issue with DB functions:** PostgreSQL's default `search_path` is `"$user", public` — the `dune` schema is NOT on it. Any function defined in the `dune` schema that references tables without the `dune.` prefix (e.g., `accounts`, `player_state`, `actors`, `world_partition`) will fail when called from outside the schema. Our `teleport_player()` fix: run `SET search_path TO dune, public` before calling the function. This affects the teleport function `admin_move_offline_player_to_partition` and likely many of the 517 functions.

32. **Table name correction:** The table is `dune.world_partition` (singular), NOT `dune.world_partitions` (plural). `accounts` and `player_state` are **views** in the `dune` schema, not physical tables. Other notable tables:
    - `dune.actors` (physical) — id, class, map, owner_account_id, properties JSONB
    - `dune.world_partition` — partition_id, server_id, map, dimension_index, label, blocked, partition_definition JSONB
    - `dune.player_virtual_currency_balances` — player_controller_id, currency_id, balance
    - `dune.player_faction` — actor_id, faction_id
    - `dune.player_faction_reputation` — actor_id, faction_id, reputation_amount
    - `dune.player_tags` — account_id, tag
    - `dune.vehicles` — id, actor_id
    - `dune.player_state` (view) — account_id, character_name, player_controller_id, player_pawn_id, online_status
    - `dune.accounts` (view) — id, user
    - `dune.encrypted_accounts` — id, user, platform_id

---

## 13. TROUBLESHOOTING TIPS

### PowerShell Quoting for SSH Commands
PowerShell interprets `$`, `|`, `>`, `<`, `&&`, `;`, `(`, `)` in SSH command strings. Workarounds:
```powershell
# Use single quotes for outer string
ssh -i <key> user@host 'command with $vars'

# Or pipe scripts via stdin
Get-Content script.sh -Raw | ssh <args> "cat > /tmp/scr.sh && bash /tmp/scr.sh"
```

### TR Auth Testing
```bash
# From inside the VM:
sudo kubectl exec -n <ns> <bgd-pod> -- wget -q -O- \
  --post-data="username=<user>&password=<pass>" \
  http://<world>-tr-svc:5059/v0/auth/user
```
Returns `allow` or `deny`.

### Common NodePort Connection Issues
- SSH tunnel may drop (restart via dashboard launcher)
- Windows firewall may block connections to VM IP on non-standard ports
- AMQP connections require TLS (certificate from `/etc/rabbitmq/`)

### Modifying RMQ ConfigMaps
The battlegroup operators continuously reconcile ConfigMaps. To make changes:
```bash
# 1. Scale down all operators
sudo kubectl scale deployment -n funcom-operators --replicas=0 \
  battlegroupoperator-controller-manager \
  databaseoperator-controller-manager \
  serveroperator-controller-manager \
  utilitiesoperator-controller-manager

# 2. Make your ConfigMap changes (use kubectl replace with YAML file)
# 3. Restart affected pods
sudo kubectl delete pod -n <namespace> <pod-name>

# 4. Scale operators back up
sudo kubectl scale deployment -n funcom-operators --replicas=1 \
  battlegroupoperator-controller-manager \
  databaseoperator-controller-manager \
  serveroperator-controller-manager \
  utilitiesoperator-controller-manager
```
