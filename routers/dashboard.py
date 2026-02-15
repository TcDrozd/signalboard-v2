from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from starlette.templating import Jinja2Templates

from core.bg import SignalEngine
from core.subscriptions import SubscriptionStore

router = APIRouter(tags=["dashboard"])


def _templates(request: Request) -> Jinja2Templates:
    return request.app.state.templates


def _engine(request: Request) -> SignalEngine:
    return request.app.state.engine


def _store(request: Request) -> SubscriptionStore:
    return request.app.state.subscriptions


@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    # Server-rendered shell; signal data is loaded client-side through API routes.
    return _templates(request).TemplateResponse("dashboard.html", {"request": request})


@router.get("/api/users/{username}/dashboard")
def user_dashboard(username: str, request: Request) -> dict:
    store = _store(request)
    if not store.user_exists(username):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")

    subscribed_ids = set(store.list_subscriptions(username))
    views = _engine(request).list_views(subscribed_ids)
    return {"username": username, "count": len(views), "signals": views}
