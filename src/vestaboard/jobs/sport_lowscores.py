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
from functools import cached_property

import httpx

from .. import codes
from ..font import Font
from ..scene import Scene
from .sport_highscores import (
    SCOREBOARD_URL,
    Game,
    SportHighScoresJob,
    display_name,
    game_status,
    parse_games,
)


class SportLowScoresJob(SportHighScoresJob):
    name = "sport_lowscores"

    def _league(self) -> str:
        return self.settings.sport_lowscore_league

    def _status(self, g: Game) -> str:
        """Low-scoring sports count innings/periods, not quarters: prefer ESPN's
        own live phrasing ("TOP 7TH", "P2") over the generic ``Q{period}``."""
        if g.state == "in" and g.detail:
            return g.detail.upper()
        return game_status(g)

    @cached_property
    def _score_font(self) -> Font:
        # Low scores stay 1-2 digits, so the compact 3x3 font fits two per slot.
        return Font.from_file(self.settings.fonts_dir / "3x3pixels.json")

    def _score_colors(self, away_score: int, home_score: int, final: bool) -> tuple[int, int]:
        """Leader's big score is violet while live, blue once final; loser/tie white."""
        leader = codes.BLUE if final else codes.VIOLET
        if away_score > home_score:
            return leader, codes.WHITE
        if home_score > away_score:
            return codes.WHITE, leader
        return codes.WHITE, codes.WHITE

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
        final = data.state == "post"
        c_away, c_home = self._score_colors(away.score, home.score, final)

        # A - B: big scores hugging a centred dash (away right, home left) so the
        # two- and one-digit cases both read tight, e.g. "12-9" / "3-5".
        scene.glyphs(str(away.score), region="A", on_code=c_away, align="right", font=self._score_font)
        scene.glyphs("-", region="J", on_code=codes.WHITE, align="center", font=self._score_font)
        scene.glyphs(str(home.score), region="B", on_code=c_home, align="left", font=self._score_font)

        # status spans the top-right (the league's own phrasing while live, e.g. "TOP 7TH")
        scene.write(self._status(data), region="C", align="right")
        # away (left-aligned): abbr D, score E, name F
        scene.write(away.abbr.upper(), region="D")
        scene.write(str(away.score), region="E")
        scene.write(display_name(away), region="F")
        # home (right-aligned): abbr G, score H, name I
        scene.write(home.abbr.upper(), region="G", align="right")
        scene.write(str(home.score), region="H", align="right")
        scene.write(display_name(home), region="I", align="right")

        # Final games get a blue accent pixel by region I, matching the winner's blue score.
        if final and away.score != home.score:
            i = scene.regions["I"]
            scene.set(i.row0, i.col0, codes.BLUE)
        return scene
