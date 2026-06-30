import pytest
from fastapi.testclient import TestClient

from artistaboard.api import create_app
from artistaboard.config import Settings


def _settings(tmp_path, **overrides):
    return Settings(
        _env_file=None,
        database_url=f"sqlite:///{tmp_path}/test.db",
        session_secret="test-secret",
        **overrides,
    )


@pytest.fixture
def settings(tmp_path):
    return _settings(tmp_path)


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as c:
        yield c


@pytest.fixture
def auth_client(client):
    """A client with a registered+logged-in owner (register sets the session cookie)."""
    r = client.post("/auth/register", json={"email": "owner@example.com", "password": "supersecret"})
    assert r.status_code == 201, r.text
    return client
