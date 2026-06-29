"""Spotify "now playing" job.

Spotify's currently-playing track is private user data, so this needs OAuth: a
Spotify app (client id/secret) and a one-time auth to get a refresh token (run
``vestaboard spotify-auth``). The job refreshes an access token each poll and
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

from .base import Job

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

    def fetch(self) -> NowPlaying | None:
        s = self.settings
        if not (s.spotify_client_id and s.spotify_client_secret and s.spotify_refresh_token):
            raise RuntimeError(
                "spotify job needs SPOTIFY_CLIENT_ID/SECRET/REFRESH_TOKEN (run `vestaboard spotify-auth`)"
            )
        token = get_access_token(s.spotify_client_id, s.spotify_client_secret, s.spotify_refresh_token)
        resp = httpx.get(NOW_PLAYING_URL, headers={"Authorization": f"Bearer {token}"}, timeout=15.0)
        if resp.status_code == 204:  # nothing playing
            return None
        resp.raise_for_status()
        return parse_now_playing(resp.json())

    def bind(self, data: NowPlaying | None) -> dict[str, Any]:
        if data is None:
            return {}  # scene's fallback renders "NOTHING PLAYING"
        return {"track": data.track, "artists": ", ".join(data.artists)}
