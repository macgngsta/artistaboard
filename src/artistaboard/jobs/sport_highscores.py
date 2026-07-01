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
from typing import Any, ClassVar

from pydantic import Field

from ..http import get_json
from ..rotation import rotate_index
from .base import Job, JobOptions, jsonable
from .espn import event_sides, parse_iso, to_int

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


def _team(competitor: dict) -> Team:
    t = competitor.get("team", {})
    return Team(
        abbr=t.get("abbreviation", "?"),
        name=t.get("name", t.get("abbreviation", "?")),
        score=to_int(competitor.get("score")),
    )


def parse_games(payload: dict) -> list[Game]:
    games: list[Game] = []
    for e in payload.get("events", []):
        home_c, away_c = event_sides(e)
        if not home_c or not away_c:
            continue
        status = e.get("status", {})
        st = status.get("type", {})
        games.append(
            Game(
                id=str(e.get("id", "")),
                home=_team(home_c),
                away=_team(away_c),
                state=st.get("state", "pre"),
                detail=st.get("shortDetail", ""),
                clock=status.get("displayClock", ""),
                period=to_int(status.get("period")),
                start=parse_iso(e.get("date", "")),
            )
        )
    return games


def _game_from_dict(d: dict) -> Game:
    """Rebuild a Game from a snapshot payload: nested Team dicts and a serialized
    start timestamp (inverse of jsonable)."""
    d = dict(d)
    start = d.get("start")
    d["start"] = datetime.fromisoformat(start) if start else None
    d["home"] = Team(**d["home"])
    d["away"] = Team(**d["away"])
    return Game(**d)


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


class SportHighScoresOptions(JobOptions):
    league: str | None = None  # ESPN sport/league path (e.g. "basketball/nba")
    rotate_seconds: int | None = Field(default=None, gt=0)
    single: bool | None = None  # show one game (no rotation) instead of cycling the pool
    override_map: ClassVar[dict[str, str]] = {
        "league": "sport_league",
        "rotate_seconds": "sport_rotate_seconds",
        "single": "sport_single",
    }
    fetch_defining: ClassVar[frozenset[str]] = frozenset({"league"})  # each league is its own series


class SportHighScoresJob(Job):
    name = "sport_highscores"
    interval_seconds = 60
    scene_name = "sport_highscores"
    Options = SportHighScoresOptions

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
        if self.settings.sport_single or len(pool) == 1:
            return pool[0]
        # Cycle the live-game pool on the rotate cadence, purely from the clock so
        # rotation advances across paints without any per-paint state.
        return pool[rotate_index(len(pool), now, self.settings.sport_rotate_seconds)]

    def _league(self) -> str:
        return self.settings.sport_league

    def _scoreboard_payload(self) -> dict:
        return get_json(SCOREBOARD_URL.format(league=self._league()))

    def fetch(self) -> Game | None:
        return self.select_game(parse_games(self._scoreboard_payload()), datetime.now())

    def poll(self) -> dict[str, Any]:
        # Every game in the league; live selection / rotation is applied at render.
        return {
            "games": jsonable(parse_games(self._scoreboard_payload())),
            "league": self._league(),
            "polled_at": datetime.now().isoformat(),
        }

    def from_snapshot(self, payload: dict[str, Any]) -> Game | None:
        games = [_game_from_dict(g) for g in payload.get("games", [])]
        return self.select_game(games, datetime.now())

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
