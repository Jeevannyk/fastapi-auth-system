import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import RegisteredDevice, User
from pydantic import BaseModel, EmailStr

from ..schemas import MessageResponse, RegisterRequest, RegisterResponse
from ..security import new_opaque_token

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    """Enroll a new user and issue a device token for the registering browser."""
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

    logger.info("New user registered: %s (device: %s)", user.email, device.name)
    return RegisterResponse(
        user_id=user.id,
        device_token=raw_token,
        message="Account created. Save the device_token — it is your authenticator.",
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


@router.get("/me", tags=["users"])
def me(db: Session = Depends(get_db)):
    """Placeholder — real /me is behind the access-token cookie (see deps.current_user)."""
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
