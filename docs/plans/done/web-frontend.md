# Web frontend

**Goal:** a self-hosted, multi-user web UI — design scenes, manage boards, assemble/run
pipelines, and eventually manage the data-layer jobs — served same-origin by FastAPI.

The core app and the graphical scene designer are **shipped** (CHANGELOG "Web frontend"). This
plan tracks what remains. Health/quality follow-ups touching `web/` are tracked as `review-*`
rows in the coordination tracker (notably `review-web-ci-tests`, `review-422-error-contract`,
`review-schema-drift-ci`).

## Remaining tasks

- `jobs-mgmt` — **Jobs management UI.** The Jobs page (#43) is read-only. Grow it into management:
  data freshness (latest snapshot age per source), a manual "poll now", and per-source status.
  **Blocked on** the data-layer HTTP surface — spec'd in
  [`jobs-management-api.md`](jobs-management-api.md) (`GET /data/sources`, `POST /data/poll`); build
  the UI once those endpoints land and the client is regenerated.
- `display-options-ui` — When backend **phase 3** (generic rotation primitive) lands, surface its
  display knobs (single-vs-rotate, highlight-live, which group/lines) in the per-entry options
  form (extends #36). Pairs with `docs/plans/active/phase-3-rotation.md`.
- `nested-pipelines-ui` — UI for backend **phase 4**: a pipeline entry pointing at another pipeline
  (`source_type="pipeline"` + `sub_pipeline_id`), with a cycle guard. Pairs with
  `docs/plans/active/phase-4-nested-pipelines.md`.
- `rule-color-builder` — Graphical editor for `{rule: leader|imminent}` colors in `ColorPicker`
  (currently read-only with a "clear"). Low priority; advanced/rare.
- `bundle-split` — Route-level code-splitting to shrink the single ~370 kB JS chunk. Perf nicety.

## Decisions

- **Hash router** is load-bearing: the API owns top-level paths, so path-based client routes would
  collide same-origin. Do not switch to `BrowserRouter`.
- **Typed client generated** from `/openapi.json` (`npm run gen:api`); never hand-edit
  `web/src/api/schema.d.ts`.
- **`POST /preview` is the only scene renderer** — no binding/transform logic in JS.
- Frontend's only backend edits are additive: CORS (dev) + `StaticFiles` serve of `web/dist` (prod).

## Open questions

- What endpoints will the data layer expose for snapshot freshness / manual poll? (Gates
  `jobs-mgmt`.)
- Should pipeline scene-entries show a data-freshness indicator from the data layer?
