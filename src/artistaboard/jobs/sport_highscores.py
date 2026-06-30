"""Sport high-scores job: a live scoreboard for high-scoring sports (NBA, etc.).

Data: ESPN's public scoreboard JSON (no API key) for the configured
``SPORT_LEAGUE`` (e.g. ``basketball/nba``). Declarative — the scene
(sport_highscores.json) owns the layout and the leader colouring (the ``leader``
rule, green scheme); this job parses ESPN, selects which game to show, and
supplies the data envelope.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from functools import cached_property
from typing import Any

import httpx

from ..rotation import RotationState, select
from .base import Job

SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/{league}/scoreboard"
NAME_WIDTH = 9  # region F/I width


@dataclass(frozen=True)
class Team:
    abbr: str
    name: str
    score: int


@dataclass(frozen=True)
class Game:
    id: str
    home: Team
    away: Team
    state: str  # pre / in / post
    detail: str
    clock: str
    period: int
    start: datetime | None

    @property
    def live(self) -> bool:
        return self.state == "in"


def _parse_dt(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def _team(competitor: dict) -> Team:
    t = competitor.get("team", {})
    return Team(
        abbr=t.get("abbreviation", "?"),
        name=t.get("name", t.get("abbreviation", "?")),
        score=int(competitor.get("score") or 0),
    )


def parse_games(payload: dict) -> list[Game]:
    games: list[Game] = []
    for e in payload.get("events", []):
        comp = (e.get("competitions") or [{}])[0]
        sides = {c.get("homeAway"): c for c in comp.get("competitors", [])}
        if "home" not in sides or "away" not in sides:
            continue
        status = e.get("status", {})
        st = status.get("type", {})
        games.append(
            Game(
                id=str(e.get("id", "")),
                home=_team(sides["home"]),
                away=_team(sides["away"]),
                state=st.get("state", "pre"),
                detail=st.get("shortDetail", ""),
                clock=status.get("displayClock", ""),
                period=int(status.get("period") or 0),
                start=_parse_dt(e.get("date", "")),
            )
        )
    return games


def game_status(g: Game) -> str:
    if g.state == "post":
        return "FINAL"
    if g.state == "in":
        return g.clock or f"Q{g.period}"
    return g.start.strftime("%H:%M") if g.start else "TBD"


def display_name(team: Team) -> str:
    """The team name, or its abbreviation when the name doesn't fit."""
    name = team.name.upper()
    return name if len(name) <= NAME_WIDTH else team.abbr.upper()


class SportHighScoresJob(Job):
    name = "sport_highscores"
    interval_seconds = 60
    scene_name = "sport_highscores"

    def __init__(self, settings) -> None:
        super().__init__(settings)
        self._rotation = RotationState()

    @cached_property
    def _states(self) -> dict[str, str]:
        data = json.loads(self.settings.team_states_path.read_text())
        return data.get(self.settings.sport_league, {})

    def _state(self, abbr: str) -> str:
        return self._states.get(abbr, abbr[:2])

    def _pool(self, games: list[Game]) -> list[Game]:
        live = [g for g in games if g.live]
        return live or games[:1]

    def select_game(self, games: list[Game], now: datetime) -> Game | None:
        pool = self._pool(games)
        if not pool:
            return None
        # A score change in any pool game wins the board immediately; otherwise
        # hold the current game until the rotate cadence elapses, then advance.
        chosen, self._rotation = select(
            pool,
            key=lambda g: g.id,
            signal=lambda g: (g.home.score, g.away.score),
            state=self._rotation,
            now=now,
            rotate_seconds=self.settings.sport_rotate_seconds,
        )
        return chosen

    def fetch(self) -> Game | None:
        url = SCOREBOARD_URL.format(league=self.settings.sport_league)
        payload = httpx.get(url, timeout=15.0).json()
        return self.select_game(parse_games(payload), datetime.now())

    def bind(self, data: Game | None) -> dict[str, Any]:
        if data is None:
            return {}  # scene's region-F fallback renders "NO GAMES"
        h, a = data.home, data.away
        return {
            "home.score": h.score,
            "away.score": a.score,
            "home.name": display_name(h),
            "away.name": display_name(a),
            "home.state": self._state(h.abbr),
            "away.state": self._state(a.abbr),
            "status": game_status(data),
        }
