from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


# ── User ─────────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=120)
    device_name: str = Field("My Device", max_length=120)


class RegisterResponse(BaseModel):
    user_id: int
    message: str


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Devices ───────────────────────────────────────────────────────────────────

class DeviceResponse(BaseModel):
    id: int
    name: str
    last_used_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── QR Sessions ───────────────────────────────────────────────────────────────

class CreateSessionRequest(BaseModel):
    client_id: str | None = None
    redirect_uri: str | None = None
    scope: str = "openid profile email"


class QRSessionResponse(BaseModel):
    session_id: str
    qr_data_url: str
    qr_ttl: int        # seconds until QR image should be refreshed
    session_ttl: int   # total seconds the session stays alive


class FreshQRResponse(BaseModel):
    qr_data_url: str
    ttl: int


class SessionStatusResponse(BaseModel):
    status: str                   # pending | scanned | approved | consumed | expired
    user: UserResponse | None = None
    redirect_url: str | None = None


class ScanRequest(BaseModel):
    timestamp: int
    sig: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int


# ── OAuth ─────────────────────────────────────────────────────────────────────

class OAuthTokenRequest(BaseModel):
    grant_type: str
    code: str
    client_id: str
    client_secret: str
    redirect_uri: str


class OAuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    scope: str


# ── Generic ───────────────────────────────────────────────────────────────────

class MessageResponse(BaseModel):
    message: str
