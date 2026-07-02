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
- **Per-job config lives in the job module**, not `Settings`. Each job defines a nested
  `BaseSettings` (env-prefixed, e.g. `WORLDCUP_*` → `WorldCupConfig`) exposed as a `Settings` field
  (`settings.worldcup.group`); `Settings` holds only infra. Jobs read `self.settings.<attr>.<field>`
  and set `config_attr` so `build_job` splices per-entry overrides into a copy of that sub-config
  (singleton untouched). Env var names are unchanged. To break the `config → jobs → base → config`
  cycle, `jobs/base.py` imports `Settings` only under `TYPE_CHECKING`. Add a new job's knobs to its
  own config, never to the global.

### Frontend (`web/`)

- **Dev:** `cd web && npm install && npm run gen:api && npm run dev` (Vite `:5173`, proxies the API).
  **Prod:** `npm --prefix web run build` → `web/dist`, which `serve` hosts same-origin. Pre-push:
  `npm run typecheck && npm run lint && npm run build` (CI does *not* run these yet — see
  `review-web-ci-tests`).
- **Hash router** (`createHashRouter`) is intentional: the API owns top-level paths (`/scenes`,
  `/boards`, `/pipelines`), so path-based client routes collide same-origin. Don't use `BrowserRouter`.
- **Typed client is generated** from `/openapi.json` (`npm run gen:api`) — never hand-edit
  `web/src/api/schema.d.ts`; regenerate after any backend API change.
- **`POST /preview` is the only scene renderer.** Never reimplement binding/transform/color in JS.
  `previewWithAutoSeed` seeds missing data keys by regex-parsing the 422 message (fragile — see
  `review-422-error-contract`).
- **zustand v5:** never return a fresh array/object from a `useSceneEditor` selector — a new
  reference each call loops `useSyncExternalStore` → React #185. Select stable state, derive in the body.
- **Board depictions stay dark in both themes** (`BoardGrid` + painter grid use fixed dark colors);
  everything else themes via the inverted `neutral` scale under `.light`.
- **Board R/W key is write-only** — never store or echo it client-side (only `has_key` + `rw_key_last4`
  come back). The frontend's only backend edits are additive: `CORSMiddleware` + `StaticFiles`.
