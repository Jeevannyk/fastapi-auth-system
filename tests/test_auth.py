def signup(client, email="alice@example.com", password="correct-horse-battery"):
    return client.post(
        "/api/auth/signup",
        json={"full_name": "Alice", "email": email, "password": password},
    )


def test_signup_creates_account(client):
    r = signup(client)
    assert r.status_code == 201
    body = r.json()
    assert body["email_verification_required"] is False  # EMAIL_ENABLED=false


def test_signup_rejects_duplicate_email(client):
    signup(client)
    r = signup(client)
    assert r.status_code == 409


def test_signup_validates_password_length(client):
    r = client.post(
        "/api/auth/signup",
        json={"full_name": "Alice", "email": "a@b.com", "password": "short"},
    )
    assert r.status_code == 422


def test_login_sets_cookies(client):
    signup(client)
    r = client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "correct-horse-battery"},
    )
    assert r.status_code == 200
    assert r.json()["requires_2fa"] is False
    assert "access_token" in r.cookies
    assert "refresh_token" in r.cookies


def test_login_wrong_password(client):
    signup(client)
    r = client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "wrong"},
    )
    assert r.status_code == 401


def test_me_requires_auth(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 401


def test_me_returns_user(client):
    signup(client)
    client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "correct-horse-battery"},
    )
    r = client.get("/api/auth/me")
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == "alice@example.com"
    assert body["totp_enabled"] is False


def test_logout_clears_cookies(client):
    signup(client)
    client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "correct-horse-battery"},
    )
    r = client.post("/api/auth/logout")
    assert r.status_code == 200
    me = client.get("/api/auth/me")
    assert me.status_code == 401


def test_refresh_rotates_tokens(client):
    signup(client)
    login = client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "correct-horse-battery"},
    )
    old_refresh = login.cookies.get("refresh_token")
    r = client.post("/api/auth/refresh")
    assert r.status_code == 200
    assert client.cookies.get("refresh_token") != old_refresh

    # Old refresh token must no longer work.
    client.cookies.set("refresh_token", old_refresh)
    bad = client.post("/api/auth/refresh")
    assert bad.status_code == 401


def test_account_lockout_after_failed_attempts(client):
    signup(client)
    for _ in range(5):
        client.post(
            "/api/auth/login",
            json={"email": "alice@example.com", "password": "wrong"},
        )
    r = client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "correct-horse-battery"},
    )
    assert r.status_code == 423
