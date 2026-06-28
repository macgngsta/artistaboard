"""The Job abstraction: fetch data, render a Scene, paint it to the board."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..client import VestaboardClient
from ..config import Settings
from ..scene import Scene


class Job(ABC):
    """A unit of board business logic.

    Subclasses implement :meth:`fetch` (get data) and :meth:`render` (turn data
    into a Scene). :meth:`build` and :meth:`paint` are the orchestration glue.
    """

    name: str
    interval_seconds: int

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @abstractmethod
    def fetch(self) -> Any:
        """Get whatever data this job needs to draw."""

    @abstractmethod
    def render(self, data: Any) -> Scene:
        """Turn fetched data into a Scene."""

    def build(self) -> Scene:
        return self.render(self.fetch())

    def paint(self, client: VestaboardClient) -> dict:
        return client.send(self.build().to_characters())
