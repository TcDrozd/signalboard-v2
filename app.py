from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.requests import Request

from core.cache import CacheStore
from core.view import build_views, format_age
from signals import load_signals
from signals.base import Signal, SignalMeta, SignalResult


CACHE_PATH = Path("data/cache.json")

app = FastAPI(title="SignalBoard", version="0.2")
templates = Jinja2Templates(directory="templates")
BASE_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@dataclass
class AppState:
    registry: Dict[str, Signal]
    metas: List[SignalMeta]
    cache: CacheStore
    lock: asyncio.Lock


STATE = AppState(
    registry={},
    metas=[],
    cache=CacheStore(CACHE_PATH),
    lock=asyncio.Lock(),
)


def _rebuild_registry() -> None:
    registry = load_signals()
    metas = [sig.meta for sig in registry.values()]
    metas.sort(key=lambda m: m.title.lower())
    STATE.registry = registry
    STATE.metas = metas

from datetime import datetime, timezone
import time

def _now_utc() -> datetime:
    return datetime.now(timezone.utc)

def _safe_fetch(sig_id: str, sig: Signal) -> SignalResult:
    """
    Runs in a worker thread via asyncio.to_thread().
    Must never raise.
    """
    try:
        return sig.fetch()
    except Exception as e:
        # normalized failure result
        return SignalResult(
            status="bad",
            value="fetch failed",
            ts=_now_utc(),
            details=str(e),
        )

# initial load
STATE.cache.load()
_rebuild_registry()

def _get_views():
    snap = STATE.cache.snapshot()
    views = build_views(STATE.metas, snap)
    return [
        {
            "id": v.id,
            "title": v.title,
            "status": v.status,
            "value": v.value,
            "ts": v.ts.isoformat(),
            "age_s": v.age_s,
            "age": format_age(v.age_s),
            "details": v.details,
            "link": v.link,
        }
        for v in views
    ]

@app.get("/api/signals")
def api_signals() -> dict[str, Any]:
    return {"signals": _get_views(), "count": len(STATE.metas)}

@app.get("/txt", response_class=PlainTextResponse)
def txt_signals() -> str:
    views = _get_views()
    lines = []
    for s in views:
        status = s["status"].upper().ljust(7)
        age = s["age"].rjust(4)
        title = s["id"].ljust(18)[:18]
        value = s["value"]
        lines.append(f"{status} {title} {age}  {value}")
    return "\n".join(lines) + "\n"

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "signals": _get_views()})

@app.post("/reload")
async def reload_signals() -> dict[str, Any]:
    async with STATE.lock:
        _rebuild_registry()
        return {
            "ok": True,
            "count": len(STATE.registry),
            "signals": list(STATE.registry.keys()),
        }

@app.post("/refresh")
async def refresh() -> dict[str, Any]:
    start = time.perf_counter()

    async with STATE.lock:
        # capture current registry snapshot to keep refresh consistent
        items = list(STATE.registry.items())

    async def run_one(sig_id: str, sig: Signal) -> dict[str, Any]:
        timeout_s = sig.meta.timeout_s
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(_safe_fetch, sig_id, sig),
                timeout=timeout_s,
            )
            return {"id": sig_id, "ok": True, "status": result.status, "result": result}
        except asyncio.TimeoutError:
            result = SignalResult(
                status="bad",
                value="timeout",
                ts=_now_utc(),
                details=f"Exceeded {timeout_s:.2f}s",
            )
            return {"id": sig_id, "ok": False, "status": "bad", "result": result}

    # run concurrently
    outcomes = await asyncio.gather(*(run_one(sig_id, sig) for sig_id, sig in items))

    # write to cache under lock + flush once
    async with STATE.lock:
        for o in outcomes:
            STATE.cache.set(o["id"], o["result"])
        STATE.cache.flush()

    dur_ms = int((time.perf_counter() - start) * 1000)

    # counts
    counts = {"ok": 0, "warn": 0, "bad": 0, "unknown": 0}
    per_signal = []
    for o in outcomes:
        status = o["result"].status
        counts[status] = counts.get(status, 0) + 1
        per_signal.append({
            "id": o["id"],
            "status": status,
            "note": o["result"].value,
        })

    return {
        "ok": True,
        "duration_ms": dur_ms,
        "counts": counts,
        "signals": per_signal,
    }
