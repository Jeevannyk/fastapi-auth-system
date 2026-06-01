from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from .database import get_db
from .models import RegisteredDevice, User
from .security import decode_access_token, hash_token

ACCESS_COOKIE = "access_token"
DEVICE_COOKIE = "device_token"


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """JWT access token from HttpOnly cookie → authenticated User."""
    token = request.cookies.get(ACCESS_COOKIE)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        user_id = decode_access_token(token)
    except ValueError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired")
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    return user


def current_device(
    request: Request,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> RegisteredDevice:
    """Resolve the calling device from its token → RegisteredDevice.

    The token is read from the HttpOnly ``device_token`` cookie (browser flow,
    not exposed to JavaScript) and falls back to an ``Authorization: Bearer``
    header for programmatic API clients.

    This dependency is read-only — it never writes ``last_used_at`` or commits.
    The "device was used" timestamp is recorded by the endpoint *after* the
    operation succeeds, so a failed call (e.g. a bad QR challenge) does not
    leave a usage trail and there is no half-applied transaction.
    """
    raw = request.cookies.get(DEVICE_COOKIE)
    if not raw and authorization and authorization.startswith("Bearer "):
        raw = authorization.split(" ", 1)[1]
    if not raw:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Device token required")

    token_hash = hash_token(raw)
    device = db.query(RegisteredDevice).filter(RegisteredDevice.token_hash == token_hash).first()
    if not device:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unrecognized device token")
    return device
