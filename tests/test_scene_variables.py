from artistaboard.render import scene_variables


def _by_name(doc):
    return {v["name"]: v for v in scene_variables(doc)}


def test_bind_and_color_data_variables():
    doc = {
        "render": {
            "A": {"bind": "title", "as": "text"},
            "B": {"bind": "score", "as": "glyphs", "color": {"data": "score_color"}},
        }
    }
    vs = _by_name(doc)
    assert set(vs) == {"title", "score", "score_color"}
    assert vs["score_color"]["kind"] == "color"
    assert vs["title"]["required"] is True


def test_fallback_makes_variable_optional():
    doc = {"render": {"F": {"bind": "msg", "as": "text", "fallback": "NO MATCHES"}}}
    msg = _by_name(doc)["msg"]
    assert msg["required"] is False and msg["fallback"] == "NO MATCHES"


def test_leader_rule_pulls_score_and_final_keys():
    doc = {"render": {"A": {"as": "fill", "color": {"rule": "leader", "team": "home"}}}}
    vs = _by_name(doc)
    assert set(vs) == {"home.score", "away.score", "final"}


def test_stricter_use_overrides_optional():
    # same variable bound with a fallback in one region and without in another
    doc = {
        "render": {
            "A": {"bind": "x", "as": "text", "fallback": "-"},
            "B": {"bind": "x", "as": "text"},
        }
    }
    assert _by_name(doc)["x"]["required"] is True


def test_bare_array_has_no_variables():
    assert scene_variables(["A" * 22] * 6) == []
