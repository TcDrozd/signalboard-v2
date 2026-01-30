# SignalBoard Documentation

SignalBoard is a lightweight, LAN-local ambient status board designed to surface
small, meaningful signals from personal systems without demanding attention.

It favors:
- clarity over cleverness
- cache-backed rendering over live calls
- incremental growth over completeness

---

## Core Concepts

### Signal
A signal is a small plugin responsible for fetching **one** piece of information
and normalizing it into a standard shape.

Signals live in `signals/` and are auto-discovered at runtime.

### Cache
All UI surfaces render **from cache only**.
This ensures fast, reliable output even if upstream services are slow or unavailable.

### Surfaces
SignalBoard exposes the same data through:
- HTML (`/`)
- plain text (`/txt`)
- JSON (`/api/signals`)

---

## Control Endpoints

- `POST /refresh` — fetch all signals and update cache
- `POST /reload` — re-scan signal plugins

These are intentionally explicit and separate.

---

## Philosophy

SignalBoard is not a monitoring or alerting system.

It is meant to be:
- glanced at
- trusted
- ignored when life is busy

If a signal stops being useful, it should be easy to remove.
