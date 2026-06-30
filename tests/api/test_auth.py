from fastapi.testclient import TestClient

from artistaboard.api import create_app
from artistaboard.config import Settings


def test_register_then_me(auth_client):
    r = auth_client.get("/auth/me")
    assert r.status_code == 200
    assert r.json()["email"] == "owner@example.com"


def test_me_requires_auth(client):
    assert client.get("/auth/me").status_code == 401


def test_duplicate_email_conflicts(auth_client):
    r = auth_client.post("/auth/register", json={"email": "owner@example.com", "password": "anotherone"})
    assert r.status_code == 409


def test_login_wrong_password(auth_client):
    auth_client.post("/auth/logout")
    r = auth_client.post("/auth/login", json={"email": "owner@example.com", "password": "wrongpass1"})
    assert r.status_code == 401


def test_login_logout_cycle(auth_client):
    assert auth_client.post("/auth/logout").status_code == 204
    assert auth_client.get("/auth/me").status_code == 401
    r = auth_client.post("/auth/login", json={"email": "owner@example.com", "password": "supersecret"})
    assert r.status_code == 200
    assert auth_client.get("/auth/me").status_code == 200


def test_short_password_rejected(client):
    r = client.post("/auth/register", json={"email": "x@example.com", "password": "short"})
    assert r.status_code == 422  # min_length on the schema


def test_signup_gating_after_first_owner(tmp_path):
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite:///{tmp_path}/gating.db",
        session_secret="test-secret",
        allow_signup=False,
    )
    with TestClient(create_app(settings)) as c:
        # first account always allowed (bootstrap), even with signup closed
        first = c.post("/auth/register", json={"email": "first@example.com", "password": "supersecret"})
        assert first.status_code == 201
        c.post("/auth/logout")
        # second is gated
        r = c.post("/auth/register", json={"email": "second@example.com", "password": "supersecret"})
        assert r.status_code == 403
