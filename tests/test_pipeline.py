from datetime import datetime, timedelta

from artistaboard.pipeline import Pipeline, RuntimeEntry
from artistaboard.rotation import RotationState

NOW = datetime(2026, 6, 29, 12, 0)


def _entry(eid, dur):
    return RuntimeEntry(
        id=eid, duration_seconds=dur, refresh_seconds=None, source_type="scene", job_name=None, scene_id=eid
    )


def _fresh(entries):
    return Pipeline("p", entries, loop=True, state=RotationState(index=-1))


def test_starts_at_first_entry():
    p = _fresh([_entry("a", 60), _entry("b", 60)])
    assert p.active(NOW).id == "a"


def test_holds_within_window_then_advances_and_loops():
    p = _fresh([_entry("a", 60), _entry("b", 30)])
    assert p.active(NOW).id == "a"
    assert p.active(NOW + timedelta(seconds=30)).id == "a"  # within a's 60s
    assert p.active(NOW + timedelta(seconds=61)).id == "b"  # a's window elapsed
    assert p.active(NOW + timedelta(seconds=92)).id == "a"  # b's 30s elapsed -> loop to a


def test_seconds_left_counts_down_within_window():
    p = _fresh([_entry("a", 60)])
    e = p.active(NOW)
    assert p.seconds_left(e, NOW + timedelta(seconds=20)) == 60 - 20


def test_non_looping_finishes_after_last_entry():
    p = Pipeline("p", [_entry("a", 60), _entry("b", 30)], loop=False, state=RotationState(index=-1))
    assert p.active(NOW).id == "a"
    assert p.active(NOW + timedelta(seconds=61)).id == "b"  # advance to last
    assert p.active(NOW + timedelta(seconds=92)) is None  # b's window elapsed -> finished
    assert p.completed is True


def test_non_looping_holds_last_entry_until_due():
    p = Pipeline("p", [_entry("a", 60)], loop=False, state=RotationState(index=-1))
    assert p.active(NOW).id == "a"
    assert p.active(NOW + timedelta(seconds=30)).id == "a"  # still within window
    assert p.completed is False
    assert p.active(NOW + timedelta(seconds=61)) is None  # done
    assert p.completed is True


def test_rotation_state_round_trips():
    p = _fresh([_entry("a", 60), _entry("b", 60)])
    p.active(NOW)
    restored = RotationState.from_dict(p.state.to_dict())
    assert restored.index == p.state.index
    assert restored.last_switch == p.state.last_switch
    assert restored.current_id == "a"


# -- nested pipelines --------------------------------------------------------------


def _pentry(eid, dur, sub):
    return RuntimeEntry(
        id=eid,
        duration_seconds=dur,
        refresh_seconds=None,
        source_type="pipeline",
        job_name=None,
        scene_id=None,
        sub_pipeline_id=sub,
    )


def _nested(parent_entries, child):
    # Wire a parent whose entry `child_of` embeds `child`, sharing the child's state
    # into the parent tree the way _build_pipeline does.
    state = RotationState(index=-1)
    children = {}
    for e in parent_entries:
        if e.source_type == "pipeline":
            state.children[e.id] = child.state
            children[e.id] = child
    return Pipeline("parent", parent_entries, loop=True, state=state, children=children)


def test_pipeline_entry_descends_to_child_leaf():
    child = Pipeline("child", [_entry("x", 30), _entry("y", 30)], loop=True, state=RotationState(index=-1))
    parent = _nested([_pentry("e", 120, "child")], child)
    assert parent.active(NOW).id == "x"  # descends to the child's current leaf
    # the child rotates on its own 30s cadence inside the parent's 120s window
    assert parent.active(NOW + timedelta(seconds=31)).id == "y"


def test_parent_advances_off_pipeline_entry_after_its_duration():
    child = Pipeline("child", [_entry("x", 30)], loop=True, state=RotationState(index=-1))
    parent = _nested([_pentry("e", 60, "child"), _entry("z", 60)], child)
    assert parent.active(NOW).id == "x"  # inside the pipeline entry's window
    assert parent.active(NOW + timedelta(seconds=61)).id == "z"  # parent's 60s elapsed -> next entry


def test_empty_child_yields_no_leaf():
    child = Pipeline("child", [], loop=True, state=RotationState(index=-1))
    parent = _nested([_pentry("e", 60, "child")], child)
    assert parent.active(NOW) is None


def test_rotation_state_children_round_trip():
    child = Pipeline("child", [_entry("x", 30)], loop=True, state=RotationState(index=-1))
    parent = _nested([_pentry("e", 120, "child")], child)
    parent.active(NOW)
    restored = RotationState.from_dict(parent.state.to_dict())
    assert "e" in restored.children
    assert restored.children["e"].current_id == "x"


def test_load_pipeline_builds_nested_tree(tmp_path):
    from sqlmodel import Session

    from artistaboard.db.engine import create_db_and_tables, get_engine, init_engine
    from artistaboard.db.models import Pipeline as PipelineRow
    from artistaboard.db.models import PipelineEntry as EntryRow
    from artistaboard.db.models import User
    from artistaboard.pipeline import load_pipeline

    init_engine(f"sqlite:///{tmp_path}/nested.db")
    create_db_and_tables()
    with Session(get_engine()) as s:
        u = User(email="n@example.com", password_hash="x")
        s.add(u)
        s.flush()
        child = PipelineRow(owner_id=u.id, name="child")
        parent = PipelineRow(owner_id=u.id, name="parent")
        s.add(child)
        s.add(parent)
        s.flush()
        s.add(EntryRow(pipeline_id=child.id, position=0, source_type="job", job_name="clock", duration_seconds=30))
        s.add(
            EntryRow(
                pipeline_id=parent.id,
                position=0,
                source_type="pipeline",
                sub_pipeline_id=child.id,
                duration_seconds=120,
            )
        )
        s.commit()
        parent_id = parent.id

    with Session(get_engine()) as s:
        p = load_pipeline(s, parent_id, None)
        leaf = p.active(NOW)
        assert leaf is not None and leaf.source_type == "job" and leaf.job_name == "clock"
        # the tree carries a substate keyed by the parent's pipeline entry id
        assert list(p.state.children) == [p.entries[0].id]
