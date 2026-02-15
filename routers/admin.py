from __future__ import annotations

from fastapi import APIRouter, Query, Request

from core.bg import SignalEngine
from core.registry import RegistryStore

router = APIRouter(prefix="/api", tags=["admin"])


def _registry(request: Request) -> RegistryStore:
    return request.app.state.registry


def _engine(request: Request) -> SignalEngine:
    return request.app.state.engine


@router.get("/registry")
def api_registry(request: Request) -> dict:
    registry = _registry(request)
    metas = registry.meta_dicts()
    return {"count": len(metas), "signals": metas}


@router.get("/signals")
def api_global_signals(request: Request) -> dict:
    engine = _engine(request)
    views = engine.list_views()
    return {"count": len(views), "signals": views}


@router.post("/refresh")
async def refresh(request: Request, force: int = Query(0, ge=0, le=1)) -> dict:
    engine = _engine(request)
    return await engine.refresh(force=bool(force))


@router.post("/reload")
def reload_signals(request: Request) -> dict:
    registry = _registry(request)
    registry.reload()
    signal_ids = [meta.id for meta in registry.metas()]
    return {"ok": True, "count": len(signal_ids), "signals": signal_ids}


@router.get("/bg")
async def bg_status(request: Request) -> dict:
    engine = _engine(request)
    return await engine.bg_status()
