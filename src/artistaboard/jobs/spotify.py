"""Spotify "now playing" job.

Spotify's currently-playing track is private user data, so this needs OAuth: a
Spotify app (client id/secret) and a one-time auth to get a refresh token (run
``artistaboard spotify-auth``). The job refreshes an access token each poll and
reads the currently-playing track.

Declarative: the scene (spotify.json) owns the layout/colours (green logo +
accents, the "NOTHING PLAYING" fallback); this job only supplies the track and
artists data.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx
from pydantic_settings import BaseSettings, SettingsConfigDict

from .base import Job, jsonable


class SpotifyConfig(BaseSettings):
    """Spotify job config / OAuth credentials (env: SPOTIFY_*)."""

    model_config = SettingsConfigDict(env_prefix="SPOTIFY_", env_file=".env", extra="ignore")
    client_id: str = ""
    client_secret: str = ""
    refresh_token: str = ""
    redirect_uri: str = "http://127.0.0.1:8888/callback"


AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
NOW_PLAYING_URL = "https://api.spotify.com/v1/me/player/currently-playing"
SCOPE = "user-read-currently-playing"


@dataclass(frozen=True)
class NowPlaying:
    track: str
    artists: list[str]
    is_playing: bool


def authorize_url(client_id: str, redirect_uri: str) -> str:
    query = urlencode({"client_id": client_id, "response_type": "code", "redirect_uri": redirect_uri, "scope": SCOPE})
    return f"{AUTH_URL}?{query}"


def _basic_auth(client_id: str, client_secret: str) -> str:
    return base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()


def exchange_code(code: str, client_id: str, client_secret: str, redirect_uri: str) -> str:
    """Exchange an authorization code for a refresh token (one-time setup)."""
    resp = httpx.post(
        TOKEN_URL,
        data={"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri},
        headers={"Authorization": f"Basic {_basic_auth(client_id, client_secret)}"},
        timeout=15.0,
    )
    resp.raise_for_status()
    return resp.json()["refresh_token"]


def get_access_token(client_id: str, client_secret: str, refresh_token: str) -> str:
    resp = httpx.post(
        TOKEN_URL,
        data={"grant_type": "refresh_token", "refresh_token": refresh_token},
        headers={"Authorization": f"Basic {_basic_auth(client_id, client_secret)}"},
        timeout=15.0,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def parse_now_playing(payload: dict | None) -> NowPlaying | None:
    if not payload or not payload.get("item"):
        return None
    item = payload["item"]
    return NowPlaying(
        track=item.get("name", ""),
        artists=[a.get("name", "") for a in item.get("artists", [])],
        is_playing=bool(payload.get("is_playing")),
    )


class SpotifyJob(Job):
    name = "spotify"
    interval_seconds = 20
    scene_name = "spotify"
    config_attr = "spotify"

    def fetch(self) -> NowPlaying | None:
        s = self.settings.spotify
        if not (s.client_id and s.client_secret and s.refresh_token):
            raise RuntimeError(
                "spotify job needs SPOTIFY_CLIENT_ID/SECRET/REFRESH_TOKEN (run `artistaboard spotify-auth`)"
            )
        token = get_access_token(s.client_id, s.client_secret, s.refresh_token)
        resp = httpx.get(NOW_PLAYING_URL, headers={"Authorization": f"Bearer {token}"}, timeout=15.0)
        if resp.status_code == 204:  # nothing playing
            return None
        resp.raise_for_status()
        return parse_now_playing(resp.json())

    def poll(self) -> dict[str, Any]:
        # A single now-playing item is already the full dataset; None when nothing plays.
        return {"now_playing": jsonable(self.fetch())}

    def from_snapshot(self, payload: dict[str, Any]) -> NowPlaying | None:
        now = payload.get("now_playing")
        return NowPlaying(**now) if now else None

    def bind(self, data: NowPlaying | None) -> dict[str, Any]:
        if data is None:
            return {}  # scene's fallback renders "NOTHING PLAYING"
        return {"track": data.track, "artists": ", ".join(data.artists)}
