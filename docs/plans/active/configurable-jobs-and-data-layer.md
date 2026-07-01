# Configurable jobs & the data layer

**Goal:** every "job" (World Cup, Muni, clock, …) configurable **per board**, backed by a **persistent data layer** so the board paints from a database instead of calling APIs live.

**Status:** Phases 1–2 shipped (see `CHANGELOG.md`). Phases 3–4 open.

## Done (see CHANGELOG)

- **Phase 1 — typed per-entry job options** (#33/#31/#29/#36). A job is configurable per pipeline entry, not one global env var; unset options fall back to global `Settings`.
- **Phase 2 — persistent data layer** (#39/#41/#44/#46). Poll → Postgres `data_snapshots` → paint reads the DB. Two kinds of option (fetch-defining vs display), `source_key`, snapshot-miss → live fetch. Durable invariants in `CLAUDE.md`.

## Phase 3 — generic rotation primitive (next)

Today "which item to show / rotate / highlight-live" lives inside each job (World Cup's `select` + live-score preemption). Extract it into a **reusable primitive** applied over the full snapshot: any entry/group shows a single item or rotates a set, with an optional live/priority item that preempts. Now that the full dataset is in the DB, selection is a pure display concern over stored data.

- `rotation-primitive` — extract the select/live-preempt logic into a shared primitive.
- `muni-rotate` — apply it to Muni multi-line/direction.
- `worldcup-rotate` — fold World Cup's internal rotation into the same primitive.

## Phase 4 — nested pipelines (planned)

`PipelineEntry.source_type = "pipeline"` + `sub_pipeline_id` so a pipeline entry can point at another pipeline ("Muni group + World Cup group + clock" = a top pipeline of three entries, two nested). The runner recurses (the entry's `duration_seconds` bounds the sub-pipeline's window); needs a cycle guard (precedent: the non-looping-pipeline enforcement, #29) and a small tree `rotation_state`.

## Loose ends

- **Deploy:** the `artistaboard poll` pod isn't in the k3s manifests yet — coordinate with whoever owns deployment.
- **Hygiene:** the `feat/data-layer-snapshots` branch is stale (its work merged via #39/#41) — safe to `git push origin --delete feat/data-layer-snapshots`. GitHub still points the repo default at the stale `feat/vestaboard-controller`; the real base is `main`.
