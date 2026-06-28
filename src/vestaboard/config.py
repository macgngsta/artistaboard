"""Runtime configuration, loaded from the environment / a local .env file."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_data_dir() -> Path:
    """Repo root that holds scenes/ and fonts/.

    In an editable dev install this file lives at <root>/src/vestaboard/config.py,
    so walk up until we find a directory that actually contains scenes/. The
    Docker image overrides this with VESTABOARD_DATA_DIR.
    """
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "scenes").is_dir() and (parent / "fonts").is_dir():
            return parent
    return Path.cwd()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Where scenes/ and fonts/ live. The Docker image sets VESTABOARD_DATA_DIR=/app.
    data_dir: Path = Field(default_factory=_default_data_dir, validation_alias="VESTABOARD_DATA_DIR")

    # Vestaboard Read/Write API.
    vestaboard_rw_key: str = ""

    # Daemon: which job to paint on a schedule.
    active_job: str = "clock"

    # Glyph font (a file <font>.json in fonts/). Bundled: nanofont3x4, bytesized3x4.
    font: str = "nanofont3x4"

    # Accent colors (Vestaboard color codes).
    clock_color: int = 69  # white
    muni_color: int = 66  # green

    # SF Muni (511.org).
    fiveoneone_api_key: str = ""
    muni_stop_code: str = ""

    # Aircraft job (stub).
    aircraft_lat: float = 37.7749
    aircraft_lon: float = -122.4194

    @property
    def scenes_dir(self) -> Path:
        return self.data_dir / "scenes"

    @property
    def fonts_dir(self) -> Path:
        return self.data_dir / "fonts"

    @property
    def font_path(self) -> Path:
        return self.fonts_dir / f"{self.font}.json"


@lru_cache
def get_settings() -> Settings:
    return Settings()
