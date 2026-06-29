from datetime import datetime

from vestaboard import codes
from vestaboard.config import Settings
from vestaboard.jobs.nba import Game, NBAJob, Team, game_status, leader_colors, parse_games


def _game(hs, as_, state="in", gid="1", clock="8:32", period=3):
    return Game(
        id=gid,
        home=Team("SA", "Spurs", hs),
        away=Team("MIN", "Wolves", as_),
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
    assert g.away.abbr == "NY" and g.away.score == 94
    assert g.live and g.clock == "8:32"


def test_leader_colors():
    assert leader_colors(106, 107) == (codes.WHITE, codes.GREEN)  # away leads
    assert leader_colors(107, 106) == (codes.GREEN, codes.WHITE)  # home leads
    assert leader_colors(100, 100) == (codes.WHITE, codes.WHITE)  # tie


def test_game_status():
    assert game_status(_game(1, 0, state="post")) == "FINAL"
    assert game_status(_game(1, 0, state="in", clock="8:32")) == "8:32"
    assert game_status(_game(0, 0, state="pre")) == "19:00"


def test_select_rotates_then_switches_on_score_change():
    job = NBAJob(Settings(_env_file=None))
    job.settings.nba_rotate_seconds = 300
    a = _game(50, 48, gid="a")
    b = _game(60, 55, gid="b")
    first = job.select_game([a, b], datetime(2026, 6, 28, 19, 0))
    held = job.select_game([a, b], datetime(2026, 6, 28, 19, 2))
    assert held.id == first.id
    rotated = job.select_game([a, b], datetime(2026, 6, 28, 19, 6))
    assert rotated.id != first.id
    b2 = _game(60, 58, gid="b")  # score changed
    assert job.select_game([a, b2], datetime(2026, 6, 28, 19, 7)).id == "b"


def test_render_colors_badges_by_score():
    job = NBAJob(Settings(_env_file=None))
    scene = job.render(_game(106, 107))  # away (bottom) leads
    a, b = scene.regions["A"], scene.regions["B"]
    assert {scene.grid[r][c] for r, c in a.cells} == {codes.WHITE}
    assert {scene.grid[r][c] for r, c in b.cells} == {codes.GREEN}
    flat = [c for row in scene.to_characters() for c in row]
    assert codes.char_to_code("S") in flat  # team name rendered


def test_paint_skips_when_unchanged():
    sent = []

    class FakeClient:
        def send(self, chars):
            sent.append(chars)
            return {"status": "ok"}

    job = NBAJob(Settings(_env_file=None))
    job.fetch = lambda: _game(90, 94, state="post")
    job.paint(FakeClient())
    job.paint(FakeClient())
    assert len(sent) == 1
