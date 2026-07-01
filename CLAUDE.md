# artistaboard — agent guide

Vestaboard controller: composable scenes + jobs, a web app, and a persistent data layer. See
`README.md` for the domain model, `CHANGELOG.md` for what's shipped, and `docs/plans/` for plans of
record. Cross-session status: `claude-sync/coordination/artistaboard/progress.md`.

## Workflow

- Branch off **`main`** → PR → merge. Personal repo: may auto-merge once CI (GitHub Actions) is
  green. Never commit to `main`.
- Post-change: `uv run ruff check src tests` + `uv run ruff format --check src tests` + `uv run
  pytest -q`. All must pass before pushing.

## Durable learnings (honor these)

- **Base branch is `main`.** `feat/vestaboard-controller` diverged at repo-init and is stale (and is
  still the GitHub default pointer) — do **not** target it. Real integration branch is `main`.
- **After a squash-merge, start each new PR from a fresh branch off `origin/main`** — don't reuse the
  merged branch (its history was squashed; pushing to it re-creates a stray branch).
- **SQLite-first, Postgres opt-in.** `DATABASE_URL` defaults to SQLite and CI runs on it; Postgres is
  opt-in (`postgresql+psycopg://…`). Any migration using Postgres-only DDL (e.g. RANGE partitioning)
  **must be dialect-aware** — branch on `op.get_bind().dialect.name`, with a plain-table path for
  SQLite. See migration `c2d3e4f50617`.
- **The poller (`artistaboard poll`) is Postgres-only** (Procrastinate). It applies Procrastinate's
  schema on first run and ensures `data_snapshots` partitions on startup; runs as its own daemon.
- **Snapshot series identity** = `registry.source_key(name, options)`, derived from *fetch-defining*
  options only (`JobOptions.fetch_defining`). The poller write and the render read must use the same
  derivation, or a board reads the wrong (or no) series.
- **Options split:** *fetch-defining* options (Muni `stop_code`, sport `league`) pick which data to
  poll; *display* options (World Cup `group`, Muni `line`) filter the full snapshot at render. Put
  new options on the right side.
- **Paint reads the DB.** `render_entry` reads `latest_snapshot` and falls back to a live `fetch()`
  only on a miss — so in prod the poller must be running to keep snapshots fresh; without it, boards
  silently fall back to live fetches.
- **Jobs contract:** a pollable job implements `poll()` (full dataset), `from_snapshot(payload)`
  (deserialize + select, mirroring `fetch()`'s shape), and its `Options`. `poll()`/`from_snapshot`
  are inverses of `jsonable()`.
