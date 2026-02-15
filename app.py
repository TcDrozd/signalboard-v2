from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from core.bg import SignalEngine
from core.cache import CacheStore
from core.registry import RegistryStore
from core.subscriptions import SubscriptionStore
from routers.admin import router as admin_router
from routers.dashboard import router as dashboard_router
from routers.subscriptions import router as subscriptions_router

BASE_DIR = Path(__file__).resolve().parent
CACHE_PATH = BASE_DIR / "data" / "cache.json"
SUBSCRIPTIONS_DB_PATH = BASE_DIR / "data" / "subscriptions.db"
BACKGROUND_SIGNALS = {"capybara_wisdom"}


def create_app() -> FastAPI:
    app = FastAPI(title="SignalBoard V2", version="2.0")

    app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
    app.state.templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

    # Shared global services.
    app.state.cache = CacheStore(CACHE_PATH)
    app.state.registry = RegistryStore()
    app.state.subscriptions = SubscriptionStore(SUBSCRIPTIONS_DB_PATH)
    app.state.engine = SignalEngine(
        cache=app.state.cache,
        registry=app.state.registry,
        background_signals=BACKGROUND_SIGNALS,
    )

    app.include_router(dashboard_router)
    app.include_router(admin_router)
    app.include_router(subscriptions_router)

    @app.on_event("startup")
    def startup() -> None:
        # Startup order:
        # 1) create DB schema for preferences
        # 2) load persisted global signal cache
        # 3) discover signal registry
        app.state.subscriptions.init_schema()
        app.state.cache.load()
        app.state.registry.reload()

    return app


app = create_app()
