# artistaboard web

React 18/19 + Vite + TypeScript frontend for the artistaboard API. Server state via
TanStack Query, editor state via Zustand, UI with Tailwind + Radix. The request/response
types are generated from the backend's OpenAPI schema — never hand-written.

## Develop

The backend must be running first (`mise serve`, http://127.0.0.1:8000):

```bash
npm install          # from web/  (or `npm run web:install` from the repo root)
npm run gen:api      # regenerate src/api/schema.d.ts from /openapi.json
npm run dev          # Vite dev server on http://localhost:5173
```

The dev server proxies the API prefixes (`/auth`, `/scenes`, `/preview`, `/boards`,
`/pipelines`, `/health`) to the backend so the browser stays same-origin and the
httpOnly `session` cookie works. The backend also enables CORS for the dev origin as a
fallback (`CORS_ORIGINS` env var).

## Build & serve in production

```bash
npm run build        # -> web/dist
```

When `web/dist` exists, `python -m artistaboard serve` mounts it and serves the SPA
same-origin at `/`, alongside the API. The app uses a hash router (`/#/scenes`) so
client routes never collide with the API's top-level paths.

## Scripts

- `npm run dev` — Vite dev server
- `npm run build` — typecheck + production build
- `npm run gen:api` — regenerate the typed client from the live OpenAPI schema
- `npm run lint` / `npm run typecheck`

## Notes

- The board Read/Write key is write-only: it is sent on save but never returned or
  stored client-side (only `has_key` + last-4 come back).
- `POST /preview` is the single renderer for scene documents; the canvas only maps the
  returned character codes to glyphs (`src/lib/codes.ts`, mirrored from the backend).
