# CLAUDE.md — artistaboard

Guidance for working in this repo. Inherits `~/code/CLAUDE.md` and `~/.claude/CLAUDE.md`.

## What this is

Drives a **Vestaboard** (6×22 character grid) from composable **scenes** and scheduled **jobs**. A job (clock, Muni, World Cup, NBA, Spotify, …) supplies data; a scene declares how to display it; a **pipeline** rotates scenes on a board. A React web app manages scenes/boards/pipelines; a **data layer** polls each source's full dataset into Postgres so the board paints from the DB instead of live APIs.

Delivered history is in `CHANGELOG.md`; the remaining plan (phases 3–4) in `docs/plans/`.

## Toolchain

- **mise** is the front door (`mise.toml` pins `python 3.13` + `uv`). `mise install` sets up `.venv`.
- **Python via `uv`** (`uv sync --dev`, `uv run`). Web frontend under `web/` (Node).
- Runtime deps: FastAPI + uvicorn (web), `sqlmodel` + Alembic (DB/migrations), `psycopg` (Postgres), **Procrastinate** (poller orchestration), APScheduler (paint scheduler), httpx (source fetches), argon2/itsdangerous/cryptography (auth).

## Build / test / run

```bash
mise test        # uv run pytest -q
mise lint        # ruff check + format --check   (lint-fix to auto-fix)
mise migrate     # alembic upgrade head
mise run         # scheduler daemon for the active job
mise serve       # web app (uvicorn) on http://127.0.0.1:8000
mise preview <job> / mise paint <job>   # render to terminal / send to board once
```

CLI subcommands live behind `python -m artistaboard` (`run`/`preview`/`paint`/`serve`/`poll`). The **`artistaboard poll`** daemon is the Postgres-only poller (Procrastinate periodic cron).

## Layout

- `src/artistaboard/` — `scene.py` · `pipeline.py` · `render.py` · `rotation.py` · `registry.py` · `poller.py` · `worker.py` · `client.py` (Vestaboard) · `config.py` · `font.py` · `preview.py`.
- `src/artistaboard/db/` — `engine.py` · `models.py` · `snapshots.py` (`data_snapshots` store) · `partitions.py` · `seed.py` · `migrate.py`.
- `src/artistaboard/jobs/` — one module per source (worldcup, muni, spotify, …).
- `src/artistaboard/api/` — FastAPI web app. `src/artistaboard/migrations/` — Alembic.

## Conventions

- **Immutability + explicit errors** per the inherited baseline. Scenes are stored as human-readable 6×22 character grids; glyph fonts are JSON.
- DB is **SQLite by default**, Postgres via `DATABASE_URL=postgresql+psycopg://…`. Migrations are Alembic (`mise migrate`), not `create_all`.
- Prefer `.env.example` / `config.py` (pydantic-settings) as the source of truth for env vars.

## Data layer — durable learnings

Still-live constraints from the Phase-2 build (full history in `CHANGELOG.md`):

- **Two kinds of option.** *Fetch-defining* options (Muni `stop_code`, sport `league`) define **which data** to pull → part of the snapshot's `source_key`; the poller pulls one series per key. *Display* options (World Cup `group` filter, which line/direction, single-vs-rotate) apply at **render** over the full snapshot. This is what makes re-filtering/switching free — the full data is already stored.
- **`source_key`** is a stable identity over only the fetch-defining options (`""` when none). Two entries differing merely in display options share one polled series.
- **Full payloads, not envelopes** — snapshots store the whole normalized dataset (`Job.poll()` returns everything, not the single item `fetch()` selects), so display isn't limited to what one scene computed.
- **Snapshot-miss → live fetch.** A cold start / no poller / SQLite dev falls back to one live `fetch()` so a board always paints; in steady state the poller keeps snapshots fresh and the board stays off external APIs.
- **Postgres, native RANGE partitioning** (monthly + `DEFAULT` catch-all) — *not* ClickHouse/Timescale: tiny volume, the hot query is a "latest row" point lookup (OLTP-shaped). SQLite gets a plain table. `db/partitions.py` creates months ahead and prunes (~1yr).
- **Procrastinate** is the orchestrator (Postgres-native task queue — jobs/workers/retries/periodic cron), reusing the DB we already run — **no Redis**. Runs as the standalone `artistaboard poll` daemon; applies its schema on first run.

## Git / workflow

- Remote `origin` is `https://github.com/macgngsta/artistaboard`; real base branch is **`main`** (GitHub's default still points at the stale `feat/vestaboard-controller` — pending fix).
- Branch → PR → merge; never commit to `main`. After any code change run the post-change pipeline (`mise lint`, `mise test`, review the diff). Personal repo — may auto-merge on green CI.
