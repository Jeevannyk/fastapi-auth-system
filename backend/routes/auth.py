import logging

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from ..config import get_settings
from ..csrf import ENROLLED_COOKIE
from ..database import get_db
from ..deps import DEVICE_COOKIE
from ..models import RegisteredDevice, User
from ..schemas import RegisterRequest, RegisterResponse
from ..security import new_opaque_token

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])
settings = get_settings()

# Device tokens don't expire on their own — give the cookie a long life so the
# enrolled browser stays a trusted authenticator across sessions.
DEVICE_COOKIE_MAX_AGE = 60 * 60 * 24 * 365  # 1 year


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register(data: RegisterRequest, response: Response, db: Session = Depends(get_db)):
    """Enroll a new user and bind a device token to the registering browser.

    The raw device token is delivered only as an HttpOnly cookie — it is never
    returned in the response body or exposed to JavaScript, so an XSS payload
    cannot read it. A separate readable ``device_enrolled`` flag lets the UI
    know this browser is enrolled without revealing the token itself.
    """
    if db.query(User).filter(User.email == data.email.lower()).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    user = User(
        email=data.email.lower(),
        full_name=data.full_name.strip(),
    )
    db.add(user)
    db.flush()  # get user.id before committing

    raw_token, token_hash = new_opaque_token()
    device = RegisteredDevice(
        user_id=user.id,
        name=data.device_name.strip() or "My Device",
        token_hash=token_hash,
    )
    db.add(device)
    db.commit()

    response.set_cookie(
        DEVICE_COOKIE,
        raw_token,
        max_age=DEVICE_COOKIE_MAX_AGE,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        ENROLLED_COOKIE,
        "1",
        max_age=DEVICE_COOKIE_MAX_AGE,
        httponly=False,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )

    logger.info("New user registered: %s (device: %s)", user.email, device.name)
    return RegisterResponse(
        user_id=user.id,
        message="Account created. This browser is now a trusted authenticator.",
    )


class LookupRequest(BaseModel):
    email: EmailStr


@router.post("/lookup", status_code=status.HTTP_200_OK)
def lookup(data: LookupRequest, db: Session = Depends(get_db)):
    """Check whether an email is registered. Used by the sign-in form to give the user early feedback."""
    user = db.query(User).filter(User.email == data.email.lower()).first()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No account found")
    return {"found": True, "full_name": user.full_name}
