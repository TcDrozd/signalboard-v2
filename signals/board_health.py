# signals/board_health.py
from __future__ import annotations

from dataclasses import dataclass

from .base import SignalMeta, SignalResult, now_utc

@dataclass(frozen=True)
class BoardHealthSignal:
    meta: SignalMeta = SignalMeta(
        id="board_health",
        title="Board Health",
        poll_interval_s=60,
        timeout_s=1.0,
    )

    def fetch(self) -> SignalResult:
        return SignalResult(
            status="ok",
            value="board alive",
            ts=now_utc(),
            details="Signal registry loaded successfully.",
        )

SIGNAL = BoardHealthSignal()
