from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import current_user
from ..models import User
from ..schemas import MessageResponse, TOTPSetupResponse, TOTPVerifyRequest
from ..security import generate_qr_data_url, generate_totp_secret, totp_provisioning_uri, verify_totp

router = APIRouter(prefix="/api/2fa", tags=["2fa"])


@router.post("/setup", response_model=TOTPSetupResponse)
def setup_totp(user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.totp_enabled:
        raise HTTPException(status.HTTP_409_CONFLICT, "2FA already enabled")

    secret = generate_totp_secret()
    user.totp_secret = secret
    db.commit()
    otpauth_url = totp_provisioning_uri(secret, user.email)
    return TOTPSetupResponse(
        secret=secret,
        otpauth_url=otpauth_url,
        qr_code_data_url=generate_qr_data_url(otpauth_url),
    )


@router.post("/enable", response_model=MessageResponse)
def enable_totp(
    data: TOTPVerifyRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    if user.totp_enabled:
        raise HTTPException(status.HTTP_409_CONFLICT, "2FA already enabled")
    if not user.totp_secret:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Run /setup first")
    if not verify_totp(user.totp_secret, data.code):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid code")

    user.totp_enabled = True
    db.commit()
    return MessageResponse(message="Two-factor authentication enabled")


@router.post("/disable", response_model=MessageResponse)
def disable_totp(
    data: TOTPVerifyRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    if not user.totp_enabled or not user.totp_secret:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "2FA not enabled")
    if not verify_totp(user.totp_secret, data.code):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid code")

    user.totp_enabled = False
    user.totp_secret = None
    db.commit()
    return MessageResponse(message="Two-factor authentication disabled")
