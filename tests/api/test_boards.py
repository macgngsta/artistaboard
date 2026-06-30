def _make_board(auth_client, **over):
    body = {"name": "kitchen", "rw_key": "SECRET7890", **over}
    return auth_client.post("/boards", json=body)


def test_boards_require_auth(client):
    assert client.get("/boards").status_code == 401


def test_create_board_never_returns_key(auth_client):
    r = _make_board(auth_client)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["has_key"] is True and body["rw_key_last4"] == "7890"
    assert "rw_key" not in body and "rw_key_encrypted" not in body


def test_board_crud_and_scoping(auth_client):
    bid = _make_board(auth_client).json()["id"]
    assert auth_client.get(f"/boards/{bid}").json()["name"] == "kitchen"
    upd = auth_client.put(f"/boards/{bid}", json={"name": "living room"})
    assert upd.status_code == 200 and upd.json()["name"] == "living room"
    # updating without rw_key keeps the existing key
    assert upd.json()["has_key"] is True
    assert auth_client.delete(f"/boards/{bid}").status_code == 204
    assert auth_client.get(f"/boards/{bid}").status_code == 404


def test_assign_start_stop_flow(auth_client):
    bid = _make_board(auth_client).json()["id"]
    pid = auth_client.post(
        "/pipelines",
        json={"name": "p", "entries": [{"source_type": "job", "job_name": "clock", "duration_seconds": 60}]},
    ).json()["id"]

    # cannot start before assigning a pipeline
    assert auth_client.post(f"/boards/{bid}/start").status_code == 400

    assigned = auth_client.post(f"/boards/{bid}/assign", params={"pipeline_id": pid})
    assert assigned.status_code == 200 and assigned.json()["state"] == "stopped"

    started = auth_client.post(f"/boards/{bid}/start")
    assert started.status_code == 200 and started.json()["state"] == "running"

    assert auth_client.get(f"/boards/{bid}/run").json()["state"] == "running"

    stopped = auth_client.post(f"/boards/{bid}/stop")
    assert stopped.status_code == 200 and stopped.json()["state"] == "stopped"
