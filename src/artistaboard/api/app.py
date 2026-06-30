"""FastAPI application factory.

``create_app(settings)`` wires the engine to ``settings.database_url`` and, on
startup, creates tables and seeds the bundled scenes as system templates. Auth state
rides in a signed session cookie (Starlette ``SessionMiddleware``).
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlmodel import Session
from starlette.middleware.sessions import SessionMiddleware

from ..config import Settings, get_settings
from ..db.engine import get_engine, init_engine
from ..db.migrate import run_migrations
from ..db.seed import seed_system_scenes
from ..worker import BoardManager
from .routers import auth, boards, pipelines, preview, scenes


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    init_engine(settings.database_url)
    manager = BoardManager(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        run_migrations(settings.database_url)  # upgrade to head (creates schema on a fresh DB)
        with Session(get_engine()) as session:
            seed_system_scenes(session, settings)
        await manager.reconcile()  # resume any board that was running
        yield
        await manager.shutdown()

    app = FastAPI(title="artistaboard", lifespan=lifespan)
    app.state.settings = settings
    app.state.manager = manager
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret,
        same_site="lax",
        https_only=False,
    )
    app.include_router(auth.router)
    app.include_router(scenes.router)
    app.include_router(preview.router)
    app.include_router(boards.router)
    app.include_router(pipelines.router)

    @app.get("/health", tags=["meta"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
