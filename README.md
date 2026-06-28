# vestaboard

Drive a [Vestaboard](https://www.vestaboard.com/) (6 rows × 22 columns) with three
composable concepts:

- **Scene** — the board model, defined as a JSON file (`scenes/*.json`): a 6×22 grid
  where each cell holds an alphabet **region label** (`A`, `B`, …). The loader groups
  same-labeled cells into named regions you stamp content into.
- **Glyph / Font** — glyphs are defined as a JSON font map (`fonts/*.json`):
  `{"structure": "3x4", "glyphs": {"A": [0,1,0,1,1,1,1,1,1,1,0,1], ...}}`, each value a
  flattened row-major on/off pixel array. Two 3×4 fonts ship (`nanofont3x4`,
  `bytesized3x4`); set `FONT` to pick one, or drop in a new JSON file to add your own.
- **Job** — a scheduled unit of business logic: *fetch data → build a scene → paint
  it to the board*. Jobs are run by an [APScheduler](https://apscheduler.readthedocs.io/)
  daemon.

Inspired by [fiestaboard.app](https://fiestaboard.app).

## Quickstart

```bash
mise install                 # python 3.13 + uv + deps
cp .env.example .env         # then fill in your keys

# See a job rendered in your terminal — no board, no API key needed:
mise preview clock

# Send a job to the board once (needs VESTABOARD_RW_KEY):
mise paint clock

# Run the daemon, painting ACTIVE_JOB on its schedule:
mise run
```

## Jobs

| Job | Interval | Needs | Notes |
|-----|----------|-------|-------|
| `clock` | 60s | — | Big 3×4-glyph `HH:MM` clock. |
| `muni` | 30s | `FIVEONEONE_API_KEY`, `MUNI_STOP_CODE` | Next L Taraval arrivals from [511.org](https://511.org/open-data/token). |
| `aircraft` | — | — | Stub: ADS-B planes overhead (not yet implemented). |

## Configuration

All via `.env` (see `.env.example`). Key vars:

- `VESTABOARD_RW_KEY` — Vestaboard Read/Write API key. Required for `paint`/`run`.
- `ACTIVE_JOB` — which job the daemon paints (`clock` | `muni` | `aircraft`).
- `FIVEONEONE_API_KEY`, `MUNI_STOP_CODE` — for the Muni job.

## Docker

```bash
mise docker-up      # build + run the daemon (reads .env)
mise docker-down
```

## Development

```bash
mise test           # pytest
mise lint           # ruff check + format check
mise lint-fix       # auto-fix
```

## Credits

Bundled 3×4 fonts are transcribed into JSON from upstream pixel fonts:

- `fonts/nanofont3x4.json` — from [Michaelangel007/nanofont3x4](https://github.com/Michaelangel007/nanofont3x4).
- `fonts/bytesized3x4.json` — from [balt-dev/bytesized-gf](https://github.com/balt-dev/bytesized-gf) (OFL-1.1).
