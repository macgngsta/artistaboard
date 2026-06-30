"""Runtime configuration, loaded from the environment / a local .env file."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from . import codes


def _default_data_dir() -> Path:
    """Repo root that holds scenes/ and fonts/.

    In an editable dev install this file lives at <root>/src/artistaboard/config.py,
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

    # Web app (api/). database_url defaults to a SQLite file in the working dir;
    # session_secret signs the auth cookie (override in any real deployment);
    # allow_signup gates registration after the first owner account exists.
    database_url: str = "sqlite:///./artistaboard.db"
    session_secret: str = "dev-insecure-change-me"
    allow_signup: bool = True
    # Encrypts board Read/Write keys at rest (Fernet). Falls back to session_secret
    # when unset — fine for local dev, set a dedicated key in any real deployment.
    app_encryption_key: str = ""

    @property
    def encryption_secret(self) -> str:
        return self.app_encryption_key or self.session_secret

    # Glyph font (a file <font>.json in fonts/). Bundled: nanofont3x4, bytesized3x4, 3x3pixels, 3by5.
    font: str = "bytesized3x4"

    # Accent colors: a code (69) or a name ("white"/"violet"). muni_color is
    # optional — when unset, the badge uses the Muni line's own color.
    clock_color: int = codes.WHITE
    muni_color: int | None = None

    @field_validator("clock_color", "muni_color", mode="before")
    @classmethod
    def _resolve_color(cls, v: object) -> object:
        if v is None or v == "":
            return None
        return codes.resolve_color(v)  # type: ignore[arg-type]

    # Small timezone label shown in the clock's corner (2 chars, e.g. PT/ET).
    clock_tz_label: str = "PT"

    # SF Muni (511.org). muni_line picks which route to show; the badge takes that
    # line's colour (L→violet, T→red, …) unless muni_color overrides it.
    fiveoneone_api_key: str = ""
    muni_stop_code: str = ""
    muni_line: str = "L"

    # World Cup job: only show a specific group (e.g. "C") when set; rotate among
    # live matches every N seconds (or immediately on a score change).
    worldcup_group: str = ""
    worldcup_rotate_seconds: int = 300

    # Sport high-scores job: ESPN sport/league path + rotation cadence.
    sport_league: str = "basketball/nba"
    sport_rotate_seconds: int = 300

    # Sport low-scores job: ESPN sport/league path for sports whose scores stay
    # to 1-2 digits (baseball, soccer, hockey). Shares sport_rotate_seconds.
    sport_lowscore_league: str = "baseball/mlb"

    # Spotify "now playing" job (OAuth). Create an app at developer.spotify.com,
    # then run `artistaboard spotify-auth` to obtain the refresh token.
    spotify_client_id: str = ""
    spotify_client_secret: str = ""
    spotify_refresh_token: str = ""
    spotify_redirect_uri: str = "http://127.0.0.1:8888/callback"

    @property
    def scenes_dir(self) -> Path:
        return self.data_dir / "scenes"

    @property
    def fonts_dir(self) -> Path:
        return self.data_dir / "fonts"

    @property
    def font_path(self) -> Path:
        return self.fonts_dir / f"{self.font}.json"

    @property
    def flags_path(self) -> Path:
        return self.data_dir / "data" / "flags.json"

    @property
    def team_states_path(self) -> Path:
        return self.data_dir / "data" / "team_states.json"


@lru_cache
def get_settings() -> Settings:
    return Settings()
