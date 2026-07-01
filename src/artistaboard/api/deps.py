"""Shared FastAPI dependencies: settings, DB session, and the current user."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlmodel import Session, SQLModel

from ..config import Settings
from ..db import User, get_session


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings


SessionDep = Annotated[Session, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings_dep)]


def get_owned[T: SQLModel](session: Session, model: type[T], obj_id: str, user_id: str, *, not_found: str) -> T:
    """Fetch a row by id, 404ing if it's missing or not owned by the user. For
    resources with plain per-owner access (boards, pipelines); scenes differ
    (system scenes are world-readable) and keep their own check."""
    obj = session.get(model, obj_id)
    if obj is None or obj.owner_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, not_found)
    return obj


def current_user(request: Request, session: SessionDep) -> User:
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not authenticated")
    user = session.get(User, user_id)
    if user is None or not user.is_active:
        request.session.clear()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not authenticated")
    return user


CurrentUser = Annotated[User, Depends(current_user)]
