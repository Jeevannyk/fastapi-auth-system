from datetime import datetime, timedelta, timezone

from backend.database import SessionLocal
from backend.models import User
from backend.security import hash_refresh_token


def _signup(client, email="alice@example.com", password="correct-horse-battery"):
    client.post(
        "/api/auth/signup",
        json={"full_name": "Alice", "email": email, "password": password},
    )


def _login(client, email="alice@example.com", password="correct-horse-battery"):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def _plant_reset_token(email: str, raw: str, expired: bool = False) -> None:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        user.reset_token_hash = hash_refresh_token(raw)
        delta = timedelta(seconds=-1) if expired else timedelta(hours=1)
        user.reset_token_expires = datetime.now(timezone.utc) + delta
        db.commit()
    finally:
        db.close()


def test_forgot_password_always_succeeds(client):
    r = client.post("/api/auth/forgot-password", json={"email": "nobody@nowhere.com"})
    assert r.status_code == 200


def test_forgot_password_returns_same_message_for_any_email(client):
    _signup(client)
    real = client.post("/api/auth/forgot-password", json={"email": "alice@example.com"})
    fake = client.post("/api/auth/forgot-password", json={"email": "ghost@example.com"})
    assert real.json()["message"] == fake.json()["message"]


def test_reset_password_valid_token(client):
    _signup(client)
    raw = "valid-reset-token-abc123"
    _plant_reset_token("alice@example.com", raw)

    r = client.post(
        "/api/auth/reset-password",
        json={"token": raw, "password": "brand-new-password-456"},
    )
    assert r.status_code == 200

    assert _login(client, password="correct-horse-battery").status_code == 401
    assert _login(client, password="brand-new-password-456").status_code == 200


def test_reset_password_invalid_token(client):
    r = client.post(
        "/api/auth/reset-password",
        json={"token": "bogus-token", "password": "newpassword123"},
    )
    assert r.status_code == 400


def test_reset_password_expired_token(client):
    _signup(client)
    raw = "expired-reset-token"
    _plant_reset_token("alice@example.com", raw, expired=True)

    r = client.post(
        "/api/auth/reset-password",
        json={"token": raw, "password": "newpassword123"},
    )
    assert r.status_code == 400


def test_reset_password_clears_lockout(client):
    _signup(client)

    for _ in range(5):
        _login(client, password="wrong")

    assert _login(client).status_code == 423

    raw = "unlock-reset-token"
    _plant_reset_token("alice@example.com", raw)
    client.post(
        "/api/auth/reset-password",
        json={"token": raw, "password": "unlocked-password-789"},
    )

    assert _login(client, password="unlocked-password-789").status_code == 200


def test_reset_token_is_single_use(client):
    _signup(client)
    raw = "single-use-reset-token"
    _plant_reset_token("alice@example.com", raw)

    client.post(
        "/api/auth/reset-password",
        json={"token": raw, "password": "first-new-password-123"},
    )

    r = client.post(
        "/api/auth/reset-password",
        json={"token": raw, "password": "second-new-password-456"},
    )
    assert r.status_code == 400
