from datetime import datetime

from vestaboard import codes
from vestaboard.config import Settings
from vestaboard.jobs.sport_highscores import (
    Game,
    SportHighScoresJob,
    Team,
    display_name,
    game_status,
    leader_colors,
    parse_games,
)


def _game(hs, as_, state="in", gid="1", clock="8:32", period=3, home="Spurs", away="Wolves"):
    return Game(
        id=gid,
        home=Team("SA", home, hs),
        away=Team("MIN", away, as_),
        state=state,
        detail="",
        clock=clock,
        period=period,
        start=datetime(2026, 6, 28, 19, 0),
    )


def test_parse_games_maps_competitors_and_status():
    payload = {
        "events": [
            {
                "id": "401",
                "date": "2026-06-28T23:00Z",
                "status": {"type": {"state": "in", "shortDetail": "8:32 - 3rd"}, "displayClock": "8:32", "period": 3},
                "competitions": [
                    {
                        "competitors": [
                            {"homeAway": "home", "team": {"abbreviation": "SA", "name": "Spurs"}, "score": "90"},
                            {"homeAway": "away", "team": {"abbreviation": "NY", "name": "Knicks"}, "score": "94"},
                        ]
                    }
                ],
            }
        ]
    }
    g = parse_games(payload)[0]
    assert g.home.abbr == "SA" and g.home.score == 90
    assert g.away.score == 94 and g.live and g.clock == "8:32"


def test_leader_colors():
    assert leader_colors(106, 107) == (codes.WHITE, codes.GREEN)
    assert leader_colors(107, 106) == (codes.GREEN, codes.WHITE)
    assert leader_colors(100, 100) == (codes.WHITE, codes.WHITE)


def test_game_status():
    assert game_status(_game(1, 0, state="post")) == "FINAL"
    assert game_status(_game(1, 0, state="in", clock="8:32")) == "8:32"
    assert game_status(_game(0, 0, state="pre")) == "19:00"


def test_display_name_falls_back_to_abbreviation_when_too_long():
    assert display_name(Team("LAL", "Lakers", 0)) == "LAKERS"
    assert display_name(Team("MIN", "Timberwolves", 0)) == "MIN"  # 12 chars > 9


def test_state_lookup_uses_data_file():
    job = SportHighScoresJob(Settings(_env_file=None))
    assert job._state("SA") == "TX" and job._state("MIN") == "MN"
    assert job._state("ZZZ") == "ZZ"  # fallback to abbr[:2]


def test_select_rotates_then_switches_on_score_change():
    job = SportHighScoresJob(Settings(_env_file=None))
    job.settings.sport_rotate_seconds = 300
    a = _game(50, 48, gid="a")
    b = _game(60, 55, gid="b")
    first = job.select_game([a, b], datetime(2026, 6, 28, 19, 0))
    assert job.select_game([a, b], datetime(2026, 6, 28, 19, 2)).id == first.id
    assert job.select_game([a, b], datetime(2026, 6, 28, 19, 6)).id != first.id
    b2 = _game(60, 58, gid="b")  # score changed
    assert job.select_game([a, b2], datetime(2026, 6, 28, 19, 7)).id == "b"


def test_render_big_scores_colored_by_leader():
    job = SportHighScoresJob(Settings(_env_file=None))
    scene = job.render(_game(106, 107))  # away (bottom) leads -> B green, A white
    a_colors = {scene.grid[r][c] for r, c in scene.regions["A"].cells}
    b_colors = {scene.grid[r][c] for r, c in scene.regions["B"].cells}
    assert codes.WHITE in a_colors and codes.GREEN in b_colors
    flat = [c for row in scene.to_characters() for c in row]
    assert codes.char_to_code("T") in flat  # state TX rendered


def test_paint_skips_when_unchanged():
    sent = []

    class FakeClient:
        def send(self, chars):
            sent.append(chars)
            return {"status": "ok"}

    job = SportHighScoresJob(Settings(_env_file=None))
    job.fetch = lambda: _game(90, 94, state="post")
    job.paint(FakeClient())
    job.paint(FakeClient())
    assert len(sent) == 1
