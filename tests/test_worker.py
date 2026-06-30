"""Worker integration, fully offline: a fake board client captures sends, two static
scene entries render to distinct frames, and we drive ticks to assert rotation +
frame-diff + state persistence — no network, no real board."""

from datetime import datetime, timedelta

import pytest
from sqlmodel import Session

from artistaboard import worker as worker_mod
from artistaboard.config import Settings
from artistaboard.crypto import encrypt
from artistaboard.db.engine import create_db_and_tables, get_engine, init_engine
from artistaboard.db.models import Board, BoardRun, Pipeline, PipelineEntry, Scene, User
from artistaboard.worker import BoardWorker


def _fill_doc(color):
    return {"grid": ["AAAAAAAAAAAAAAAAAAAAAA"] * 6, "render": {"A": {"as": "fill", "color": color}}}


class FakeClient:
    sends: list = []

    def __init__(self, key, min_interval=15):
        self.key = key

    def send(self, characters):
        FakeClient.sends.append(characters)
        return {"status": "ok"}

    def close(self):
        pass


@pytest.fixture
def setup(tmp_path, monkeypatch):
    FakeClient.sends = []
    monkeypatch.setattr(worker_mod, "VestaboardClient", FakeClient)
    settings = Settings(_env_file=None, database_url=f"sqlite:///{tmp_path}/w.db")
    init_engine(settings.database_url)
    create_db_and_tables()
    with Session(get_engine()) as s:
        user = User(email="w@example.com", password_hash="x")
        s.add(user)
        s.flush()
        red = Scene(owner_id=user.id, name="red", document=_fill_doc("red"))
        blue = Scene(owner_id=user.id, name="blue", document=_fill_doc("blue"))
        s.add(red)
        s.add(blue)
        board = Board(
            owner_id=user.id,
            name="b",
            rw_key_encrypted=encrypt("KEY1234", settings.encryption_secret),
            rw_key_last4="1234",
        )
        pipe = Pipeline(owner_id=user.id, name="p")
        s.add(board)
        s.add(pipe)
        s.flush()
        s.add(PipelineEntry(pipeline_id=pipe.id, position=0, source_type="scene", scene_id=red.id, duration_seconds=60))
        s.add(
            PipelineEntry(pipeline_id=pipe.id, position=1, source_type="scene", scene_id=blue.id, duration_seconds=60)
        )
        s.add(BoardRun(board_id=board.id, owner_id=user.id, pipeline_id=pipe.id, state="running"))
        s.commit()
        board_id = board.id
    return settings, board_id


def test_tick_sends_holds_then_advances(setup):
    settings, board_id = setup
    w = BoardWorker(board_id, settings)

    assert w._tick() is True
    assert len(FakeClient.sends) == 1  # first frame (red) sent

    assert w._tick() is True
    assert len(FakeClient.sends) == 1  # within window, same frame -> skipped

    # force the first entry's window to have elapsed, then tick advances to blue
    with Session(get_engine()) as s:
        run = s.get(BoardRun, board_id)
        run.rotation_state = {
            **run.rotation_state,
            "last_switch": (datetime.now() - timedelta(seconds=120)).isoformat(),
        }
        s.add(run)
        s.commit()

    assert w._tick() is True
    assert len(FakeClient.sends) == 2  # advanced -> distinct frame sent
    assert FakeClient.sends[1] != FakeClient.sends[0]


def test_tick_stops_when_run_not_running(setup):
    settings, board_id = setup
    with Session(get_engine()) as s:
        run = s.get(BoardRun, board_id)
        run.state = "stopped"
        s.add(run)
        s.commit()
    assert BoardWorker(board_id, settings)._tick() is False
