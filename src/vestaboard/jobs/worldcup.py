"""World Cup job: a live match scoreboard with flag-colored team badges.

Data: rezarahiminia/worldcup2026 raw JSON (no API key). It carries live fields
(``finished``, ``time_elapsed``, scores) during the tournament; outside it the
data is the pre-tournament snapshot (all ``notstarted``), so we fall back to the
next upcoming match.

Color coding: each team's badge takes the Vestaboard color closest to its flag's
most prominent color (data/flags.json). If both teams resolve to the same color,
the team for whom it's more prominent keeps it and the other gets a random color.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import cached_property

import httpx

from .. import codes
from ..font import Font
from ..scene import Scene
from .base import Job

MATCHES_URL = "https://raw.githubusercontent.com/rezarahiminia/worldcup2026/main/football.matches.json"
TEAMS_URL = "https://raw.githubusercontent.com/rezarahiminia/worldcup2026/main/football.teams.json"

LIVE_WINDOW = timedelta(minutes=150)  # a match is "live" within this of kickoff
_RANDOM_PALETTE = ["red", "orange", "yellow", "green", "blue", "violet", "white"]
_STAGE_LINE3 = {
    "r32": "ROUND 32",
    "r16": "ROUND 16",
    "qf": "QTR FINAL",
    "sf": "SEMI FINAL",
    "third": "3RD PLACE",
    "final": "FINAL",
}


@dataclass(frozen=True)
class Match:
    id: str
    home: str
    away: str
    home_code: str
    away_code: str
    home_score: int
    away_score: int
    group: str
    stage: str  # group / r32 / r16 / qf / sf / third / final
    matchday: str
    kickoff: datetime | None
    finished: bool
    elapsed: str

    @property
    def started(self) -> bool:
        return self.finished or (self.elapsed not in ("", "notstarted"))


def _parse_kickoff(local_date: str) -> datetime | None:
    try:
        return datetime.strptime(local_date.strip(), "%m/%d/%Y %H:%M")
    except (ValueError, AttributeError):
        return None


def parse_matches(matches_json: list[dict], teams_json: list[dict]) -> list[Match]:
    by_id = {t["id"]: t for t in teams_json}

    def team(tid: str) -> tuple[str, str]:
        t = by_id.get(tid, {})
        return t.get("name_en", tid), t.get("fifa_code", tid)

    out: list[Match] = []
    for m in matches_json:
        home, home_code = team(m.get("home_team_id", ""))
        away, away_code = team(m.get("away_team_id", ""))
        out.append(
            Match(
                id=str(m.get("id", "")),
                home=home,
                away=away,
                home_code=home_code,
                away_code=away_code,
                home_score=int(m.get("home_score") or 0),
                away_score=int(m.get("away_score") or 0),
                group=str(m.get("group", "")),
                stage=str(m.get("type", "group")),
                matchday=str(m.get("matchday", "")),
                kickoff=_parse_kickoff(m.get("local_date", "")),
                finished=str(m.get("finished", "")).upper() == "TRUE",
                elapsed=str(m.get("time_elapsed", "")),
            )
        )
    return out


def is_live(m: Match, now: datetime) -> bool:
    if m.finished:
        return False
    if m.elapsed not in ("", "notstarted"):
        return True
    return m.kickoff is not None and m.kickoff <= now < m.kickoff + LIVE_WINDOW


def match_status(m: Match, now: datetime) -> str:
    if m.finished:
        return "FT"
    if m.elapsed not in ("", "notstarted"):
        return f"{m.elapsed}'" if m.elapsed.isdigit() else m.elapsed.upper()
    if m.kickoff is not None:
        return m.kickoff.strftime("%H:%M")
    return "TBD"


def stage_lines(m: Match) -> tuple[str, str]:
    """The 2nd and 3rd metadata lines (line 1 is always WORLD CUP)."""
    if m.stage == "group":
        return f"STAGE {m.matchday}", f"GROUP {m.group}"
    return "STAGE 2", _STAGE_LINE3.get(m.stage, m.stage.upper())


def resolve_colors(home_colors: list[str], away_colors: list[str], rng: random.Random) -> tuple[int, int]:
    """Pick each team's badge color. Distinct primaries → each keeps theirs.
    Same primary → the team for whom it's more prominent keeps it (tiebreak: the
    flag with fewer colors is "more" that color); the loser gets a random color."""
    home = [codes.resolve_color(c) for c in home_colors] or [codes.WHITE]
    away = [codes.resolve_color(c) for c in away_colors] or [codes.WHITE]
    if home[0] != away[0]:
        return home[0], away[0]
    shared = home[0]
    home_keeps = len(home_colors) <= len(away_colors)
    other = codes.resolve_color(rng.choice([c for c in _RANDOM_PALETTE if codes.resolve_color(c) != shared]))
    return (shared, other) if home_keeps else (other, shared)


class WorldCupJob(Job):
    name = "world_cup"
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
    def _flags(self) -> dict[str, list[str]]:
        return json.loads(self.settings.flags_path.read_text())["teams"]

    def _team_colors(self, name: str) -> list[str]:
        return self._flags.get(name, ["white"])

    # -- selection -------------------------------------------------------------
    def _known(self, m: Match) -> bool:
        # both teams are real (knockout slots are placeholders we can't display)
        return m.home in self._flags and m.away in self._flags

    def _pool(self, matches: list[Match], now: datetime) -> list[Match]:
        group = self.settings.worldcup_group.strip().upper()
        if group:
            matches = [m for m in matches if m.group.upper() == group]
        matches = [m for m in matches if self._known(m)]
        live = [m for m in matches if is_live(m, now)]
        if live:
            return live
        upcoming = sorted((m for m in matches if m.kickoff and m.kickoff >= now), key=lambda m: m.kickoff)
        return upcoming[:1] or matches[:1]

    def select_match(self, matches: list[Match], now: datetime) -> Match | None:
        pool = self._pool(matches, now)
        if not pool:
            return None
        by_id = {m.id: m for m in pool}
        # A score change in any pool match wins the board immediately.
        changed = [
            m for m in pool if self._last_scores.get(m.id, (m.home_score, m.away_score)) != (m.home_score, m.away_score)
        ]
        for m in pool:
            self._last_scores[m.id] = (m.home_score, m.away_score)

        rotate = timedelta(seconds=self.settings.worldcup_rotate_seconds)
        if changed:
            chosen = changed[0]
            self._last_switch = now
        elif self._current_id in by_id and self._last_switch and now - self._last_switch < rotate:
            chosen = by_id[self._current_id]  # hold current
        else:
            self._rotation_index = (self._rotation_index + 1) % len(pool)
            chosen = pool[self._rotation_index]
            self._last_switch = now
        self._current_id = chosen.id
        return chosen

    # -- job hooks -------------------------------------------------------------
    def fetch(self) -> Match | None:
        matches = httpx.get(MATCHES_URL, timeout=15.0).json()
        teams = httpx.get(TEAMS_URL, timeout=15.0).json()
        return self.select_match(parse_matches(matches, teams), datetime.now())

    def render(self, data: Match | None) -> Scene:
        scene = Scene.from_file(self.settings.scenes_dir / "worldcup.json", font=self._font)
        if data is None:
            scene.text("NO MATCHES", r=0, region="D", align="center")
            return scene
        m = data
        rng = random.Random(f"{m.home}-{m.away}")
        c_home, c_away = resolve_colors(self._team_colors(m.home), self._team_colors(m.away), rng)

        scene.fill(c_home, region="A")  # hollow-square badges (shape-aware fill)
        scene.fill(c_away, region="B")

        line2, line3 = stage_lines(m)
        scene.text("WORLD CUP", r=0, region="M", align="right")
        scene.text(line2, r=1, region="M", align="right")
        scene.text(line3, r=2, region="M", align="right")

        now = datetime.now()
        scene.set(4, 0, c_home)  # team color indicator
        scene.text(_short(m.home, m.home_code, 14), c=2, region="D")
        if m.started:
            scene.text(f"{m.home_score} : {m.away_score}", region="D", align="right")

        scene.text(_short(m.away, m.away_code, 14), c=2, region="E")
        scene.set(5, 0, c_away)
        scene.text(match_status(m, now), region="E", align="right")
        return scene

    def paint(self, client) -> dict | None:
        chars = self.build().to_characters()
        if chars == self._last_sent:  # avoid re-flapping the board when nothing changed
            return None
        result = client.send(chars)
        self._last_sent = chars
        return result


def _short(name: str, code: str, width: int) -> str:
    name = name.upper()
    return name if len(name) <= width else (code.upper() if code else name[:width])
