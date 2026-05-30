# Dune Awakening Dashboard

A modern, full‑featured management dashboard for **Dune: Awakening** private servers. Provides real‑time monitoring, player tools, chat logs, file browsing, admin utilities, and secure remote access.

> “A comprehensive web-based management dashboard for Dune: Awakening private servers.”  

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

- **Interactive Maps** with calibrated coordinates  
- **Player Management** (vitals, inventory, vehicles, buildings, guilds, reputation)  
- **Chat Logs** with channel filtering and auto-refresh  
- **Director Tools** (battlegroups, world state, transfers)  
- **SSH File Browser** + **in-browser shell**  
- **Admin Tools** (ban/kick, history, read‑only SQL viewer)  
- **Firewall Hardening** via iptables  
- **Auto‑Update** with safe file replacement  
- **HTTPS + Remote Access** (self‑signed or Let’s Encrypt)  
- **Cross‑Platform Launchers**  
- **Organized Logging** with automatic cleanup and redaction  
- **Debug Mode** with full request/SSH/K8s tracing  
- **14 Dune house themes** (Atreides, Harkonnen, Fremen etc.)  
- And yes, it’s all probably more than you’ll ever need — but it *felt right at the time*.

---

## Project Structure

```
DuneDashboard/
├── backend/      # Flask API + services
├── frontend/     # React + Vite + Tailwind SPA
├── app/          # Legacy Flask/Jinja2 dashboard
├── launcher.ps1  # Windows launcher
├── start.sh      # Linux/macOS launcher
└── settings.yaml # Generated config (gitignored)
```

> The legacy dashboard still works. Like an old Fremen still wandering the desert — reliable, but we don’t talk about it much.

---

## Requirements

- Python 3.8+  
- Node.js 18+  
- OpenSSH client  
- `kubectl` access to your Dune Awakening cluster  
- SSH access to the game server VM  

---

## Security

- `settings.yaml` is never committed  
- SSH keys stored with restricted permissions  
- All DB queries parameterized  
- Raw SQL endpoint is **read‑only SELECT**  
- All mutations audited  
- CSP, HSTS, X‑Frame‑Options enforced in production  

> “Raw SQL query endpoint is read‑only SELECT — INSERT/UPDATE/DELETE… are blocked.”  
> Because letting users run `DROP TABLE` from a web UI is how horror stories begin.

---

## Development

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Backend
```bash
cd backend
pip install -r requirements.txt
python run.py
```

---

## Branching Strategy

- **main** — stable-ish beta  
- **nightly** — latest features  
- **experimental** — where chaos becomes innovation  

> “This seemed like a great idea at 3am.” — every experimental commit ever

---

## License

Source Available under the **Dune Dashboard Source License (DDSL)**  
- No redistribution  
- No claiming authorship  
- Personal, non-commercial use only  
- Basically: look, learn, enjoy — just don’t repost it as “Dune Dashboard Pro Deluxe Edition”.

