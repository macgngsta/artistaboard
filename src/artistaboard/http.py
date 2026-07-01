"""Shared HTTP helper: a thin httpx wrapper with bounded retry.

External data feeds (ESPN, 511) are flaky — a transient connection blip or a 5xx
shouldn't blank the board when the previous snapshot would have done. ``get_json``
retries a bounded number of times on transport errors and 5xx responses with a
short linear backoff, then raises. A 4xx is a permanent client error and is not
retried.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

log = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 15.0
DEFAULT_RETRIES = 2  # total attempts = retries + 1
BACKOFF_SECONDS = 0.5


def get_json(
    url: str,
    *,
    params: dict | None = None,
    headers: dict | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
) -> Any:
    """GET ``url`` and return parsed JSON, retrying transient failures.

    Retries transport errors and 5xx responses (bounded, linear backoff); raises
    ``httpx.HTTPStatusError`` on a 4xx or a final 5xx, or the last transport error
    if every attempt fails.
    """
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            resp = httpx.get(url, params=params, headers=headers, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code < 500:
                raise  # client error — retrying won't help
            last_exc = exc
        except httpx.TransportError as exc:
            last_exc = exc
        if attempt < retries:
            wait = BACKOFF_SECONDS * (attempt + 1)
            log.warning("GET %s failed (%s); retry %d/%d in %.1fs", url, last_exc, attempt + 1, retries, wait)
            time.sleep(wait)
    # Reached only when the final attempt failed without returning, so last_exc is set.
    assert last_exc is not None
    raise last_exc
