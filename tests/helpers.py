"""Shared test helpers for the QR-auth flow."""

import time

from backend.security import hash_token, sign_qr_challenge


def csrf(client) -> dict:
    """Header carrying the double-submit CSRF token from the client's cookie jar."""
    token = client.cookies.get("csrf_token")
    return {"X-CSRF-Token": token} if token else {}


def register(client, email="alice@example.com", full_name="Alice", device_name="My Device"):
    """Register a user; the device + csrf cookies land in the client's jar.

    Sends the CSRF header so a repeat call from an already-enrolled client (one
    that now carries the device cookie) still reaches the route logic.
    """
    return client.post(
        "/api/auth/register",
        json={"full_name": full_name, "email": email, "device_name": device_name},
        headers=csrf(client),
    )


def lookup(client, email="alice@example.com"):
    return client.post("/api/auth/lookup", json={"email": email}, headers=csrf(client))


def create_session(client, **body):
    return client.post("/api/qr/sessions", json=body, headers=csrf(client))


def scan(client, session_id):
    ts = int(time.time())
    sig = sign_qr_challenge(session_id, ts)
    return client.post(
        f"/api/qr/sessions/{session_id}/scan",
        json={"timestamp": ts, "sig": sig},
        headers=csrf(client),
    )


def approve(client, session_id):
    return client.post(f"/api/qr/sessions/{session_id}/approve", headers=csrf(client))


def make_oauth_client(client_id="acme", secret="s3cret-value", redirect="https://acme.test/callback"):
    """Insert an active OAuth client directly into the DB; return its secret."""
    from backend.database import SessionLocal
    from backend.models import OAuthClient

    db = SessionLocal()
    try:
        db.add(OAuthClient(
            client_id=client_id,
            client_secret_hash=hash_token(secret),
            name="Acme",
            redirect_uris=redirect,
        ))
        db.commit()
    finally:
        db.close()
    return secret
