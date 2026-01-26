# signals/base.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Protocol, Literal

Status = Literal["ok", "warn", "bad", "unknown"]

def now_utc() -> datetime:
    return datetime.now(timezone.utc)

@dataclass(frozen=True)
class SignalResult:
    status: Status
    value: str
    ts: datetime
    details: Optional[str] = None
    link: Optional[str] = None

@dataclass(frozen=True)
class SignalMeta:
    id: str                 # stable key (used in cache + routes later)
    title: str              # human label
    poll_interval_s: int = 60
    timeout_s: float = 2.0  # used later when we do concurrent refresh

class Signal(Protocol):
    meta: SignalMeta

    def fetch(self) -> SignalResult:
        """Fetch current signal state. Must not throw."""
        ...
