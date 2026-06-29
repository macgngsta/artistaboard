import random
from datetime import datetime

from vestaboard import codes
from vestaboard.config import Settings
from vestaboard.jobs.worldcup import (
    Match,
    WorldCupJob,
    is_live,
    match_status,
    parse_matches,
    resolve_colors,
    stage_lines,
)

NOW = datetime(2026, 6, 28, 14, 0)


def _match(**kw):
    base = dict(
        id="1",
        home="Scotland",
        away="Morocco",
        home_code="SCO",
        away_code="MAR",
        home_score=0,
        away_score=0,
        group="C",
        stage="group",
        matchday="1",
        kickoff=datetime(2026, 6, 28, 13, 0),
        finished=False,
        elapsed="notstarted",
    )
    base.update(kw)
    return Match(**base)


def test_parse_matches_maps_team_ids_and_scores():
    teams = [{"id": "1", "name_en": "Mexico", "fifa_code": "MEX"}, {"id": "2", "name_en": "Brazil", "fifa_code": "BRA"}]
    raw = [
        {
            "id": "1",
            "home_team_id": "1",
            "away_team_id": "2",
            "home_score": "2",
            "away_score": "1",
            "group": "A",
            "type": "group",
            "matchday": "1",
            "local_date": "06/11/2026 13:00",
            "finished": "TRUE",
            "time_elapsed": "90",
        }
    ]
    m = parse_matches(raw, teams)[0]
    assert (m.home, m.away) == ("Mexico", "Brazil")
    assert (m.home_score, m.away_score) == (2, 1)
    assert m.finished and m.kickoff == datetime(2026, 6, 11, 13, 0)


def test_is_live():
    assert is_live(_match(elapsed="67"), NOW)  # in progress
    assert not is_live(_match(finished=True, elapsed="90"), NOW)  # finished
    assert is_live(_match(elapsed="notstarted", kickoff=datetime(2026, 6, 28, 13, 30)), NOW)  # within window
    assert not is_live(_match(elapsed="notstarted", kickoff=datetime(2026, 6, 28, 9, 0)), NOW)  # window passed


def test_match_status():
    assert match_status(_match(finished=True), NOW) == "FT"
    assert match_status(_match(elapsed="67"), NOW) == "67'"
    assert match_status(_match(elapsed="HT"), NOW) == "HT"
    assert match_status(_match(elapsed="notstarted"), NOW) == "13:00"


def test_stage_lines():
    assert stage_lines(_match(stage="group", matchday="2", group="C")) == ("STAGE 2", "GROUP C")
    assert stage_lines(_match(stage="r16")) == ("STAGE 2", "ROUND 16")


def test_resolve_colors_distinct_and_collision():
    rng = random.Random("seed")
    # distinct primaries: each keeps its own
    assert resolve_colors(["blue", "white"], ["red", "green"], rng) == (codes.BLUE, codes.RED)
    # same primary (red): home keeps red (fewer colors wins tiebreak), away gets a non-red color
    home, away = resolve_colors(["red", "white"], ["red", "white", "blue"], rng)
    assert home == codes.RED and away != codes.RED


def _job_with_flags(flags):
    job = WorldCupJob(Settings(_env_file=None))
    job._flags = flags  # override the file-loaded DB
    return job


def test_select_rotates_then_switches_on_score_change():
    flags = {"Scotland": ["blue"], "Morocco": ["red"], "Spain": ["red"], "Japan": ["white"]}
    a = _match(id="a", home="Scotland", away="Morocco", elapsed="20")
    b = _match(id="b", home="Spain", away="Japan", elapsed="20")
    job = _job_with_flags(flags)
    job.settings.worldcup_rotate_seconds = 300

    first = job.select_match([a, b], datetime(2026, 6, 28, 14, 0))
    # not enough time elapsed -> holds the same match
    held = job.select_match([a, b], datetime(2026, 6, 28, 14, 2))
    assert held.id == first.id
    # 5+ minutes later -> rotates to the other live match
    rotated = job.select_match([a, b], datetime(2026, 6, 28, 14, 6))
    assert rotated.id != first.id
    # a score change immediately wins the board
    b2 = _match(id="b", home="Spain", away="Japan", elapsed="21", home_score=1)
    after_goal = job.select_match([a, b2], datetime(2026, 6, 28, 14, 7))
    assert after_goal.id == "b"


def test_render_two_badges_and_kickoff_card():
    job = _job_with_flags({"Scotland": ["blue", "white"], "Morocco": ["red", "green"]})
    scene = job.render(_match())  # kickoff 06/28/2026 13:00
    a = {scene.grid[r][c] for r, c in scene.regions["A"].cells}
    b = {scene.grid[r][c] for r, c in scene.regions["B"].cells}
    assert a == {codes.BLUE} and b == {codes.RED}  # home left, away right flag colors
    flat = [c for row in scene.to_characters() for c in row]
    for ch in "SCOTLAND":  # home team name on its row
        assert codes.char_to_code(ch) in flat
    assert codes.char_to_code("J") in flat  # JUN date
    assert codes.char_to_code(":") in flat  # 13:00 kickoff time


def test_paint_skips_when_unchanged():
    sent = []

    class FakeClient:
        def send(self, chars):
            sent.append(chars)
            return {"status": "ok"}

    job = _job_with_flags({"Scotland": ["blue"], "Morocco": ["red"]})
    job.fetch = lambda: _match(elapsed="67")  # deterministic
    client = FakeClient()
    job.paint(client)
    job.paint(client)  # identical scene -> second send skipped
    assert len(sent) == 1
