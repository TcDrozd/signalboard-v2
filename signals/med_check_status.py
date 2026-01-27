from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from .base import SignalMeta, SignalResult, now_utc


def _get_json(url: str, timeout_s: float) -> dict:
    req = Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "signalboard/0.1"},
        method="GET",
    )
    with urlopen(req, timeout=timeout_s) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object, got {type(payload).__name__}")
    return payload


def _parse_iso(ts: str) -> datetime:
    # Handles offsets like "-05:00" and also "Z"
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _fmt_local(dt_utc: datetime, tz_name: str) -> str:
    # Keep this minimal; if tz isn't available, fall back to UTC
    try:
        from zoneinfo import ZoneInfo
        return dt_utc.astimezone(ZoneInfo(tz_name)).strftime("%-I:%M %p")
    except Exception:
        return dt_utc.strftime("%H:%M UTC")


def _fmt_duration(seconds: int) -> str:
    seconds = max(seconds, 0)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    if h and m:
        return f"{h}h {m}m"
    if h:
        return f"{h}h"
    return f"{m}m"


@dataclass(frozen=True)
class MedCheckStatusSignal:
    meta: SignalMeta = SignalMeta(
        id="med_check_status",
        title="MedCheck",
        poll_interval_s=120,
        timeout_s=1.5,
    )

    def fetch(self) -> SignalResult:
        base = os.getenv("MEDCHECK_BASE_URL", "http://apps.local:5055").rstrip("/")
        url = f"{base}/api/status"

        try:
            data = _get_json(url, timeout_s=self.meta.timeout_s)
        except HTTPError as e:
            return SignalResult("bad", f"medcheck HTTP {e.code}", now_utc(), details=e.reason, link=url)
        except URLError as e:
            return SignalResult("bad", "medcheck unreachable", now_utc(), details=str(getattr(e, "reason", e)), link=url)
        except Exception as e:
            return SignalResult("bad", "medcheck fetch failed", now_utc(), details=str(e), link=url)

        # Exact expected schema:
        # {
        #   "reset_hour_local":3,
        #   "resets_at":"2026-01-28T03:00:00-05:00",
        #   "taken":true,
        #   "taken_at":"2026-01-27T12:24:42.354679-05:00",
        #   "timezone":"America/Detroit"
        # }
        try:
            taken = bool(data["taken"])
            resets_at = _parse_iso(str(data["resets_at"]))
            tz_name = str(data.get("timezone", "UTC"))
            taken_at_raw = data.get("taken_at")
            taken_at = _parse_iso(str(taken_at_raw)) if taken_at_raw else None
        except Exception as e:
            return SignalResult(
                status="bad",
                value="medcheck payload invalid",
                ts=now_utc(),
                details=f"{e}. Got keys: {sorted(list(data.keys()))}",
                link=url,
            )

        now = now_utc()
        seconds_to_reset = int((resets_at - now).total_seconds())

        # Status policy:
        # - taken -> ok
        # - not taken -> warn, escalate to bad if close to reset (<= 2h)
        if taken:
            status = "ok"
            value = "taken ✅"
            detail = f"taken at {_fmt_local(taken_at or now, tz_name)} · resets {_fmt_local(resets_at, tz_name)}"
            ts = taken_at or now
        else:
            close_s = int(os.getenv("MEDCHECK_BAD_WITHIN_SECONDS", str(2 * 3600)))
            status = "bad" if seconds_to_reset <= close_s else "warn"
            value = "not taken ⚠️"
            detail = f"resets {_fmt_local(resets_at, tz_name)} (in {_fmt_duration(seconds_to_reset)})"
            ts = resets_at  # next meaningful boundary

        return SignalResult(
            status=status,
            value=value,
            ts=ts,
            details=detail,
            link=url,
        )


SIGNAL = MedCheckStatusSignal()
