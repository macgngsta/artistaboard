"""World Cup job: a live match scoreboard with flag-colored team badges.

Data: rezarahiminia/worldcup2026 raw JSON (no API key). It carries live fields
(``finished``, ``time_elapsed``, scores) during the tournament; outside it the
data is the pre-tournament snapshot (all ``notstarted``), so we fall back to the
next upcoming match.

Declarative: the scene (worldcup.json) owns the layout and the leader colouring
(the ``leader`` rule, violet while live / blue once final). This job parses the
feed, selects the match, supplies the data envelope, and adds two pixel-level
touches the config can't express via a ``post_render`` hook: an accent pixel
after each team name (in its score colour) and the winner's ``WIN`` banner.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import cached_property
from typing import Any

import httpx

from .. import codes
from ..render import leader_color
from ..scene import Scene
from .base import Job

MATCHES_URL = "https://raw.githubusercontent.com/rezarahiminia/worldcup2026/main/football.matches.json"
TEAMS_URL = "https://raw.githubusercontent.com/rezarahiminia/worldcup2026/main/football.teams.json"

LIVE_WINDOW = timedelta(minutes=150)  # a match is "live" within this of kickoff
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


class WorldCupJob(Job):
    name = "world_cup"
    interval_seconds = 60
    scene_name = "worldcup"

    def __init__(self, settings) -> None:
        super().__init__(settings)
        self._rotation_index = 0
        self._last_switch: datetime | None = None
        self._last_scores: dict[str, tuple[int, int]] = {}
        self._current_id: str | None = None

    @cached_property
    def _flags(self) -> dict[str, list[str]]:
        return json.loads(self.settings.flags_path.read_text())["teams"]

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

    def bind(self, data: Match | None) -> dict[str, Any]:
        if data is None:
            return {}  # scene's region-F fallback renders "NO MATCHES"
        m = data
        final = m.finished
        live = m.started and not m.finished
        stage2, stage3 = stage_lines(m)
        # G/I per-state text (the WIN banner for final games is drawn in post_render):
        # live -> elapsed minute on G; pre-match -> kickoff date (G) and time (I).
        if final:
            g_text = i_text = ""
        elif live:
            g_text, i_text = _elapsed(m), ""
        elif m.kickoff:
            g_text, i_text = m.kickoff.strftime("%b %d").upper(), m.kickoff.strftime("%H:%M")
        else:
            g_text, i_text = "TBD", ""
        env: dict[str, Any] = {
            "home.score": m.home_score,
            "away.score": m.away_score,
            "final": final,
            "sep": "-",
            "title": "WORLD CUP",
            "stage2": stage2,
            "stage3": stage3,
            "home.name": _short(m.home, m.home_code, _NAME_WIDTH),
            "away.name": _short(m.away, m.away_code, _NAME_WIDTH),
            "g_text": g_text,
            "i_text": i_text,
        }
        if final:
            env["final_label"] = "FINAL"
        return env

    def post_render(self, scene: Scene, data: Match | None) -> None:
        if data is None:
            return
        m = data
        final = m.finished
        # An accent pixel right after each name, in that team's score colour.
        self._accent(
            scene, "F", _short(m.home, m.home_code, _NAME_WIDTH), leader_color(m.home_score, m.away_score, final=final)
        )
        self._accent(
            scene, "H", _short(m.away, m.away_code, _NAME_WIDTH), leader_color(m.away_score, m.home_score, final=final)
        )
        # A WIN banner on the winner's row at full time.
        if final and m.home_score > m.away_score:
            self._win_banner(scene, "G")
        elif final and m.away_score > m.home_score:
            self._win_banner(scene, "I")

    def _accent(self, scene: Scene, region: str, label: str, color: int) -> None:
        r = scene.regions[region]
        accent_col = r.col0 + len(label)
        if accent_col <= r.col1:
            scene.set(r.row0, accent_col, color)

    def _win_banner(self, scene: Scene, region: str) -> None:
        """A centred ``[green] W I N [green]`` strip marking the winner's row."""
        r = scene.regions[region]
        cells = [codes.GREEN, codes.char_to_code("W"), codes.char_to_code("I"), codes.char_to_code("N"), codes.GREEN]
        start = r.col0 + max(0, (r.width - len(cells)) // 2)
        for i, code in enumerate(cells):
            if start + i <= r.col1:
                scene.set(r.row0, start + i, code)


# Region F/H are 12 wide; cap names at 11 so the accent pixel has a cell to land in.
_NAME_WIDTH = 11


def _short(name: str, code: str, width: int) -> str:
    name = name.upper()
    return name if len(name) <= width else (code.upper() if code else name[:width])


def _elapsed(m: Match) -> str:
    """Live clock for region G: the minute (``67'``) or the feed's own label (``HT``)."""
    return f"{m.elapsed}'" if m.elapsed.isdigit() else m.elapsed.upper()
