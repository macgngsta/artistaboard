# Changelog

Distilled record of delivered work, newest first. Open/in-flight work lives in the cross-session
tracker (`claude-sync/coordination/artistaboard/progress.md`); plans of record are in
`docs/plans/`.

## Local CI for the merge gate (complete)

- **#76** `local-ci-mise` — add a `ci` mise task mirroring `ci.yml` + `web.yml`'s `web` job (uv sync,
  ruff, pyright, pytest, web typecheck/lint/test/build) so `claude-sync`'s `local-ci.sh` runs it on a
  PR head and posts the `local-ci` status ci-watch's merge gate reads (macgngsta/* Actions never run).

## Nested pipelines & config decomposition (complete)

- **#74** `settings-decompose` — split the `Settings` god object into per-job nested `BaseSettings`
  models (`WorldCupConfig`, `MuniConfig`, …); `Settings` now holds only infra. Env var names unchanged.
- **#73** `nested-pipelines` — a pipeline entry can embed another pipeline, composing groups
  (e.g. "Muni group + World Cup group + clock"). Delivers `phase-4-nested-pipelines`.

## CI & tooling (complete)

- **#72** `api-drift-uv-lock` — stop the backend in the api-drift job to fix a uv cache-lock hang.
- **#71** `pyright-gate` — add a pyright type-check CI gate (basic, tuned for ORM noise).
- **#70** `changelog-graduate` — graduate delivered PRs (#53–#69) into this CHANGELOG.

## Health, hardening & CI — repo-review backlog (complete)

Sustainability pass from the repository review: security, ops, test determinism, dedup, and CI
gates. Findings tracked in the cross-session tracker.

- **#69** `schema-drift-dedupe` — drop the duplicate schema-drift workflow, keeping #67's api-drift gate.
- **#68** `schema-drift-gate` — CI fails on a stale typed web client; resynced `schema.d.ts`.
- **#67** `api-drift-gate` — CI regenerates the API client and fails if the committed `schema.d.ts` is stale.
- **#65** `entry-idchurn` — `PUT /pipelines/{id}` updates entries **in place** by position, so entry ids survive a rename (a running board's `BoardRun.current_entry_id` no longer breaks).
- **#64** `espn-dedup` — shared ESPN scoreboard envelope helpers; removes the parallel parsers across `worldcup` + `sport_{high,low}scores`.
- **#63** `get-owned` — generic `get_owned()` ownership dependency dedups the boards/pipelines authz guard (scenes keep their world-readable-system check).
- **#62** `http-retry` — shared httpx `get_json` helper with bounded retry + `raise_for_status`.
- **#61** `scheduler-flaky` — deterministic scheduler test (fake scheduler, no wall-clock) + parallel-safe worker fixture (fixture-owned sends).
- **#59** `migration-roundtrip` — alembic upgrade → downgrade → upgrade round-trip test (proves downgrades and re-runnability).
- **#58** `compose-ops` — Docker: named SQLite state volume, non-root `app` user, `HEALTHCHECK`.
- **#57** `preview-422-contract` — structured preview 422 `{message, missing_key}`; the client prefers the structured key (regex only a legacy fallback).
- **#56** `secret-guard` — reject the insecure dev secret outside dev (`APP_ENV` guard); protects cookie signing + board-key encryption.
- **#53** `simplify-pass` — dedup helpers, fix the `list_pipelines` N+1, drop dead code (quality-only).

## Jobs management + rotation (complete)

- **#66** `web-jobs-mgmt` — Jobs page gains a **Data sources** freshness section (`useDataSources`, 30s poll) + a **Poll now** button (`usePollNow` → `POST /data/poll`); `formatAge`/`isStale` helpers.
- **#60** `datalayer-http-api` — `GET /data/sources` + `POST /data/poll`, thin wrappers over the poller/snapshot layer scoped to the current user's boards.
- **#55** `rotation-primitive` — stateless clock-derived `rotate_index` (advances across paints with no persisted cursor) + a `single` display option on World Cup/sport + durable `BoardRun.last_frame_hash` dedup. (phase-3 part 1 of 2.)

## Web frontend — scene designer & UI (complete)

React 19 + Vite + TS SPA in `web/`, served same-origin by FastAPI. Typed client generated from
`/openapi.json`; `POST /preview` is the sole scene renderer. Plan: `docs/plans/active/web-frontend.md`.

- **#52** `web-ci-tests` — Vitest + a `web` CI job (typecheck/lint/test/build); 18 tests over codes/variables/store/`previewWithAutoSeed`. `web/` errors no longer merge green.
- **#48** `region-dropdown` — Region editor header is a dropdown (badge + "Region X") to switch regions instead of targeting small grid badges.
- **#47** `designer-color-layout` — Color-by-name dropdowns (swatch + word) for color sample vars and solid region colors; sample-data fields show which region uses each variable; relayout (region options under the painter, sample data under the preview).
- **#45** `light-mode` — Light/dark theme toggle (persisted) by inverting the Tailwind `neutral` scale under `.light`; board depictions stay fixed-dark.
- **#43** `jobs-catalogue` — Read-only Jobs page listing built-in jobs + their typed options from `GET /jobs`.
- **#42** `preview-fix-presets` — `previewWithAutoSeed` seeds any missing data key the server reports and retries (fixes `cannot render scene: 'X'`); region-type presets + guidance.
- **#40** `graphical-designer` — Graphical scene designer: click-drag paint regions on a 6×22 grid, add/remove regions, swatch color picker, always-on live preview.

## Data layer — paint reads the DB, not APIs (complete)

Pollers fetch each referenced source's full dataset into Postgres on a schedule; the paint path
only reads the DB. Switch/re-filter a datasource with no re-fetch; board stays off external APIs in
steady state. Plan: `docs/plans/done/phase-2-data-layer.md`.

- **#46** `render-from-snapshot` — `render_entry` reads the latest `data_snapshot` via
  `Job.from_snapshot(payload)` (deserialize + the job's existing selection), falling back to a live
  `fetch()` on a miss. Boards paint from the DB.
- **#44** `poller-daemon` — `artistaboard poll`, a Procrastinate-orchestrated periodic task
  (Postgres-backed, no Redis) that discovers the `(source, source_key)` pairs referenced by running
  boards and writes a snapshot per source; per-source failures isolated.
- **#41** `poll-layer` — `Job.poll()` returns each source's full normalized dataset;
  `JobOptions.fetch_defining` + `registry.source_key()` split fetch-defining vs display options.
- **#39** `snapshots-storage` — `data_snapshots` table (append-only; Postgres RANGE-partitioned
  monthly + retention, plain table on SQLite); `write_snapshot` / `latest_snapshot`.

## Configurable jobs (complete)

- **#33** `entry-options` — typed per-entry job `Options` (`PipelineEntry.options` JSON), validated
  on write and applied as `build_job` overrides; `GET /jobs` exposes each job's options schema.
  Plan: `docs/plans/done/phase-1-entry-options.md`.

## Foundations (pre-initiative)

Web app + jobs the above builds on: React frontend (#35), pipeline editor options (#36), psycopg
Postgres driver (#37), pipelines-on-a-board (#28), Alembic baseline (#30), dynamic scene data
binding (#31), World Cup live pinning (#32).
