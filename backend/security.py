import base64
import hashlib
import hmac
import io
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Literal
from urllib.parse import urlparse

import qrcode
import qrcode.image.pure
from jose import JWTError, jwt

from .config import get_settings

settings = get_settings()
ALGORITHM = "HS256"

TokenType = Literal["access"]

# Scopes this identity provider understands. Any requested scope outside this
# set is rejected before a session is ever created.
OIDC_SCOPES = {"openid", "profile", "email"}


def validate_scope(scope: str) -> set[str]:
    """Parse a space-delimited scope string and ensure every scope is known.

    Returns the parsed scope set. Raises ValueError if any scope is unknown or
    the string is empty.
    """
    requested = {s for s in scope.split() if s}
    if not requested:
        raise ValueError("scope must not be empty")
    unknown = requested - OIDC_SCOPES
    if unknown:
        raise ValueError(f"unsupported scope(s): {', '.join(sorted(unknown))}")
    return requested


def redirect_uri_allowed(uri: str, allowed: list[str]) -> bool:
    """Validate a redirect URI against an exact-match allow-list.

    Beyond exact matching we also require an http/https scheme and a network
    location, which blocks ``javascript:``/``data:`` and other open-redirect
    vectors even if a malformed entry slips into the allow-list.
    """
    if uri not in allowed:
        return False
    parsed = urlparse(uri)
    if parsed.scheme not in ("http", "https"):
        return False
    if not parsed.netloc:
        return False
    return True


# ── JWT access tokens ────────────────────────────────────────────────────────

def create_access_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.access_token_minutes)).timestamp()),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> int:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except JWTError as e:
        raise ValueError("invalid token") from e
    if payload.get("type") != "access":
        raise ValueError("wrong token type")
    sub = payload.get("sub")
    if not sub:
        raise ValueError("missing subject")
    return int(sub)


# ── Opaque token helpers (device tokens, auth codes) ────────────────────────

def new_opaque_token() -> tuple[str, str]:
    """Return (raw_token, sha256_hex). Store only the hash."""
    raw = secrets.token_urlsafe(48)
    return raw, hashlib.sha256(raw.encode()).hexdigest()


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


# ── QR challenge signing ─────────────────────────────────────────────────────

def sign_qr_challenge(session_id: str, timestamp: int) -> str:
    """HMAC-SHA256 of 'session_id:timestamp' keyed with SECRET_KEY.

    Returns a 32-char base64url string (truncated for URL compactness).
    """
    msg = f"{session_id}:{timestamp}".encode()
    raw = hmac.new(settings.secret_key.encode(), msg, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")[:32]


def verify_qr_challenge(session_id: str, timestamp: int, sig: str, max_age: int = 35) -> bool:
    """Return True iff sig is valid and timestamp is within max_age seconds."""
    if abs(time.time() - timestamp) > max_age:
        return False
    expected = sign_qr_challenge(session_id, timestamp)
    return hmac.compare_digest(expected, sig)


def build_scan_url(session_id: str) -> str:
    ts = int(time.time())
    sig = sign_qr_challenge(session_id, ts)
    return f"{settings.app_base_url}/scan?s={session_id}&t={ts}&sig={sig}"


# ── QR image generation ──────────────────────────────────────────────────────

def generate_qr_data_url(content: str) -> str:
    qr = qrcode.QRCode(box_size=6, border=2)
    qr.add_data(content)
    qr.make(fit=True)
    img = qr.make_image(image_factory=qrcode.image.pure.PyPNGImage)
    buf = io.BytesIO()
    img.save(buf)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"
