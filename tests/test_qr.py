from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from backend.main import app
from tests.helpers import approve, create_session, csrf, make_oauth_client, register, scan


# ── Direct-login QR lifecycle ────────────────────────────────────────────────

def test_direct_login_full_flow(client):
    register(client)

    r = create_session(client)
    assert r.status_code == 200
    sid = r.json()["session_id"]

    assert scan(client, sid).status_code == 200
    assert client.get(f"/api/qr/sessions/{sid}/status").json()["status"] == "scanned"

    assert approve(client, sid).status_code == 200
    status = client.get(f"/api/qr/sessions/{sid}/status").json()
    assert status["status"] == "approved"
    assert status["user"]["email"] == "alice@example.com"
    # Direct login (no OAuth redirect_uri) → no redirect_url
    assert status["redirect_url"] is None

    tok = client.post(f"/api/qr/sessions/{sid}/token", headers=csrf(client))
    assert tok.status_code == 200
    assert client.cookies.get("access_token")

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "alice@example.com"


def test_session_cannot_be_reused(client):
    register(client)
    sid = create_session(client).json()["session_id"]
    scan(client, sid)
    approve(client, sid)
    assert client.post(f"/api/qr/sessions/{sid}/token", headers=csrf(client)).status_code == 200
    # Second exchange must fail — session is consumed.
    again = client.post(f"/api/qr/sessions/{sid}/token", headers=csrf(client))
    assert again.status_code == 400


def test_scan_requires_valid_challenge(client):
    register(client)
    sid = create_session(client).json()["session_id"]
    bad = client.post(
        f"/api/qr/sessions/{sid}/scan",
        json={"timestamp": 0, "sig": "deadbeef"},
        headers=csrf(client),
    )
    assert bad.status_code == 400
    # Failed scan must not advance the session.
    assert client.get(f"/api/qr/sessions/{sid}/status").json()["status"] == "pending"


def test_approve_requires_scanned_state(client):
    register(client)
    sid = create_session(client).json()["session_id"]
    # Approving a pending (un-scanned) session is a conflict.
    assert approve(client, sid).status_code == 409


# ── Scope validation (#17) ────────────────────────────────────────────────────

def test_create_session_rejects_unknown_scope(client):
    register(client)
    r = create_session(client, scope="openid admin")
    assert r.status_code == 400


# ── CSRF protection (#6) ──────────────────────────────────────────────────────

def test_state_change_without_csrf_is_rejected(client):
    register(client)  # client now carries the device cookie
    sid = create_session(client).json()["session_id"]
    # POST /scan carrying the device cookie but no CSRF header → 403.
    r = client.post(f"/api/qr/sessions/{sid}/scan", json={"timestamp": 0, "sig": "x"})
    assert r.status_code == 403


def test_scan_without_device_cookie_is_unauthorized(client):
    # Fresh client (never registered) → no device cookie.
    sid_owner = TestClient(app)
    register(sid_owner)
    sid = create_session(sid_owner).json()["session_id"]

    bare = TestClient(app)
    # No device cookie present → CSRF is skipped entirely, so the request
    # reaches device auth, which fails.
    r = bare.post(
        f"/api/qr/sessions/{sid}/scan",
        json={"timestamp": 0, "sig": "x"},
    )
    assert r.status_code == 401


# ── OAuth authorization-code flow (#2, #4, #7) ────────────────────────────────

def test_oauth_authorize_redirects_to_login(client):
    make_oauth_client()
    r = client.get(
        "/oauth/authorize",
        params={"client_id": "acme", "redirect_uri": "https://acme.test/callback"},
        follow_redirects=False,
    )
    assert r.status_code == 302
    assert r.headers["location"].startswith("/login?")
    assert "client_id=acme" in r.headers["location"]


def test_oauth_authorize_rejects_bad_redirect(client):
    make_oauth_client()
    r = client.get(
        "/oauth/authorize",
        params={"client_id": "acme", "redirect_uri": "https://evil.test/callback"},
        follow_redirects=False,
    )
    assert r.status_code == 400


def test_oauth_authorize_rejects_unknown_scope(client):
    make_oauth_client()
    r = client.get(
        "/oauth/authorize",
        params={
            "client_id": "acme",
            "redirect_uri": "https://acme.test/callback",
            "scope": "openid wat",
        },
        follow_redirects=False,
    )
    assert r.status_code == 400


def test_oauth_code_exchange(client):
    secret = make_oauth_client()
    register(client)

    redirect_uri = "https://acme.test/callback"
    sid = create_session(client, client_id="acme", redirect_uri=redirect_uri).json()["session_id"]
    scan(client, sid)
    approve(client, sid)

    status = client.get(f"/api/qr/sessions/{sid}/status").json()
    assert status["redirect_url"], "OAuth flow must deliver a redirect_url with the code"
    code = parse_qs(urlparse(status["redirect_url"]).query)["code"][0]

    # The raw code is delivered to the browser exactly once; a second poll has none.
    second = client.get(f"/api/qr/sessions/{sid}/status").json()
    assert second["redirect_url"] is None

    # Token exchange is server-to-server (no cookies) — use a bare client.
    oauth_client = TestClient(app)
    r = oauth_client.post(
        "/oauth/token",
        params={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": "acme",
            "client_secret": secret,
            "redirect_uri": redirect_uri,
        },
    )
    assert r.status_code == 200
    assert r.json()["access_token"]


def test_oauth_token_rejects_direct_login_code(client):
    # A direct-login session (no client_id) generates an auth code too; it must
    # not be redeemable at the OAuth token endpoint (#2 None-comparison guard).
    secret = make_oauth_client()
    register(client)
    sid = create_session(client).json()["session_id"]  # no client_id
    scan(client, sid)
    approve(client, sid)

    # Pull the raw code straight from the DB (direct-login never exposes it).
    from backend.database import SessionLocal
    from backend.models import QRSession

    db = SessionLocal()
    try:
        code = db.query(QRSession).filter(QRSession.session_id == sid).first().auth_code
    finally:
        db.close()

    oauth_client = TestClient(app)
    r = oauth_client.post(
        "/oauth/token",
        params={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": "acme",
            "client_secret": secret,
            "redirect_uri": "https://acme.test/callback",
        },
    )
    assert r.status_code == 400
