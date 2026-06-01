import time

import pytest

from backend.security import (
    OIDC_SCOPES,
    build_scan_url,
    create_access_token,
    decode_access_token,
    hash_token,
    new_opaque_token,
    redirect_uri_allowed,
    sign_qr_challenge,
    validate_scope,
    verify_qr_challenge,
)


def test_access_token_round_trip():
    token = create_access_token(42)
    assert decode_access_token(token) == 42


def test_access_token_rejects_garbage():
    with pytest.raises(ValueError):
        decode_access_token("not-a-token")


def test_opaque_token_hash_is_deterministic():
    raw, h = new_opaque_token()
    assert hash_token(raw) == h
    assert len(h) == 64  # sha256 hex


def test_qr_challenge_round_trip():
    ts = int(time.time())
    sig = sign_qr_challenge("sess-123", ts)
    assert verify_qr_challenge("sess-123", ts, sig)


def test_qr_challenge_rejects_tampered_sig():
    ts = int(time.time())
    sig = sign_qr_challenge("sess-123", ts)
    assert not verify_qr_challenge("sess-123", ts, sig[:-1] + ("a" if sig[-1] != "a" else "b"))


def test_qr_challenge_rejects_stale_timestamp():
    old = int(time.time()) - 120
    sig = sign_qr_challenge("sess-123", old)
    assert not verify_qr_challenge("sess-123", old, sig)


def test_build_scan_url_is_verifiable():
    url = build_scan_url("sess-abc")
    from urllib.parse import parse_qs, urlparse

    q = parse_qs(urlparse(url).query)
    assert q["s"][0] == "sess-abc"
    assert verify_qr_challenge("sess-abc", int(q["t"][0]), q["sig"][0])


def test_validate_scope_accepts_known():
    assert validate_scope("openid profile") == {"openid", "profile"}
    assert validate_scope("openid profile email") == OIDC_SCOPES


def test_validate_scope_rejects_unknown():
    with pytest.raises(ValueError):
        validate_scope("openid admin")


def test_validate_scope_rejects_empty():
    with pytest.raises(ValueError):
        validate_scope("   ")


def test_redirect_uri_allowed_exact_match():
    allowed = ["https://app.test/cb", "http://localhost:3000/cb"]
    assert redirect_uri_allowed("https://app.test/cb", allowed)
    assert not redirect_uri_allowed("https://evil.test/cb", allowed)


def test_redirect_uri_allowed_rejects_bad_scheme():
    allowed = ["javascript:alert(1)", "data:text/html,x"]
    assert not redirect_uri_allowed("javascript:alert(1)", allowed)
    assert not redirect_uri_allowed("data:text/html,x", allowed)
