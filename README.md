## `README.md`

```markdown
# SignalBoard

SignalBoard is a small, LAN-local “ambient status board” that aggregates lightweight
signals from services, scripts, and APIs into a fast, readable dashboard.

It is intentionally simple:
- no database
- no auth (LAN-only)
- no websockets
- no heavy frontend framework

The goal is **low cognitive load** and **easy extensibility** — something you can
add to in short bursts and still find useful even when half-finished.

---

## What it does (today)

- Discovers “signals” automatically from `signals/`
- Periodically refreshes signal data into a disk-backed cache
- Renders cached state via:
  - HTML dashboard (`/`)
  - Plain-text view (`/txt`) — great for terminals
  - JSON API (`/api/signals`)
- Supports live control actions:
  - `POST /refresh` — fetch all signals now
  - `POST /reload` — re-scan signal plugins

Everything renders **from cache only**, so the UI stays fast even if upstream
services are slow or down.

---

## Architecture (mental model)

```
signals/        → fetch + normalize data
core/cache.py   → persistence + safety
core/view.py    → view model (age, defaults, formatting)
FastAPI routes  → render cached state only
```

Key idea:
> **Signals fetch. Routes render. Cache mediates.**

---

## Signals

A *signal* is a small Python module that:
- lives in `signals/`
- exposes a single object named `SIGNAL`
- implements:
  - metadata (`id`, `title`, refresh cadence, timeout)
  - `fetch()` → returns a normalized `SignalResult`

Signals are auto-discovered at runtime — adding a new file is enough.

Examples included:
- `board_health` – sanity check that the board is alive
- `portfolio_last_commit_age` – polls GitHub for last commit time
- `latest_dog_walk` – reads the most recent dog walk from a local API

---

## Configuration

SignalBoard is designed to run as a system service.

Configuration is supplied via environment variables, typically through a
systemd `EnvironmentFile` (recommended).

Example variables:

```bash
# GitHub-backed signals
GITHUB_OWNER=TcDrozd
GITHUB_REPO=portfolio
GITHUB_TOKEN=github_pat_...

PORTFOLIO_WARN_DAYS=7
PORTFOLIO_BAD_DAYS=21

# Local API signals
DOGWALK_BASE_URL=http://apps.local:5010

# Server
PORT=8099
```

No `.env` parsing library is required — systemd handles injection.

---

## Running locally (dev)

```bash
python3 -m venv venv
source venv/bin/activate
pip install fastapi uvicorn jinja2

uvicorn app:app --host 0.0.0.0 --port 8099
```

Then:

- `GET /` – HTML dashboard
- `GET /txt` – terminal view
- `POST /refresh`
- `POST /reload`

---

## Running persistently (recommended)

SignalBoard is intended to run as a systemd service on a LAN host or LXC.

Typical setup:
- `signalboard.service` → runs uvicorn
- `signalboard-refresh.timer` → periodically hits `/refresh`

This keeps the app stateless and avoids background refresh loops in-process.

---

## Non-goals (for now)

- Authentication
- Multi-user support
- Real-time push updates
- Heavy UI or client-side state
- Central configuration UI

Those can be added later **if they earn their keep**.

---

## Why this exists

SignalBoard is less about the dashboard itself and more about:
- building small, composable observability tools
- practicing clean boundaries (fetch vs render vs policy)
- creating ambient feedback loops that don’t demand attention

It’s meant to be useful even when unfinished.
```


