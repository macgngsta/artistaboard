from artistaboard import codes
from artistaboard.config import Settings
from artistaboard.jobs.sport_highscores import Game, Team
from artistaboard.jobs.sport_lowscores import SportLowScoresJob


def _game(away_score, home_score, state="post", away="Yankees", home="Red Sox", detail=""):
    return Game(
        id="1",
        home=Team("BOS", home, home_score),
        away=Team("NYY", away, away_score),
        state=state,
        detail=detail,
        clock="",
        period=9,
        start=None,
    )


def test_render_side_by_side_with_league_and_names():
    job = SportLowScoresJob(Settings(_env_file=None, sport_lowscore_league="baseball/mlb"))
    scene = job.render(_game(4, 5))  # home (Red Sox) leads
    flat = [c for row in scene.to_characters() for c in row]
    # league label MLB and both team names rendered
    for ch in "MLB":
        assert codes.char_to_code(ch) in flat
    assert codes.char_to_code("Y") in flat  # YANKEES
    assert codes.char_to_code("X") in flat  # RED SOX


def _region_colors(scene, label):
    return {scene.grid[r][c] for r, c in scene.regions[label].cells}


def test_big_score_colored_by_state_and_leader():
    job = SportLowScoresJob(Settings(_env_file=None, sport_lowscore_league="baseball/mlb"))

    # Live: the leader's big score is violet, the other white.
    live = job.render(_game(4, 5, state="in"))  # home leads
    assert codes.WHITE in _region_colors(live, "A") and codes.VIOLET in _region_colors(live, "B")

    # Final: the leader turns blue and a matching blue accent pixel appears in region I.
    final = job.render(_game(4, 5, state="post"))
    assert codes.WHITE in _region_colors(final, "A") and codes.BLUE in _region_colors(final, "B")
    i = final.regions["I"]
    assert final.grid[i.row0][i.col0] == codes.BLUE


def test_status_uses_league_phrasing_while_live():
    job = SportLowScoresJob(Settings(_env_file=None, sport_lowscore_league="baseball/mlb"))
    scene = job.render(_game(1, 0, state="in", detail="Bot 8th"))
    c = scene.regions["C"]
    code_to_char = {v: k for k, v in codes.CHAR_TO_CODE.items()}
    text = "".join(code_to_char.get(scene.grid[c.row0][cc], "") for cc in range(c.col0, c.col1 + 1))
    assert "BOT 8TH" in text  # ESPN detail, not the generic "Q8"


def test_render_no_games():
    job = SportLowScoresJob(Settings(_env_file=None))
    flat = [c for row in job.render(None).to_characters() for c in row]
    assert codes.char_to_code("N") in flat  # "NO GAMES"


def test_long_name_falls_back_to_abbreviation():
    job = SportLowScoresJob(Settings(_env_file=None))
    scene = job.render(_game(2, 1, away="Diamondbacks", home="Red Sox"))  # 12 chars > 9
    code_to_char = {v: k for k, v in codes.CHAR_TO_CODE.items()}
    f_text = "".join(code_to_char.get(scene.grid[r][c], "") for r, c in scene.regions["F"].cells)
    assert f_text.strip() == "NYY"  # abbreviation, not the 12-char name
