# core/cache.py
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from signals.base import SignalResult

def _serialize_result(result: SignalResult) -> dict:
    data = asdict(result)
    data["ts"] = result.ts.isoformat()
    return data

def _deserialize_result(data: dict) -> SignalResult:
    return SignalResult(
        status=data["status"],
        value=data["value"],
        ts=datetime.fromisoformat(data["ts"]),
        details=data.get("details"),
        link=data.get("link"),
    )

class CacheStore:
    def __init__(self, path: Path):
        self.path = path
        self._data: Dict[str, SignalResult] = {}

    def load(self) -> None:
        if not self.path.exists():
            return

        try:
            raw = json.loads(self.path.read_text())
            for signal_id, payload in raw.items():
                self._data[signal_id] = _deserialize_result(payload)
        except Exception:
            # Corrupt cache should never crash the app
            self._data = {}

    def flush(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        serialized = {
            sid: _serialize_result(result)
            for sid, result in self._data.items()
        }
        self.path.write_text(json.dumps(serialized, indent=2))

    def get(self, signal_id: str) -> Optional[SignalResult]:
        return self._data.get(signal_id)

    def set(self, signal_id: str, result: SignalResult) -> None:
        self._data[signal_id] = result

    def snapshot(self) -> Dict[str, SignalResult]:
        # Return a shallow copy so renderers can't mutate internal state
        return dict(self._data)
