# vestaboard

Drive a [Vestaboard](https://www.vestaboard.com/) (6 rows × 22 columns) with three
composable concepts:

- **Scene** — the board model, defined as a JSON file (`scenes/*.json`): **6 strings of
  22 characters**, so the file reads like the board. Each character is a region **label**
  (`A`, `B`, …) or `.`/space for unassigned; same-labeled cells form a named region you
  stamp content into. For example `scenes/muni.json`:

  ```json
  [
    "AAAAA.BBBBBBBBBBBBBBBB",
    "AAAAA.BBBBBBBBBBBBBBBB",
    "AAAAA.BBBBBBBBBBBBBBBB",
    "AAAAA.BBBBBBBBBBBBBBBB",
    "AAAAA.BBBBBBBBBBBBBBBB",
    "AAAAA.BBBBBBBBBBBBBBBB"
  ]
  ```

  region `A` is the left 5 columns (the L badge), `B` is the right 16 (arrivals).
  Use `.`, a space, or `#` for unassigned/filler cells (so you can draw walls/gaps).

  The **job drives what each region holds** — either an array of big **glyphs**
  (`scene.glyphs("16:34", region="B", on_code=WHITE, fill=VIOLET, invert=False)`)
  or pure **alphanumerics** (`scene.text("08 MIN", region="D", align="right")`).
  Both support `align` (`left`/`center`/`right`); `glyphs()` also supports `fill`
  (shape-aware — non-rectangular regions keep their outline) and `invert` (carve
  the letters out of the fill). `#`/`.`/space mark filler cells.
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
| `world_cup` | 60s | — | Live 2026 World Cup scoreboard ([data](https://github.com/rezarahiminia/worldcup2026), no key). Flag-colored team badges; rotates among live matches every `WORLDCUP_ROTATE_SECONDS` or on a score change. |
| `aircraft` | — | — | Stub: ADS-B planes overhead (not yet implemented). |

The `world_cup` badges are **color-coded by flag** (`data/flags.json` → nearest
Vestaboard color). If both teams' primary color collides, the team it's more
prominent for keeps it and the other gets a random color.

## Configuration

All via `.env` (see `.env.example`). Key vars:

- `VESTABOARD_RW_KEY` — Vestaboard Read/Write API key. Required for `paint`/`run`.
- `ACTIVE_JOB` — which job the daemon paints (`clock` | `muni` | `aircraft`).
- `FIVEONEONE_API_KEY`, `MUNI_STOP_CODE` — for the Muni job.
- `CLOCK_COLOR` / `MUNI_COLOR` — a color **name** (`red orange yellow green blue
  violet`/`purple white black filled`) or code (`63`–`71`). Leave `MUNI_COLOR`
  blank to use the line's own color.

**Muni line colors** — the L badge auto-colors to match the line:
`J`=yellow · `K`=blue · `L`=purple · `M`=green · `N`=blue · `T`=red.

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
- `fonts/bytesized3x4.json` — [balt-dev/bytesized-gf](https://github.com/balt-dev/bytesized-gf)
  (OFL-1.1); alphanumerics transcribed from the project's specimen so upper- and
  lowercase are distinct (`A`/`a`, `L`/`l`, …), punctuation from the repo glyphs.
