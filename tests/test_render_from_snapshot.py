"""render_entry reads source data from the latest data_snapshot (poller-fed), and
falls back to a live fetch() only when there's no snapshot. Uses a scene entry with a
plain-text binding so the rendered value is directly assertable."""

from datetime import UTC, datetime

from sqlmodel import Session

from artistaboard import codes
from artistaboard.config import Settings
from artistaboard.db.engine import create_db_and_tables, get_engine, init_engine
from artistaboard.db.models import Scene, User
from artistaboard.db.snapshots import write_snapshot
from artistaboard.jobs.muni import MuniJob
from artistaboard.pipeline import RuntimeEntry, render_entry

# A scene whose one text region shows the "time" the clock job binds.
TIME_DOC = {"grid": ["AAAAAAAAAAAAAAAAAAAAAA"] * 6, "render": {"A": {"bind": "time", "as": "text", "align": "left"}}}


def _setup(tmp_path):
    settings = Settings(_env_file=None, database_url=f"sqlite:///{tmp_path}/r.db")
    init_engine(settings.database_url)
    create_db_and_tables()
    with Session(get_engine()) as s:
        user = User(email="r@example.com", password_hash="x")
        s.add(user)
        s.flush()
        scene = Scene(owner_id=user.id, name="t", document=TIME_DOC)
        s.add(scene)
        s.commit()
        return settings, scene.id


def _clock_scene_entry(scene_id):
    return RuntimeEntry(
        id="e",
        duration_seconds=60,
        refresh_seconds=None,
        source_type="scene",
        job_name=None,
        scene_id=scene_id,
        data_source="clock",
        options={},
    )


def _row0(scene, n):
    chars = scene.to_characters()
    return "".join(codes.CODE_TO_CHAR.get(chars[0][c], " ") for c in range(n))


def test_renders_from_snapshot_not_live(tmp_path):
    settings, scene_id = _setup(tmp_path)
    with Session(get_engine()) as s:
        # A snapshot whose time is fixed and NOT "now": proves render used the DB.
        write_snapshot(s, "clock", {"iso": "2026-01-02T03:04:00"}, source_key="")
        scene = render_entry(_clock_scene_entry(scene_id), settings, s)
    assert _row0(scene, 5) == "03:04"  # from the snapshot's iso, not the wall clock


def test_falls_back_to_live_fetch_when_no_snapshot(tmp_path):
    settings, scene_id = _setup(tmp_path)
    with Session(get_engine()) as s:
        # No snapshot rows -> clock renders via live fetch(), so the board still paints.
        scene = render_entry(_clock_scene_entry(scene_id), settings, s)
    text = _row0(scene, 5)
    assert text[2] == ":" and text[:2].isdigit()  # a real HH:MM from the live clock


def test_muni_from_snapshot_filters_to_the_configured_line(tmp_path):
    settings, _ = _setup(tmp_path)
    full = {
        "arrivals": [
            {"line": "L", "direction": "INBOUND", "destination": "EMBARCADERO", "minutes": 8},
            {"line": "N", "direction": "OUTBOUND", "destination": "OCEAN", "minutes": 2},
            {"line": "L", "direction": "INBOUND", "destination": "EMBARCADERO", "minutes": 3},
        ],
        "polled_at": datetime.now(UTC).isoformat(),
    }
    job = MuniJob(settings.model_copy(update={"muni": settings.muni.model_copy(update={"line": "L"})}))
    selected = job.from_snapshot(full)
    assert selected.minutes == [3, 8]  # only L, soonest first — N is ignored
    assert selected.destination == "EMBARCADERO"

    job_n = MuniJob(settings.model_copy(update={"muni": settings.muni.model_copy(update={"line": "N"})}))
    assert job_n.from_snapshot(full).minutes == [2]  # same snapshot, different line, no re-fetch
