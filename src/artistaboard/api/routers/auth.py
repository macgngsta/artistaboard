"""Auth: register, login, logout, me. Session lives in a signed httpOnly cookie.

Registration is open for the very first account (self-host bootstrap → owner) and
thereafter gated by ``settings.allow_signup``.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from sqlmodel import select

from ...db import User
from ..deps import CurrentUser, SessionDep, SettingsDep
from ..schemas import LoginIn, RegisterIn, UserOut
from ..security import hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


def _login(request: Request, user: User) -> None:
    request.session["user_id"] = user.id


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(body: RegisterIn, request: Request, session: SessionDep, settings: SettingsDep) -> User:
    has_users = session.exec(select(User.id).limit(1)).first() is not None
    if has_users and not settings.allow_signup:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "registration is closed")
    if session.exec(select(User).where(User.email == body.email)).first() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "email already registered")
    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        display_name=body.display_name,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    _login(request, user)
    return user


@router.post("/login", response_model=UserOut)
def login(body: LoginIn, request: Request, session: SessionDep) -> User:
    user = session.exec(select(User).where(User.email == body.email)).first()
    if user is None or not verify_password(user.password_hash, body.password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "account is disabled")
    _login(request, user)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request) -> None:
    request.session.clear()


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> User:
    return user
