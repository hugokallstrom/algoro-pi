from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from slopstop.admin.app import create_app
from slopstop.auth import is_password_set


@pytest.fixture
def fresh_app(db_path: Path):
    # db_path is initialized by the conftest fixture but no password is set
    assert not is_password_set(db_path)
    return create_app(db_path=db_path)


@pytest.fixture
def fresh_client(fresh_app):
    return TestClient(fresh_app)


def test_get_setup_renders_form_when_no_password(fresh_client: TestClient) -> None:
    resp = fresh_client.get("/setup")
    assert resp.status_code == 200
    # Form must have a password field and a confirm field
    assert 'name="password"' in resp.text
    assert 'name="confirm"' in resp.text
