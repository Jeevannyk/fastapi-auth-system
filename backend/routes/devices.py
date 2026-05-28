import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import current_user, device_from_bearer
from ..models import RegisteredDevice, User
from ..schemas import DeviceResponse, MessageResponse, RegisterRequest, UserResponse
from ..security import new_opaque_token

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/devices", tags=["devices"])


@router.get("", response_model=list[DeviceResponse])
def list_devices(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """List all trusted devices registered to the authenticated user."""
    return user.devices


@router.post("/enroll", response_model=dict)
def enroll_additional_device(
    device_name: str = "New Device",
    device: RegisteredDevice = Depends(device_from_bearer),
    db: Session = Depends(get_db),
):
    """Add a second trusted device. Requires an existing device token to authorize."""
    raw_token, token_hash = new_opaque_token()
    new_device = RegisteredDevice(
        user_id=device.user_id,
        name=device_name.strip() or "New Device",
        token_hash=token_hash,
    )
    db.add(new_device)
    db.commit()
    logger.info("New device enrolled for user %s: %s", device.user_id, device_name)
    return {"device_token": raw_token, "device_id": new_device.id, "name": new_device.name}


@router.delete("/{device_id}", response_model=MessageResponse)
def revoke_device(
    device_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Revoke a trusted device. Requires JWT auth (you must be logged in)."""
    device = db.query(RegisteredDevice).filter(
        RegisteredDevice.id == device_id,
        RegisteredDevice.user_id == user.id,
    ).first()
    if not device:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Device not found")
    db.delete(device)
    db.commit()
    return MessageResponse(message=f"Device '{device.name}' revoked")


@router.get("/me", response_model=UserResponse)
def whoami(device: RegisteredDevice = Depends(device_from_bearer), db: Session = Depends(get_db)):
    """Return the user associated with the presented device token."""
    return UserResponse.model_validate(device.user)
