# artistaboard

Drive a [Vestaboard](https://www.vestaboard.com/) (6 rows × 22 columns) with composable scenes and
scheduled jobs — either from a small **command-line daemon** or a self-hosted **multi-user web app**
where you design scenes graphically, assemble them into pipelines, and run them on your boards.

Inspired by [fiestaboard.app](https://fiestaboard.app).

## Two ways to use it

- **CLI** — preview a job in your terminal, paint it to the board once, or run a scheduler daemon
  that paints one job on a schedule. No database required. Jump to [Quickstart](#quickstart).
- **Web app** — a React + FastAPI application: sign in, design scenes on a 6×22 grid, register your
  boards, compose scenes/jobs into **pipelines**, and let a Postgres-backed **poller** keep live data
  fresh so boards paint from the database. Jump to [Web app](#web-app).

## Core concepts

- **Scene** — the board model, defined as a JSON file (`scenes/*.json`): **6 strings of
  22 characters**, so the file reads like the board. Each character is a region **label**
  (`A`, `B`, …) or `.`/space for unassigned; same-labeled cells form a named region you
  stamp content into. For example `scenes/transit.json` (shared by transit jobs):

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
  daemon (CLI) or scheduled through a pipeline (web app). See [Jobs](#jobs).
- **Board** — a registered Vestaboard: a name plus a write-only Read/Write key (stored
  encrypted at rest). Web-app only.
- **Pipeline / Entry** — an ordered list of **entries** that a board runs. Each entry is a
  scene, a job, or **another pipeline** (nested), with optional per-entry job **options**.
  This is how you compose "Muni + World Cup + clock" onto one board. Web-app only.

## Architecture

```
CLI (python -m artistaboard …)          Web app
  preview / paint / run                   serve  ── FastAPI + React SPA (web/)
                                          poll   ── Procrastinate poller (Postgres)
        │                                     │
        └──────────── scenes/, fonts/, jobs/ ─┘
                              │
                     data_snapshots (DB)  ←── poller writes, paint reads
```

- **Backend** (`src/artistaboard/`) — the scene/glyph engine, jobs, the FastAPI app (`api/`), and
  the poller. SQLite by default; Postgres opt-in (required for the poller).
- **Frontend** (`web/`) — React 19 + Vite + TypeScript SPA. Types are generated from the backend's
  OpenAPI schema. See [`web/README.md`](web/README.md).
- **Data layer** — the poller fetches each referenced source's full dataset into `data_snapshots` on
  a schedule; the paint path reads the latest snapshot and only falls back to a live fetch on a miss.
  So in production the poller must be running to keep boards off external APIs in steady state.

## Quickstart

Terminal-only, no database or web app needed:

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

## Web app

Run the backend and the frontend, then open the app in your browser.

```bash
mise install                 # backend deps
mise migrate                 # apply DB migrations (alembic upgrade head)
mise serve                   # FastAPI on http://127.0.0.1:8000

# In another terminal — the dev frontend (Vite, proxies the API):
cd web && npm install && npm run gen:api && npm run dev   # http://localhost:5173
```

For production, build the SPA (`npm --prefix web run build` → `web/dist`); when `web/dist` exists,
`mise serve` mounts and serves it same-origin at `/` alongside the API. Full frontend docs are in
[`web/README.md`](web/README.md).

The **poller** (`python -m artistaboard poll`) is **Postgres-only** — set a `postgresql+psycopg://…`
`DATABASE_URL`, then run it as its own daemon to keep `data_snapshots` fresh. See
[Configuration](#configuration) for the security-relevant env vars (`SESSION_SECRET`, `APP_ENV`,
`APP_ENCRYPTION_KEY`).

## Jobs

| Job | Needs | Notes |
|-----|-------|-------|
| `clock` | — | Big 3×4-glyph `HH:MM` clock. |
| `muni` | `FIVEONEONE_API_KEY`, `MUNI_STOP_CODE` | Next L Taraval arrivals from [511.org](https://511.org/open-data/token). |
| `world_cup` | — | Live 2026 World Cup scoreboard ([data](https://github.com/rezarahiminia/worldcup2026), no key). Flag-colored team badges; rotates among live matches every `WORLDCUP_ROTATE_SECONDS` or on a score change. |
| `sport_highscores` | — | Live scoreboard for high-scoring sports ([ESPN](https://www.espn.com/), no key) — set `SPORT_LEAGUE` (e.g. `basketball/nba`). Big score in the **leader's color (green, else white)**; rotates among live games. |
| `sport_lowscores` | — | Side-by-side scoreboard for low-scoring sports (1-2 digit scores) — set `SPORT_LOWSCORE_LEAGUE` (e.g. `baseball/mlb`). Same leader coloring; rotates among live games. |
| `spotify` | OAuth (see below) | "Now playing" — track + artists with the Spotify-green logo/accents. |

Poll/paint cadence is governed by `POLL_CRON` (poller) and per-entry pipeline config; the older
per-job intervals are nominal defaults.

**Spotify setup:** create an app at [developer.spotify.com](https://developer.spotify.com),
put the client id/secret + redirect URI in `.env`, then run `artistaboard spotify-auth`
once to get `SPOTIFY_REFRESH_TOKEN`.

The `world_cup` badges are **color-coded by flag** (`data/flags.json` → nearest
Vestaboard color). If both teams' primary color collides, the team it's more
prominent for keeps it and the other gets a random color.

## Configuration

All via `.env` (see [`.env.example`](.env.example) for the full annotated list).

**Jobs / CLI:**

- `VESTABOARD_RW_KEY` — Vestaboard Read/Write API key. Required for `paint`/`run`.
- `ACTIVE_JOB` — which job the daemon paints (`clock` | `muni` | `world_cup` | `sport_highscores` | `sport_lowscores` | `spotify`).
- `FIVEONEONE_API_KEY`, `MUNI_STOP_CODE` — for the Muni job.
- `CLOCK_COLOR` / `MUNI_COLOR` — a color **name** (`red orange yellow green blue
  violet`/`purple white black filled`) or code (`63`–`71`). Leave `MUNI_COLOR`
  blank to use the line's own color.

**Muni line colors** — the L badge auto-colors to match the line:
`J`=yellow · `K`=blue · `L`=purple · `M`=green · `N`=blue · `T`=red.

**Web app / data layer** (only needed for `serve` / `poll`):

- `DATABASE_URL` — SQLite by default; use `postgresql+psycopg://…` for the poller.
- `APP_ENV` — keep `dev` locally; set to `prod` (anything `!= dev`) in a real deployment, which
  **rejects the insecure default `SESSION_SECRET` at startup**.
- `SESSION_SECRET` — signs the auth session cookie. **Set a real value in any deployment.**
- `APP_ENCRYPTION_KEY` — encrypts board R/W keys at rest (Fernet); falls back to `SESSION_SECRET`
  when unset. Set a dedicated key in production.
- `ALLOW_SIGNUP` — allow new-account signup after the first owner account exists.
- `CORS_ORIGINS` — browser origins allowed to call the API with credentials (dev server only).
- `POLL_CRON` — poller cadence (cron; default every minute).

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
mise migrate        # alembic upgrade head
```

Frontend checks live in `web/` (`npm run typecheck && npm run lint && npm run build`); see
[`web/README.md`](web/README.md). Plans of record are in [`docs/plans/`](docs/plans/); shipped work
is distilled in [`CHANGELOG.md`](CHANGELOG.md). `CLAUDE.md` is a contributor/agent guide.

## Credits

Bundled fonts are transcribed into JSON from upstream pixel fonts:

- `fonts/nanofont3x4.json` — from [Michaelangel007/nanofont3x4](https://github.com/Michaelangel007/nanofont3x4).
- `fonts/bytesized3x4.json` — [balt-dev/bytesized-gf](https://github.com/balt-dev/bytesized-gf)
  (OFL-1.1); alphanumerics transcribed from the project's specimen so upper- and
  lowercase are distinct (`A`/`a`, `L`/`l`, …), punctuation from the repo glyphs.
- `fonts/3x3pixels.json` — a tiny 3×3 font, pixel-sampled from the *3x3 Pixels
  Regular* specimen ([onlinewebfonts.com](https://www.onlinewebfonts.com)). The
  colon is hand-set to vertical dots so `HH:MM` clocks stay legible.
- `fonts/3by5.json` — a 3×5 font, pixel-sampled from the *3-by-5.ttf* specimen.
  Uppercase + digits only; lowercase falls back to the uppercase glyph.

## License

[MIT](LICENSE) © 2026 Greg Tam.
