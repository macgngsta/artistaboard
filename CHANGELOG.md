# Changelog

Distilled record of delivered work, newest first. Open/in-flight work lives in the cross-session
tracker (`claude-sync/coordination/artistaboard/progress.md`); plans of record are in
`docs/plans/`.

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
