# Jobs management API (data-layer HTTP surface)

**Goal:** expose the data layer over HTTP so the web Jobs page can show **data freshness** per
source and trigger a **manual poll** — unblocking `web-jobs-mgmt`. Today the data layer (phase 2)
is storage + poller + render with **no HTTP surface**.

This is a **backend** task (data-layer owner). The endpoints are thin wrappers over existing,
already-unit-tested pure functions — no new domain logic.

## Reuse (already exists)

- `poller.referenced_sources(session) -> list[SourceRef]` — distinct `(source, source_key, options)`
  referenced by **running** boards' pipelines (`poller.py:38`).
- `snapshots.latest_snapshot(session, source, source_key) -> DataSnapshot | None` — newest reading;
  has `fetched_at`, `payload` (`db/snapshots.py`).
- `poller.run_poll_cycle(session, settings) -> PollResult` — poll every referenced source once,
  per-source failures isolated; returns `{polled: [...], failed: [(source, err)]}` (`poller.py:63`).
- `GET /jobs` — already lists jobs + option schemas (`routers/jobs.py`).

## Proposed endpoints (new `routers/data.py`, `CurrentUser`-guarded)

### `GET /data/sources`
Active data series with freshness — the core of the management view.
```
[ { "source": "world_cup", "source_key": "group=C",
    "last_fetched_at": "…Z"|null, "age_seconds": 42|null, "has_data": true } ]
```
Impl: `referenced_sources(session)` → for each ref, `latest_snapshot(...)` → shape the row.
**Ownership:** `referenced_sources` is global; scope it to the current user's boards (filter
`BoardRun`→`Board.owner_id == user.id`) — add an owner-filtered variant or a param.

### `POST /data/poll`
Manual poll of all referenced sources now (a kick; the Postgres daemon still polls on schedule —
and on SQLite/dev this is the only poll path).
```
-> { "polled": ["clock:", "world_cup:group=C"], "failed": [["muni", "no stop_code"]] }
```
Impl: `run_poll_cycle(session, settings)`. Owner-only; consider a short rate-limit.

### (optional, later)
- `GET /data/sources/{source}/latest?source_key=` → latest raw `payload` for inspection/debug.
- `GET /data/poller` → daemon status (`last_cycle_at`, `interval_seconds`, running?). Needs the
  poller to record heartbeat/last-cycle state — not tracked today; defer.

## Frontend follow-up (`web-jobs-mgmt`, this session's lane)

Once the above ships: regenerate the client (`npm run gen:api`); on the Jobs page, per job show its
active series + freshness ("polled 2m ago" / "never") and a **Poll now** button (`POST /data/poll`),
with results toasted. New TanStack Query hooks `useDataSources` (poll every ~30s) + `usePollNow`.

## Decisions / open questions

- Freshness is **per `(source, source_key)`**, not per job — one job can back several series.
- Should `POST /data/poll` be all-sources only, or also `POST /jobs/{name}/poll?source_key=` for a
  single series? (Start all-sources; add targeted later.)
- Multi-user scoping of `referenced_sources` — confirm the owner filter with the data-layer owner.
