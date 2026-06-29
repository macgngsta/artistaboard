"""NBA job: a live game scoreboard with score-driven badge colors.

Data: ESPN's public scoreboard JSON (no API key). Badge color is set by the
score — the leading team is green, the other white (a tie is both white). Two
fixed badge shapes (from the mockup) are recolored per game.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import cached_property

import httpx

from .. import codes
from ..font import Font
from ..scene import Scene
from .base import Job

SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"


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
    detail: str  # e.g. "Final", "8:32 - 3rd"
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
    """Short status for the corner (≤6 chars)."""
    if g.state == "post":
        return "FINAL"
    if g.state == "in":
        return g.clock or f"Q{g.period}"
    return g.start.strftime("%H:%M") if g.start else "TBD"


class NBAJob(Job):
    name = "nba"
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

    def _pool(self, games: list[Game]) -> list[Game]:
        live = [g for g in games if g.live]
        if live:
            return live
        return games[:1]  # ESPN already returns the most relevant slate

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

        rotate = timedelta(seconds=self.settings.nba_rotate_seconds)
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
        payload = httpx.get(SCOREBOARD_URL, timeout=15.0).json()
        return self.select_game(parse_games(payload), datetime.now())

    def render(self, data: Game | None) -> Scene:
        scene = Scene.from_file(self.settings.scenes_dir / "nba.json", font=self._font)
        if data is None:
            scene.text("NO GAMES", r=2, align="center")
            return scene
        top, bottom = data.home, data.away
        c_top, c_bottom = leader_colors(top.score, bottom.score)
        scene.fill(c_top, region="A")  # shape-aware: recolors the badge cells
        scene.fill(c_bottom, region="B")

        # top team: stats right-aligned, rows 0-2
        scene.text(game_status(data), r=0, align="right")
        scene.text(f"{top.score} {top.abbr}", r=1, align="right")
        scene.text(_name(top.name, 9), r=2, align="right")
        # bottom team: stats left-aligned, rows 4-5
        scene.text(f"{bottom.abbr} {bottom.score}", r=4, c=0)
        scene.text(_name(bottom.name, 10), r=5, c=0)
        return scene

    def paint(self, client) -> dict | None:
        chars = self.build().to_characters()
        if chars == self._last_sent:
            return None
        result = client.send(chars)
        self._last_sent = chars
        return result


def _name(name: str, width: int) -> str:
    name = name.upper()
    return name if len(name) <= width else name[:width]
