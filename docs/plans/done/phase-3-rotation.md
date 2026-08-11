# Phase 3 — generic rotation primitive

**Status:** done (shipped as #55).
**Goal:** extract "show a single item vs rotate a set, and highlight the live/priority one" out of
individual jobs into a **reusable primitive applied over the full snapshot**, so any entry/group
can be configured to rotate — unifying World Cup's internal rotation with Muni multi-line/direction.

## Why now

The full dataset is already in `data_snapshots` (Phase 2), so "which item(s) to show" is a pure
**display** concern over stored data — no fetch involved. Today this logic is buried per-job
(`worldcup.select_match` + `rotation.select` with live-score preemption; muni filters to one line).

## Tasks

- `rotation-primitive` — a reusable selector over a list of items with: single-vs-rotate, per-item
  dwell, `max_items`, and an optional "live/priority" item that preempts. Generalize the existing
  `rotation.select` (which already does score-change preemption for one job).
- `display-options` — surface the display knobs as entry `Options` (single vs multi, highlight-live,
  how many per line, which directions) that filter/shape the full snapshot at render.
- `wire-sources` — apply the primitive in `from_snapshot`/render for World Cup (rotate matches,
  highlight live) and Muni (multi-line / both directions), replacing the per-job selection.

## Decisions (to confirm during build)

- Where the rotation state lives across paints (reuse `BoardRun.rotation_state` / `RotationState`).
- Whether rotation is configured per entry or per "group" (ties into Phase 4).

## Open questions

- How rotation interacts with the pipeline's own entry advance (nested cadences).
