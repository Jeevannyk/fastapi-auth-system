from tests.helpers import lookup, register


def test_register_creates_account_and_sets_device_cookie(client):
    r = register(client)
    assert r.status_code == 201
    body = r.json()
    assert body["user_id"] > 0
    # The raw device token must NOT be in the response body — it is delivered
    # only as an HttpOnly cookie, never exposed to JavaScript.
    assert "device_token" not in body
    assert client.cookies.get("device_token")          # HttpOnly token cookie
    assert client.cookies.get("device_enrolled") == "1"  # readable enrollment flag


def test_register_rejects_duplicate_email(client):
    register(client)
    r = register(client)
    assert r.status_code == 409


def test_register_validates_full_name_length(client):
    r = client.post(
        "/api/auth/register",
        json={"full_name": "A", "email": "a@b.com", "device_name": "Dev"},
    )
    assert r.status_code == 422


def test_lookup_found(client):
    register(client)
    r = lookup(client)
    assert r.status_code == 200
    assert r.json() == {"found": True, "full_name": "Alice"}


def test_lookup_not_found(client):
    r = lookup(client, email="nobody@example.com")
    assert r.status_code == 404


def test_me_requires_auth(client):
    # The real /api/auth/me (cookie-authenticated) must 401 without a session,
    # not be shadowed by the old placeholder route that was removed.
    r = client.get("/api/auth/me")
    assert r.status_code == 401
