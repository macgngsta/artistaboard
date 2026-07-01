"""World Cup job: a live match scoreboard with flag-colored team badges.

Data: ESPN's public ``fifa.world`` scoreboard JSON (no API key). It resolves
knockout brackets and carries live state (``pre``/``in``/``post`` plus a display
clock and scores), so the board tracks real games as they happen. We query a
window around now so the selector can pick a live match or fall back to the next
upcoming one.

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
from typing import Any, ClassVar

import httpx
from pydantic import Field

from .. import codes
from ..render import leader_color
from ..rotation import RotationState, select
from ..scene import Scene
from .base import Job, JobOptions

SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard"
FETCH_WINDOW_DAYS = 14  # how far ahead to look for the next upcoming match

LIVE_WINDOW = timedelta(minutes=150)  # a match is "live" within this of kickoff
# ESPN season slug -> our stage code (drives the metadata lines in stage_lines).
_STAGE_FROM_SLUG = {
    "group-stage": "group",
    "round-of-32": "r32",
    "round-of-16": "r16",
    "quarterfinals": "qf",
    "semifinals": "sf",
    "third-place": "third",
    "final": "final",
}
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


def _parse_kickoff(iso: str) -> datetime | None:
    """ESPN gives UTC ISO timestamps (``2026-06-29T17:00Z``); selection compares
    against ``datetime.now()`` (naive local), so convert UTC -> local naive."""
    try:
        dt = datetime.fromisoformat(iso.strip().replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
    return dt.astimezone().replace(tzinfo=None)


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def parse_espn(events: list[dict]) -> list[Match]:
    out: list[Match] = []
    for e in events:
        comp = (e.get("competitions") or [{}])[0]
        sides = {c.get("homeAway"): c for c in comp.get("competitors", [])}
        home, away = sides.get("home", {}), sides.get("away", {})
        home_team, away_team = home.get("team", {}), away.get("team", {})
        status = (e.get("status") or {}).get("type", {})
        state = status.get("state", "")  # pre / in / post
        finished = state == "post"
        if state == "in":
            elapsed = (e.get("status") or {}).get("displayClock", "") or "LIVE"
        elif finished:
            elapsed = ""
        else:
            elapsed = "notstarted"
        slug = (e.get("season") or {}).get("slug", "")
        out.append(
            Match(
                id=str(e.get("id", "")),
                home=home_team.get("displayName", ""),
                away=away_team.get("displayName", ""),
                home_code=home_team.get("abbreviation", ""),
                away_code=away_team.get("abbreviation", ""),
                home_score=_int(home.get("score")),
                away_score=_int(away.get("score")),
                group="",  # the scoreboard feed doesn't carry the group letter
                stage=_STAGE_FROM_SLUG.get(slug, "group"),
                matchday="",
                kickoff=_parse_kickoff(e.get("date", "")),
                finished=finished,
                elapsed=elapsed,
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


class WorldCupOptions(JobOptions):
    group: str | None = None  # restrict to one group letter (e.g. "C")
    rotate_seconds: int | None = Field(default=None, gt=0)  # cadence for rotating live matches
    live_only: bool | None = None  # pin to in-play matches; show "NO MATCHES" when none are live
    override_map: ClassVar[dict[str, str]] = {
        "group": "worldcup_group",
        "rotate_seconds": "worldcup_rotate_seconds",
        "live_only": "worldcup_live_only",
    }


class WorldCupJob(Job):
    name = "world_cup"
    interval_seconds = 60
    scene_name = "worldcup"
    Options = WorldCupOptions

    def __init__(self, settings) -> None:
        super().__init__(settings)
        self._rotation = RotationState()

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
        if self.settings.worldcup_live_only:
            return []  # pinned to live games: nothing in play -> "NO MATCHES"
        upcoming = sorted((m for m in matches if m.kickoff and m.kickoff >= now), key=lambda m: m.kickoff)
        return upcoming[:1] or matches[:1]

    def select_match(self, matches: list[Match], now: datetime) -> Match | None:
        pool = self._pool(matches, now)
        if not pool:
            return None
        # A score change in any pool match wins the board immediately; otherwise
        # hold the current match until the rotate cadence elapses, then advance.
        chosen, self._rotation = select(
            pool,
            key=lambda m: m.id,
            signal=lambda m: (m.home_score, m.away_score),
            state=self._rotation,
            now=now,
            rotate_seconds=self.settings.worldcup_rotate_seconds,
        )
        return chosen

    # -- job hooks -------------------------------------------------------------
    def fetch(self) -> Match | None:
        now = datetime.now()
        start = (now - timedelta(days=1)).strftime("%Y%m%d")
        end = (now + timedelta(days=FETCH_WINDOW_DAYS)).strftime("%Y%m%d")
        resp = httpx.get(SCOREBOARD_URL, params={"dates": f"{start}-{end}", "limit": 200}, timeout=15.0)
        events = resp.json().get("events", [])
        return self.select_match(parse_espn(events), now)

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
            g_text, i_text = _split_elapsed(m)
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
            scene,
            "F",
            _short(m.home, m.home_code, _NAME_WIDTH),
            leader_color(m.home_score, m.away_score, final=final, scheme="red_blue"),
        )
        self._accent(
            scene,
            "H",
            _short(m.away, m.away_code, _NAME_WIDTH),
            leader_color(m.away_score, m.home_score, final=final, scheme="red_blue"),
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


def _split_elapsed(m: Match) -> tuple[str, str]:
    """Split the live clock into (base minute, stoppage) so ``90'+4'`` shows the
    base on the home row (G) and ``+4'`` on the away row (I)."""
    text = _elapsed(m)
    base, sep, added = text.partition("+")
    return base, f"+{added}" if sep else ""
