# Dune Awakening Dashboard

A modern, full‑featured management dashboard for **Dune: Awakening** private servers. Provides real‑time monitoring, player tools, chat logs, file browsing, admin utilities, and secure remote access.

---

## Quick Start

### **Windows**
1. Run `launcher.bat` or `.\launcher.ps1`
2. Select **[2] Run Setup** on first launch  
3. Select **[1] Start Dashboard** to open the UI

> The launcher automatically finds your Dune Awakening SSH key and politely ignores PowerShell’s opinions about execution policies.

### **Linux / macOS**
```bash
chmod +x start.sh
./start.sh
```

---

## Features

- **Player Management** (vitals, inventory, vehicles, buildings, guilds, reputation)  
- **In-Game Notifications** — instant broadcasts plus scheduled one-shot/daily/weekly/monthly messages  
- **Graceful Shutdown / Restart** — in-game countdown warnings with cancel notices, plus scheduled restarts  
- **Battlegroup Control** — start/stop/restart/update, with update blocked while players are online  
- **Chat Logs** with channel filtering and auto-refresh  
- **Director Tools** (battlegroups, world state, transfers)  
- **SSH File Browser** (jailed to allowed directories) + **in-browser shell**  
- **Pod Management** (list, logs, describe, delete with safe-mode for DB backup pods)  
- **Backup & Restore** — encrypted full-server snapshots with scheduled backups and retention cleanup  
- **Funcom Service Auth Token Management** — update the `ServiceAuthToken` JWT across files and live K8s resources with verification  
- **Firewall Hardening** via iptables  
- **HTTPS + Remote Access** (self-signed or Let's Encrypt)  
- **Cross-Platform Launchers** (Windows + Linux/macOS, incl. debug mode and SSH key rotation)

---

## Project Structure

```
DuneDashboard/
├── app/          # Flask/Jinja2 dashboard
├── launcher.ps1  # Windows launcher
├── start.sh      # Linux/macOS launcher
└── settings.yaml # Generated config (gitignored)
```

---

## Requirements

- Python 3.8+  
- OpenSSH client  
- `kubectl` access to your Dune Awakening cluster  
- SSH access to the game server VM  

---

## Development

Run `launcher.bat` or `.\launcher.ps1` — the launcher handles dependencies, SSH key configuration, and server setup automatically.

---

## License

Source Available under the **Dune Dashboard Source License (DDSL)**  
- No redistribution  
- No claiming authorship  
- Personal, non-commercial use only  
- Basically: look, learn, enjoy — just don’t repost it as “Dune Dashboard Pro Deluxe Edition”.

