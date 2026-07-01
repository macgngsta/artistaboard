from artistaboard.render import render_scene
from artistaboard.scene import Scene

SAMPLE = {"time": "14:30", "tz": "PT", "time_color": 69}


def _clock_doc(auth_client):
    return next(s for s in auth_client.get("/scenes").json() if s["name"] == "clock")["document"]


def test_preview_matches_direct_render(auth_client, settings):
    doc = _clock_doc(auth_client)
    resp = auth_client.post("/preview", json={"document": doc, "sample_data": SAMPLE})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert (body["rows"], body["cols"]) == (6, 22)

    # the endpoint must reuse the real renderer: same grid as building it directly
    scene = Scene.from_dict(doc)
    render_scene(scene, SAMPLE, settings)
    assert body["characters"] == scene.to_characters()


def test_preview_requires_auth(client):
    assert client.post("/preview", json={"document": ["A" * 22] * 6}).status_code == 401


def test_preview_invalid_document_is_422(auth_client):
    assert auth_client.post("/preview", json={"document": ["nope"] * 6}).status_code == 422


def test_preview_missing_data_key_returns_structured_422(auth_client):
    # A color bound to {data: k} with no value → structured 422 exposing the key,
    # so the client can seed it without parsing the message.
    doc = _clock_doc(auth_client)  # clock binds time_color via {data: time_color}
    resp = auth_client.post("/preview", json={"document": doc, "sample_data": {"time": "14:30", "tz": "PT"}})
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert detail["missing_key"] == "time_color"
    assert "cannot render scene" in detail["message"]
