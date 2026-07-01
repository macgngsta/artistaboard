"""Data-layer HTTP surface: owner-scoped freshness + manual poll."""

from sqlmodel import Session

from artistaboard.db.engine import get_engine
from artistaboard.db.models import BoardRun


def _running_clock_board(auth_client):
    """Create a board + clock pipeline, assign, and mark the run running (directly, to
    skip the worker's board I/O). Returns nothing — the DB state is what the API reads."""
    board_id = auth_client.post("/boards", json={"name": "b"}).json()["id"]
    pid = auth_client.post(
        "/pipelines",
        json={"name": "p", "entries": [{"source_type": "job", "job_name": "clock", "duration_seconds": 30}]},
    ).json()["id"]
    auth_client.post(f"/boards/{board_id}/assign", params={"pipeline_id": pid})
    with Session(get_engine()) as s:
        run = s.get(BoardRun, board_id)
        run.state = "running"
        s.add(run)
        s.commit()


def test_data_sources_require_auth(client):
    assert client.get("/data/sources").status_code == 401


def test_poll_requires_auth(client):
    assert client.post("/data/poll").status_code == 401


def test_sources_empty_without_running_boards(auth_client):
    assert auth_client.get("/data/sources").json() == []


def test_sources_lists_referenced_series_without_data(auth_client):
    _running_clock_board(auth_client)
    rows = auth_client.get("/data/sources").json()
    assert len(rows) == 1
    row = rows[0]
    assert row["source"] == "clock"
    assert row["has_data"] is False
    assert row["last_fetched_at"] is None
    assert row["age_seconds"] is None


def test_poll_then_sources_reports_fresh(auth_client):
    _running_clock_board(auth_client)
    result = auth_client.post("/data/poll").json()
    assert result["polled"] == ["clock:"]  # clock has no fetch-defining options → empty key
    assert result["failed"] == []

    row = auth_client.get("/data/sources").json()[0]
    assert row["has_data"] is True
    assert row["last_fetched_at"] is not None
    assert 0 <= row["age_seconds"] < 60


def test_sources_scoped_to_owner(client):
    """One owner's running board must not surface in another owner's sources."""
    a = client.post("/auth/register", json={"email": "a@example.com", "password": "supersecret"})
    assert a.status_code == 201
    _running_clock_board(client)  # 'a' owns a running clock board
    client.post("/auth/logout")
    client.post("/auth/register", json={"email": "b@example.com", "password": "supersecret"})
    assert client.get("/data/sources").json() == []  # 'b' sees nothing
