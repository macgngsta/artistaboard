"""render_entry: a scene entry fills its variables from a data_source job (offline,
using clock whose tz is deterministic) or renders static when there's no source."""

from sqlmodel import Session

from artistaboard import codes
from artistaboard.config import Settings
from artistaboard.db.engine import create_db_and_tables, get_engine, init_engine
from artistaboard.db.models import Scene, User
from artistaboard.pipeline import RuntimeEntry, render_entry

# A scene with one text region bound to the variable "tz".
TZ_DOC = {"grid": ["AAAAAAAAAAAAAAAAAAAAAA"] * 6, "render": {"A": {"bind": "tz", "as": "text", "align": "left"}}}


def _entry(scene_id, data_source):
    return RuntimeEntry(
        id="e",
        duration_seconds=60,
        refresh_seconds=None,
        source_type="scene",
        job_name=None,
        scene_id=scene_id,
        data_source=data_source,
    )


def _setup(tmp_path):
    settings = Settings(_env_file=None, database_url=f"sqlite:///{tmp_path}/r.db")
    init_engine(settings.database_url)
    create_db_and_tables()
    with Session(get_engine()) as s:
        user = User(email="r@example.com", password_hash="x")
        s.add(user)
        s.flush()
        scene = Scene(owner_id=user.id, name="tz", document=TZ_DOC)
        s.add(scene)
        s.commit()
        return settings, scene.id


def _row0(scene, n):
    chars = scene.to_characters()
    return "".join(codes.CODE_TO_CHAR.get(chars[0][c], " ") for c in range(n))


def test_scene_entry_renders_with_data_source_envelope(tmp_path):
    settings, scene_id = _setup(tmp_path)
    with Session(get_engine()) as s:
        scene = render_entry(_entry(scene_id, "clock"), settings, s)
    assert _row0(scene, 2) == "PT"  # clock publishes tz from clock_tz_label (default PT)


def test_scene_entry_without_data_source_is_static(tmp_path):
    settings, scene_id = _setup(tmp_path)
    with Session(get_engine()) as s:
        scene = render_entry(_entry(scene_id, None), settings, s)
    assert _row0(scene, 2) == "  "  # no envelope -> the tz binding stays blank
