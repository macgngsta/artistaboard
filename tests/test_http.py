import httpx
import pytest
import respx

from artistaboard.http import get_json

URL = "https://example.test/data"


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    # keep the bounded-retry backoff from actually sleeping in tests
    monkeypatch.setattr("artistaboard.http.time.sleep", lambda *_: None)


@respx.mock
def test_returns_json_on_success():
    respx.get(URL).mock(return_value=httpx.Response(200, json={"ok": True}))
    assert get_json(URL) == {"ok": True}


@respx.mock
def test_retries_5xx_then_succeeds():
    route = respx.get(URL).mock(side_effect=[httpx.Response(503), httpx.Response(200, json={"ok": 1})])
    assert get_json(URL, retries=2) == {"ok": 1}
    assert route.call_count == 2  # one failure, then success


@respx.mock
def test_raises_after_exhausting_retries_on_5xx():
    route = respx.get(URL).mock(return_value=httpx.Response(500))
    with pytest.raises(httpx.HTTPStatusError):
        get_json(URL, retries=2)
    assert route.call_count == 3  # initial + 2 retries


@respx.mock
def test_does_not_retry_4xx():
    route = respx.get(URL).mock(return_value=httpx.Response(404))
    with pytest.raises(httpx.HTTPStatusError):
        get_json(URL, retries=2)
    assert route.call_count == 1  # client error is not retried


@respx.mock
def test_retries_transport_error_then_succeeds():
    route = respx.get(URL).mock(side_effect=[httpx.ConnectError("boom"), httpx.Response(200, json={"ok": 2})])
    assert get_json(URL, retries=2) == {"ok": 2}
    assert route.call_count == 2
