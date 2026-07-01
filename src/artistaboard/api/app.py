"""FastAPI application factory.

``create_app(settings)`` wires the engine to ``settings.database_url`` and, on
startup, creates tables and seeds the bundled scenes as system templates. Auth state
rides in a signed session cookie (Starlette ``SessionMiddleware``).
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session
from starlette.middleware.sessions import SessionMiddleware

from ..config import Settings, get_settings
from ..db.engine import get_engine, init_engine
from ..db.migrate import run_migrations
from ..db.partitions import ensure_partitions, prune_partitions
from ..db.seed import seed_system_scenes
from ..worker import BoardManager
from .routers import auth, boards, jobs, pipelines, preview, scenes


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    init_engine(settings.database_url)
    manager = BoardManager(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        run_migrations(settings.database_url)  # upgrade to head (creates schema on a fresh DB)
        with Session(get_engine()) as session:
            seed_system_scenes(session, settings)
            # Snapshot partitions must exist before the poller writes; prune expired ones
            # (both no-op on SQLite). Runtime creation covers month rollover past migration.
            ensure_partitions(session)
            prune_partitions(session)
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
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,  # required to send the session cookie cross-origin
            allow_methods=["*"],
            allow_headers=["*"],
        )
    app.include_router(auth.router)
    app.include_router(scenes.router)
    app.include_router(preview.router)
    app.include_router(boards.router)
    app.include_router(pipelines.router)
    app.include_router(jobs.router)

    @app.get("/health", tags=["meta"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    # Serve the built SPA same-origin when present. Mounted last so it never
    # shadows the API routers, /health, or /openapi.json above it. The frontend
    # uses a hash router, so only "/" and static assets are ever requested here.
    if settings.web_dist_dir.is_dir():
        app.mount("/", StaticFiles(directory=settings.web_dist_dir, html=True), name="spa")

    return app
