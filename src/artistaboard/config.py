"""Runtime configuration, loaded from the environment / a local .env file."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .jobs.clock import ClockConfig
from .jobs.muni import MuniConfig
from .jobs.sport_highscores import SportConfig
from .jobs.spotify import SpotifyConfig
from .jobs.worldcup import WorldCupConfig

# The bundled placeholder secret. Fine for local dev; a real deployment must override
# it (see the APP_ENV guard below) since it's public and signs cookies + encrypts keys.
_DEV_SECRET = "dev-insecure-change-me"


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
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore", populate_by_name=True)

    # Where scenes/ and fonts/ live. The Docker image sets VESTABOARD_DATA_DIR=/app.
    data_dir: Path = Field(default_factory=_default_data_dir, validation_alias="VESTABOARD_DATA_DIR")

    # Vestaboard Read/Write API.
    vestaboard_rw_key: str = ""

    # Daemon: which job to paint on a schedule.
    active_job: str = "clock"

    # Poller daemon (`artistaboard poll`): how often to fetch referenced sources into
    # data_snapshots (cron; default every minute — the design's 1-minute resolution).
    poll_cron: str = "* * * * *"

    # Web app (api/). database_url defaults to a SQLite file in the working dir;
    # session_secret signs the auth cookie (override in any real deployment);
    # allow_signup gates registration after the first owner account exists.
    database_url: str = "sqlite:///./artistaboard.db"
    session_secret: str = _DEV_SECRET
    allow_signup: bool = True
    # Deployment environment. Anything other than "dev" (set APP_ENV=prod in a real
    # deployment) rejects the insecure default secret at load — see the guard below.
    app_env: str = Field(default="dev", validation_alias="APP_ENV")
    # Browser origins allowed to call the API with credentials. Defaults cover the
    # Vite dev server; production serves the SPA same-origin so no CORS is needed.
    # Accepts a JSON list or a comma-separated string via CORS_ORIGINS.
    cors_origins: list[str] = Field(
        default=["http://localhost:5173", "http://127.0.0.1:5173"],
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip().startswith("["):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    # Encrypts board Read/Write keys at rest (Fernet). Falls back to session_secret
    # when unset — fine for local dev, set a dedicated key in any real deployment.
    app_encryption_key: str = ""

    @property
    def encryption_secret(self) -> str:
        return self.app_encryption_key or self.session_secret

    @model_validator(mode="after")
    def _reject_dev_secret_outside_dev(self) -> Settings:
        # Fail loud rather than silently signing cookies / encrypting board keys with a
        # public constant. encryption_secret falls back to session_secret, so guarding
        # the session secret covers both.
        if self.app_env != "dev" and self.session_secret == _DEV_SECRET:
            raise ValueError(
                "SESSION_SECRET is the insecure dev default but APP_ENV is "
                f"{self.app_env!r}; set a real SESSION_SECRET (and APP_ENCRYPTION_KEY)."
            )
        return self

    # Glyph font (a file <font>.json in fonts/). Bundled: nanofont3x4, bytesized3x4, 3x3pixels, 3by5.
    font: str = "bytesized3x4"

    # Per-job config lives in each job module (env: CLOCK_*, MUNI_*, WORLDCUP_*,
    # SPORT_*, SPOTIFY_*). Each is its own BaseSettings, so adding a job widens its
    # own config, not this global. Per-entry pipeline options override these at
    # build_job time (see JobOptions.to_overrides + registry.build_job).
    clock: ClockConfig = Field(default_factory=ClockConfig)
    muni: MuniConfig = Field(default_factory=MuniConfig)
    worldcup: WorldCupConfig = Field(default_factory=WorldCupConfig)
    sport: SportConfig = Field(default_factory=SportConfig)
    spotify: SpotifyConfig = Field(default_factory=SpotifyConfig)

    @property
    def web_dist_dir(self) -> Path:
        """Built SPA (web/dist). Served same-origin when present."""
        return self.data_dir / "web" / "dist"

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
