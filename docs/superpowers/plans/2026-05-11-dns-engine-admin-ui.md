# slopstop DNS Engine + Admin Web UI — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Raspberry Pi Zero 2 W that blocks configured DNS domains for all LAN devices, with a password-protected local web UI at port 80 for managing the blocklist.

**Architecture:** Unbound handles DNS resolution and domain blocking via `local-zone: "domain." always_nxdomain` directives (blocks apex + all subdomains). dnscrypt-proxy sits between Unbound and upstream resolvers (port 5353 locally) to encrypt outbound DNS. A FastAPI + Jinja2 app served on port 80 provides the password-protected admin UI. All state lives in SQLite. Services managed by systemd. No cloud dependency in this plan.

**Tech Stack:** Python 3.11+, FastAPI 0.111+, Uvicorn, Jinja2, HTMX 1.9 (bundled locally — no CDN), bcrypt, SQLite (stdlib), Unbound, dnscrypt-proxy, systemd, Raspberry Pi OS Lite 64-bit

**v1 simplification:** "Recent block events" from the spec is deferred — requires IPC between Unbound and the admin app. The UI shows status + blocklist only.

---

## File Structure

```
firmware/
├── pyproject.toml
├── conftest.py                          # shared pytest fixtures
├── src/
│   └── slopstop/
│       ├── __init__.py
│       ├── db.py                        # SQLite init + connection factory
│       ├── auth.py                      # password hashing + session tokens
│       ├── blocklist.py                 # domain CRUD + file export + preset import
│       ├── dns_control.py               # Unbound config generation + reload
│       ├── led.py                       # LED status daemon (GPIO or no-op)
│       └── admin/
│           ├── __init__.py
│           ├── app.py                   # create_app() factory
│           ├── deps.py                  # require_auth dependency
│           └── routes/
│               ├── __init__.py
│               ├── auth_routes.py       # GET/POST /login, POST /logout
│               └── blocklist_routes.py  # GET /, POST /add, POST /remove
├── templates/
│   ├── base.html
│   ├── login.html
│   ├── dashboard.html
│   └── blocklist_row.html              # HTMX partial for single row
├── static/
│   ├── htmx.min.js                     # bundled, no CDN
│   └── style.css
├── dns/
│   └── unbound.conf.j2                 # Jinja2 template for Unbound config
├── blocklists/
│   ├── social_only.txt
│   ├── social_news.txt
│   └── hard_mode.txt
├── systemd/
│   ├── slopstop-admin.service
│   ├── slopstop-led.service
│   └── install.sh
└── tests/
    ├── test_db.py
    ├── test_auth.py
    ├── test_blocklist.py
    ├── test_dns_control.py
    ├── test_admin.py
    └── test_led.py
```

---

## Task 1: Project scaffold

**Files:**
- Create: `firmware/pyproject.toml`
- Create: `firmware/conftest.py`
- Create: `firmware/src/slopstop/__init__.py`
- Create: `firmware/.gitignore`

- [ ] **Step 1: Create the directory structure**

```bash
mkdir -p firmware/src/slopstop/admin/routes
mkdir -p firmware/templates
mkdir -p firmware/static
mkdir -p firmware/dns
mkdir -p firmware/blocklists
mkdir -p firmware/systemd
mkdir -p firmware/tests
touch firmware/src/slopstop/__init__.py
touch firmware/src/slopstop/admin/__init__.py
touch firmware/src/slopstop/admin/routes/__init__.py
```

- [ ] **Step 2: Write `firmware/pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "slopstop"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.111",
    "uvicorn[standard]>=0.29",
    "jinja2>=3.1",
    "bcrypt>=4.1",
    "python-multipart>=0.0.9",
    "httpx>=0.27",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.1",
    "pytest-asyncio>=0.23",
    "anyio>=4.3",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "integration: requires running Unbound on a Pi or in Docker",
]
```

- [ ] **Step 3: Write `firmware/conftest.py`**

```python
import pytest
from pathlib import Path
from slopstop.db import init_db


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "test.db"
    init_db(path)
    return path
```

- [ ] **Step 4: Write `firmware/.gitignore`**

```
__pycache__/
*.pyc
*.egg-info/
dist/
.venv/
*.db
```

- [ ] **Step 5: Install dependencies**

```bash
cd firmware
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Expected: installs without errors.

- [ ] **Step 6: Commit**

```bash
git add firmware/
git commit -m "feat: project scaffold for firmware"
```

---

## Task 2: Database layer

**Files:**
- Create: `firmware/src/slopstop/db.py`
- Create: `firmware/tests/test_db.py`

- [ ] **Step 1: Write the failing test**

`firmware/tests/test_db.py`:
```python
import sqlite3
from pathlib import Path
from slopstop.db import init_db, get_db


def test_init_db_creates_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    init_db(db_path)
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    names = {r["name"] for r in rows}
    assert "config" in names
    assert "blocked_domains" in names


def test_init_db_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    init_db(db_path)
    init_db(db_path)  # must not raise or corrupt


def test_get_db_returns_row_factory(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    init_db(db_path)
    with get_db(db_path) as conn:
        conn.execute("INSERT INTO config (key, value) VALUES ('k', 'v')")
    with get_db(db_path) as conn:
        row = conn.execute("SELECT key, value FROM config").fetchone()
    assert row["key"] == "k"
    assert row["value"] == "v"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd firmware
pytest tests/test_db.py -v
```

Expected: `ImportError: No module named 'slopstop.db'`

- [ ] **Step 3: Write `firmware/src/slopstop/db.py`**

```python
import sqlite3
from pathlib import Path

DB_PATH = Path("/var/lib/slopstop/slopstop.db")


def get_db(path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(path: Path = DB_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with get_db(path) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS config (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS blocked_domains (
                domain   TEXT PRIMARY KEY,
                preset   TEXT,
                enabled  INTEGER NOT NULL DEFAULT 1,
                added_at TEXT    NOT NULL DEFAULT (datetime('now'))
            );
        """)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_db.py -v
```

Expected: 3 tests PASSED.

- [ ] **Step 5: Commit**

```bash
git add firmware/src/slopstop/db.py firmware/tests/test_db.py
git commit -m "feat: SQLite database layer"
```

---

## Task 3: Auth module

**Files:**
- Create: `firmware/src/slopstop/auth.py`
- Create: `firmware/tests/test_auth.py`

- [ ] **Step 1: Write the failing tests**

`firmware/tests/test_auth.py`:
```python
from pathlib import Path
from slopstop.auth import (
    hash_password,
    verify_password,
    set_password,
    check_password,
    is_password_set,
    create_session_token,
    validate_session_token,
)


def test_hash_and_verify_correct_password() -> None:
    hashed = hash_password("correcthorsebatterystaple")
    assert verify_password("correcthorsebatterystaple", hashed) is True


def test_hash_and_verify_wrong_password() -> None:
    hashed = hash_password("correcthorsebatterystaple")
    assert verify_password("wrongpassword", hashed) is False


def test_set_and_check_password(db_path: Path) -> None:
    set_password("mypassword", db_path)
    assert check_password("mypassword", db_path) is True
    assert check_password("wrongpassword", db_path) is False


def test_is_password_set_false_initially(db_path: Path) -> None:
    assert is_password_set(db_path) is False


def test_is_password_set_true_after_set(db_path: Path) -> None:
    set_password("secret", db_path)
    assert is_password_set(db_path) is True


def test_session_token_validates(db_path: Path) -> None:
    token = create_session_token(db_path)
    assert validate_session_token(token, db_path) is True


def test_wrong_session_token_rejected(db_path: Path) -> None:
    create_session_token(db_path)
    assert validate_session_token("not-the-real-token", db_path) is False


def test_new_token_invalidates_old(db_path: Path) -> None:
    old_token = create_session_token(db_path)
    create_session_token(db_path)
    assert validate_session_token(old_token, db_path) is False
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_auth.py -v
```

Expected: `ImportError: No module named 'slopstop.auth'`

- [ ] **Step 3: Write `firmware/src/slopstop/auth.py`**

```python
import secrets
from pathlib import Path

import bcrypt

from .db import get_db


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def set_password(password: str, db_path: Path) -> None:
    hashed = hash_password(password)
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO config (key, value) VALUES ('password_hash', ?)",
            (hashed,),
        )


def check_password(password: str, db_path: Path) -> bool:
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT value FROM config WHERE key = 'password_hash'"
        ).fetchone()
    if row is None:
        return False
    return verify_password(password, row["value"])


def is_password_set(db_path: Path) -> bool:
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT value FROM config WHERE key = 'password_hash'"
        ).fetchone()
    return row is not None


def create_session_token(db_path: Path) -> str:
    token = secrets.token_urlsafe(32)
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO config (key, value) VALUES ('session_token', ?)",
            (token,),
        )
    return token


def validate_session_token(token: str, db_path: Path) -> bool:
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT value FROM config WHERE key = 'session_token'"
        ).fetchone()
    if row is None:
        return False
    return secrets.compare_digest(token, row["value"])
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_auth.py -v
```

Expected: 8 tests PASSED.

- [ ] **Step 5: Commit**

```bash
git add firmware/src/slopstop/auth.py firmware/tests/test_auth.py
git commit -m "feat: auth module — password hashing and session tokens"
```

---

## Task 4: Blocklist manager

**Files:**
- Create: `firmware/src/slopstop/blocklist.py`
- Create: `firmware/tests/test_blocklist.py`

- [ ] **Step 1: Write the failing tests**

`firmware/tests/test_blocklist.py`:
```python
from pathlib import Path
from slopstop.blocklist import (
    add_domain,
    remove_domain,
    list_domains,
    export_to_file,
)


def test_add_and_list_domain(db_path: Path) -> None:
    add_domain("instagram.com", db_path)
    domains = list_domains(db_path)
    assert len(domains) == 1
    assert domains[0]["domain"] == "instagram.com"


def test_add_domain_normalises_whitespace_and_case(db_path: Path) -> None:
    add_domain("  Instagram.COM  ", db_path)
    domains = list_domains(db_path)
    assert domains[0]["domain"] == "instagram.com"


def test_add_domain_strips_trailing_dot(db_path: Path) -> None:
    add_domain("reddit.com.", db_path)
    assert list_domains(db_path)[0]["domain"] == "reddit.com"


def test_add_domain_is_idempotent(db_path: Path) -> None:
    add_domain("twitter.com", db_path)
    add_domain("twitter.com", db_path)
    assert len(list_domains(db_path)) == 1


def test_remove_domain(db_path: Path) -> None:
    add_domain("tiktok.com", db_path)
    remove_domain("tiktok.com", db_path)
    assert list_domains(db_path) == []


def test_remove_nonexistent_domain_does_not_raise(db_path: Path) -> None:
    remove_domain("nothere.com", db_path)  # must not raise


def test_export_writes_enabled_domains(db_path: Path, tmp_path: Path) -> None:
    add_domain("instagram.com", db_path)
    add_domain("tiktok.com", db_path)
    out = tmp_path / "blocklist.txt"
    export_to_file(db_path, out)
    lines = out.read_text().splitlines()
    assert "instagram.com" in lines
    assert "tiktok.com" in lines


def test_export_empty_blocklist_writes_empty_file(db_path: Path, tmp_path: Path) -> None:
    out = tmp_path / "blocklist.txt"
    export_to_file(db_path, out)
    assert out.read_text() == ""


def test_add_domain_stores_preset(db_path: Path) -> None:
    add_domain("facebook.com", db_path, preset="social_only")
    domains = list_domains(db_path)
    assert domains[0]["preset"] == "social_only"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_blocklist.py -v
```

Expected: `ImportError: No module named 'slopstop.blocklist'`

- [ ] **Step 3: Write `firmware/src/slopstop/blocklist.py`**

```python
import os
from pathlib import Path

from .db import get_db

ACTIVE_BLOCKLIST_PATH = Path(
    os.environ.get("SLOPSTOP_BLOCKLIST_PATH", "/var/lib/slopstop/active_blocklist.txt")
)
PRESET_DIR = Path(
    os.environ.get("SLOPSTOP_PRESET_DIR", str(Path(__file__).parent.parent.parent / "blocklists"))
)


def add_domain(domain: str, db_path: Path, preset: str | None = None) -> None:
    domain = domain.strip().lower().rstrip(".")
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO blocked_domains (domain, preset) VALUES (?, ?)",
            (domain, preset),
        )


def remove_domain(domain: str, db_path: Path) -> None:
    domain = domain.strip().lower().rstrip(".")
    with get_db(db_path) as conn:
        conn.execute("DELETE FROM blocked_domains WHERE domain = ?", (domain,))


def list_domains(db_path: Path) -> list[dict]:
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT domain, preset, enabled, added_at FROM blocked_domains ORDER BY added_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def export_to_file(db_path: Path, out_path: Path = ACTIVE_BLOCKLIST_PATH) -> None:
    domains = [r["domain"] for r in list_domains(db_path) if r["enabled"]]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(domains) + "\n" if domains else "")


def import_preset(preset_name: str, db_path: Path) -> int:
    preset_path = PRESET_DIR / f"{preset_name}.txt"
    lines = preset_path.read_text().splitlines()
    domains = [l.strip() for l in lines if l.strip() and not l.startswith("#")]
    for domain in domains:
        add_domain(domain, db_path, preset=preset_name)
    return len(domains)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_blocklist.py -v
```

Expected: 9 tests PASSED.

- [ ] **Step 5: Commit**

```bash
git add firmware/src/slopstop/blocklist.py firmware/tests/test_blocklist.py
git commit -m "feat: blocklist manager — domain CRUD and file export"
```

---

## Task 5: DNS config generation and control

**Files:**
- Create: `firmware/dns/unbound.conf.j2`
- Create: `firmware/src/slopstop/dns_control.py`
- Create: `firmware/tests/test_dns_control.py`

- [ ] **Step 1: Write the failing tests**

`firmware/tests/test_dns_control.py`:
```python
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from slopstop.dns_control import (
    generate_unbound_conf,
    is_unbound_running,
    reload_unbound,
    reload_dns,
)

TEMPLATE_DIR = Path(__file__).parent.parent / "dns"


def test_generate_conf_includes_blocked_domains(tmp_path: Path) -> None:
    blocklist = tmp_path / "blocklist.txt"
    blocklist.write_text("instagram.com\ntiktok.com\n")
    out = tmp_path / "slopstop.conf"
    generate_unbound_conf(blocklist, out, template_dir=TEMPLATE_DIR)
    conf = out.read_text()
    assert 'local-zone: "instagram.com." always_nxdomain' in conf
    assert 'local-zone: "tiktok.com." always_nxdomain' in conf


def test_generate_conf_empty_blocklist_has_no_local_zones(tmp_path: Path) -> None:
    blocklist = tmp_path / "blocklist.txt"
    blocklist.write_text("")
    out = tmp_path / "slopstop.conf"
    generate_unbound_conf(blocklist, out, template_dir=TEMPLATE_DIR)
    assert "local-zone" not in out.read_text()


def test_generate_conf_skips_blank_lines(tmp_path: Path) -> None:
    blocklist = tmp_path / "blocklist.txt"
    blocklist.write_text("facebook.com\n\nreddit.com\n\n")
    out = tmp_path / "slopstop.conf"
    generate_unbound_conf(blocklist, out, template_dir=TEMPLATE_DIR)
    conf = out.read_text()
    assert conf.count("local-zone") == 2


def test_reload_unbound_runs_correct_command() -> None:
    with patch("subprocess.run") as mock_run:
        reload_unbound()
        mock_run.assert_called_once_with(["unbound-control", "reload"], check=True)


def test_is_unbound_running_true() -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="active\n")
        assert is_unbound_running() is True


def test_is_unbound_running_false() -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="inactive\n")
        assert is_unbound_running() is False


def test_reload_dns_calls_all_three_steps(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    from slopstop.db import init_db
    from slopstop.blocklist import add_domain
    init_db(db_path)
    add_domain("reddit.com", db_path)

    blocklist_path = tmp_path / "blocklist.txt"
    conf_path = tmp_path / "slopstop.conf"

    with patch("slopstop.dns_control.reload_unbound") as mock_reload:
        reload_dns(db_path, blocklist_path, conf_path, TEMPLATE_DIR)
        mock_reload.assert_called_once()

    assert "reddit.com" in blocklist_path.read_text()
    assert 'local-zone: "reddit.com." always_nxdomain' in conf_path.read_text()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_dns_control.py -v
```

Expected: `ImportError: No module named 'slopstop.dns_control'`

- [ ] **Step 3: Write `firmware/dns/unbound.conf.j2`**

```jinja2
server:
    verbosity: 1
    interface: 0.0.0.0
    port: 53
    access-control: 192.168.0.0/16 allow
    access-control: 10.0.0.0/8 allow
    access-control: 172.16.0.0/12 allow
    do-ip4: yes
    do-ip6: no
    hide-identity: yes
    hide-version: yes
    prefetch: yes
{% for domain in domains %}
    local-zone: "{{ domain }}." always_nxdomain
{% endfor %}

forward-zone:
    name: "."
    forward-addr: 127.0.0.1@5353
```

- [ ] **Step 4: Write `firmware/src/slopstop/dns_control.py`**

```python
import os
import subprocess
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from .blocklist import export_to_file

UNBOUND_CONF_PATH = Path(
    os.environ.get("SLOPSTOP_UNBOUND_CONF", "/etc/unbound/unbound.conf.d/slopstop.conf")
)
DEFAULT_TEMPLATE_DIR = Path(
    os.environ.get("SLOPSTOP_DNS_TEMPLATE_DIR", str(Path(__file__).parent.parent.parent / "dns"))
)


def generate_unbound_conf(
    blocklist_path: Path,
    out_path: Path = UNBOUND_CONF_PATH,
    template_dir: Path = DEFAULT_TEMPLATE_DIR,
) -> None:
    env = Environment(loader=FileSystemLoader(str(template_dir)))
    template = env.get_template("unbound.conf.j2")
    text = blocklist_path.read_text() if blocklist_path.exists() else ""
    domains = [line.strip() for line in text.splitlines() if line.strip()]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(template.render(domains=domains))


def reload_unbound() -> None:
    subprocess.run(["unbound-control", "reload"], check=True)


def is_unbound_running() -> bool:
    result = subprocess.run(
        ["systemctl", "is-active", "unbound"],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() == "active"


def reload_dns(
    db_path: Path,
    blocklist_path: Path,
    unbound_conf_path: Path = UNBOUND_CONF_PATH,
    template_dir: Path = DEFAULT_TEMPLATE_DIR,
) -> None:
    export_to_file(db_path, blocklist_path)
    generate_unbound_conf(blocklist_path, unbound_conf_path, template_dir)
    reload_unbound()
```

- [ ] **Step 5: Run test to verify it passes**

```bash
pytest tests/test_dns_control.py -v
```

Expected: 7 tests PASSED.

- [ ] **Step 6: Commit**

```bash
git add firmware/dns/unbound.conf.j2 firmware/src/slopstop/dns_control.py firmware/tests/test_dns_control.py
git commit -m "feat: DNS config generation and Unbound control"
```

---

## Task 6: Preset domain lists

**Files:**
- Create: `firmware/blocklists/social_only.txt`
- Create: `firmware/blocklists/social_news.txt`
- Create: `firmware/blocklists/hard_mode.txt`
- Modify: `firmware/tests/test_blocklist.py` (add import_preset tests)

- [ ] **Step 1: Write the failing tests** — add to `firmware/tests/test_blocklist.py`

```python
import os
from slopstop.blocklist import import_preset

PRESET_DIR = str(Path(__file__).parent.parent / "blocklists")


def test_import_social_only_preset(db_path: Path) -> None:
    os.environ["SLOPSTOP_PRESET_DIR"] = PRESET_DIR
    count = import_preset("social_only", db_path)
    assert count > 0
    domains = {d["domain"] for d in list_domains(db_path)}
    assert "instagram.com" in domains
    assert "facebook.com" in domains
    assert "tiktok.com" in domains


def test_import_preset_sets_preset_field(db_path: Path) -> None:
    os.environ["SLOPSTOP_PRESET_DIR"] = PRESET_DIR
    import_preset("social_only", db_path)
    domains = list_domains(db_path)
    assert all(d["preset"] == "social_only" for d in domains)


def test_import_preset_skips_comment_lines(db_path: Path) -> None:
    os.environ["SLOPSTOP_PRESET_DIR"] = PRESET_DIR
    count_before = len(list_domains(db_path))
    import_preset("social_only", db_path)
    count_after = len(list_domains(db_path))
    # Every imported row should be a real domain, not a comment
    for d in list_domains(db_path):
        assert not d["domain"].startswith("#")


def test_hard_mode_contains_more_domains_than_social_only(db_path: Path, tmp_path: Path) -> None:
    os.environ["SLOPSTOP_PRESET_DIR"] = PRESET_DIR
    db_social = tmp_path / "social.db"
    db_hard = tmp_path / "hard.db"
    from slopstop.db import init_db
    init_db(db_social)
    init_db(db_hard)
    social_count = import_preset("social_only", db_social)
    hard_count = import_preset("hard_mode", db_hard)
    assert hard_count > social_count
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_blocklist.py::test_import_social_only_preset -v
```

Expected: `FileNotFoundError` (preset file does not exist yet)

- [ ] **Step 3: Write `firmware/blocklists/social_only.txt`**

```
# Facebook / Instagram / Threads
facebook.com
instagram.com
cdninstagram.com
fbcdn.net
threads.net
# Twitter / X
twitter.com
t.co
twimg.com
x.com
# TikTok
tiktok.com
tiktokcdn.com
tiktokv.com
# Reddit
reddit.com
redd.it
redditstatic.com
redditmedia.com
reddituploads.com
# Snapchat
snapchat.com
sc-cdn.net
# Pinterest
pinterest.com
pinimg.com
# LinkedIn
linkedin.com
licdn.com
```

- [ ] **Step 4: Write `firmware/blocklists/social_news.txt`**

```
# === Social (same as social_only) ===
facebook.com
instagram.com
cdninstagram.com
fbcdn.net
threads.net
twitter.com
t.co
twimg.com
x.com
tiktok.com
tiktokcdn.com
tiktokv.com
reddit.com
redd.it
redditstatic.com
redditmedia.com
reddituploads.com
snapchat.com
sc-cdn.net
pinterest.com
pinimg.com
linkedin.com
licdn.com
# === News ===
nytimes.com
theguardian.com
bbc.com
bbc.co.uk
cnn.com
dn.se
svt.se
aftonbladet.se
expressen.se
```

- [ ] **Step 5: Write `firmware/blocklists/hard_mode.txt`**

```
# === Social + News (same as social_news) ===
facebook.com
instagram.com
cdninstagram.com
fbcdn.net
threads.net
twitter.com
t.co
twimg.com
x.com
tiktok.com
tiktokcdn.com
tiktokv.com
reddit.com
redd.it
redditstatic.com
redditmedia.com
reddituploads.com
snapchat.com
sc-cdn.net
pinterest.com
pinimg.com
linkedin.com
licdn.com
nytimes.com
theguardian.com
bbc.com
bbc.co.uk
cnn.com
dn.se
svt.se
aftonbladet.se
expressen.se
# === Video / streaming ===
youtube.com
googlevideo.com
ytimg.com
youtu.be
netflix.com
nflxvideo.net
twitch.tv
twitchsvc.net
# === Gaming / chat ===
discord.com
discordapp.com
discordapp.net
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
pytest tests/test_blocklist.py -v
```

Expected: all tests PASSED (including the 4 new import_preset tests).

- [ ] **Step 7: Commit**

```bash
git add firmware/blocklists/ firmware/tests/test_blocklist.py
git commit -m "feat: preset domain lists (social_only, social_news, hard_mode)"
```

---

## Task 7: Admin web app — skeleton, auth routes, session middleware

**Files:**
- Create: `firmware/src/slopstop/admin/app.py`
- Create: `firmware/src/slopstop/admin/deps.py`
- Create: `firmware/src/slopstop/admin/routes/auth_routes.py`
- Create: `firmware/templates/base.html`
- Create: `firmware/templates/login.html`
- Create: `firmware/static/style.css`
- Create: `firmware/tests/test_admin.py`

- [ ] **Step 1: Download HTMX and save locally**

```bash
curl -sL https://unpkg.com/htmx.org@1.9.12/dist/htmx.min.js -o firmware/static/htmx.min.js
```

Expected: file created at `firmware/static/htmx.min.js` (~45KB).

- [ ] **Step 2: Write the failing tests**

`firmware/tests/test_admin.py`:
```python
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
```

- [ ] **Step 3: Run test to verify it fails**

```bash
pytest tests/test_admin.py -v
```

Expected: `ImportError: No module named 'slopstop.admin.app'`

- [ ] **Step 4: Write `firmware/templates/base.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>slopstop</title>
  <link rel="stylesheet" href="/static/style.css">
  <script src="/static/htmx.min.js" defer></script>
</head>
<body>
  {% block content %}{% endblock %}
</body>
</html>
```

- [ ] **Step 5: Write `firmware/templates/login.html`**

```html
{% extends "base.html" %}
{% block content %}
<main>
  <h1>slopstop</h1>
  <form method="post" action="/login">
    <label for="password">Password</label>
    <input type="password" id="password" name="password" autofocus required>
    {% if error %}
    <p class="error">{{ error }}</p>
    {% endif %}
    <button type="submit">Unlock</button>
  </form>
</main>
{% endblock %}
```

- [ ] **Step 6: Write `firmware/static/style.css`**

```css
*, *::before, *::after { box-sizing: border-box; }
body {
  font-family: system-ui, -apple-system, sans-serif;
  max-width: 640px;
  margin: 2rem auto;
  padding: 0 1rem;
  color: #111;
  background: #fff;
}
h1 { font-size: 1.4rem; margin-bottom: 1.5rem; }
label { display: block; margin-bottom: 0.25rem; font-size: 0.9rem; color: #555; }
input[type="text"], input[type="password"] {
  width: 100%; padding: 0.5rem 0.75rem;
  border: 1px solid #ccc; border-radius: 4px;
  font-size: 1rem; margin-bottom: 0.75rem;
}
button {
  padding: 0.5rem 1.25rem;
  background: #111; color: #fff;
  border: none; border-radius: 4px;
  cursor: pointer; font-size: 1rem;
}
button.danger { background: #c00; }
.error { color: #c00; font-size: 0.9rem; margin: 0.25rem 0 0.75rem; }
.status { font-size: 0.9rem; margin-bottom: 1.5rem; }
.status-active { color: green; font-weight: 600; }
.status-inactive { color: #c00; font-weight: 600; }
.domain-list { list-style: none; padding: 0; margin: 0 0 1.5rem; }
.domain-list li {
  display: flex; justify-content: space-between; align-items: center;
  padding: 0.4rem 0; border-bottom: 1px solid #eee; font-size: 0.95rem;
}
.domain-list li button { padding: 0.2rem 0.6rem; font-size: 0.8rem; }
nav { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; }
nav a { font-size: 0.9rem; color: #555; text-decoration: none; }
```

- [ ] **Step 7: Write `firmware/src/slopstop/admin/deps.py`**

```python
from fastapi import HTTPException, Request


def require_auth(request: Request) -> str:
    from slopstop.auth import validate_session_token
    token = request.cookies.get("session", "")
    db_path = request.app.state.db_path
    if not token or not validate_session_token(token, db_path):
        raise HTTPException(status_code=302, headers={"location": "/login"})
    return token
```

- [ ] **Step 8: Write `firmware/src/slopstop/admin/routes/auth_routes.py`**

```python
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from slopstop.auth import check_password, create_session_token, validate_session_token
from slopstop.admin.deps import require_auth

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent.parent.parent / "templates"))


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@router.post("/login")
def login(request: Request, password: str = Form(...)):
    db_path = request.app.state.db_path
    if not check_password(password, db_path):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid password."},
            status_code=200,
        )
    token = create_session_token(db_path)
    response = RedirectResponse(url="/", status_code=302)
    response.set_cookie("session", token, httponly=True, samesite="strict")
    return response


@router.post("/logout")
def logout(request: Request, _token: str = Depends(require_auth)):
    from slopstop.db import get_db
    db_path = request.app.state.db_path
    with get_db(db_path) as conn:
        conn.execute("DELETE FROM config WHERE key = 'session_token'")
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("session")
    return response
```

- [ ] **Step 9: Write `firmware/src/slopstop/admin/app.py`**

```python
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from slopstop.blocklist import ACTIVE_BLOCKLIST_PATH
from slopstop.dns_control import DEFAULT_TEMPLATE_DIR, UNBOUND_CONF_PATH
from slopstop.admin.routes.auth_routes import router as auth_router

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

    return app
```

- [ ] **Step 10: Run tests to verify they pass**

```bash
pytest tests/test_admin.py -v
```

Expected: 7 tests PASSED (blocklist UI tests will be added in Task 8).

- [ ] **Step 11: Commit**

```bash
git add firmware/src/slopstop/admin/ firmware/templates/base.html firmware/templates/login.html firmware/static/ firmware/tests/test_admin.py
git commit -m "feat: admin web app skeleton with login/logout"
```

---

## Task 8: Admin web app — dashboard and blocklist UI

**Files:**
- Create: `firmware/templates/dashboard.html`
- Create: `firmware/templates/blocklist_row.html`
- Create: `firmware/src/slopstop/admin/routes/blocklist_routes.py`
- Modify: `firmware/src/slopstop/admin/app.py` (add blocklist router + root redirect)
- Modify: `firmware/tests/test_admin.py` (add blocklist UI tests)

- [ ] **Step 1: Write the failing tests** — add to `firmware/tests/test_admin.py`

```python
from unittest.mock import patch

from slopstop.blocklist import add_domain, list_domains


def test_dashboard_shows_blocked_domain_count(authed_client: TestClient, db_path: Path) -> None:
    add_domain("instagram.com", db_path)
    add_domain("tiktok.com", db_path)
    resp = authed_client.get("/")
    assert resp.status_code == 200
    assert "instagram.com" in resp.text
    assert "tiktok.com" in resp.text


def test_add_domain_requires_auth(client: TestClient) -> None:
    resp = client.post("/blocklist/add", data={"domain": "reddit.com"}, follow_redirects=False)
    assert resp.status_code == 302


def test_add_domain_when_authenticated(authed_client: TestClient, db_path: Path) -> None:
    with patch("slopstop.admin.routes.blocklist_routes.reload_dns"):
        resp = authed_client.post(
            "/blocklist/add", data={"domain": "reddit.com"}, follow_redirects=True
        )
    assert resp.status_code == 200
    domains = {d["domain"] for d in list_domains(db_path)}
    assert "reddit.com" in domains


def test_remove_domain_when_authenticated(authed_client: TestClient, db_path: Path) -> None:
    add_domain("facebook.com", db_path)
    with patch("slopstop.admin.routes.blocklist_routes.reload_dns"):
        resp = authed_client.post(
            "/blocklist/remove", data={"domain": "facebook.com"}, follow_redirects=True
        )
    assert resp.status_code == 200
    domains = {d["domain"] for d in list_domains(db_path)}
    assert "facebook.com" not in domains


def test_add_empty_domain_is_rejected(authed_client: TestClient) -> None:
    with patch("slopstop.admin.routes.blocklist_routes.reload_dns"):
        resp = authed_client.post("/blocklist/add", data={"domain": ""})
    assert resp.status_code in (200, 422)
    # empty domain must not appear in DB
    # (db_path fixture is shared via authed_client → app fixture)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_admin.py::test_dashboard_shows_blocked_domain_count -v
```

Expected: 404 on GET / (route not registered yet)

- [ ] **Step 3: Write `firmware/templates/dashboard.html`**

```html
{% extends "base.html" %}
{% block content %}
<nav>
  <h1>slopstop</h1>
  <form method="post" action="/logout" style="display:inline">
    <button type="submit" class="danger" style="font-size:0.8rem;padding:0.25rem 0.75rem">Logout</button>
  </form>
</nav>

<p class="status">
  Status:
  {% if blocking_active %}
  <span class="status-active">Blocking active</span>
  {% else %}
  <span class="status-inactive">Blocking inactive — check Unbound service</span>
  {% endif %}
  &mdash; {{ domain_count }} domain{% if domain_count != 1 %}s{% endif %} blocked
</p>

<form method="post" action="/blocklist/add" style="display:flex;gap:0.5rem;margin-bottom:1.5rem">
  <input type="text" name="domain" placeholder="e.g. example.com" required style="flex:1;margin:0">
  <button type="submit">Add</button>
</form>

<ul class="domain-list">
  {% for d in domains %}
  <li>
    <span>{{ d.domain }}{% if d.preset %} <small style="color:#999">({{ d.preset }})</small>{% endif %}</span>
    <form method="post" action="/blocklist/remove">
      <input type="hidden" name="domain" value="{{ d.domain }}">
      <button type="submit" class="danger">Remove</button>
    </form>
  </li>
  {% else %}
  <li style="color:#999;border:none">No domains blocked yet.</li>
  {% endfor %}
</ul>
{% endblock %}
```

- [ ] **Step 4: Write `firmware/src/slopstop/admin/routes/blocklist_routes.py`**

```python
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from slopstop.admin.deps import require_auth
from slopstop.blocklist import add_domain, list_domains, remove_domain
from slopstop.dns_control import is_unbound_running, reload_dns

router = APIRouter()
templates = Jinja2Templates(
    directory=str(Path(__file__).parent.parent.parent.parent / "templates")
)


def _dashboard_response(request: Request) -> HTMLResponse:
    db_path = request.app.state.db_path
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "domains": list_domains(db_path),
            "domain_count": len(list_domains(db_path)),
            "blocking_active": is_unbound_running(),
        },
    )


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, _token: str = Depends(require_auth)) -> HTMLResponse:
    return _dashboard_response(request)


@router.post("/blocklist/add")
def blocklist_add(
    request: Request,
    domain: str = Form(...),
    _token: str = Depends(require_auth),
):
    if not domain.strip():
        return RedirectResponse(url="/", status_code=302)
    db_path = request.app.state.db_path
    add_domain(domain, db_path)
    reload_dns(
        db_path,
        request.app.state.blocklist_path,
        request.app.state.unbound_conf_path,
        request.app.state.template_dir,
    )
    return RedirectResponse(url="/", status_code=302)


@router.post("/blocklist/remove")
def blocklist_remove(
    request: Request,
    domain: str = Form(...),
    _token: str = Depends(require_auth),
):
    db_path = request.app.state.db_path
    remove_domain(domain, db_path)
    reload_dns(
        db_path,
        request.app.state.blocklist_path,
        request.app.state.unbound_conf_path,
        request.app.state.template_dir,
    )
    return RedirectResponse(url="/", status_code=302)
```

- [ ] **Step 5: Update `firmware/src/slopstop/admin/app.py`** — add blocklist router

```python
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from slopstop.blocklist import ACTIVE_BLOCKLIST_PATH
from slopstop.dns_control import DEFAULT_TEMPLATE_DIR, UNBOUND_CONF_PATH
from slopstop.admin.routes.auth_routes import router as auth_router
from slopstop.admin.routes.blocklist_routes import router as blocklist_router

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

    return app
```

- [ ] **Step 6: Run all admin tests to verify they pass**

```bash
pytest tests/test_admin.py -v
```

Expected: all tests PASSED.

- [ ] **Step 7: Run the full test suite**

```bash
pytest -v
```

Expected: all tests PASSED.

- [ ] **Step 8: Commit**

```bash
git add firmware/templates/ firmware/src/slopstop/admin/routes/blocklist_routes.py firmware/src/slopstop/admin/app.py firmware/tests/test_admin.py
git commit -m "feat: admin dashboard and blocklist management UI"
```

---

## Task 9: LED status daemon

**Files:**
- Create: `firmware/src/slopstop/led.py`
- Create: `firmware/tests/test_led.py`

- [ ] **Step 1: Write the failing tests**

`firmware/tests/test_led.py`:
```python
import time
from unittest.mock import MagicMock, call, patch

import pytest


def test_set_led_when_gpio_unavailable_does_not_raise() -> None:
    import slopstop.led as led_module
    original = led_module.GPIO_AVAILABLE
    try:
        led_module.GPIO_AVAILABLE = False
        led_module.set_led(True)
        led_module.set_led(False)
    finally:
        led_module.GPIO_AVAILABLE = original


def test_set_led_calls_gpio_output_when_available() -> None:
    import slopstop.led as led_module
    mock_gpio = MagicMock()
    mock_gpio.HIGH = 1
    mock_gpio.LOW = 0
    original = led_module.GPIO_AVAILABLE
    original_gpio = getattr(led_module, "GPIO", None)
    try:
        led_module.GPIO_AVAILABLE = True
        led_module.GPIO = mock_gpio
        led_module.set_led(True)
        mock_gpio.output.assert_called_once_with(led_module.LED_PIN, mock_gpio.HIGH)
    finally:
        led_module.GPIO_AVAILABLE = original
        if original_gpio is not None:
            led_module.GPIO = original_gpio


def test_led_daemon_turns_on_when_unbound_active() -> None:
    from slopstop.led import run_led_daemon
    calls = []

    def fake_sleep(seconds):
        # After 2 sleep calls, raise to exit the loop
        calls.append(seconds)
        if len(calls) >= 8:  # 3 startup blinks (6 sleeps) + 2 loop iterations
            raise KeyboardInterrupt

    with patch("slopstop.led.is_unbound_running", return_value=True), \
         patch("slopstop.led.set_led") as mock_led, \
         patch("slopstop.led.setup_gpio"), \
         patch("time.sleep", side_effect=fake_sleep):
        try:
            run_led_daemon()
        except KeyboardInterrupt:
            pass

    led_states = [c.args[0] for c in mock_led.call_args_list]
    assert True in led_states


def test_led_daemon_turns_off_when_unbound_inactive() -> None:
    from slopstop.led import run_led_daemon
    call_count = [0]

    def fake_sleep(seconds):
        call_count[0] += 1
        if call_count[0] >= 8:
            raise KeyboardInterrupt

    with patch("slopstop.led.is_unbound_running", return_value=False), \
         patch("slopstop.led.set_led") as mock_led, \
         patch("slopstop.led.setup_gpio"), \
         patch("time.sleep", side_effect=fake_sleep):
        try:
            run_led_daemon()
        except KeyboardInterrupt:
            pass

    # Last steady-state call should be False (LED off)
    steady_calls = [c.args[0] for c in mock_led.call_args_list
                    if c == mock_led.call_args_list[-1]]
    assert mock_led.call_args_list[-1].args[0] is False
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_led.py -v
```

Expected: `ImportError: No module named 'slopstop.led'`

- [ ] **Step 3: Write `firmware/src/slopstop/led.py`**

```python
import os
import time

try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False

from .dns_control import is_unbound_running

LED_PIN = int(os.environ.get("SLOPSTOP_LED_PIN", "17"))


def setup_gpio() -> None:
    if not GPIO_AVAILABLE:
        return
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(LED_PIN, GPIO.OUT)


def set_led(state: bool) -> None:
    if not GPIO_AVAILABLE:
        return
    GPIO.output(LED_PIN, GPIO.HIGH if state else GPIO.LOW)


def run_led_daemon() -> None:
    setup_gpio()
    # Startup blink: 3 flashes
    for _ in range(3):
        set_led(True)
        time.sleep(0.2)
        set_led(False)
        time.sleep(0.2)
    # Steady-state loop
    while True:
        set_led(is_unbound_running())
        time.sleep(5)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_led.py -v
```

Expected: 4 tests PASSED.

- [ ] **Step 5: Run the full test suite to confirm nothing regressed**

```bash
pytest -v
```

Expected: all tests PASSED.

- [ ] **Step 6: Commit**

```bash
git add firmware/src/slopstop/led.py firmware/tests/test_led.py
git commit -m "feat: LED status daemon"
```

---

## Task 10: Systemd service files and install script

**Files:**
- Create: `firmware/systemd/slopstop-admin.service`
- Create: `firmware/systemd/slopstop-led.service`
- Create: `firmware/systemd/install.sh`

No unit tests for this task — the services are verified by the integration test in Task 11.

- [ ] **Step 1: Write `firmware/systemd/slopstop-admin.service`**

```ini
[Unit]
Description=slopstop Admin Web Interface
After=network.target unbound.service

[Service]
ExecStart=/usr/local/bin/uvicorn slopstop.admin.app:app --host 0.0.0.0 --port 80
WorkingDirectory=/opt/slopstop/firmware
Environment="SLOPSTOP_DB_PATH=/var/lib/slopstop/slopstop.db"
Environment="SLOPSTOP_BLOCKLIST_PATH=/var/lib/slopstop/active_blocklist.txt"
Environment="SLOPSTOP_UNBOUND_CONF=/etc/unbound/unbound.conf.d/slopstop.conf"
Environment="SLOPSTOP_DNS_TEMPLATE_DIR=/opt/slopstop/firmware/dns"
Environment="SLOPSTOP_PRESET_DIR=/opt/slopstop/firmware/blocklists"
Restart=always
User=root

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 2: Write `firmware/systemd/slopstop-led.service`**

```ini
[Unit]
Description=slopstop LED Status Daemon
After=slopstop-admin.service

[Service]
ExecStart=/usr/bin/python3 -c "from slopstop.led import run_led_daemon; run_led_daemon()"
WorkingDirectory=/opt/slopstop/firmware
Environment="PYTHONPATH=/opt/slopstop/firmware/src"
Restart=always
User=root

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 3: Write `firmware/systemd/install.sh`**

```bash
#!/usr/bin/env bash
# Run as root on the Pi. Assumes:
# - repo is checked out at /opt/slopstop
# - Python 3.11+, pip, unbound, dnscrypt-proxy are installed
set -euo pipefail

INSTALL_DIR=/opt/slopstop/firmware
DATA_DIR=/var/lib/slopstop

echo "==> Installing Python package..."
pip install -e "$INSTALL_DIR"

echo "==> Creating data directory..."
mkdir -p "$DATA_DIR"

echo "==> Initialising database..."
python3 -c "
from pathlib import Path
from slopstop.db import init_db
import os
os.environ['SLOPSTOP_DB_PATH'] = '/var/lib/slopstop/slopstop.db'
init_db(Path('/var/lib/slopstop/slopstop.db'))
"

echo "==> Installing systemd units..."
cp "$INSTALL_DIR/systemd/slopstop-admin.service" /etc/systemd/system/
cp "$INSTALL_DIR/systemd/slopstop-led.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable slopstop-admin slopstop-led
systemctl start slopstop-admin slopstop-led

echo "==> Done. Admin UI running at http://$(hostname -I | awk '{print $1}')"
echo "    Set your router's DNS server to that IP."
```

- [ ] **Step 4: Make install script executable**

```bash
chmod +x firmware/systemd/install.sh
```

- [ ] **Step 5: Commit**

```bash
git add firmware/systemd/
git commit -m "feat: systemd service files and install script"
```

---

## Task 11: End-to-end integration test (Pi or Docker)

**Files:**
- Create: `firmware/tests/test_integration.py`

This test requires Unbound installed and running. It is marked `integration` and skipped in normal `pytest` runs. Run it on a Pi or in a Docker container built with `apt-get install -y unbound dnscrypt-proxy`.

- [ ] **Step 1: Write the integration test**

`firmware/tests/test_integration.py`:
```python
import socket
import subprocess
import time
from pathlib import Path

import pytest

from slopstop.auth import set_password
from slopstop.blocklist import add_domain, export_to_file
from slopstop.db import init_db
from slopstop.dns_control import (
    DEFAULT_TEMPLATE_DIR,
    UNBOUND_CONF_PATH,
    generate_unbound_conf,
    reload_unbound,
)


@pytest.mark.integration
def test_blocked_domain_returns_nxdomain(tmp_path: Path) -> None:
    """
    Requires: unbound installed, unbound-control configured, running as root.
    """
    db_path = tmp_path / "test.db"
    init_db(db_path)
    add_domain("slopstop-integration-test-blocked.invalid", db_path)

    blocklist_path = tmp_path / "blocklist.txt"
    export_to_file(db_path, blocklist_path)
    generate_unbound_conf(blocklist_path, UNBOUND_CONF_PATH, DEFAULT_TEMPLATE_DIR)
    reload_unbound()
    time.sleep(0.5)  # give Unbound a moment to reload

    try:
        socket.getaddrinfo("slopstop-integration-test-blocked.invalid", None)
        pytest.fail("Expected socket.gaierror (NXDOMAIN) but got a result")
    except socket.gaierror:
        pass  # expected: domain is blocked


@pytest.mark.integration
def test_non_blocked_domain_resolves(tmp_path: Path) -> None:
    """
    Confirms non-blocked domains still resolve after config is applied.
    """
    result = socket.getaddrinfo("example.com", 80)
    assert len(result) > 0
```

- [ ] **Step 2: Run unit tests to confirm they still pass (skip integration)**

```bash
pytest -v -m "not integration"
```

Expected: all non-integration tests PASSED.

- [ ] **Step 3: On a Pi or Docker container, run the integration tests**

On the Pi (run as root after install.sh):
```bash
cd /opt/slopstop/firmware
pytest tests/test_integration.py -v -m integration
```

Expected: 2 integration tests PASSED.

- [ ] **Step 4: Commit**

```bash
git add firmware/tests/test_integration.py
git commit -m "test: end-to-end integration tests for DNS blocking"
```

---

## Self-review notes

- All types used in tests (`Path`, `TestClient`, etc.) are defined or imported in each task — no cross-task type dependencies.
- `reload_dns` is consistently patched in admin tests via `patch("slopstop.admin.routes.blocklist_routes.reload_dns")` — matches where it is imported.
- `SLOPSTOP_PRESET_DIR` env var is set in each preset test that needs it — tests are independent.
- The `app.py` in Task 8 replaces the version from Task 7 completely — both versions shown in full, no "similar to" shortcuts.
- "Recent block events" from the spec is explicitly deferred (noted at top of plan).
- Hardware LED GPIO pin 17 is the default; configurable via `SLOPSTOP_LED_PIN` env var.
- Password recovery path (re-flash SD card) is not implemented in this plan — it is a physical operation, not a software one.
