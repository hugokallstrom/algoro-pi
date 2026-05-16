# Setup Route Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a minimal `/setup` route so a freshly-flashed Pi can self-bootstrap on first boot — user sets the admin password (with confirmation), is auto-logged in, and the route closes off forever until SD card re-flash.

**Architecture:** A new `setup_routes.py` module owns GET/POST `/setup`. `auth_routes.py` and `deps.py` each add a single pre-check: if `is_password_set()` is False, redirect to `/setup` instead of `/login`. After successful password set, the route stores the password, creates a session, sets the session cookie, and redirects to `/`. Once a password exists, GET and POST on `/setup` are inert 302s to `/login`.

**Tech Stack:** Python 3.11+, FastAPI, Jinja2, existing `algoro.auth` module (`hash_password`, `set_password`, `is_password_set`, `create_session_token`). No new dependencies.

**Spec:** `docs/superpowers/specs/2026-05-11-setup-route-design.md`

---

## File Structure

```
firmware/
├── src/algoro/admin/
│   ├── app.py                        # MODIFY — register setup router
│   ├── deps.py                       # MODIFY — require_auth pre-checks is_password_set
│   └── routes/
│       ├── auth_routes.py            # MODIFY — login GET/POST pre-check is_password_set
│       └── setup_routes.py           # NEW — GET/POST /setup
├── templates/
│   └── setup.html                    # NEW — two-field form + inline error
└── tests/
    └── test_setup.py                 # NEW — 9 tests for the setup behavior
```

---

## Task 1: Setup route — render the form when no password is set

**Files:**
- Create: `firmware/tests/test_setup.py`
- Create: `firmware/src/algoro/admin/routes/setup_routes.py`
- Create: `firmware/templates/setup.html`
- Modify: `firmware/src/algoro/admin/app.py`

- [ ] **Step 1: Write the failing test**

`firmware/tests/test_setup.py`:
```python
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from algoro.admin.app import create_app
from algoro.auth import is_password_set


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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd firmware
.venv/bin/pytest tests/test_setup.py::test_get_setup_renders_form_when_no_password -v
```

Expected: 404 (route not registered yet).

- [ ] **Step 3: Write `firmware/templates/setup.html`**

```html
{% extends "base.html" %}
{% block content %}
<main>
  <h1>algoro — first-time setup</h1>
  <p style="font-size:0.9rem;color:#555;margin-bottom:1.5rem">
    Choose an admin password. <strong>This is the only way to manage the device.</strong>
    If you forget it, the only recovery is re-flashing the SD card.
  </p>
  <form method="post" action="/setup">
    <label for="password">Password (min 5 characters)</label>
    <input type="password" id="password" name="password" autofocus required minlength="5">

    <label for="confirm">Confirm password</label>
    <input type="password" id="confirm" name="confirm" required minlength="5">

    {% if error %}
    <p class="error">{{ error }}</p>
    {% endif %}

    <button type="submit">Set password</button>
  </form>
</main>
{% endblock %}
```

- [ ] **Step 4: Write `firmware/src/algoro/admin/routes/setup_routes.py`**

```python
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(
    directory=str(Path(__file__).parent.parent.parent.parent.parent / "templates")
)


@router.get("/setup", response_class=HTMLResponse)
def setup_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "setup.html", {"error": None})
```

- [ ] **Step 5: Register the router in `firmware/src/algoro/admin/app.py`**

Replace the existing imports and `create_app` body so that the setup router is included alongside the existing two. The full new file is:

```python
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from algoro.admin.routes.auth_routes import router as auth_router
from algoro.admin.routes.blocklist_routes import router as blocklist_router
from algoro.admin.routes.setup_routes import router as setup_router
from algoro.blocklist import ACTIVE_BLOCKLIST_PATH
from algoro.dns_control import DEFAULT_TEMPLATE_DIR, UNBOUND_CONF_PATH

STATIC_DIR = Path(__file__).parent.parent.parent.parent / "static"


def create_app(
    db_path: Path,
    blocklist_path: Path = ACTIVE_BLOCKLIST_PATH,
    unbound_conf_path: Path = UNBOUND_CONF_PATH,
    template_dir: Path = DEFAULT_TEMPLATE_DIR,
) -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None)
    app.state.db_path = db_path
    app.state.blocklist_path = blocklist_path
    app.state.unbound_conf_path = unbound_conf_path
    app.state.template_dir = template_dir

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.include_router(auth_router)
    app.include_router(blocklist_router)
    app.include_router(setup_router)

    return app
```

- [ ] **Step 6: Run test to verify it passes**

```bash
.venv/bin/pytest tests/test_setup.py::test_get_setup_renders_form_when_no_password -v
```

Expected: 1 test PASSED.

- [ ] **Step 7: Commit**

```bash
git add firmware/templates/setup.html firmware/src/algoro/admin/routes/setup_routes.py firmware/src/algoro/admin/app.py firmware/tests/test_setup.py
git commit -m "feat: GET /setup renders password form on fresh device"
```

---

## Task 2: Redirect `/` and `/login` to `/setup` when no password is set

**Files:**
- Modify: `firmware/tests/test_setup.py` (add 3 tests)
- Modify: `firmware/src/algoro/admin/deps.py`
- Modify: `firmware/src/algoro/admin/routes/auth_routes.py`

- [ ] **Step 1: Write the failing tests** — append to `firmware/tests/test_setup.py`

```python
def test_get_root_redirects_to_setup_when_no_password(fresh_client: TestClient) -> None:
    resp = fresh_client.get("/", follow_redirects=False)
    assert resp.status_code == 302
    assert "/setup" in resp.headers["location"]


def test_get_login_redirects_to_setup_when_no_password(fresh_client: TestClient) -> None:
    resp = fresh_client.get("/login", follow_redirects=False)
    assert resp.status_code == 302
    assert "/setup" in resp.headers["location"]


def test_post_login_redirects_to_setup_when_no_password(fresh_client: TestClient) -> None:
    resp = fresh_client.post(
        "/login", data={"password": "anything"}, follow_redirects=False
    )
    assert resp.status_code == 302
    assert "/setup" in resp.headers["location"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/pytest tests/test_setup.py -v
```

Expected: the three new tests fail. `GET /` currently 302s to `/login` (not `/setup`); `GET /login` currently 200s; `POST /login` currently 200s with "Invalid password".

- [ ] **Step 3: Update `firmware/src/algoro/admin/deps.py`** — add `is_password_set` pre-check

Replace the file with:

```python
from fastapi import HTTPException, Request


def require_auth(request: Request) -> str:
    from algoro.auth import is_password_set, validate_session_token
    db_path = request.app.state.db_path
    if not is_password_set(db_path):
        raise HTTPException(status_code=302, headers={"location": "/setup"})
    token = request.cookies.get("session", "")
    if not token or not validate_session_token(token, db_path):
        raise HTTPException(status_code=302, headers={"location": "/login"})
    return token
```

- [ ] **Step 4: Update `firmware/src/algoro/admin/routes/auth_routes.py`** — add the same pre-check at the top of `login_page` (GET) and `login` (POST)

Replace the two route handlers (`login_page` and `login`) with:

```python
@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request) -> HTMLResponse:
    db_path = request.app.state.db_path
    from algoro.auth import is_password_set
    if not is_password_set(db_path):
        return RedirectResponse(url="/setup", status_code=302)
    return templates.TemplateResponse(request, "login.html", {"error": None})


@router.post("/login")
def login(request: Request, password: str = Form(...)):
    db_path = request.app.state.db_path
    from algoro.auth import is_password_set
    if not is_password_set(db_path):
        return RedirectResponse(url="/setup", status_code=302)
    if not check_password(password, db_path):
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "Invalid password."},
            status_code=200,
        )
    token = create_session_token(db_path)
    response = RedirectResponse(url="/", status_code=302)
    response.set_cookie("session", token, httponly=True, samesite="strict")
    return response
```

(Leave the `logout` handler unchanged.)

- [ ] **Step 5: Run all setup tests to verify they pass**

```bash
.venv/bin/pytest tests/test_setup.py -v
```

Expected: all 4 tests so far PASSED.

- [ ] **Step 6: Run the full test suite to ensure no regressions**

```bash
.venv/bin/pytest -m "not integration" -v
```

Expected: all existing tests still pass. (The `app` fixture in `test_admin.py` calls `set_password("testpass", db_path)` before creating the app, so `is_password_set()` is True throughout those tests.)

- [ ] **Step 7: Commit**

```bash
git add firmware/src/algoro/admin/deps.py firmware/src/algoro/admin/routes/auth_routes.py firmware/tests/test_setup.py
git commit -m "feat: redirect / and /login to /setup when no password is set"
```

---

## Task 3: POST `/setup` — happy path (auto-login + redirect)

**Files:**
- Modify: `firmware/tests/test_setup.py` (add 1 test)
- Modify: `firmware/src/algoro/admin/routes/setup_routes.py`

- [ ] **Step 1: Write the failing test** — append to `firmware/tests/test_setup.py`

```python
from algoro.auth import check_password, is_password_set


def test_post_setup_stores_password_and_logs_in(fresh_client: TestClient, db_path: Path) -> None:
    resp = fresh_client.post(
        "/setup",
        data={"password": "hunter2", "confirm": "hunter2"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert resp.headers["location"] == "/"
    # Password is stored
    assert is_password_set(db_path)
    assert check_password("hunter2", db_path)
    # Session cookie is set
    assert "session" in resp.cookies
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/pytest tests/test_setup.py::test_post_setup_stores_password_and_logs_in -v
```

Expected: 405 Method Not Allowed (no POST handler registered).

- [ ] **Step 3: Add the POST handler to `firmware/src/algoro/admin/routes/setup_routes.py`**

Replace the file with:

```python
from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from algoro.auth import create_session_token, is_password_set, set_password

router = APIRouter()
templates = Jinja2Templates(
    directory=str(Path(__file__).parent.parent.parent.parent.parent / "templates")
)

MIN_PASSWORD_LENGTH = 5


@router.get("/setup", response_class=HTMLResponse)
def setup_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "setup.html", {"error": None})


@router.post("/setup")
def setup_submit(
    request: Request,
    password: str = Form(...),
    confirm: str = Form(...),
):
    db_path = request.app.state.db_path
    set_password(password, db_path)
    token = create_session_token(db_path)
    response = RedirectResponse(url="/", status_code=302)
    response.set_cookie("session", token, httponly=True, samesite="strict")
    return response
```

- [ ] **Step 4: Run test to verify it passes**

```bash
.venv/bin/pytest tests/test_setup.py::test_post_setup_stores_password_and_logs_in -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add firmware/src/algoro/admin/routes/setup_routes.py firmware/tests/test_setup.py
git commit -m "feat: POST /setup stores password and auto-logs in"
```

---

## Task 4: POST `/setup` — server-side validation

**Files:**
- Modify: `firmware/tests/test_setup.py` (add 3 tests)
- Modify: `firmware/src/algoro/admin/routes/setup_routes.py`

- [ ] **Step 1: Write the failing tests** — append to `firmware/tests/test_setup.py`

```python
def test_post_setup_rejects_mismatched_passwords(fresh_client: TestClient, db_path: Path) -> None:
    resp = fresh_client.post(
        "/setup",
        data={"password": "hunter2", "confirm": "hunter3"},
    )
    assert resp.status_code == 200
    assert "match" in resp.text.lower()
    # Password NOT stored
    assert not is_password_set(db_path)


def test_post_setup_rejects_short_password(fresh_client: TestClient, db_path: Path) -> None:
    resp = fresh_client.post(
        "/setup",
        data={"password": "abc", "confirm": "abc"},
    )
    assert resp.status_code == 200
    assert "5 characters" in resp.text or "at least 5" in resp.text
    assert not is_password_set(db_path)


def test_post_setup_rejects_empty_password(fresh_client: TestClient, db_path: Path) -> None:
    resp = fresh_client.post(
        "/setup",
        data={"password": "", "confirm": ""},
    )
    # FastAPI Form(...) rejects empty as 422, OR our validation returns 200 with error.
    # Either is acceptable per the spec — the invariant is: password is NOT stored.
    assert resp.status_code in (200, 422)
    assert not is_password_set(db_path)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/pytest tests/test_setup.py -v
```

Expected: `test_post_setup_rejects_mismatched_passwords` and `test_post_setup_rejects_short_password` fail because the current handler stores anything. The empty-password test may or may not fail depending on Form behavior — either way, the next step will make all three pass.

- [ ] **Step 3: Add validation to `firmware/src/algoro/admin/routes/setup_routes.py`**

Replace the `setup_submit` handler:

```python
@router.post("/setup")
def setup_submit(
    request: Request,
    password: str = Form(...),
    confirm: str = Form(...),
):
    db_path = request.app.state.db_path

    error: str | None = None
    if len(password) < MIN_PASSWORD_LENGTH:
        error = f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    elif password != confirm:
        error = "Passwords do not match."

    if error is not None:
        return templates.TemplateResponse(
            request,
            "setup.html",
            {"error": error},
            status_code=200,
        )

    set_password(password, db_path)
    token = create_session_token(db_path)
    response = RedirectResponse(url="/", status_code=302)
    response.set_cookie("session", token, httponly=True, samesite="strict")
    return response
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_setup.py -v
```

Expected: all setup tests so far PASSED.

- [ ] **Step 5: Commit**

```bash
git add firmware/src/algoro/admin/routes/setup_routes.py firmware/tests/test_setup.py
git commit -m "feat: validate /setup password (min 5 chars, must match confirm)"
```

---

## Task 5: Close the `/setup` route once a password is set

**Files:**
- Modify: `firmware/tests/test_setup.py` (add 2 tests)
- Modify: `firmware/src/algoro/admin/routes/setup_routes.py`

- [ ] **Step 1: Write the failing tests** — append to `firmware/tests/test_setup.py`

```python
from algoro.auth import set_password as auth_set_password


def test_get_setup_redirects_to_login_when_password_already_set(db_path: Path) -> None:
    auth_set_password("existing", db_path)
    app = create_app(db_path=db_path)
    client = TestClient(app)
    resp = client.get("/setup", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers["location"]


def test_post_setup_does_not_overwrite_existing_password(db_path: Path) -> None:
    auth_set_password("original", db_path)
    app = create_app(db_path=db_path)
    client = TestClient(app)
    resp = client.post(
        "/setup",
        data={"password": "newpass", "confirm": "newpass"},
        follow_redirects=False,
    )
    # Must redirect to /login (no-op) and NOT change the password.
    assert resp.status_code == 302
    assert "/login" in resp.headers["location"]
    # Original password still works
    from algoro.auth import check_password
    assert check_password("original", db_path)
    assert not check_password("newpass", db_path)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/pytest tests/test_setup.py -v
```

Expected: both new tests fail. GET `/setup` returns 200; POST `/setup` overwrites the password.

- [ ] **Step 3: Close the route in `firmware/src/algoro/admin/routes/setup_routes.py`**

Add an `is_password_set` pre-check at the top of both handlers. Final file:

```python
from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from algoro.auth import create_session_token, is_password_set, set_password

router = APIRouter()
templates = Jinja2Templates(
    directory=str(Path(__file__).parent.parent.parent.parent.parent / "templates")
)

MIN_PASSWORD_LENGTH = 5


@router.get("/setup", response_class=HTMLResponse)
def setup_page(request: Request):
    db_path = request.app.state.db_path
    if is_password_set(db_path):
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse(request, "setup.html", {"error": None})


@router.post("/setup")
def setup_submit(
    request: Request,
    password: str = Form(...),
    confirm: str = Form(...),
):
    db_path = request.app.state.db_path
    if is_password_set(db_path):
        return RedirectResponse(url="/login", status_code=302)

    error: str | None = None
    if len(password) < MIN_PASSWORD_LENGTH:
        error = f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    elif password != confirm:
        error = "Passwords do not match."

    if error is not None:
        return templates.TemplateResponse(
            request,
            "setup.html",
            {"error": error},
            status_code=200,
        )

    set_password(password, db_path)
    token = create_session_token(db_path)
    response = RedirectResponse(url="/", status_code=302)
    response.set_cookie("session", token, httponly=True, samesite="strict")
    return response
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_setup.py -v
```

Expected: all 9 setup tests PASSED.

- [ ] **Step 5: Run the full test suite**

```bash
.venv/bin/pytest -m "not integration" -v
```

Expected: all tests PASSED.

- [ ] **Step 6: Commit**

```bash
git add firmware/src/algoro/admin/routes/setup_routes.py firmware/tests/test_setup.py
git commit -m "feat: close /setup route once admin password is set"
```

---

## Self-review

- **Spec coverage:** Every row of the behavior tables in the spec is covered by a test:
  - `GET /` → `/setup` when no password: Task 2, test 1
  - `GET /login` → `/setup` when no password: Task 2, test 2
  - `POST /login` → `/setup` when no password: Task 2, test 3
  - `GET /setup` → 200 form when no password: Task 1, test 1
  - `POST /setup` valid: Task 3, test 1
  - `POST /setup` invalid (mismatch / too short / empty): Task 4, tests 1–3
  - `GET /setup` → `/login` when password set: Task 5, test 1
  - `POST /setup` → `/login` (no overwrite) when password set: Task 5, test 2
- **Type consistency:** `is_password_set`, `set_password`, `create_session_token`, `check_password` are imported from `algoro.auth` everywhere they appear and match the existing module's signatures.
- **No placeholders.** Every code block is complete; every test has its assertion body.
- **No regressions:** The existing `app` fixture in `test_admin.py` calls `set_password` *before* creating the app, so `is_password_set()` returns True for those tests and they keep behaving exactly as before. Task 2 Step 6 runs the full suite to verify.
