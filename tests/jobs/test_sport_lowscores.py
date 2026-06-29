from vestaboard import codes
from vestaboard.config import Settings
from vestaboard.jobs.sport_highscores import Game, Team
from vestaboard.jobs.sport_lowscores import SportLowScoresJob


def _game(away_score, home_score, state="post", away="Yankees", home="Red Sox"):
    return Game(
        id="1",
        home=Team("BOS", home, home_score),
        away=Team("NYY", away, away_score),
        state=state,
        detail="",
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


def test_big_score_colored_by_leader():
    job = SportLowScoresJob(Settings(_env_file=None, sport_lowscore_league="baseball/mlb"))
    scene = job.render(_game(4, 5))  # home leads -> B green, away A white
    a_colors = {scene.grid[r][c] for r, c in scene.regions["A"].cells}
    b_colors = {scene.grid[r][c] for r, c in scene.regions["B"].cells}
    assert codes.WHITE in a_colors and codes.GREEN in b_colors


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
