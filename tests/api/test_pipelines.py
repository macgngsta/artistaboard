def test_pipelines_require_auth(client):
    assert client.get("/pipelines").status_code == 401


def test_create_with_ordered_entries(auth_client):
    body = {
        "name": "morning",
        "loop": True,
        "entries": [
            {"source_type": "job", "job_name": "clock", "duration_seconds": 30},
            {"source_type": "job", "job_name": "world_cup", "duration_seconds": 120, "refresh_seconds": 60},
        ],
    }
    r = auth_client.post("/pipelines", json=body)
    assert r.status_code == 201, r.text
    entries = r.json()["entries"]
    assert [e["position"] for e in entries] == [0, 1]
    assert [e["job_name"] for e in entries] == ["clock", "world_cup"]
    assert entries[1]["duration_seconds"] == 120


def test_scene_entry_accepts_system_scene(auth_client):
    clock = next(s for s in auth_client.get("/scenes").json() if s["name"] == "clock")
    r = auth_client.post(
        "/pipelines",
        json={"name": "p", "entries": [{"source_type": "scene", "scene_id": clock["id"], "duration_seconds": 45}]},
    )
    assert r.status_code == 201


def test_scene_entry_with_data_source(auth_client):
    clock = next(s for s in auth_client.get("/scenes").json() if s["name"] == "clock")
    r = auth_client.post(
        "/pipelines",
        json={
            "name": "p",
            "entries": [
                {"source_type": "scene", "scene_id": clock["id"], "data_source": "clock", "duration_seconds": 30}
            ],
        },
    )
    assert r.status_code == 201
    assert r.json()["entries"][0]["data_source"] == "clock"


def test_unknown_data_source_is_422(auth_client):
    clock = next(s for s in auth_client.get("/scenes").json() if s["name"] == "clock")
    r = auth_client.post(
        "/pipelines",
        json={
            "name": "p",
            "entries": [
                {"source_type": "scene", "scene_id": clock["id"], "data_source": "bogus", "duration_seconds": 30}
            ],
        },
    )
    assert r.status_code == 422


def test_unknown_job_entry_is_422(auth_client):
    r = auth_client.post(
        "/pipelines",
        json={"name": "p", "entries": [{"source_type": "job", "job_name": "nope", "duration_seconds": 30}]},
    )
    assert r.status_code == 422


def test_unknown_scene_entry_is_422(auth_client):
    r = auth_client.post(
        "/pipelines",
        json={"name": "p", "entries": [{"source_type": "scene", "scene_id": "missing", "duration_seconds": 30}]},
    )
    assert r.status_code == 422


def test_nonpositive_duration_is_422(auth_client):
    r = auth_client.post(
        "/pipelines",
        json={"name": "p", "entries": [{"source_type": "job", "job_name": "clock", "duration_seconds": 0}]},
    )
    assert r.status_code == 422  # schema gt=0


def test_job_entry_accepts_typed_options(auth_client):
    r = auth_client.post(
        "/pipelines",
        json={
            "name": "p",
            "entries": [
                {"source_type": "job", "job_name": "world_cup", "options": {"group": "C"}, "duration_seconds": 30}
            ],
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["entries"][0]["options"] == {"group": "C"}


def test_unknown_option_key_is_422(auth_client):
    r = auth_client.post(
        "/pipelines",
        json={
            "name": "p",
            "entries": [
                {"source_type": "job", "job_name": "world_cup", "options": {"bogus": 1}, "duration_seconds": 30}
            ],
        },
    )
    assert r.status_code == 422


def test_options_without_a_driving_job_is_422(auth_client):
    clock = next(s for s in auth_client.get("/scenes").json() if s["name"] == "clock")
    r = auth_client.post(
        "/pipelines",
        json={
            "name": "p",
            "entries": [
                {"source_type": "scene", "scene_id": clock["id"], "options": {"tz_label": "ET"}, "duration_seconds": 30}
            ],
        },
    )
    assert r.status_code == 422


def test_scene_entry_options_validate_against_data_source(auth_client):
    clock = next(s for s in auth_client.get("/scenes").json() if s["name"] == "clock")
    r = auth_client.post(
        "/pipelines",
        json={
            "name": "p",
            "entries": [
                {
                    "source_type": "scene",
                    "scene_id": clock["id"],
                    "data_source": "clock",
                    "options": {"tz_label": "ET"},
                    "duration_seconds": 30,
                }
            ],
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["entries"][0]["options"] == {"tz_label": "ET"}


def test_entry_options_default_to_empty(auth_client):
    r = auth_client.post(
        "/pipelines",
        json={"name": "p", "entries": [{"source_type": "job", "job_name": "clock", "duration_seconds": 30}]},
    )
    assert r.status_code == 201
    assert r.json()["entries"][0]["options"] == {}


def test_update_replaces_entries(auth_client):
    pid = auth_client.post(
        "/pipelines",
        json={"name": "p", "entries": [{"source_type": "job", "job_name": "clock", "duration_seconds": 30}]},
    ).json()["id"]
    upd = auth_client.put(
        f"/pipelines/{pid}",
        json={"name": "p2", "entries": [{"source_type": "job", "job_name": "spotify", "duration_seconds": 90}]},
    )
    assert upd.status_code == 200
    assert [e["job_name"] for e in upd.json()["entries"]] == ["spotify"]
