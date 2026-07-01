"""The Job abstraction: fetch data, render a Scene, paint it to the board."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Annotated, Any, ClassVar

from pydantic import BaseModel, BeforeValidator, ConfigDict

from .. import codes
from ..client import VestaboardClient
from ..config import Settings
from ..render import render_scene
from ..scene import Scene


def _resolve_color_option(value: object) -> int | None:
    """Normalise a color option (a code like ``69`` or a name like ``"violet"``) to a
    code; ``None``/``""`` means 'inherit the Settings default'. Mirrors the resolution
    Settings does, needed here because ``build_job`` overrides skip re-validation."""
    if value is None or value == "":
        return None
    return codes.resolve_color(value)  # type: ignore[arg-type]


# A color-valued option field: accepts a code or a name, inherits the default when unset.
ColorOption = Annotated[int | None, BeforeValidator(_resolve_color_option)]


class JobOptions(BaseModel):
    """Per-entry, user-supplied options for a job.

    Subclasses declare typed, user-facing fields (``group``, ``line`` …). The base
    turns the *explicitly set* ones into :class:`Settings` overrides for
    :func:`build_job` via ``override_map`` (option field -> Settings field). A field
    left ``None`` is omitted, so an unset option falls back to the process-global
    ``Settings`` — the entry inherits the deployment default rather than clobbering
    it. ``extra="forbid"`` rejects unknown keys so a typo fails loudly on write.
    """

    model_config = ConfigDict(extra="forbid")
    override_map: ClassVar[dict[str, str]] = {}

    def to_overrides(self) -> dict[str, Any]:
        data = self.model_dump(exclude_none=True)
        return {self.override_map.get(k, k): v for k, v in data.items()}


class Job(ABC):
    """A unit of board business logic.

    Subclasses implement :meth:`fetch` (get data). Then either:
      * declarative path — set :attr:`scene_name` and implement :meth:`bind`
        (data -> a flat envelope); the default :meth:`render` drives the generic
        renderer, with an optional :meth:`post_render` hook for pixel-level work;
      * imperative path — override :meth:`render` directly (legacy).

    :meth:`build` and :meth:`paint` are the orchestration glue.
    """

    name: str
    interval_seconds: int
    scene_name: str | None = None
    # The typed per-entry options this job accepts (empty by default: no knobs).
    Options: ClassVar[type[JobOptions]] = JobOptions

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._last_sent: list[list[int]] | None = None

    @abstractmethod
    def fetch(self) -> Any:
        """Get whatever data this job needs to draw."""

    def bind(self, data: Any) -> dict[str, Any] | None:
        """Map fetched data to a flat render envelope (``None`` when there's no
        data to show). Declarative jobs implement this instead of :meth:`render`."""
        raise NotImplementedError(f"{type(self).__name__} must implement bind() or override render()")

    def post_render(self, scene: Scene, data: Any) -> None:  # noqa: B027 - optional no-op hook, not abstract
        """Hook for pixel-level touches the declarative config can't express
        (accent pixels, bespoke banners). Runs after the generic render."""

    def render(self, data: Any) -> Scene:
        """Default declarative render: load the scene, bind data, paint it."""
        if self.scene_name is None:
            raise NotImplementedError(f"{type(self).__name__} needs a scene_name or a render() override")
        scene = Scene.from_file(self.settings.scenes_dir / f"{self.scene_name}.json")
        envelope = self.bind(data)
        if envelope is not None:
            render_scene(scene, envelope, self.settings)
        self.post_render(scene, data)
        return scene

    def build(self) -> Scene:
        return self.render(self.fetch())

    def paint(self, client: VestaboardClient) -> dict | None:
        """Render and send, skipping the send when the frame is unchanged (so we
        don't re-flap the board or burn the rate limit on identical content)."""
        chars = self.build().to_characters()
        if chars == self._last_sent:
            return None
        result = client.send(chars)
        self._last_sent = chars
        return result
