from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from core.registry import RegistryStore
from core.subscriptions import SubscriptionStore
from models.subscription import SubscriptionChange
from models.user import UserCreate

router = APIRouter(prefix="/api", tags=["subscriptions"])


def _store(request: Request) -> SubscriptionStore:
    return request.app.state.subscriptions


def _registry(request: Request) -> RegistryStore:
    return request.app.state.registry


def _require_user(store: SubscriptionStore, username: str) -> None:
    if not store.user_exists(username):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")


@router.get("/users")
def list_users(request: Request) -> dict:
    users = _store(request).list_users()
    return {"count": len(users), "users": users}


@router.post("/users", status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, request: Request) -> dict:
    created = _store(request).create_user(payload.username)
    return {"username": payload.username, "created": created}


@router.get("/users/{username}/subscriptions")
def list_subscriptions(username: str, request: Request) -> dict:
    store = _store(request)
    _require_user(store, username)
    signals = store.list_subscriptions(username)
    return {"username": username, "signals": signals, "count": len(signals)}


@router.post("/users/{username}/subscriptions")
def subscribe(username: str, payload: SubscriptionChange, request: Request) -> dict:
    store = _store(request)
    _require_user(store, username)

    registry = _registry(request)
    if not registry.has_signal(payload.signal_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="signal not found")

    created = store.subscribe(username, payload.signal_id)
    signals = store.list_subscriptions(username)
    return {
        "username": username,
        "signal_id": payload.signal_id,
        "subscribed": created,
        "signals": signals,
    }


@router.delete("/users/{username}/subscriptions/{signal_id}")
def unsubscribe(username: str, signal_id: str, request: Request) -> dict:
    store = _store(request)
    _require_user(store, username)
    removed = store.unsubscribe(username, signal_id)
    signals = store.list_subscriptions(username)
    return {
        "username": username,
        "signal_id": signal_id,
        "removed": removed,
        "signals": signals,
    }
