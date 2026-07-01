"""The poll cycle: discover referenced sources from running boards, poll each into a
snapshot, isolate per-source failures. Engine-agnostic logic, exercised on SQLite with
real jobs (clock polls offline; muni raises without an API key)."""

from sqlmodel import Session

from artistaboard.config import Settings
from artistaboard.db.engine import create_db_and_tables, get_engine, init_engine
from artistaboard.db.models import Board, BoardRun, Pipeline, PipelineEntry, User
from artistaboard.db.snapshots import latest_snapshot
from artistaboard.poller import referenced_sources, run_poll_cycle


def _setup(tmp_path):
    settings = Settings(_env_file=None, database_url=f"sqlite:///{tmp_path}/poll.db")
    init_engine(settings.database_url)
    create_db_and_tables()
    return settings


def _pipeline_with(session: Session, owner_id: str, entries: list[PipelineEntry]) -> Pipeline:
    p = Pipeline(owner_id=owner_id, name="p")
    session.add(p)
    session.flush()
    for pos, e in enumerate(entries):
        e.pipeline_id = p.id
        e.position = pos
        session.add(e)
    session.commit()
    return p


def _running_board(session: Session, owner_id: str, pipeline_id: str) -> None:
    board = Board(owner_id=owner_id, name="b")
    session.add(board)
    session.flush()
    session.add(BoardRun(board_id=board.id, owner_id=owner_id, pipeline_id=pipeline_id, state="running"))
    session.commit()


def test_referenced_sources_dedups_and_ignores_display_options(tmp_path):
    _setup(tmp_path)
    with Session(get_engine()) as s:
        user = User(email="a@b.c", password_hash="x")
        s.add(user)
        s.flush()
        p = _pipeline_with(
            s,
            user.id,
            [
                PipelineEntry(source_type="job", job_name="muni", options={"stop_code": "111", "line": "L"}),
                PipelineEntry(source_type="job", job_name="muni", options={"stop_code": "111", "line": "N"}),
                PipelineEntry(source_type="job", job_name="muni", options={"stop_code": "222"}),
                PipelineEntry(source_type="job", job_name="clock", options={}),
            ],
        )
        _running_board(s, user.id, p.id)
        refs = referenced_sources(s)
    keyed = sorted((r.source, r.source_key) for r in refs)
    # stop 111 collapses across the two lines (display-only); stop 222 is its own series.
    assert keyed == sorted([("clock", ""), ("muni", '{"stop_code": "111"}'), ("muni", '{"stop_code": "222"}')])


def test_referenced_sources_only_running_boards(tmp_path):
    _setup(tmp_path)
    with Session(get_engine()) as s:
        user = User(email="a@b.c", password_hash="x")
        s.add(user)
        s.flush()
        p = _pipeline_with(s, user.id, [PipelineEntry(source_type="job", job_name="clock", options={})])
        board = Board(owner_id=user.id, name="b")
        s.add(board)
        s.flush()
        s.add(BoardRun(board_id=board.id, owner_id=user.id, pipeline_id=p.id, state="stopped"))
        s.commit()
        assert referenced_sources(s) == []  # nothing running -> nothing to poll


def test_scene_entry_polls_its_data_source(tmp_path):
    _setup(tmp_path)
    with Session(get_engine()) as s:
        user = User(email="a@b.c", password_hash="x")
        s.add(user)
        s.flush()
        p = _pipeline_with(
            s, user.id, [PipelineEntry(source_type="scene", scene_id="whatever", data_source="clock", options={})]
        )
        _running_board(s, user.id, p.id)
        refs = referenced_sources(s)
    assert [(r.source, r.source_key) for r in refs] == [("clock", "")]


def test_run_poll_cycle_writes_snapshots_and_isolates_failures(tmp_path):
    settings = _setup(tmp_path)
    with Session(get_engine()) as s:
        user = User(email="a@b.c", password_hash="x")
        s.add(user)
        s.flush()
        # clock.poll() works offline; muni.poll() raises (no 511 API key configured).
        p = _pipeline_with(
            s,
            user.id,
            [
                PipelineEntry(source_type="job", job_name="clock", options={}),
                PipelineEntry(source_type="job", job_name="muni", options={"stop_code": "111"}),
            ],
        )
        _running_board(s, user.id, p.id)
        result = run_poll_cycle(s, settings)

        assert "clock:" in result.polled[0]
        assert [f for f in result.failed if f[0] == "muni"]  # muni failed but was isolated
        assert latest_snapshot(s, "clock") is not None  # clock still written despite muni failing
        assert "iso" in latest_snapshot(s, "clock").payload
        assert latest_snapshot(s, "muni", '{"stop_code": "111"}') is None  # failed source wrote nothing
