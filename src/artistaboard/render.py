"""Generic declarative scene renderer.

The principle: a *job supplies data*; a *scene declares display*. A scene's
object-form JSON may carry a ``render`` map — one entry per region letter — that
says which data field to draw, how (``text``/``glyphs``/``textbox``/``fill``),
and in what colour. The job hands over a flat data envelope (``{"time": "14:30",
...}``); this module walks the bindings and paints the scene, so jobs no longer
hand-write per-region ``render()`` code.

Colours are resolved from one of three forms:
  * a literal — a colour name or code (``"violet"`` / ``68``);
  * ``{"data": "<key>"}`` — a code the job placed in the envelope;
  * ``{"rule": "<name>", ...}`` — a *named* rule (a closed set, below) evaluated
    against the envelope. There is deliberately no expression language; anything
    a rule can't express is a job-side ``post_render`` hook.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

from . import codes
from .font import Font

if TYPE_CHECKING:
    from .config import Settings
    from .scene import Scene


@cache
def _load_font(fonts_dir: str, name: str) -> Font:
    return Font.from_file(Path(fonts_dir) / f"{name}.json")


def load_font(settings: Settings, name: str) -> Font:
    return _load_font(str(settings.fonts_dir), name)


# -- named colour rules ----------------------------------------------------------
# A rule is (envelope, params) -> Vestaboard code. Keep this set small and closed.


def leader_color(mine: int, theirs: int, *, final: bool = False, scheme: str = "violet_blue") -> int:
    """The colour for a team's cell given its score vs the opponent's. Leader gets
    ``green`` (green scheme) or violet-while-live / blue-once-final; trailer/tie
    white. Shared by the ``leader`` rule and jobs that need the same colour for an
    accent (so the logic lives in exactly one place)."""
    if mine <= theirs:
        return codes.WHITE
    if scheme == "green":
        return codes.GREEN
    if scheme == "red_blue":
        return codes.BLUE if final else codes.RED
    return codes.BLUE if final else codes.VIOLET


def _rule_leader(data: dict[str, Any], params: dict[str, Any]) -> int:
    """Highlight the leading team's cell; ``team`` says which side this region is."""
    team = params.get("team", "home")
    mine = data.get(f"{team}.score", 0)
    theirs = data.get("away.score" if team == "home" else "home.score", 0)
    return leader_color(mine, theirs, final=bool(data.get("final")), scheme=params.get("scheme", "violet_blue"))


def _rule_imminent(data: dict[str, Any], params: dict[str, Any]) -> int:
    """A threshold colour: ``near`` when ``data[field] < threshold`` else ``far``."""
    value = data.get(params["field"])
    near = codes.resolve_color(params.get("near", "red"))
    far = codes.resolve_color(params.get("far", "white"))
    if value is None:
        return far
    return near if value < params.get("threshold", 5) else far


_RULES: dict[str, Callable[[dict[str, Any], dict[str, Any]], int]] = {
    "leader": _rule_leader,
    "imminent": _rule_imminent,
}


def _resolve_color(spec: Any, data: dict[str, Any]) -> int:
    if spec is None:
        return codes.WHITE
    if isinstance(spec, dict):
        if "data" in spec:
            return int(data[spec["data"]])
        if "rule" in spec:
            return _RULES[spec["rule"]](data, spec)
        raise ValueError(f"colour spec needs 'data' or 'rule': {spec!r}")
    return codes.resolve_color(spec)


def _transform(text: str, kind: str | None) -> str:
    if kind == "upper":
        return text.upper()
    return text


# -- variable extraction ---------------------------------------------------------
# Which envelope keys a scene's render map consumes. Today this contract is
# implicit (a scene only works with a job whose bind() emits matching keys); making
# it explicit lets a designer/binder show "this scene needs: time, tz" and validate.


def _rule_variables(rule: str, params: dict[str, Any]) -> list[tuple[str, str]]:
    """The envelope keys a named colour rule reads, as (name, kind) pairs."""
    if rule == "leader":
        team = params.get("team", "home")
        other = "away" if team == "home" else "home"
        return [(f"{team}.score", "number"), (f"{other}.score", "number"), ("final", "flag")]
    if rule == "imminent" and "field" in params:
        return [(params["field"], "number")]
    return []


def scene_variables(document: dict | list) -> list[dict[str, Any]]:
    """The data-envelope variables a scene's ``render`` map needs.

    One descriptor per distinct variable: ``{name, kind, required, fallback}`` where
    ``kind`` is ``text``/``number``/``color``/``flag`` and ``required`` is true when
    the binding that introduces it has no ``fallback``. Scanned from each region's
    ``bind`` key, ``{"data": k}`` colour specs, and the keys implied by named rules.
    A pure function over the scene document — no rendering, no I/O.
    """
    render = document.get("render", {}) if isinstance(document, dict) else {}
    out: dict[str, dict[str, Any]] = {}

    def add(name: str, kind: str, *, required: bool, fallback: Any = None) -> None:
        cur = out.get(name)
        if cur is None:
            out[name] = {"name": name, "kind": kind, "required": required, "fallback": fallback}
        elif required and not cur["required"]:
            # a stricter (no-fallback) use of the same variable wins
            cur.update(required=True, fallback=None)

    for cfg in render.values():
        if "bind" in cfg:
            add(cfg["bind"], "text", required="fallback" not in cfg, fallback=cfg.get("fallback"))
        color = cfg.get("color")
        if isinstance(color, dict):
            if "data" in color:
                add(color["data"], "color", required=True)
            elif "rule" in color:
                for name, kind in _rule_variables(color["rule"], color):
                    add(name, kind, required=True)
    return list(out.values())


def render_scene(scene: Scene, data: dict[str, Any], settings: Settings) -> Scene:
    """Paint ``scene`` from its ``render`` config against the ``data`` envelope."""
    default_font = load_font(settings, scene.font_name) if scene.font_name else scene.font
    for region, cfg in scene.render_config.items():
        if region not in scene.regions:
            continue
        kind = cfg.get("as", "text")
        color = _resolve_color(cfg.get("color"), data)
        if kind == "fill":
            scene.fill(color, region=region)
            continue
        value = data.get(cfg["bind"]) if "bind" in cfg else None
        if (value is None or value == "") and "fallback" in cfg:
            value = cfg["fallback"]
        if value is None or value == "":
            continue
        text = _transform(str(value), cfg.get("transform"))
        align = cfg.get("align", "center" if kind == "glyphs" else "left")
        if kind == "glyphs":
            font = load_font(settings, cfg["font"]) if "font" in cfg else default_font
            scene.glyphs(
                text,
                region=region,
                on_code=color,
                font=font,
                align=align,
                fill=_resolve_color(cfg["fill"], data) if "fill" in cfg else None,
                invert=cfg.get("invert", False),
                spacing=cfg.get("spacing", 1),
            )
        elif kind == "textbox":
            scene.textbox(text, region=region, align=align)
        else:  # text
            scene.write(text, region=region, align=align)
    return scene
