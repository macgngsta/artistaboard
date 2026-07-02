"""Sport low-scores job: a live scoreboard for low-scoring sports (MLB, soccer,
hockey) whose scores stay to 1-2 digits.

Reuses the ESPN scoreboard parsing, rotation, and game selection of
:class:`SportHighScoresJob`. Declarative — the scene (sport_lowscores.json) lays
the two teams side by side (away left, home right) and colours the big scores via
the ``leader`` rule (violet while live, blue once final); this job supplies the
data and adds the winner's blue accent pixel via a ``post_render`` hook.
"""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import Field

from .. import codes
from ..scene import Scene
from .base import JobOptions
from .sport_highscores import (
    Game,
    SportHighScoresJob,
    display_name,
    game_status,
)


class SportLowScoresOptions(JobOptions):
    league: str | None = None  # ESPN sport/league path (e.g. "baseball/mlb")
    rotate_seconds: int | None = Field(default=None, gt=0)
    # The low job's user-facing "league" targets the shared SportConfig's
    # lowscore_league field; rotate_seconds is shared, so it maps 1:1 (no entry).
    override_map: ClassVar[dict[str, str]] = {"league": "lowscore_league"}
    fetch_defining: ClassVar[frozenset[str]] = frozenset({"league"})


class SportLowScoresJob(SportHighScoresJob):
    name = "sport_lowscores"
    scene_name = "sport_lowscores"
    Options = SportLowScoresOptions

    def _league(self) -> str:
        return self.settings.sport.lowscore_league

    def _status(self, g: Game) -> str:
        """Low-scoring sports count innings/periods, not quarters: prefer ESPN's
        own live phrasing ("TOP 7TH", "P2") over the generic ``Q{period}``."""
        if g.state == "in" and g.detail:
            return g.detail.upper()
        return game_status(g)

    # fetch() and poll() are inherited from SportHighScoresJob; both route through
    # _league() (overridden above), so they use the low-score league's scoreboard.

    def bind(self, data: Game | None) -> dict[str, Any]:
        env: dict[str, Any] = {"league": self._league().split("/")[-1].upper()}
        if data is None:
            return env  # scene's region-I fallback renders "NO GAMES"
        away, home = data.away, data.home
        env.update(
            {
                "status": self._status(data),
                "final": data.state == "post",
                "sep": "-",
                "away.score": away.score,
                "home.score": home.score,
                "away.abbr": away.abbr,
                "home.abbr": home.abbr,
                "away.name": display_name(away),
                "home.name": display_name(home),
            }
        )
        return env

    def post_render(self, scene: Scene, data: Game | None) -> None:
        """A blue accent pixel by the home name marks a finished, decided game,
        echoing the winner's blue score."""
        if data is None or data.state != "post" or data.away.score == data.home.score:
            return
        i = scene.regions["I"]
        scene.set(i.row0, i.col0, codes.BLUE)
