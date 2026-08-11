# Plans of record

Lifecycle by directory — `active/` (in flight or next), `done/` (delivered), `cancelled/` (dropped,
with a one-line reason at top). Delivered detail is distilled in the repo `CHANGELOG.md`; live
cross-session status is in `claude-sync/coordination/artistaboard/progress.md` (a local file, not
part of this repo).

The initiative: make "jobs" **configurable per board** (per-entry options, a persistent data layer,
generic rotation, and composition). Default/integration branch is **`main`**.

## active
_None — the configurable-jobs initiative (phases 1–4 + the web UI and data-layer API) has shipped._

## done
- [`phase-1-entry-options.md`](done/phase-1-entry-options.md) — typed per-entry job options (#33).
- [`phase-2-data-layer.md`](done/phase-2-data-layer.md) — persistent data layer; paint reads the DB
  (#39, #41, #44, #46).
- [`phase-3-rotation.md`](done/phase-3-rotation.md) — generic rotation primitive (single-vs-rotate,
  highlight-live) over the full snapshot (#55).
- [`phase-4-nested-pipelines.md`](done/phase-4-nested-pipelines.md) — nested pipelines to compose
  groups; an entry can point at another pipeline (#73).
- [`web-frontend.md`](done/web-frontend.md) — self-hosted web UI: scene designer, boards, pipelines,
  jobs management (#35, #40–#66).
- [`jobs-management-api.md`](done/jobs-management-api.md) — data-layer HTTP surface: freshness +
  manual poll (#60, #66).
