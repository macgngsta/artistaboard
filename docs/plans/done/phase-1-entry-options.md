# Phase 1 — typed per-entry job options

**Status:** done (PR #33).
**Goal:** a job is configurable per pipeline entry, not just via one process-global env var — two
boards (or two entries) can run World Cup with different groups, or Muni with different lines/stops.

## Delivered

- `PipelineEntry.options` JSON column (migration `a1c2e3f40506`).
- Each `Job` declares a pydantic `Options` model; clean field names map to `Settings` fields via
  `override_map`. Unset fields fall back to global `Settings` (don't clobber the deployment default).
- Validated on write (unknown key / bad type / bad value → 422); applied as
  `build_job(name, settings, **overrides)` at render.
- `GET /jobs` exposes each job's options JSON Schema to drive a form UI.

Per-job knobs: World Cup (`group`, `rotate_seconds`, `live_only`), Muni (`stop_code`, `line`,
`color`), clock (`tz_label`, `color`), sports (`league`, `rotate_seconds`).

## Decisions

- **Unset = inherit, not clobber** — options omit `None` fields from overrides, so a per-entry
  option left blank falls back to the global `Settings` default.
- **Typed schema per job** (not a freeform bag) — enables write-time validation and an
  auto-generated form UI.
