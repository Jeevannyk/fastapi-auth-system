from backend.security import (
    create_access_token,
    decode_token,
    hash_password,
    hash_refresh_token,
    new_refresh_token,
    verify_password,
)


def test_password_round_trip():
    h = hash_password("hunter2hunter2")
    assert verify_password("hunter2hunter2", h)
    assert not verify_password("hunter3hunter3", h)


def test_access_token_round_trip():
    token = create_access_token(42)
    assert decode_token(token, "access") == 42


def test_token_type_is_enforced():
    token = create_access_token(42)
    try:
        decode_token(token, "pending_2fa")
    except ValueError:
        return
    raise AssertionError("expected ValueError on wrong token type")


def test_refresh_hash_deterministic():
    raw, h = new_refresh_token()
    assert hash_refresh_token(raw) == h
