"""Sport low-scores job: a live scoreboard for low-scoring sports (MLB, soccer,
hockey) whose scores stay to 1-2 digits.

Reuses the ESPN scoreboard parsing and rotation logic of
:class:`SportHighScoresJob`, but renders the two teams side by side (away left,
home right) with bigger room per digit. The leading team's big score is green,
the other white (a tie is both white). Layout per region:
  L    league (e.g. MLB)        C    game status/clock
  A/B  big score (nanofont), away right-aligned / home left-aligned
  D/G  team abbreviation        E/H  score (small)
  F/I  team name (or abbreviation if > 9 chars)
"""

from __future__ import annotations

from datetime import datetime

import httpx

from ..scene import Scene
from .sport_highscores import (
    SCOREBOARD_URL,
    Game,
    SportHighScoresJob,
    display_name,
    game_status,
    leader_colors,
    parse_games,
)


class SportLowScoresJob(SportHighScoresJob):
    name = "sport_lowscores"

    def _league(self) -> str:
        return self.settings.sport_lowscore_league

    def fetch(self) -> Game | None:
        url = SCOREBOARD_URL.format(league=self._league())
        payload = httpx.get(url, timeout=15.0).json()
        return self.select_game(parse_games(payload), datetime.now())

    def render(self, data: Game | None) -> Scene:
        scene = Scene.from_file(self.settings.scenes_dir / "sport_lowscores.json", font=self._font)
        scene.write(self._league().split("/")[-1].upper(), region="L")
        if data is None:
            scene.write("NO GAMES", region="I", align="right")
            return scene
        away, home = data.away, data.home
        c_away, c_home = leader_colors(away.score, home.score)

        # A/B: big score, hugging the centre (away right-aligned, home left-aligned)
        scene.glyphs(str(away.score), region="A", on_code=c_away, align="right", font=self._score_font)
        scene.glyphs(str(home.score), region="B", on_code=c_home, align="left", font=self._score_font)

        # status spans the top-right
        scene.write(game_status(data), region="C", align="right")
        # away (left-aligned): abbr D, score E, name F
        scene.write(away.abbr.upper(), region="D")
        scene.write(str(away.score), region="E")
        scene.write(display_name(away), region="F")
        # home (right-aligned): abbr G, score H, name I
        scene.write(home.abbr.upper(), region="G", align="right")
        scene.write(str(home.score), region="H", align="right")
        scene.write(display_name(home), region="I", align="right")
        return scene
