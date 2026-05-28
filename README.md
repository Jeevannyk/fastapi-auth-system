# Cipher Auth

A production-shaped FastAPI authentication service. Cookie-based sessions, refresh-token rotation, TOTP two-factor, email verification, password reset, account lockout, rate limiting, Alembic migrations, and a Postgres-ready Docker setup.

## Stack

- FastAPI + Pydantic v2 + pydantic-settings
- SQLAlchemy 2.x + Alembic
- bcrypt, python-jose (JWT), pyotp (TOTP), qrcode
- slowapi for rate limiting
- SQLite for local dev, Postgres for prod (psycopg 3)
- Vanilla JS frontend (no build step)

## Auth model

- **Access tokens** — short-lived JWT in an `HttpOnly SameSite=Lax` cookie at path `/`. 15 min default.
- **Refresh tokens** — opaque random tokens; only their SHA-256 hash lives in the database. Stored in a separate `HttpOnly` cookie scoped to `/api/auth`. On `/refresh`, the old token is revoked and a new one is issued (rotation).
- **Email verification** — new accounts receive a 24-hour verification link. Set `EMAIL_ENABLED=false` (default) to skip in dev; auto-verifies immediately. Unverified accounts cannot log in.
- **Password reset** — time-limited (1 hour) reset links sent by email. Always returns a generic success message to prevent email enumeration. Resets the account lockout on success.
- **2FA / TOTP** — RFC 6238. When enabled, `/login` returns `requires_2fa: true` and sets a short-lived `pending_2fa` cookie. The client posts a 6-digit code to `/login/2fa` to finalize. QR code generated server-side.
- **Lockout** — after 5 failed logins the account locks for 15 minutes (configurable).
- **Rate limiting** — `5/minute` on `/login`, `3/minute` on `/signup` (per IP, configurable).
- **HTTPS enforcement** — when `ENVIRONMENT=production`, HTTP requests are automatically redirected to HTTPS.

## Quick start (local)

```bash
python -m venv .venv
. .venv/Scripts/activate            # PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt

cp .env.example .env                # then edit SECRET_KEY
alembic upgrade head

uvicorn backend.main:app --reload
```

Open <http://127.0.0.1:8000>. API docs at `/docs`.

## Quick start (Docker + Postgres)

```bash
echo "SECRET_KEY=$(python -c 'import secrets;print(secrets.token_urlsafe(48))')" > .env
docker compose up --build
```

Postgres + the app start together; migrations run automatically on startup.

## Email setup

By default `EMAIL_ENABLED=false` — users are verified instantly and no SMTP server is needed. To enable real emails:

```env
EMAIL_ENABLED=true
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=user@example.com
SMTP_PASSWORD=your-password
SMTP_FROM=noreply@cipher.app
APP_BASE_URL=https://your-domain.com
```

## API

| Method | Path                        | Notes                                              |
| ------ | --------------------------- | -------------------------------------------------- |
| POST   | `/api/auth/signup`          | `{full_name, email, password}` → 201               |
| GET    | `/api/auth/verify-email`    | `?token=xxx` — activates account                   |
| POST   | `/api/auth/login`           | Sets cookies; may return `requires_2fa: true`      |
| POST   | `/api/auth/login/2fa`       | `{user_id, code}` — completes 2FA login            |
| POST   | `/api/auth/refresh`         | Rotates refresh + access cookies                   |
| POST   | `/api/auth/logout`          | Revokes refresh token, clears cookies              |
| GET    | `/api/auth/me`              | Current user (requires auth)                       |
| POST   | `/api/auth/forgot-password` | `{email}` — sends reset link if registered        |
| POST   | `/api/auth/reset-password`  | `{token, password}` — sets new password            |
| POST   | `/api/2fa/setup`            | Returns secret + otpauth URL + QR code data URL    |
| POST   | `/api/2fa/enable`           | Confirms with a TOTP code                          |
| POST   | `/api/2fa/disable`          | Confirms with a TOTP code                          |
| GET    | `/health`                   | Liveness check                                     |

## Tests

```bash
pytest
```

The suite uses a throwaway SQLite file and covers:

- Signup / login / refresh / logout / cookie handling
- Email verification flow (valid token, expired token, single-use enforcement)
- Password reset flow (valid token, expired token, lockout cleared, single-use enforcement)
- Anti-enumeration (forgot-password returns identical response for any email)
- TOTP setup + enforced 2FA login
- Account lockout after failed attempts

## Production checklist

- Set `ENVIRONMENT=production`, a real `SECRET_KEY`, and `DATABASE_URL` pointing to Postgres.
- Terminate TLS in front of the app; set `COOKIE_SECURE=true`.
- Set `EMAIL_ENABLED=true` and configure SMTP credentials.
- Set `APP_BASE_URL` to the public HTTPS URL (used in verification/reset links).
- Restrict `ALLOWED_ORIGINS` to the actual frontend origin.
- Run `alembic upgrade head` on deploy.
- The default rate-limit backend is in-memory; for multi-process deployments point slowapi at Redis.

## Layout

```
backend/
  config.py        settings (pydantic-settings)
  database.py      engine, session, declarative Base
  models.py        User, RefreshToken
  schemas.py       request/response models
  security.py      hashing, JWT, TOTP, QR code generation
  email.py         SMTP email sending (verification + reset)
  deps.py          current_user dependency
  rate_limit.py    slowapi limiter
  routes/
    auth.py        signup/login/refresh/logout/me/verify-email/forgot-password/reset-password
    twofa.py       setup/enable/disable
    pages.py       HTML page routes
  main.py          app factory
frontend/
  login.html / login.js
  signup.html / signup.js
  home.html / home.js
  totp.html / totp.js
  verify-email.html / verify-email.js
  forgot-password.html / forgot-password.js
  reset-password.html / reset-password.js
  util.js          shared fetch + error helpers
alembic/           migrations
tests/             pytest suite
```
