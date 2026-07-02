from datetime import datetime, timedelta

from artistaboard import codes
from artistaboard.config import Settings
from artistaboard.jobs.worldcup import (
    Match,
    WorldCupJob,
    is_live,
    parse_espn,
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


def _espn_event(**status):
    return {
        "id": "9",
        "date": "2026-06-29T17:00Z",
        "season": {"slug": "round-of-32"},
        "status": {"type": status},
        "competitions": [
            {
                "competitors": [
                    {"homeAway": "home", "score": "2", "team": {"displayName": "Brazil", "abbreviation": "BRA"}},
                    {"homeAway": "away", "score": "1", "team": {"displayName": "Japan", "abbreviation": "JPN"}},
                ]
            }
        ],
    }


def test_parse_espn_maps_teams_scores_and_stage():
    m = parse_espn([_espn_event(state="post", completed=True)])[0]
    assert (m.home, m.away) == ("Brazil", "Japan")
    assert (m.home_code, m.away_code) == ("BRA", "JPN")
    assert (m.home_score, m.away_score) == (2, 1)
    assert m.stage == "r32" and m.finished
    assert isinstance(m.kickoff, datetime)  # UTC ISO -> local naive


def test_parse_espn_state_to_elapsed():
    pre = parse_espn([_espn_event(state="pre")])[0]
    live = parse_espn([_espn_event(state="in")])[0]
    assert pre.elapsed == "notstarted" and not pre.finished
    assert not live.finished and live.elapsed == "LIVE"  # falls back when no display clock


def test_is_live():
    assert is_live(_match(elapsed="67"), NOW)  # in progress
    assert not is_live(_match(finished=True, elapsed="90"), NOW)  # finished
    assert is_live(_match(elapsed="notstarted", kickoff=datetime(2026, 6, 28, 13, 30)), NOW)  # within window
    assert not is_live(_match(elapsed="notstarted", kickoff=datetime(2026, 6, 28, 9, 0)), NOW)  # window passed


def test_stage_lines():
    assert stage_lines(_match(stage="group", matchday="2", group="C")) == ("STAGE 2", "GROUP C")
    assert stage_lines(_match(stage="r16")) == ("STAGE 2", "ROUND 16")


def _job_with_flags(flags):
    job = WorldCupJob(Settings(_env_file=None))
    job._flags = flags  # override the file-loaded DB
    return job


def test_select_rotates_live_pool_by_clock():
    flags = {"Scotland": ["blue"], "Morocco": ["red"], "Spain": ["red"], "Japan": ["white"]}
    a = _match(id="a", home="Scotland", away="Morocco", elapsed="20")
    b = _match(id="b", home="Spain", away="Japan", elapsed="20")
    job = _job_with_flags(flags)
    job.settings.worldcup.rotate_seconds = 300

    t0 = datetime(2026, 6, 28, 14, 0)
    # Within one 300s bucket the pick is stable...
    assert job.select_match([a, b], t0).id == job.select_match([a, b], t0 + timedelta(seconds=120)).id
    # ...and across consecutive buckets both live matches get shown.
    seen = {job.select_match([a, b], t0 + timedelta(seconds=300 * k)).id for k in range(2)}
    assert seen == {"a", "b"}


def test_single_pins_first_of_pool():
    flags = {"Scotland": ["blue"], "Morocco": ["red"], "Spain": ["red"], "Japan": ["white"]}
    a = _match(id="a", home="Scotland", away="Morocco", elapsed="20")
    b = _match(id="b", home="Spain", away="Japan", elapsed="20")
    job = _job_with_flags(flags)
    job.settings.worldcup.single = True
    # No rotation: the same match shows regardless of the clock.
    t0 = datetime(2026, 6, 28, 14, 0)
    assert job.select_match([a, b], t0).id == "a"
    assert job.select_match([a, b], t0 + timedelta(minutes=30)).id == "a"


def _colors(scene, label):
    return {scene.grid[r][c] for r, c in scene.regions[label].cells}


def _row_text(scene, label):
    r = scene.regions[label]
    return "".join(codes.CODE_TO_CHAR.get(scene.grid[r.row0][c], " ") for c in range(r.col0, r.col1 + 1))


def test_render_prematch_names_dates_and_white_accents():
    job = WorldCupJob(Settings(_env_file=None))
    scene = job.render(_match())  # 0-0 notstarted, kickoff 06/28 13:00
    assert _row_text(scene, "F").startswith("SCOTLAND")
    assert _row_text(scene, "H").startswith("MOROCCO")
    # accent pixel right after each name; a 0-0 tie makes both white
    f = scene.regions["F"]
    assert scene.grid[f.row0][f.col0 + len("SCOTLAND")] == codes.WHITE
    assert "JUN 28" in _row_text(scene, "G")
    assert "13:00" in _row_text(scene, "I")


def test_render_live_leader_red_and_elapsed_clock():
    job = WorldCupJob(Settings(_env_file=None))
    scene = job.render(_match(home_score=2, away_score=1, elapsed="67"))
    assert codes.RED in _colors(scene, "A")  # home leads -> red while live
    assert codes.RED not in _colors(scene, "B")  # away trails -> white
    assert codes.RED in _colors(scene, "F")  # leader's name accent is red too
    assert "67'" in _row_text(scene, "G")  # elapsed minute on G, no banner
    assert codes.GREEN not in _colors(scene, "G")


def test_render_live_stoppage_time_splits_to_away_row():
    job = WorldCupJob(Settings(_env_file=None))
    scene = job.render(_match(home_score=1, away_score=0, elapsed="90'+4'"))
    assert "90'" in _row_text(scene, "G")  # base minute stays on the home row
    assert "+4'" in _row_text(scene, "I")  # stoppage moves to the away row
    assert "+4'" not in _row_text(scene, "G")


def test_render_final_blue_leader_win_banner_and_final_label():
    job = WorldCupJob(Settings(_env_file=None))
    scene = job.render(_match(home_score=1, away_score=3, finished=True, elapsed="90"))
    assert codes.BLUE in _colors(scene, "B")  # away leads -> blue once final
    assert _row_text(scene, "K").strip() == "FINAL"
    # winner (away) gets the green-flanked WIN banner on its row I; home row G does not
    assert "WIN" in _row_text(scene, "I") and codes.GREEN in _colors(scene, "I")
    assert codes.GREEN not in _colors(scene, "G")


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
