VALID_DOC = {
    "grid": ["AAAAAAAAAAAAAAAAAAAAAA"] * 6,
    "render": {"A": {"bind": "msg", "as": "text", "fallback": "HI"}},
}


def test_scenes_require_auth(client):
    assert client.get("/scenes").status_code == 401


def test_list_includes_seeded_system_scenes(auth_client):
    rows = auth_client.get("/scenes").json()
    names = {s["name"] for s in rows}
    assert "clock" in names  # bundled scenes are seeded as system templates
    assert all(s["is_system"] for s in rows if s["name"] == "clock")


def test_create_get_update_delete(auth_client):
    created = auth_client.post("/scenes", json={"name": "mine", "document": VALID_DOC})
    assert created.status_code == 201, created.text
    sid = created.json()["id"]
    assert created.json()["owner_id"] is not None

    assert auth_client.get(f"/scenes/{sid}").json()["name"] == "mine"

    updated = auth_client.put(f"/scenes/{sid}", json={"name": "renamed", "document": VALID_DOC})
    assert updated.status_code == 200 and updated.json()["name"] == "renamed"

    assert auth_client.delete(f"/scenes/{sid}").status_code == 204
    assert auth_client.get(f"/scenes/{sid}").status_code == 404


def test_required_variables_derived_on_create(auth_client):
    doc = {
        "grid": ["BBBBBBBBBBBBBBBBBBBBBB"] * 6,
        "render": {"B": {"bind": "time", "as": "glyphs", "color": {"data": "time_color"}}},
    }
    body = auth_client.post("/scenes", json={"name": "v", "document": doc}).json()
    names = {v["name"] for v in body["required_variables"]}
    assert names == {"time", "time_color"}


def test_create_invalid_document_is_422(auth_client):
    bad = {"grid": ["TOO_SHORT"] * 6}  # rows not 22 wide
    assert auth_client.post("/scenes", json={"name": "bad", "document": bad}).status_code == 422


def test_cannot_edit_or_delete_system_scene(auth_client):
    system = next(s for s in auth_client.get("/scenes").json() if s["is_system"])
    sid = system["id"]
    assert auth_client.put(f"/scenes/{sid}", json={"name": "hijack", "document": VALID_DOC}).status_code == 403
    assert auth_client.delete(f"/scenes/{sid}").status_code == 403
