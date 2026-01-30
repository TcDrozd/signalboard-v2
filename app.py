from __future__ import annotations

# =============================================================================
# SignalBoard (FastAPI)
#
# Responsibilities:
# - Load signal registry (signals/load_signals)
# - Cache latest results (data/cache.json via CacheStore)
# - Render UI (/), text output (/txt), API output (/api/signals)
# - Refresh signals (/refresh) with support for background-only signals
# - Hot-reload registry (/reload)
# - Serve lightweight markdown docs (/docs)
# =============================================================================

# ---- stdlib ----
import asyncio
import html
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from zoneinfo import ZoneInfo

# ---- web ----
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

# ---- local ----
from core.cache import CacheStore
from core.view import build_views, format_age
from signals import load_signals
from signals.base import Signal, SignalMeta, SignalResult

log = logging.getLogger("signalboard")

# =============================================================================
# Config / Paths
# =============================================================================

BASE_DIR = Path(__file__).resolve().parent
CACHE_PATH = Path("data/cache.json")
DOCS_PATH = Path("docs")

# Signals that should NOT block /refresh (kick off work, return immediately)
BACKGROUND_SIGNALS = {"capybara_wisdom"}

# =============================================================================
# App setup
# =============================================================================

app = FastAPI(title="SignalBoard", version="0.2")
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# =============================================================================
# State
# =============================================================================

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

# Background task tracking (dedupe per signal)
_BG_TASKS: dict[str, asyncio.Task] = {}
_BG_LOCK = asyncio.Lock()


# =============================================================================
# Small helpers
# =============================================================================

def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _is_today_local(ts: datetime, tz_name: str) -> bool:
    tz = ZoneInfo(tz_name)
    return ts.astimezone(tz).date() == datetime.now(tz).date()


def _rebuild_registry() -> None:
    """Reload signals from disk and rebuild meta list."""
    registry = load_signals()
    metas = [sig.meta for sig in registry.values()]
    metas.sort(key=lambda m: m.title.lower())
    STATE.registry = registry
    STATE.metas = metas


def _safe_fetch(sig_id: str, sig: Signal) -> SignalResult:
    """
    Runs in a worker thread via asyncio.to_thread().
    Must never raise.
    """
    try:
        return sig.fetch()
    except Exception as e:
        return SignalResult(
            status="bad",
            value="fetch failed",
            ts=_now_utc(),
            details=str(e),
        )


async def _store_result(sig_id: str, result: SignalResult) -> None:
    """Write one result to cache (locked) and flush."""
    async with STATE.lock:
        STATE.cache.set(sig_id, result)
        STATE.cache.flush()


def _get_views() -> list[dict[str, Any]]:
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


# =============================================================================
# Background refresh implementation
# =============================================================================

async def _run_bg_fetch(sig_id: str, sig: Signal) -> None:
    """Fetch a signal in background, then commit result to cache."""
    timeout_s = sig.meta.timeout_s
    log.warning("[bg] start sig=%s timeout=%.2fs", sig_id, timeout_s)

    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(_safe_fetch, sig_id, sig),
            timeout=timeout_s,
        )
        log.warning("[bg] done sig=%s status=%s value=%r", sig_id, result.status, result.value)
    except asyncio.TimeoutError:
        result = SignalResult(
            status="bad",
            value="timeout",
            ts=_now_utc(),
            details=f"Exceeded {timeout_s:.2f}s (background)",
        )
        log.warning("[bg] timeout sig=%s", sig_id)
    except Exception as e:
        result = SignalResult(
            status="bad",
            value="error",
            ts=_now_utc(),
            details=f"{type(e).__name__}: {e}",
        )
        log.exception("[bg] exception sig=%s", sig_id)

    log.warning("[bg] writing cache sig=%s", sig_id)
    await _store_result(sig_id, result)
    log.warning("[bg] wrote cache sig=%s", sig_id)

    async with _BG_LOCK:
        _BG_TASKS.pop(sig_id, None)
    log.warning("[bg] cleared task sig=%s", sig_id)


async def _kickoff_bg(sig_id: str, sig: Signal, *, force: bool = False) -> SignalResult:
    """
    Start background refresh if not already running.

    Daily-gate: capybara_wisdom only generates once per local day unless force=True.
    Returns either cached result (if gated) or a "generating…" placeholder.
    """
    async with _BG_LOCK:
        existing = _BG_TASKS.get(sig_id)
        if existing and not existing.done():
            placeholder = SignalResult(
                status="unknown",
                value="generating…",
                ts=_now_utc(),
                details="background refresh already running",
            )
            await _store_result(sig_id, placeholder)
            return placeholder

        # ---- Daily gate for capybara ----
        if sig_id == "capybara_wisdom" and not force:
            tz_name = os.getenv("CAPYBARA_TZ", "America/Detroit")
            async with STATE.lock:
                cached = STATE.cache.get(sig_id)

            if cached is not None:
                cached_value = getattr(cached, "value", None) or cached.get("value")
                cached_ts = getattr(cached, "ts", None) or cached.get("ts")

                if isinstance(cached_ts, datetime) and cached_value and cached_value != "generating…":
                    if _is_today_local(cached_ts, tz_name):
                        return cached  # already have today's wisdom

        # Put placeholder then kick task
        placeholder = SignalResult(
            status="unknown",
            value="generating…",
            ts=_now_utc(),
            details="background refresh started",
        )
        await _store_result(sig_id, placeholder)

        _BG_TASKS[sig_id] = asyncio.create_task(_run_bg_fetch(sig_id, sig))
        log.warning("[bg] task created sig=%s", sig_id)
        return placeholder


# =============================================================================
# Docs rendering (tiny markdown)
# =============================================================================

def _render_markdown(md: str) -> str:
    """
    Extremely small markdown renderer:
    - headings (#, ##)
    - paragraphs
    - code blocks (```)

    This is intentional — docs are controlled input.
    """
    lines = md.splitlines()
    html_lines: list[str] = []
    in_code = False

    for line in lines:
        if line.strip().startswith("```"):
            in_code = not in_code
            html_lines.append("<pre><code>" if in_code else "</code></pre>")
            continue

        if in_code:
            html_lines.append(html.escape(line))
            continue

        if line.startswith("## "):
            html_lines.append(f"<h2>{html.escape(line[3:])}</h2>")
        elif line.startswith("# "):
            html_lines.append(f"<h1>{html.escape(line[2:])}</h1>")
        elif line.strip() == "":
            html_lines.append("<br>")
        else:
            html_lines.append(f"<p>{html.escape(line)}</p>")

    return "\n".join(html_lines)


# =============================================================================
# Routes
# =============================================================================

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "signals": _get_views()})


@app.get("/txt", response_class=PlainTextResponse)
def txt_signals() -> str:
    views = _get_views()
    lines: list[str] = []
    for s in views:
        status = s["status"].upper().ljust(7)
        age = s["age"].rjust(4)
        title = s["id"].ljust(18)[:18]
        value = s["value"]
        lines.append(f"{status} {title} {age}  {value}")
    return "\n".join(lines) + "\n"


@app.get("/api/signals")
def api_signals() -> dict[str, Any]:
    return {"signals": _get_views(), "count": len(STATE.metas)}


@app.get("/docs", response_class=HTMLResponse)
@app.get("/docs/{page}", response_class=HTMLResponse)
def docs(page: str = "index"):
    md_path = DOCS_PATH / f"{page}.md"
    if not md_path.exists():
        return HTMLResponse("<h1>Docs not found</h1>", status_code=404)

    content = md_path.read_text()
    body = _render_markdown(content)

    return HTMLResponse(
        f"""
        <html>
          <head>
            <title>SignalBoard Docs</title>
            <meta name="viewport" content="width=device-width, initial-scale=1" />
            <style>
              body {{
                font-family: system-ui, sans-serif;
                margin: 24px;
                max-width: 900px;
              }}
              code {{
                background: #f3f3f3;
                padding: 2px 4px;
                border-radius: 4px;
              }}
              pre {{
                background: #f3f3f3;
                padding: 12px;
                overflow-x: auto;
              }}
            </style>
          </head>
          <body>
            <a href="/docs">Docs index</a>
            {body}
          </body>
        </html>
        """
    )


@app.post("/reload")
async def reload_signals() -> dict[str, Any]:
    async with STATE.lock:
        _rebuild_registry()
        return {
            "ok": True,
            "count": len(STATE.registry),
            "signals": list(STATE.registry.keys()),
        }


@app.get("/bg")
async def bg_status():
    async with _BG_LOCK:
        return {
            "running": [k for k, t in _BG_TASKS.items() if not t.done()],
            "done": [k for k, t in _BG_TASKS.items() if t.done()],
        }


@app.post("/refresh")
async def refresh(force: int = Query(0)) -> dict[str, Any]:
    """
    Refresh all signals concurrently.

    - Background signals return immediately with placeholder/cached result and do NOT
      block on slow upstreams (Ollama, etc).
    - Foreground signals are fetched and written as a batch.
    - Use /refresh?force=1 to bypass daily gating for capybara_wisdom.
    """
    start = time.perf_counter()

    async with STATE.lock:
        items = list(STATE.registry.items())

    async def run_one(sig_id: str, sig: Signal) -> dict[str, Any]:
        # background signals: kick off and return immediately
        if sig_id in BACKGROUND_SIGNALS:
            result = await _kickoff_bg(sig_id, sig, force=bool(force))
            return {"id": sig_id, "ok": True, "result": result}

        # normal (foreground) signals
        timeout_s = sig.meta.timeout_s
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(_safe_fetch, sig_id, sig),
                timeout=timeout_s,
            )
            return {"id": sig_id, "ok": True, "result": result}
        except asyncio.TimeoutError:
            result = SignalResult(
                status="bad",
                value="timeout",
                ts=_now_utc(),
                details=f"Exceeded {timeout_s:.2f}s",
            )
            return {"id": sig_id, "ok": False, "result": result}
        except Exception as e:
            result = SignalResult(
                status="bad",
                value="error",
                ts=_now_utc(),
                details=f"{type(e).__name__}: {e}",
            )
            return {"id": sig_id, "ok": False, "result": result}

    outcomes = await asyncio.gather(*(run_one(sig_id, sig) for sig_id, sig in items))

    # Write non-background results in one flush
    async with STATE.lock:
        for o in outcomes:
            if o["id"] in BACKGROUND_SIGNALS:
                continue
            STATE.cache.set(o["id"], o["result"])
        STATE.cache.flush()

    dur_ms = int((time.perf_counter() - start) * 1000)

    counts = {"ok": 0, "warn": 0, "bad": 0, "unknown": 0}
    per_signal: list[dict[str, Any]] = []
    for o in outcomes:
        status = o["result"].status
        counts[status] = counts.get(status, 0) + 1
        per_signal.append({"id": o["id"], "status": status, "note": o["result"].value})

    return {
        "ok": True,
        "duration_ms": dur_ms,
        "counts": counts,
        "signals": per_signal,
    }


# =============================================================================
# Startup
# =============================================================================

STATE.cache.load()
_rebuild_registry()
