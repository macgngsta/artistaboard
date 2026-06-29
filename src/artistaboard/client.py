"""Vestaboard Read/Write API client.

Read/Write API: base ``https://rw.vestaboard.com/`` with header
``X-Vestaboard-Read-Write-Key``. ``GET /`` returns the current message;
``POST /`` with the raw 6x22 character array sets it.

NOTE: the exact request/response envelope should be confirmed with a live read
(see ``_LIVE_CHECK`` in the README open-items) — both the documented and legacy
shapes are handled defensively here.
"""

from __future__ import annotations

import json
import logging
import time

import httpx

from . import COLS, ROWS

log = logging.getLogger(__name__)

BASE_URL = "https://rw.vestaboard.com/"
HEADER = "X-Vestaboard-Read-Write-Key"
MIN_SEND_INTERVAL = 15.0  # seconds; the board drops messages sent faster than this


class VestaboardError(RuntimeError):
    pass


class VestaboardClient:
    def __init__(
        self,
        key: str,
        *,
        base_url: str = BASE_URL,
        min_interval: float = MIN_SEND_INTERVAL,
        client: httpx.Client | None = None,
    ) -> None:
        if not key:
            raise VestaboardError("a Vestaboard Read/Write key is required")
        self._key = key
        self._min_interval = min_interval
        self._last_send: float | None = None
        self._client = client or httpx.Client(
            base_url=base_url,
            headers={HEADER: key, "Content-Type": "application/json"},
            timeout=10.0,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> VestaboardClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def read(self) -> list[list[int]]:
        resp = self._client.get("/")
        self._raise_for_status(resp)
        data = resp.json()
        layout = data.get("currentMessage", {}).get("layout", data) if isinstance(data, dict) else data
        if isinstance(layout, str):
            layout = json.loads(layout)
        return layout

    def send(self, characters: list[list[int]]) -> dict:
        _validate(characters)
        self._respect_rate_limit()
        resp = self._client.post("/", json=characters)
        self._raise_for_status(resp)
        self._last_send = time.monotonic()
        return resp.json()

    # -- internals -------------------------------------------------------------
    def _respect_rate_limit(self) -> None:
        if self._last_send is None:
            return
        elapsed = time.monotonic() - self._last_send
        wait = self._min_interval - elapsed
        if wait > 0:
            log.info("rate limit: sleeping %.1fs before next send", wait)
            time.sleep(wait)

    @staticmethod
    def _raise_for_status(resp: httpx.Response) -> None:
        if resp.status_code >= 400:
            raise VestaboardError(f"Vestaboard API {resp.status_code}: {resp.text}")


def _validate(characters: list[list[int]]) -> None:
    if len(characters) != ROWS or any(len(row) != COLS for row in characters):
        raise VestaboardError("characters must be a 6x22 grid")
    for row in characters:
        for code in row:
            if not (0 <= code <= 71):
                raise VestaboardError(f"code {code} out of range 0-71")
