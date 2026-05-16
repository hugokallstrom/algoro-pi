# algoro `/setup` route — minimal first-boot bootstrap

**Status:** design (pre-implementation)
**Date:** 2026-05-11
**Parent:** [2026-05-11-algoro-v1-design.md](2026-05-11-algoro-v1-design.md) — section "Setup UX"

## Summary

A minimal `/setup` route that lets a freshly flashed Pi self-bootstrap. On first boot, every HTTP request lands the user on a single page where they choose an admin password. After submit, they are auto-logged in and the route is closed off until SD card re-flash.

This is the *minimal slice* of the v1 spec's setup UX — no captive portal, no preset selection, no router-DNS instructions. Those layer on top later without rewriting this.

## Goal

Clear the "fresh DB has no password" cliff so a technical first user can install the firmware, reach the Pi's IP, and reach a working admin UI without running a Python one-liner to call `set_password` from the shell.

## Non-goals

- Captive portal / AP-mode setup wizard (spec §"Setup UX" full version — deferred)
- Preset selection at setup time (deferred to dashboard work)
- Username / multi-admin (single-admin appliance by design)
- Password rotation (separate feature, behind auth, not in this spec)
- "Forgot password" flow (intentionally impossible — re-flash is the recovery path)
- Router-brand auto-detection (deferred to wizard work)
- "Test your blocking is live" verification step (deferred)

## Behavior

### When `is_password_set()` returns False

| Request | Response |
|---|---|
| `GET /` | 302 → `/setup` |
| `GET /login` | 302 → `/setup` |
| `POST /login` | 302 → `/setup` |
| `GET /setup` | 200, render setup form |
| `POST /setup` (valid) | Store password, create session, set cookie, 302 → `/` |
| `POST /setup` (invalid) | 200, re-render form with inline error |

### When `is_password_set()` returns True

| Request | Response |
|---|---|
| `GET /` | unchanged — auth-protected, redirects to `/login` if unauthed |
| `GET /login` | unchanged — renders login form |
| `GET /setup` | 302 → `/login` |
| `POST /setup` | 302 → `/login` (no-op; do not overwrite the password) |

## The setup form

Two fields plus a submit button:

- `password` — type=password, required, minlength=5
- `confirm` — type=password, required, minlength=5

HTML attributes are hints. Server-side validation is the source of truth:

- Reject if either field is empty
- Reject if either field is shorter than 5 characters
- Reject if `password != confirm`
- On reject: re-render the form with an inline error message describing the failure

## Architecture

### New files

- `firmware/src/algoro/admin/routes/setup_routes.py` — GET/POST `/setup`
- `firmware/templates/setup.html` — extends `base.html`, contains the two-field form, shows inline error

### Modified files

- `firmware/src/algoro/admin/app.py` — register the setup router
- `firmware/src/algoro/admin/deps.py` — `require_auth` adds a pre-check: if `is_password_set()` is False, redirect to `/setup` instead of `/login`
- `firmware/src/algoro/admin/routes/auth_routes.py` — `login_page` (GET) and `login` (POST) both add a pre-check at the top: if `is_password_set()` is False, redirect to `/setup`

### Data model

No changes. Existing `auth.set_password()`, `auth.is_password_set()`, and `auth.create_session_token()` are sufficient.

## Test plan

TDD, same pattern as the rest of the firmware suite. New test file `firmware/tests/test_setup.py`:

1. `GET /setup` renders the form when no password is set
2. `GET /setup` redirects to `/login` when a password is already set
3. `GET /` redirects to `/setup` when no password is set
4. `GET /login` redirects to `/setup` when no password is set
4b. `POST /login` redirects to `/setup` when no password is set (does not call `check_password`)
5. `POST /setup` with valid matching password stores password, sets session cookie, redirects to `/`
6. `POST /setup` with mismatched passwords re-renders form with error, password is not stored
7. `POST /setup` with password shorter than 5 chars re-renders form with error
8. `POST /setup` when password is already set is a no-op redirect to `/login` and does not overwrite the existing hash

Existing tests in `test_admin.py` continue to pass — they all use the `app` fixture which calls `set_password("testpass", db_path)` before instantiating the app, so `is_password_set()` is True throughout those tests.

## Success criteria

- A flashed Pi with an empty DB and no password configured can be brought up to a working admin UI in one form submission (password + confirm).
- The setup route cannot be used to rotate the password once it is set.
- No existing test regresses.
