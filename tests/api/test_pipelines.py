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


def _new_pipeline(auth_client, name="p", entries=None):
    r = auth_client.post("/pipelines", json={"name": name, "entries": entries or []})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_pipeline_entry_embeds_another_pipeline(auth_client):
    child = _new_pipeline(auth_client, "child")
    r = auth_client.post(
        "/pipelines",
        json={
            "name": "parent",
            "entries": [{"source_type": "pipeline", "sub_pipeline_id": child, "duration_seconds": 60}],
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["entries"][0]["sub_pipeline_id"] == child


def test_pipeline_entry_requires_sub_pipeline_id(auth_client):
    r = auth_client.post(
        "/pipelines",
        json={"name": "p", "entries": [{"source_type": "pipeline", "duration_seconds": 60}]},
    )
    assert r.status_code == 422


def test_pipeline_entry_unknown_sub_pipeline_is_422(auth_client):
    r = auth_client.post(
        "/pipelines",
        json={
            "name": "p",
            "entries": [{"source_type": "pipeline", "sub_pipeline_id": "missing", "duration_seconds": 60}],
        },
    )
    assert r.status_code == 422


def test_pipeline_self_reference_is_rejected(auth_client):
    pid = _new_pipeline(auth_client, "p")
    r = auth_client.put(
        f"/pipelines/{pid}",
        json={"name": "p", "entries": [{"source_type": "pipeline", "sub_pipeline_id": pid, "duration_seconds": 60}]},
    )
    assert r.status_code == 422
    assert "cycle" in r.text.lower()


def test_pipeline_two_node_cycle_is_rejected(auth_client):
    child = _new_pipeline(auth_client, "child")
    parent = _new_pipeline(
        auth_client, "parent", [{"source_type": "pipeline", "sub_pipeline_id": child, "duration_seconds": 60}]
    )
    # parent -> child exists; child -> parent would close the loop
    r = auth_client.put(
        f"/pipelines/{child}",
        json={
            "name": "child",
            "entries": [{"source_type": "pipeline", "sub_pipeline_id": parent, "duration_seconds": 60}],
        },
    )
    assert r.status_code == 422
    assert "cycle" in r.text.lower()


def test_update_preserves_entry_ids_when_entries_unchanged(auth_client):
    entries = [
        {"source_type": "job", "job_name": "clock", "duration_seconds": 30},
        {"source_type": "job", "job_name": "spotify", "duration_seconds": 60},
    ]
    created = auth_client.post("/pipelines", json={"name": "p", "entries": entries}).json()
    ids_before = [e["id"] for e in created["entries"]]

    # Rename only, same entries: ids must survive so a running board's
    # BoardRun.current_entry_id keeps pointing at a real entry.
    upd = auth_client.put(f"/pipelines/{created['id']}", json={"name": "renamed", "entries": entries})
    assert upd.status_code == 200
    assert [e["id"] for e in upd.json()["entries"]] == ids_before
