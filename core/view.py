# core/view.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, List

from signals.base import SignalResult, SignalMeta

@dataclass(frozen=True)
class SignalView:
    id: str
    title: str
    status: str
    value: str
    ts: datetime
    age_s: int
    details: Optional[str] = None
    link: Optional[str] = None

def _now_utc() -> datetime:
    return datetime.now(timezone.utc)

def build_views(metas: List[SignalMeta], results_by_id: dict[str, SignalResult]) -> List[SignalView]:
    now = _now_utc()
    views: List[SignalView] = []

    for meta in metas:
        r = results_by_id.get(meta.id)
        if r is None:
            views.append(SignalView(
                id=meta.id,
                title=meta.title,
                status="unknown",
                value="no data yet",
                ts=now,
                age_s=0,
                details=None,
                link=None,
            ))
            continue

        age = int((now - r.ts).total_seconds())
        views.append(SignalView(
            id=meta.id,
            title=meta.title,
            status=r.status,
            value=r.value,
            ts=r.ts,
            age_s=max(age, 0),
            details=r.details,
            link=r.link,
        ))

    return views

def format_age(age_s: int) -> str:
    if age_s < 60:
        return f"{age_s}s"
    if age_s < 3600:
        return f"{age_s // 60}m"
    if age_s < 86400:
        return f"{age_s // 3600}h"
    return f"{age_s // 86400}d"
