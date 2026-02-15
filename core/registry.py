from __future__ import annotations

from dataclasses import asdict
from typing import Any

from signals import load_signals
from signals.base import Signal, SignalMeta


class RegistryStore:
    """
    In-memory signal registry.

    Signal execution stays global in V2. This service is responsible only for
    discovery and metadata lookup so user-specific filtering can happen later.
    """

    def __init__(self) -> None:
        self._registry: dict[str, Signal] = {}
        self._metas: list[SignalMeta] = []

    def reload(self) -> None:
        registry = load_signals()
        metas = [signal.meta for signal in registry.values()]
        metas.sort(key=lambda meta: meta.title.lower())
        self._registry = registry
        self._metas = metas

    def has_signal(self, signal_id: str) -> bool:
        return signal_id in self._registry

    def items(self) -> list[tuple[str, Signal]]:
        return list(self._registry.items())

    def metas(self) -> list[SignalMeta]:
        return list(self._metas)

    def meta_dicts(self) -> list[dict[str, Any]]:
        return [asdict(meta) for meta in self._metas]
