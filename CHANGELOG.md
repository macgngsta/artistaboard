# Changelog

Distilled history of what's been delivered on `main`, newest first. The remaining plan lives in `docs/plans/`; still-live constraints in `CLAUDE.md`; live cross-session status (open work only) in the coordinate tracker at `~/code/claude-sync/coordination/artistaboard/progress.md`.

## Data layer — poll into Postgres, paint reads the DB (complete)

Background pollers fetch each referenced source's **full** dataset into Postgres on a schedule; the paint path only ever **reads the DB** (live-fetch fallback on a miss). Re-filtering or switching a datasource needs no re-fetch.

- **#46** render from `data_snapshots` (3/3) — `from_snapshot` deserializes the full payload and applies the job's selection; `render_entry` reads `latest_snapshot`, falls back to a live `fetch()` on a miss.
- **#44** Procrastinate poller daemon (2b/3) — the `artistaboard poll` daemon; periodic cron over the distinct `(source, source_key)` pairs referenced by running boards; one source's failure is isolated.
- **#41** source poll layer (2a/3) — `Job.poll()` returns each source's full normalized dataset; `source_key` splits fetch-defining from display options.
- **#39** `data_snapshots` time-series store (1/3) — append-only snapshots; Postgres RANGE-partitioned by month (SQLite plain table); create-ahead + prune (~1yr retention).
- **#38** Windows 11 WSL2 + k3s single-node dev-server installer.
- **#37** psycopg driver for Postgres support.

## Per-entry job options & pipelines (Phase 1, complete)

- **#36** per-entry job options in the pipeline editor (+ gitignore tsbuildinfo).
- **#33** typed per-entry job options — `PipelineEntry.options` JSON, per-job pydantic `Options`, validated on write, applied as `build_job(**overrides)`; unset fields fall back to global `Settings`.
- **#31** dynamic data binding for scene pipeline entries.
- **#29** enforce non-looping pipelines.

## Web app & scene designer (complete)

- **#47** designer color-name dropdowns, region-aware sample data, relayout.
- **#45** light/dark mode toggle.
- **#43** read-only Jobs catalogue page.
- **#42** always-on preview auto-seeds missing data keys; region-type presets + guidance.
- **#40** graphical scene designer — paint regions, swatch color picker, always-on preview.
- **#35** React web frontend for scenes, boards, and pipelines.
- **#28** web app Phase 2 — pipelines running on a board.
- **#27** web app Phase 1 — DB, auth, scene CRUD, live preview.

## Scenes & jobs foundation (complete)

- **#34** muni badge letter white; arrival list led by soonest.
- **#32** world cup live-only pinning, red leader scheme, split stoppage clock.
- **#30** Alembic migrations (baseline) replacing `create_all`.
- **#26** shared rotation selector; `Scene.from_dict` + `build_job` overrides.
- **#25** drive the World Cup scoreboard from ESPN live data.
- **#24** rename package `vestaboard` → `artistaboard`.
- **#22** generalize the Muni scene into a shared transit layout.
- **#21** declarative scenes — jobs supply data, scenes declare display.
- **#1–#20** initial controller: scenes as 6×22 character grids, JSON glyph fonts, clock/muni/world-cup/nba/spotify jobs, APScheduler daemon, ruff CI.
