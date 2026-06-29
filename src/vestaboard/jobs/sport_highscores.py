"""Sport high-scores job: a live scoreboard for high-scoring sports (NBA, etc.).

Data: ESPN's public scoreboard JSON (no API key) for the configured
``SPORT_LEAGUE`` (e.g. ``basketball/nba``). The leading team's big score (A/B)
is green, the other white (a tie is both white). Layout per region:
  A/B  big score (nanofont, fits the 3-row badge), left/right
  C    game status/clock        D/G  team state (2-letter)
  E/H  score (small)            F/I  team name (or abbreviation if > 9 chars)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import cached_property

import httpx

from .. import codes
from ..font import Font
from ..scene import Scene
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


def leader_colors(home_score: int, away_score: int) -> tuple[int, int]:
    """Leader → green, other → white; a tie is both white."""
    if home_score > away_score:
        return codes.GREEN, codes.WHITE
    if away_score > home_score:
        return codes.WHITE, codes.GREEN
    return codes.WHITE, codes.WHITE


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

    def __init__(self, settings) -> None:
        super().__init__(settings)
        self._rotation_index = 0
        self._last_switch: datetime | None = None
        self._last_scores: dict[str, tuple[int, int]] = {}
        self._current_id: str | None = None
        self._last_sent: list[list[int]] | None = None

    @cached_property
    def _font(self) -> Font:
        return Font.from_file(self.settings.font_path)

    @cached_property
    def _score_font(self) -> Font:
        # nanofont's digits are 3 rows tall, so the big score fits the badge.
        return Font.from_file(self.settings.fonts_dir / "nanofont3x4.json")

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
        by_id = {g.id: g for g in pool}
        changed = [
            g for g in pool if self._last_scores.get(g.id, (g.home.score, g.away.score)) != (g.home.score, g.away.score)
        ]
        for g in pool:
            self._last_scores[g.id] = (g.home.score, g.away.score)

        rotate = timedelta(seconds=self.settings.sport_rotate_seconds)
        if changed:
            chosen = changed[0]
            self._last_switch = now
        elif self._current_id in by_id and self._last_switch and now - self._last_switch < rotate:
            chosen = by_id[self._current_id]
        else:
            self._rotation_index = (self._rotation_index + 1) % len(pool)
            chosen = pool[self._rotation_index]
            self._last_switch = now
        self._current_id = chosen.id
        return chosen

    def fetch(self) -> Game | None:
        url = SCOREBOARD_URL.format(league=self.settings.sport_league)
        payload = httpx.get(url, timeout=15.0).json()
        return self.select_game(parse_games(payload), datetime.now())

    def render(self, data: Game | None) -> Scene:
        scene = Scene.from_file(self.settings.scenes_dir / "sport_highscores.json", font=self._font)
        if data is None:
            scene.write("NO GAMES", region="F", align="right")
            return scene
        top, bottom = data.home, data.away
        c_top, c_bottom = leader_colors(top.score, bottom.score)

        # A/B: big score in the leader color (no leading zero)
        scene.glyphs(str(top.score), region="A", on_code=c_top, align="left", font=self._score_font)
        scene.glyphs(str(bottom.score), region="B", on_code=c_bottom, align="right", font=self._score_font)

        # top team (right-aligned): status C, state D, score E, name F
        scene.write(game_status(data), region="C", align="right")
        scene.write(self._state(top.abbr), region="D", align="right")
        scene.write(str(top.score), region="E", align="right")
        scene.write(display_name(top), region="F", align="right")
        # bottom team (left-aligned): state G, score H, name I
        scene.write(self._state(bottom.abbr), region="G")
        scene.write(str(bottom.score), region="H")
        scene.write(display_name(bottom), region="I")
        return scene

    def paint(self, client) -> dict | None:
        chars = self.build().to_characters()
        if chars == self._last_sent:
            return None
        result = client.send(chars)
        self._last_sent = chars
        return result
