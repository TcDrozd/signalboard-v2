# SignalBoard V2 Documentation

SignalBoard V2 keeps signal fetching centralized while adding user-specific
dashboard composition.

## Core Concepts

### Global Execution
Signals run once globally through the refresh engine in `core/bg.py`.
Results are persisted in `CacheStore`.

### Subscription Filtering
Users subscribe to signal ids. Subscriptions are stored in SQLite and used only
to filter which cached signals appear on each user's dashboard.

### Rendering
The dashboard UI (`/`) is user-centric and calls API routes to:
- select/create users
- toggle subscriptions
- load personalized dashboard cards

## API Surfaces

- `GET /api/registry`
- `GET /api/users`
- `POST /api/users`
- `GET /api/users/{username}/subscriptions`
- `POST /api/users/{username}/subscriptions`
- `DELETE /api/users/{username}/subscriptions/{signal_id}`
- `GET /api/users/{username}/dashboard`

Operational endpoints:
- `POST /api/refresh`
- `POST /api/reload`
- `GET /api/bg`
- `GET /api/signals`

## Storage

- `data/cache.json` -> global signal results
- `data/subscriptions.db` -> users + subscriptions

See `docs/subscriptions_schema.sql` for schema.
