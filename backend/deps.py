from datetime import datetime, timezone

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from .database import get_db
from .models import RegisteredDevice, User
from .security import decode_access_token, hash_token

ACCESS_COOKIE = "access_token"


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


def device_from_bearer(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> RegisteredDevice:
    """Bearer device token from Authorization header → RegisteredDevice (with user loaded)."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Device token required")
    raw = authorization.split(" ", 1)[1]
    token_hash = hash_token(raw)
    device = db.query(RegisteredDevice).filter(RegisteredDevice.token_hash == token_hash).first()
    if not device:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unrecognized device token")
    device.last_used_at = datetime.now(timezone.utc)
    db.commit()
    return device
