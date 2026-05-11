from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from slopstop.auth import set_password
from slopstop.admin.app import create_app


@pytest.fixture
def app(db_path: Path):
    set_password("testpass", db_path)
    return create_app(db_path=db_path)


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def authed_client(app):
    client = TestClient(app)
    client.post("/login", data={"password": "testpass"})
    return client


def test_unauthenticated_root_redirects_to_login(client: TestClient) -> None:
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers["location"]


def test_login_page_renders(client: TestClient) -> None:
    resp = client.get("/login")
    assert resp.status_code == 200
    assert "password" in resp.text.lower()


def test_login_with_correct_password_sets_cookie(client: TestClient) -> None:
    resp = client.post("/login", data={"password": "testpass"}, follow_redirects=False)
    assert resp.status_code == 302
    assert "session" in resp.cookies


def test_login_with_wrong_password_shows_error(client: TestClient) -> None:
    resp = client.post("/login", data={"password": "wrong"})
    assert resp.status_code == 200
    assert "invalid" in resp.text.lower()


def test_authenticated_root_renders_dashboard(authed_client: TestClient) -> None:
    resp = authed_client.get("/")
    assert resp.status_code == 200
    assert "slopstop" in resp.text.lower()


def test_logout_clears_session(authed_client: TestClient) -> None:
    resp = authed_client.post("/logout", follow_redirects=False)
    assert resp.status_code == 302
    # After logout, root redirects to login
    resp2 = authed_client.get("/", follow_redirects=False)
    assert resp2.status_code == 302
