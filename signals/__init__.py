# signals/__init__.py
from __future__ import annotations

import importlib
import pkgutil
from typing import Dict

from .base import Signal

def load_signals() -> Dict[str, Signal]:
    """
    Auto-discover signals in this package.
    Each module must expose SIGNAL = <Signal instance>.
    """
    registry: Dict[str, Signal] = {}

    package_name = __name__  # "signals"
    for mod in pkgutil.iter_modules(__path__):
        # Skip internal modules
        if mod.name.startswith("_") or mod.name in ("base",):
            continue

        module = importlib.import_module(f"{package_name}.{mod.name}")

        sig = getattr(module, "SIGNAL", None)
        if sig is None:
            continue  # allow helper modules later

        sig_id = getattr(sig, "meta", None).id if getattr(sig, "meta", None) else None
        if not sig_id:
            raise ValueError(f"{module.__name__}.SIGNAL missing meta.id")

        if sig_id in registry:
            raise ValueError(f"Duplicate signal id: {sig_id}")

        registry[sig_id] = sig

    return registry
