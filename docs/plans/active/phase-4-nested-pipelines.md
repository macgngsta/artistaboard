# Phase 4 — nested pipelines (compose groups)

**Status:** active (not started, after Phase 3).
**Goal:** string groups together — "Muni group + World Cup group + clock" — by letting a pipeline
entry point at another pipeline.

## Tasks

- `nested-entry` — `PipelineEntry.source_type = "pipeline"` + `sub_pipeline_id` (migration + API
  schema + validation).
- `recursive-runner` — the pipeline runner recurses into a sub-pipeline; the parent entry's
  `duration_seconds` bounds the sub-pipeline's window, and it rotates its own children within it.
- `tree-rotation-state` — `BoardRun.rotation_state` becomes a small tree so nested rotation resumes
  across restarts.
- `cycle-guard` — reject pipelines that reference themselves (directly or transitively). Precedent:
  the non-looping-pipeline enforcement (#29).

## Decisions (to confirm)

- Whether a "group" is just a nested pipeline (chosen earlier) vs a first-class reusable entity —
  current plan is nested pipelines.

## Open questions

- Dwell semantics when a sub-pipeline's total cycle exceeds the parent entry's `duration_seconds`.
