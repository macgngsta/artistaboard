import httpx
import pytest
import respx

from artistaboard import COLS, ROWS
from artistaboard.client import BASE_URL, HEADER, VestaboardClient, VestaboardError


def _grid(code=0):
    return [[code] * COLS for _ in range(ROWS)]


def test_requires_key():
    with pytest.raises(VestaboardError):
        VestaboardClient("")


@respx.mock
def test_send_posts_raw_grid_with_header():
    route = respx.post(BASE_URL).mock(return_value=httpx.Response(200, json={"status": "ok"}))
    with VestaboardClient("k") as client:
        result = client.send(_grid(1))
    assert result == {"status": "ok"}
    request = route.calls.last.request
    assert request.headers[HEADER] == "k"
    import json

    assert json.loads(request.content) == _grid(1)


@respx.mock
def test_read_unwraps_currentmessage_layout_string():
    layout = _grid(2)
    import json

    respx.get(BASE_URL).mock(return_value=httpx.Response(200, json={"currentMessage": {"layout": json.dumps(layout)}}))
    with VestaboardClient("k") as client:
        assert client.read() == layout


@respx.mock
def test_send_raises_on_error_status():
    respx.post(BASE_URL).mock(return_value=httpx.Response(503, text="nope"))
    with VestaboardClient("k") as client, pytest.raises(VestaboardError):
        client.send(_grid())


@respx.mock
def test_rate_gate_sleeps_between_sends(monkeypatch):
    respx.post(BASE_URL).mock(return_value=httpx.Response(200, json={"status": "ok"}))
    slept = []
    monkeypatch.setattr("artistaboard.client.time.sleep", lambda s: slept.append(s))
    # advance monotonic clock only slightly between the two sends
    ticks = iter([100.0, 100.1, 100.2, 100.2])
    monkeypatch.setattr("artistaboard.client.time.monotonic", lambda: next(ticks))
    with VestaboardClient("k", min_interval=15.0) as client:
        client.send(_grid())
        client.send(_grid())
    assert slept and slept[0] == pytest.approx(14.9, abs=0.2)


def test_send_validates_shape():
    with VestaboardClient("k") as client, pytest.raises(VestaboardError):
        client.send([[0] * COLS])
