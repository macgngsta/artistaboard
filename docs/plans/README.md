# Plans of record

Lifecycle by directory — `active/` (in flight or next), `done/` (delivered), `cancelled/` (dropped,
with a one-line reason at top). Delivered detail is distilled in the repo `CHANGELOG.md`; live
cross-session status is in `claude-sync/coordination/artistaboard/progress.md`.

The initiative: make "jobs" **configurable per board** (per-entry options, a persistent data layer,
generic rotation, and composition). Default/integration branch is **`main`**.

## active
- [`phase-3-rotation.md`](active/phase-3-rotation.md) — generic rotation primitive (single-vs-rotate,
  highlight-live) over the full snapshot. Next.
- [`phase-4-nested-pipelines.md`](active/phase-4-nested-pipelines.md) — nested pipelines to compose
  groups. After Phase 3.

## done
- [`phase-1-entry-options.md`](done/phase-1-entry-options.md) — typed per-entry job options (#33).
- [`phase-2-data-layer.md`](done/phase-2-data-layer.md) — persistent data layer; paint reads the DB
  (#39, #41, #44, #46).
