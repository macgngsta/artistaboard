"""Per-board worker + manager: drive a running pipeline onto a physical board.

One ``BoardWorker`` (an asyncio task) owns one board's ``VestaboardClient`` and its
blocking 15s rate limit. Each tick it loads the running pipeline, asks it which
entry is active, renders the frame, and sends it if changed — persisting rotation
and last-sent state to ``BoardRun`` so a restart resumes mid-rotation. The whole
tick (DB + network + the rate-limit sleep) runs in a thread so the event loop stays
free; the worker just awaits the tick then sleeps to the next boundary.

``BoardManager`` reconciles desired vs actual: it reads ``BoardRun`` rows and
spawns/cancels workers to match. The API flips a row then calls ``reconcile``.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from sqlmodel import Session, select

from .client import VestaboardClient
from .config import Settings
from .crypto import decrypt
from .db.engine import get_engine
from .db.models import Board, BoardRun
from .pipeline import load_pipeline, render_entry

log = logging.getLogger("artistaboard.worker")

_IDLE_SLEEP = 30.0  # when a run has no entries / nothing to do


class BoardWorker:
    def __init__(self, board_id: str, settings: Settings) -> None:
        self.board_id = board_id
        self.settings = settings
        self._client: VestaboardClient | None = None
        self._last_sent: list[list[int]] | None = None
        self._sleep_for: float = _IDLE_SLEEP

    async def run(self) -> None:
        try:
            while True:
                keep_going = await asyncio.to_thread(self._tick)
                if not keep_going:
                    break
                await asyncio.sleep(self._sleep_for)
        except asyncio.CancelledError:
            pass
        finally:
            if self._client is not None:
                self._client.close()

    def _tick(self) -> bool:
        """One synchronous tick (runs in a thread). Returns False to stop the worker."""
        with Session(get_engine()) as session:
            run = session.get(BoardRun, self.board_id)
            if run is None or run.state != "running":
                return False
            board = session.get(Board, self.board_id)
            if board is None or not board.rw_key_encrypted:
                log.warning("board %s missing/unconfigured; stopping", self.board_id)
                return False

            pipeline = load_pipeline(session, run.pipeline_id, loop=True, rotation_state=run.rotation_state)
            if not pipeline.entries:
                self._sleep_for = _IDLE_SLEEP
                return True

            now = datetime.now()
            entry = pipeline.active(now)
            try:
                chars = render_entry(entry, self.settings, session).to_characters()
            except Exception:
                log.exception("render failed for board %s entry %s", self.board_id, entry.id)
                self._sleep_for = _IDLE_SLEEP
                return True

            if self._client is None:
                key = decrypt(board.rw_key_encrypted, self.settings.encryption_secret)
                self._client = VestaboardClient(key, min_interval=board.min_send_interval)
            if chars != self._last_sent:
                try:
                    self._client.send(chars)
                except Exception:  # a board error must not kill the worker; retry next tick
                    log.exception("send failed for board %s", self.board_id)
                    board.status = "unreachable"
                    session.add(board)
                    session.commit()
                    self._sleep_for = _IDLE_SLEEP
                    return True
                self._last_sent = chars
                run.last_sent = chars
                board.last_painted_at = now
                board.status = "ok"

            run.rotation_state = pipeline.state.to_dict()
            run.current_entry_id = entry.id
            run.updated_at = now
            session.add(run)
            session.add(board)
            session.commit()

            remaining = pipeline.seconds_left(entry, now)
            refresh = float(entry.refresh_seconds or _IDLE_SLEEP)
            target = min(refresh, remaining) if remaining > 0 else refresh
            self._sleep_for = max(float(board.min_send_interval), target)
            return True


class BoardManager:
    """Owns the set of running workers; keeps them in sync with the DB."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._workers: dict[str, asyncio.Task] = {}

    async def reconcile(self) -> None:
        with Session(get_engine()) as session:
            running = {r.board_id for r in session.exec(select(BoardRun).where(BoardRun.state == "running")).all()}
        for board_id in list(self._workers):
            task = self._workers[board_id]
            if board_id not in running or task.done():
                self._stop(board_id)
        for board_id in running:
            if board_id not in self._workers:
                worker = BoardWorker(board_id, self.settings)
                self._workers[board_id] = asyncio.create_task(worker.run(), name=f"board-{board_id}")
                log.info("started worker for board %s", board_id)

    def _stop(self, board_id: str) -> None:
        task = self._workers.pop(board_id, None)
        if task is not None and not task.done():
            task.cancel()
            log.info("stopped worker for board %s", board_id)

    async def shutdown(self) -> None:
        for board_id in list(self._workers):
            self._stop(board_id)
