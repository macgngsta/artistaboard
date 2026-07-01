def test_jobs_require_auth(client):
    assert client.get("/jobs").status_code == 401


def test_jobs_lists_options_schemas(auth_client):
    jobs = {j["name"]: j for j in auth_client.get("/jobs").json()}
    assert {"clock", "muni", "world_cup", "sport_highscores", "sport_lowscores", "spotify"} <= set(jobs)
    # World Cup exposes its typed options so the UI can render a form.
    props = jobs["world_cup"]["options_schema"]["properties"]
    assert {"group", "rotate_seconds"} <= set(props)
    # The Settings-mapping ClassVar is not a field, so it never leaks into the schema.
    assert "override_map" not in props
    # A job with no knobs has an empty options form.
    assert jobs["spotify"]["options_schema"].get("properties", {}) == {}
