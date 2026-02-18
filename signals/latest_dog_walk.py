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


def _parse_walk_ts(date_str: str, time_str: str) -> datetime:
    # date: "2026-01-25", time: "10:55"
    dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    return dt.replace(tzinfo=timezone.utc)  # treat as UTC for now (see note below)


def _days_since(dt: datetime) -> int:
    age_s = int((now_utc() - dt).total_seconds())
    return max(age_s // 86400, 0)


@dataclass(frozen=True)
class LatestDogWalkSignal:
    meta: SignalMeta = SignalMeta(
        id="latest_dog_walk",
        title="Rory: latest walk",
        poll_interval_s=120,
        # mDNS (.local) resolution can take a few seconds on some hosts.
        # Keep this above typical resolver latency so engine-level wait_for
        # doesn't mark the signal as timed out before the HTTP call completes.
        timeout_s=6.0,
    )

    def fetch(self) -> SignalResult:
        base = os.getenv("DOGWALK_BASE_URL", "http://localhost:5010").rstrip("/")
        url = f"{base}/api/latest"

        try:
            data = _get_json(url, timeout_s=self.meta.timeout_s)
        except HTTPError as e:
            return SignalResult("bad", f"dogwalk HTTP {e.code}", now_utc(), details=e.reason, link=url)
        except URLError as e:
            return SignalResult("bad", "dogwalk unreachable", now_utc(), details=str(getattr(e, "reason", e)), link=url)
        except Exception as e:
            return SignalResult("bad", "dogwalk fetch failed", now_utc(), details=str(e), link=url)

        # Exact expected schema:
        # {"date":"YYYY-MM-DD","duration":15,"end":"10:55","notes":"Snowstorm","start":"10:40"}
        try:
            date = str(data["date"])
            start = str(data["start"])
            end = str(data["end"])
            duration = int(data["duration"])
            notes = str(data.get("notes", "")).strip() or None
        except Exception as e:
            return SignalResult(
                status="bad",
                value="dogwalk payload invalid",
                ts=now_utc(),
                details=f"{e}. Got keys: {sorted(list(data.keys()))}",
                link=url,
            )

        try:
            end_dt = _parse_walk_ts(date, end)
        except Exception as e:
            return SignalResult(
                status="bad",
                value="bad walk timestamp",
                ts=now_utc(),
                details=f"{e}. date={date!r} end={end!r}",
                link=url,
            )

        age_days = _days_since(end_dt)

        # Status policy: ok today, warn yesterday, bad 2+ days
        if age_days >= 2:
            status = "bad"
        elif age_days == 1:
            status = "warn"
        else:
            status = "ok"

        value = "walked today" if age_days == 0 else f"{age_days}d since last walk"
        details = f"{duration}m ({start}–{end})"
        if notes:
            details += f" — {notes}"

        return SignalResult(
            status=status,
            value=value,
            ts=end_dt,  # event time (end of walk)
            details=details,
            link=url,
        )


SIGNAL = LatestDogWalkSignal()
