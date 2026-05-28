from datetime import datetime, timedelta, timezone

from backend.database import SessionLocal
from backend.models import User
from backend.security import hash_refresh_token


def _signup(client, email="alice@example.com", password="correct-horse-battery"):
    return client.post(
        "/api/auth/signup",
        json={"full_name": "Alice", "email": email, "password": password},
    )


def _login(client, email="alice@example.com", password="correct-horse-battery"):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def _set_unverified(email: str, token_raw: str) -> None:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        user.email_verified = False
        user.verification_token_hash = hash_refresh_token(token_raw)
        user.verification_token_expires = datetime.now(timezone.utc) + timedelta(hours=24)
        db.commit()
    finally:
        db.close()


def test_signup_auto_verifies_with_email_disabled(client):
    r = _signup(client)
    assert r.status_code == 201
    assert r.json()["email_verification_required"] is False


def test_auto_verified_user_can_login_immediately(client):
    _signup(client)
    r = _login(client)
    assert r.status_code == 200


def test_unverified_user_cannot_login(client):
    _signup(client)
    _set_unverified("alice@example.com", "some-raw-token-abc")
    r = _login(client)
    assert r.status_code == 403


def test_verify_email_valid_token(client):
    _signup(client)
    raw = "valid-test-token-for-verify-email"
    _set_unverified("alice@example.com", raw)

    r = client.get(f"/api/auth/verify-email?token={raw}")
    assert r.status_code == 200

    login = _login(client)
    assert login.status_code == 200


def test_verify_email_invalid_token(client):
    r = client.get("/api/auth/verify-email?token=bogus-token-xyz")
    assert r.status_code == 400


def test_verify_email_expired_token(client):
    _signup(client)
    raw = "expired-token-abc"
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "alice@example.com").first()
        user.email_verified = False
        user.verification_token_hash = hash_refresh_token(raw)
        user.verification_token_expires = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
    finally:
        db.close()

    r = client.get(f"/api/auth/verify-email?token={raw}")
    assert r.status_code == 400


def test_verify_email_token_consumed_after_use(client):
    _signup(client)
    raw = "single-use-token-abc"
    _set_unverified("alice@example.com", raw)

    client.get(f"/api/auth/verify-email?token={raw}")
    r = client.get(f"/api/auth/verify-email?token={raw}")
    assert r.status_code == 400
