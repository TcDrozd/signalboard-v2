from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from core.cache import CacheStore
from core.registry import RegistryStore
from core.view import build_views, format_age
from signals.base import Signal, SignalResult

log = logging.getLogger("signalboard.engine")


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _is_today_local(ts: datetime, tz_name: str) -> bool:
    tz = ZoneInfo(tz_name)
    return ts.astimezone(tz).date() == datetime.now(tz).date()


def _safe_fetch(sig: Signal) -> SignalResult:
    """Signal fetch guard. The execution engine must never propagate fetch exceptions."""
    try:
        return sig.fetch()
    except Exception as exc:
        return SignalResult(
            status="bad",
            value="fetch failed",
            ts=_now_utc(),
            details=f"{type(exc).__name__}: {exc}",
        )


class SignalEngine:
    """
    Global signal execution and cache persistence.

    User dashboards do not execute signals. They filter from this global result set.
    """

    def __init__(
        self,
        *,
        cache: CacheStore,
        registry: RegistryStore,
        background_signals: set[str] | None = None,
    ) -> None:
        self.cache = cache
        self.registry = registry
        self.background_signals = background_signals or set()
        self.lock = asyncio.Lock()
        self._bg_tasks: dict[str, asyncio.Task] = {}
        self._bg_lock = asyncio.Lock()

    async def _store_result(self, signal_id: str, result: SignalResult) -> None:
        async with self.lock:
            self.cache.set(signal_id, result)
            self.cache.flush()

    async def _run_bg_fetch(self, signal_id: str, signal: Signal) -> None:
        timeout_s = signal.meta.timeout_s

        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(_safe_fetch, signal),
                timeout=timeout_s,
            )
        except asyncio.TimeoutError:
            result = SignalResult(
                status="bad",
                value="timeout",
                ts=_now_utc(),
                details=f"Exceeded {timeout_s:.2f}s (background)",
            )
        except Exception as exc:
            log.exception("unexpected background failure for %s", signal_id)
            result = SignalResult(
                status="bad",
                value="error",
                ts=_now_utc(),
                details=f"{type(exc).__name__}: {exc}",
            )

        await self._store_result(signal_id, result)

        async with self._bg_lock:
            self._bg_tasks.pop(signal_id, None)

    async def _kickoff_bg(self, signal_id: str, signal: Signal, *, force: bool) -> SignalResult:
        async with self._bg_lock:
            existing = self._bg_tasks.get(signal_id)
            if existing and not existing.done():
                placeholder = SignalResult(
                    status="unknown",
                    value="generating...",
                    ts=_now_utc(),
                    details="background refresh already running",
                )
                await self._store_result(signal_id, placeholder)
                return placeholder

            # Daily gate remains specific to capybara_wisdom in V2.
            if signal_id == "capybara_wisdom" and not force:
                tz_name = os.getenv("CAPYBARA_TZ", "America/Detroit")
                async with self.lock:
                    cached = self.cache.get(signal_id)
                if cached and cached.value and cached.value != "generating...":
                    if _is_today_local(cached.ts, tz_name):
                        return cached

            placeholder = SignalResult(
                status="unknown",
                value="generating...",
                ts=_now_utc(),
                details="background refresh started",
            )
            await self._store_result(signal_id, placeholder)

            self._bg_tasks[signal_id] = asyncio.create_task(self._run_bg_fetch(signal_id, signal))
            return placeholder

    async def refresh(self, *, force: bool = False) -> dict[str, Any]:
        start = time.perf_counter()
        items = self.registry.items()

        async def run_one(signal_id: str, signal: Signal) -> dict[str, Any]:
            if signal_id in self.background_signals:
                result = await self._kickoff_bg(signal_id, signal, force=force)
                return {"id": signal_id, "result": result}

            timeout_s = signal.meta.timeout_s
            try:
                result = await asyncio.wait_for(
                    asyncio.to_thread(_safe_fetch, signal),
                    timeout=timeout_s,
                )
                return {"id": signal_id, "result": result}
            except asyncio.TimeoutError:
                return {
                    "id": signal_id,
                    "result": SignalResult(
                        status="bad",
                        value="timeout",
                        ts=_now_utc(),
                        details=f"Exceeded {timeout_s:.2f}s",
                    ),
                }
            except Exception as exc:
                return {
                    "id": signal_id,
                    "result": SignalResult(
                        status="bad",
                        value="error",
                        ts=_now_utc(),
                        details=f"{type(exc).__name__}: {exc}",
                    ),
                }

        outcomes = await asyncio.gather(*(run_one(signal_id, signal) for signal_id, signal in items))

        # Foreground writes are batched into one flush.
        async with self.lock:
            for outcome in outcomes:
                if outcome["id"] in self.background_signals:
                    continue
                self.cache.set(outcome["id"], outcome["result"])
            self.cache.flush()

        counts: dict[str, int] = {"ok": 0, "warn": 0, "bad": 0, "unknown": 0}
        per_signal: list[dict[str, Any]] = []
        for outcome in outcomes:
            result: SignalResult = outcome["result"]
            counts[result.status] = counts.get(result.status, 0) + 1
            per_signal.append({"id": outcome["id"], "status": result.status, "note": result.value})

        return {
            "ok": True,
            "duration_ms": int((time.perf_counter() - start) * 1000),
            "counts": counts,
            "signals": per_signal,
        }

    def list_views(self, signal_ids: set[str] | None = None) -> list[dict[str, Any]]:
        metas = self.registry.metas()
        if signal_ids is not None:
            metas = [meta for meta in metas if meta.id in signal_ids]

        snap = self.cache.snapshot()
        views = build_views(metas, snap)
        return [
            {
                "id": view.id,
                "title": view.title,
                "status": view.status,
                "value": view.value,
                "ts": view.ts.isoformat(),
                "age_s": view.age_s,
                "age": format_age(view.age_s),
                "details": view.details,
                "link": view.link,
            }
            for view in views
        ]

    async def bg_status(self) -> dict[str, list[str]]:
        async with self._bg_lock:
            return {
                "running": [key for key, task in self._bg_tasks.items() if not task.done()],
                "done": [key for key, task in self._bg_tasks.items() if task.done()],
            }
