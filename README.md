# Cipher Auth

A passwordless identity provider built with FastAPI. Users enroll a trusted
**device**, then sign in by scanning a rotating **QR code** and tapping
*Approve* — no passwords anywhere. Cipher can also act as an OAuth 2.0 / OpenID
Connect provider so third-party apps can "Sign in with Cipher".

## Stack

- FastAPI + Pydantic v2 + pydantic-settings
- SQLAlchemy 2.x + Alembic
- python-jose (JWT access tokens), qrcode + pypng (QR generation)
- slowapi for rate limiting
- SQLite for local dev, Postgres for prod (psycopg 3)
- Vanilla JS frontend (no build step)

## Auth model

- **Device enrollment** — registering a browser issues an opaque device token.
  Only its SHA-256 hash is stored; the raw token is delivered as an `HttpOnly
  SameSite=Lax` cookie, so it is never exposed to JavaScript (no `localStorage`).
  A separate readable `device_enrolled` flag lets the UI know the browser is
  enrolled without revealing the token.
- **QR login** — the login page opens a session and shows a QR code carrying an
  HMAC-signed, time-limited challenge that rotates every 30 s. The enrolled
  device scans it (`/scan`), the server validates the challenge, and the user
  taps *Approve*. The browser polls session status and exchanges the approved
  session for a short-lived JWT access token in an `HttpOnly` cookie.
- **CSRF** — cookie-authenticated state-changing requests are protected with a
  double-submit token: a readable `csrf_token` cookie echoed back in the
  `X-CSRF-Token` header. Requests with no auth cookie (public + server-to-server
  OAuth calls) are exempt.
- **OAuth 2.0 / OIDC** — `/oauth/authorize` drives the QR login scoped to a
  registered client; after approval a one-time authorization code is delivered
  to the client's exact-match `redirect_uri`, then exchanged at `/oauth/token`.
  Scopes are validated against `{openid, profile, email}`.
- **Rate limiting** — configurable per-IP limits via slowapi.
- **HTTPS enforcement** — when `ENVIRONMENT=production`, HTTP requests are
  redirected to HTTPS.

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

## API

| Method | Path                                  | Notes                                                       |
| ------ | ------------------------------------- | ----------------------------------------------------------- |
| POST   | `/api/auth/register`                  | `{full_name, email, device_name}` → enrolls device (cookie) |
| POST   | `/api/auth/lookup`                    | `{email}` — is this email registered?                       |
| GET    | `/api/auth/me`                        | Current user (JWT access cookie required)                   |
| POST   | `/api/qr/sessions`                    | Open a QR login session                                     |
| GET    | `/api/qr/sessions/{id}/qr`            | Fetch a freshly-rotated QR image                            |
| GET    | `/api/qr/sessions/{id}/status`        | Poll session lifecycle (browser long-polls)                 |
| POST   | `/api/qr/sessions/{id}/scan`          | Device validates the QR challenge (device cookie)           |
| POST   | `/api/qr/sessions/{id}/approve`       | Device approves the login (device cookie)                   |
| POST   | `/api/qr/sessions/{id}/deny`          | Device rejects the login (device cookie)                    |
| POST   | `/api/qr/sessions/{id}/token`         | Browser exchanges approved session for a JWT cookie         |
| GET    | `/api/devices`                        | List the user's trusted devices (JWT)                       |
| POST   | `/api/devices/enroll`                 | Provision an additional device (device cookie)              |
| DELETE | `/api/devices/{id}`                   | Revoke a device (JWT)                                       |
| GET    | `/api/devices/me`                     | User behind the presented device token                      |
| GET    | `/oauth/authorize`                    | OAuth 2.0 authorization endpoint                            |
| POST   | `/oauth/token`                        | Exchange authorization code for an access token             |
| GET    | `/oauth/userinfo`                     | OIDC userinfo (JWT access token)                            |
| GET    | `/oauth/.well-known/openid-configuration` | OIDC discovery document                                 |
| GET    | `/health`                             | Liveness check                                              |

## Tests

```bash
pytest
```

The suite uses a throwaway SQLite database and covers:

- Device enrollment (token delivered only as an HttpOnly cookie, never in the body)
- Email lookup and the authenticated `/api/auth/me`
- The full QR login lifecycle: create → scan → approve → token exchange
- QR challenge validation and single-use sessions
- CSRF enforcement on cookie-authenticated state changes
- Scope and redirect-URI validation
- The OAuth authorization-code flow end to end (including rejection of
  direct-login codes at the token endpoint)
- Security primitives: JWT round-trips, opaque-token hashing, QR challenge HMAC

## Production checklist

- Set `ENVIRONMENT=production`, a real `SECRET_KEY`, and `DATABASE_URL` pointing to Postgres.
- Terminate TLS in front of the app; set `COOKIE_SECURE=true`.
- Set `APP_BASE_URL` to the public HTTPS URL (used to build QR scan URLs and OIDC metadata).
- Restrict `ALLOWED_ORIGINS` to the actual frontend origin.
- Run `alembic upgrade head` on deploy.
- The default rate-limit backend is in-memory; for multi-process deployments point slowapi at Redis.

## Layout

```
backend/
  config.py        settings (pydantic-settings)
  database.py      engine, session, declarative Base
  models.py        User, RegisteredDevice, QRSession, OAuthClient
  schemas.py       request/response models
  security.py      JWT, opaque tokens, QR challenge signing, scope/redirect validation
  deps.py          current_user (JWT) + current_device (cookie/bearer) dependencies
  csrf.py          double-submit CSRF middleware
  rate_limit.py    slowapi limiter
  routes/
    auth.py        register / lookup
    qr.py          QR session lifecycle (create/scan/approve/deny/token)
    devices.py     list / enroll / revoke / me
    oauth.py       OAuth 2.0 / OIDC endpoints
    pages.py       HTML page routes
  main.py          app factory
frontend/
  login.html / login.js          QR login + enrollment
  register.html / register.js     device enrollment
  scan.html / scan.js             device-side scan & approve
  home.html / home.js             account + device management
  util.js                         shared fetch + CSRF helpers
alembic/           migrations
tests/             pytest suite
```
