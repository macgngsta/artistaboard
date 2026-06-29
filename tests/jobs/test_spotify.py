import httpx
import respx

from vestaboard import codes
from vestaboard.config import Settings
from vestaboard.jobs.spotify import (
    NowPlaying,
    SpotifyJob,
    authorize_url,
    exchange_code,
    get_access_token,
    parse_now_playing,
)


def test_authorize_url_has_client_and_scope():
    url = authorize_url("cid", "http://127.0.0.1:8888/callback")
    assert "client_id=cid" in url and "user-read-currently-playing" in url


def test_parse_now_playing():
    payload = {
        "is_playing": True,
        "item": {"name": "Open Window", "artists": [{"name": "Anna Yvette"}, {"name": "MitiS"}]},
    }
    np = parse_now_playing(payload)
    assert np.track == "Open Window" and np.artists == ["Anna Yvette", "MitiS"] and np.is_playing
    assert parse_now_playing(None) is None
    assert parse_now_playing({"item": None}) is None


@respx.mock
def test_token_exchange_and_refresh():
    respx.post("https://accounts.spotify.com/api/token").mock(
        return_value=httpx.Response(200, json={"refresh_token": "rt", "access_token": "at"})
    )
    assert exchange_code("code", "id", "secret", "uri") == "rt"
    assert get_access_token("id", "secret", "rt") == "at"


def test_render_fills_logo_and_writes_track_and_artists():
    job = SpotifyJob(Settings(_env_file=None))
    scene = job.render(NowPlaying("Open Window", ["Anna Yvette", "MitiS"], True))
    a_colors = {scene.grid[r][c] for r, c in scene.regions["A"].cells}
    assert a_colors == {codes.GREEN}  # music logo
    flat = [c for row in scene.to_characters() for c in row]
    assert codes.char_to_code("O") in flat  # track "OPEN WINDOW"
    assert codes.char_to_code("Y") in flat  # artist "ANNA YVETTE"


def test_render_nothing_playing():
    job = SpotifyJob(Settings(_env_file=None))
    flat = [c for row in job.render(None).to_characters() for c in row]
    assert codes.char_to_code("N") in flat  # "NOTHING PLAYING"


def test_paint_skips_when_unchanged():
    sent = []

    class FakeClient:
        def send(self, chars):
            sent.append(chars)
            return {"status": "ok"}

    job = SpotifyJob(Settings(_env_file=None))
    job.fetch = lambda: NowPlaying("Song", ["Artist"], True)
    job.paint(FakeClient())
    job.paint(FakeClient())
    assert len(sent) == 1
