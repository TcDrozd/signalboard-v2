# SignalBoard V2

SignalBoard V2 is a LAN-local, overengineered learning project that keeps signal
execution global while introducing per-user dashboards via subscriptions.

## What Changed From V1

- FastAPI remains the web framework.
- Signal abstractions remain unchanged: `Signal`, `SignalMeta`, `SignalResult`.
- Global `CacheStore` still holds latest signal results.
- New SQLite-backed user + subscription preferences.
- Dashboards are now filtered per user, but signals execute once globally.

## Architecture

```text
signals/             -> signal implementations (unchanged)
core/registry.py     -> signal discovery + metadata
core/bg.py           -> global refresh engine + background signals
core/cache.py        -> global cache persistence
core/subscriptions.py-> SQLite users/subscriptions
routers/             -> API + UI route modules
models/              -> request payload validation
templates/dashboard.html -> V2 UI shell
```

Design rule:
> Execution is global. Subscriptions only filter rendering.

## API Endpoints (V2 MVP)

### Registry

- `GET /api/registry` -> list all available signals from registry metadata.

### Users

- `GET /api/users` -> list users.
- `POST /api/users` -> create a user.

Request body:

```json
{"username":"alice"}
```

### Subscriptions

- `GET /api/users/{username}/subscriptions` -> list subscribed signal ids.
- `POST /api/users/{username}/subscriptions` -> subscribe user to a signal.
- `DELETE /api/users/{username}/subscriptions/{signal_id}` -> unsubscribe.

Subscribe request body:

```json
{"signal_id":"board_health"}
```

### Personalized Dashboard Data

- `GET /api/users/{username}/dashboard` -> only subscribed signals, resolved from global cache.

### Global Execution/Admin Controls

- `POST /api/refresh` -> refresh all signals (background signals are non-blocking).
- `POST /api/reload` -> reload signal registry from `signals/`.
- `GET /api/bg` -> background task status.
- `GET /api/signals` -> global cached signal views (unfiltered).

## UI

- `GET /` -> V2 dashboard UI.
  - Select/create user
  - View all available signals
  - Toggle subscriptions
  - View that user's personalized dashboard

## Storage

- Global signal results: `data/cache.json`
- User preferences: `data/subscriptions.db` (SQLite)

Schema reference: `docs/subscriptions_schema.sql`

## Running Locally

```bash
python3 -m venv venv
source venv/bin/activate
pip install fastapi uvicorn jinja2 pydantic
uvicorn app:app --host 0.0.0.0 --port 8099 --reload
```

Open:

- App UI: `http://localhost:8099/`
- OpenAPI docs: `http://localhost:8099/docs`

## Notes

- No auth complexity yet; usernames are lightweight identifiers.
- This is intentionally not production SaaS.
