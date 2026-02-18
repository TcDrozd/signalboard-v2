from __future__ import annotations

from contextlib import asynccontextmanager
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

import os
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")

PORT = int(os.getenv("PORT", 8099))
CACHE_PATH = BASE_DIR / "data" / "cache.json"
SUBSCRIPTIONS_DB_PATH = BASE_DIR / "data" / "subscriptions.db"
BACKGROUND_SIGNALS = {"capybara_wisdom"}


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Startup order:
        # 1) create DB schema for preferences
        # 2) load persisted global signal cache
        # 3) discover signal registry
        app.state.subscriptions.init_schema()
        app.state.cache.load()
        app.state.registry.reload()
        yield

    app = FastAPI(title="SignalBoard V2", version="2.0", lifespan=lifespan)

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

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=PORT, reload=False)
