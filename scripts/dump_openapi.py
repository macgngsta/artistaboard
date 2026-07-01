"""Dump the FastAPI OpenAPI schema to stdout — no running server required.

The web client (``web/src/api/schema.d.ts``) is generated from this schema via
``openapi-typescript``. CI uses this script to regenerate the client and assert
it's in sync with the backend routes (see the ``schema-drift`` workflow), so a
backend API change that isn't accompanied by ``npm run gen:api`` fails the build.
"""

from __future__ import annotations

import json

from artistaboard.api.app import create_app

if __name__ == "__main__":
    print(json.dumps(create_app().openapi()))
