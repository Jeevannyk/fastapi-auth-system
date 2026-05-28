import pyotp


def _signup_and_login(client):
    client.post(
        "/api/auth/signup",
        json={"full_name": "Alice", "email": "alice@example.com", "password": "correct-horse-battery"},
    )
    client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "correct-horse-battery"},
    )


def test_totp_setup_and_enable(client):
    _signup_and_login(client)
    setup = client.post("/api/2fa/setup")
    assert setup.status_code == 200
    secret = setup.json()["secret"]
    assert setup.json()["otpauth_url"].startswith("otpauth://totp/")

    code = pyotp.TOTP(secret).now()
    enable = client.post("/api/2fa/enable", json={"code": code})
    assert enable.status_code == 200

    me = client.get("/api/auth/me")
    assert me.json()["totp_enabled"] is True


def test_enable_rejects_bad_code(client):
    _signup_and_login(client)
    client.post("/api/2fa/setup")
    r = client.post("/api/2fa/enable", json={"code": "000000"})
    assert r.status_code == 401


def test_login_requires_2fa_when_enabled(client):
    _signup_and_login(client)
    setup = client.post("/api/2fa/setup")
    secret = setup.json()["secret"]
    client.post("/api/2fa/enable", json={"code": pyotp.TOTP(secret).now()})
    client.post("/api/auth/logout")

    login = client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "correct-horse-battery"},
    )
    assert login.status_code == 200
    body = login.json()
    assert body["requires_2fa"] is True
    user_id = body["user_id"]

    # Access cookie must NOT be set yet.
    assert "access_token" not in login.cookies

    verify = client.post(
        "/api/auth/login/2fa",
        json={"user_id": user_id, "code": pyotp.TOTP(secret).now()},
    )
    assert verify.status_code == 200
    assert client.get("/api/auth/me").status_code == 200
