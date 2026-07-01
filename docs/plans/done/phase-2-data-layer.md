# Phase 2 — persistent data layer

**Status:** done (PRs #39, #41, #44, #46).
**Goal:** pollers fetch each referenced source's full dataset into the DB on a schedule; the paint
path only reads the DB. Switch/re-filter a datasource with no re-fetch; gain freedom over what to
display; keep the board off external APIs in steady state.

```
 ┌─ artistaboard poll ─┐        ┌──── Postgres ────┐        ┌─ paint / render ─┐
 │ <source>.poll()     │─write─▶│  data_snapshots  │◀─read──│  render_entry    │
 │ (full datasets)     │  cron  │  (partitioned)   │        │  from_snapshot() │
 └─────────────────────┘        └──────────────────┘        └──────────────────┘
```

## Delivered (in order)

- **#39 storage** — `data_snapshots(source, source_key, payload jsonb, fetched_at)`, append-only.
  Dialect-aware migration `c2d3e4f50617`: Postgres RANGE-partitioned parent (monthly + DEFAULT
  catch-all) on PG, plain table on SQLite. `db/partitions.py` (create-ahead + DROP-partition
  retention, PG-only). `db/snapshots.py` (`write_snapshot`/`latest_snapshot`).
- **#41 poll layer** — `Job.poll() -> dict` full normalized dataset (all matches/games; muni
  `parse_stop_full` = all lines+directions). `jsonable()` serializer. `JobOptions.fetch_defining` +
  `registry.source_key()`.
- **#44 poller daemon** — `poller.run_poll_cycle`/`referenced_sources` (engine-agnostic, SQLite-
  tested) + a Procrastinate app/periodic task; `artistaboard poll` standalone daemon.
- **#46 render-from-snapshot** — `Job.from_snapshot(payload)` (deserialize + existing selection);
  `render_entry` reads `latest_snapshot`, live-`fetch()` fallback on miss.

## Key concepts

- **Two kinds of option.** *Fetch-defining* (Muni `stop_code`, sport `league`) → part of the
  snapshot's `source_key`; the poller pulls one series per key. *Display* (World Cup `group`, Muni
  line/direction, single-vs-rotate) → applied at render over the full snapshot. This is what makes
  re-filter/switch free.
- **Full payloads, not envelopes** — snapshots store the whole normalized dataset.

## Decisions (roads not taken)

- **Postgres, native RANGE partitioning** — not ClickHouse (~5–16M rows/yr is tiny; hot query is a
  "latest row" point lookup, OLTP-shaped). Plain PG over TimescaleDB. Append-only, 1-min resolution,
  ~1yr retention.
- **Procrastinate** orchestrator — not Huey (no Postgres broker; needs Redis/SQLite), not bare
  APScheduler (a scheduler, not an orchestrator). Reuses the Postgres we run — no Redis.
- **Snapshot-miss → live fetch** — cold start / no poller / SQLite dev falls back to one live
  fetch so a board always paints.

## Deploy note

`artistaboard poll` is a Postgres-only standalone daemon (its own k3s pod); applies Procrastinate's
schema on first run and ensures partitions on startup. Web app still defaults to SQLite; set
`DATABASE_URL=postgresql+psycopg://…` for Postgres. Cadence via `POLL_CRON` (default `* * * * *`).
