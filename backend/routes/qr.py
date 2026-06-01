import logging
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..deps import ACCESS_COOKIE, current_device
from ..models import OAuthClient, QRSession, RegisteredDevice
from ..schemas import (
    CreateSessionRequest,
    FreshQRResponse,
    MessageResponse,
    QRSessionResponse,
    ScanRequest,
    SessionStatusResponse,
    TokenResponse,
    UserResponse,
)
from ..security import (
    build_scan_url,
    create_access_token,
    generate_qr_data_url,
    new_opaque_token,
    redirect_uri_allowed,
    validate_scope,
    verify_qr_challenge,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/qr", tags=["qr-auth"])
settings = get_settings()

QR_TTL = 30          # seconds before the QR image should be refreshed
SESSION_TTL = 300    # seconds the whole session stays alive


def _get_session(session_id: str, db: Session) -> QRSession:
    """Load a session and lazily expire it.

    Expiry is evaluated exactly once per lookup so a session's status cannot
    flip underneath the caller mid-request. Callers re-read ``session.status``
    after this returns and act on that single, settled value.
    """
    s = db.query(QRSession).filter(QRSession.session_id == session_id).first()
    if not s:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    if s.status == "pending" and s.expires_at < datetime.now(timezone.utc):
        s.status = "expired"
        db.commit()
    return s


# ── Create a new QR login session ───────────────────────────────────────────

@router.post("/sessions", response_model=QRSessionResponse)
def create_session(data: CreateSessionRequest, db: Session = Depends(get_db)):
    """Generate a new QR session. Call this when the login page loads."""
    try:
        validate_scope(data.scope)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))

    if data.client_id:
        client = db.query(OAuthClient).filter(
            OAuthClient.client_id == data.client_id,
            OAuthClient.is_active == True,
        ).first()
        if not client:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown OAuth client")
        allowed = [u.strip() for u in client.redirect_uris.split(",")]
        if data.redirect_uri and not redirect_uri_allowed(data.redirect_uri, allowed):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "redirect_uri not allowed")

    session_id = secrets.token_urlsafe(32)
    session = QRSession(
        session_id=session_id,
        client_id=data.client_id,
        redirect_uri=data.redirect_uri,
        scope=data.scope,
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=SESSION_TTL),
    )
    db.add(session)
    db.commit()

    scan_url = build_scan_url(session_id)
    return QRSessionResponse(
        session_id=session_id,
        qr_data_url=generate_qr_data_url(scan_url),
        qr_ttl=QR_TTL,
        session_ttl=SESSION_TTL,
    )


# ── Refresh the QR image (rotation every QR_TTL seconds) ────────────────────

@router.get("/sessions/{session_id}/qr", response_model=FreshQRResponse)
def refresh_qr(session_id: str, db: Session = Depends(get_db)):
    """Return a fresh QR code with a new signed challenge. Call every ~25 s."""
    session = _get_session(session_id, db)
    if session.status != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, f"Session is {session.status}")
    scan_url = build_scan_url(session_id)
    return FreshQRResponse(qr_data_url=generate_qr_data_url(scan_url), ttl=QR_TTL)


# ── Poll session status (browser long-polls this) ───────────────────────────

@router.get("/sessions/{session_id}/status", response_model=SessionStatusResponse)
def get_status(session_id: str, db: Session = Depends(get_db)):
    session = _get_session(session_id, db)

    user_data = None
    redirect_url = None

    if session.status == "approved" and session.user:
        user_data = UserResponse.model_validate(session.user)
        # For an OAuth flow, hand the raw one-time code to the browser exactly
        # once so it can redirect the user agent back to the client. We deliver
        # the *raw* code (not the stored hash) and clear it immediately, so it
        # is never readable again and a DB leak exposes only the hash.
        if session.redirect_uri and session.auth_code:
            params = {"code": session.auth_code, "scope": session.scope}
            sep = "&" if "?" in session.redirect_uri else "?"
            redirect_url = f"{session.redirect_uri}{sep}{urlencode(params)}"
            session.auth_code = None
            db.commit()

    return SessionStatusResponse(
        status=session.status,
        user=user_data,
        redirect_url=redirect_url,
    )


# ── Scan: mobile device reads the QR and identifies the user ─────────────────

@router.post("/sessions/{session_id}/scan", response_model=MessageResponse)
def scan(
    session_id: str,
    data: ScanRequest,
    device: RegisteredDevice = Depends(current_device),
    db: Session = Depends(get_db),
):
    """Called by the mobile device immediately after scanning the QR code.

    Validates the cryptographic challenge embedded in the QR, then marks
    the session as 'scanned' so the login page can show a confirmation prompt.
    """
    if not verify_qr_challenge(session_id, data.timestamp, data.sig):
        logger.warning(
            "QR challenge failed for session %s (device %s)",
            session_id[:8], device.id,
        )
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "QR challenge invalid or expired")

    session = _get_session(session_id, db)
    if session.status != "pending":
        logger.warning(
            "Scan rejected: session %s is %s (device %s)",
            session_id[:8], session.status, device.id,
        )
        raise HTTPException(status.HTTP_409_CONFLICT, f"Session is already {session.status}")

    session.status = "scanned"
    session.user_id = device.user_id
    device.last_used_at = datetime.now(timezone.utc)
    db.commit()
    logger.info("QR session %s scanned by user %s", session_id[:8], device.user_id)
    return MessageResponse(message="Scanned — waiting for your approval")


# ── Approve: mobile device confirms the login ────────────────────────────────

@router.post("/sessions/{session_id}/approve", response_model=MessageResponse)
def approve(
    session_id: str,
    device: RegisteredDevice = Depends(current_device),
    db: Session = Depends(get_db),
):
    """User taps 'Approve' on the mobile scan page.

    Issues a one-time auth code for OAuth flows, then marks the session
    'approved' so the browser poll receives the signal.
    """
    session = _get_session(session_id, db)

    if session.status != "scanned":
        logger.warning(
            "Approve rejected: session %s is %s, expected scanned (device %s)",
            session_id[:8], session.status, device.id,
        )
        raise HTTPException(status.HTTP_409_CONFLICT, f"Session is {session.status}, expected scanned")
    if session.user_id != device.user_id:
        logger.warning(
            "Approve rejected: device user %s does not match session %s user %s",
            device.user_id, session_id[:8], session.user_id,
        )
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Device does not match session user")

    # Issue a one-time code for OAuth clients
    raw_code, code_hash = new_opaque_token()
    session.auth_code = raw_code
    session.auth_code_hash = code_hash
    session.auth_code_expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
    session.status = "approved"
    device.last_used_at = datetime.now(timezone.utc)
    db.commit()

    logger.info("QR session %s approved by user %s", session_id[:8], device.user_id)
    return MessageResponse(message="Login approved")


# ── Deny: mobile device rejects the login attempt ───────────────────────────

@router.post("/sessions/{session_id}/deny", response_model=MessageResponse)
def deny(
    session_id: str,
    device: RegisteredDevice = Depends(current_device),
    db: Session = Depends(get_db),
):
    session = _get_session(session_id, db)
    if session.status not in ("pending", "scanned"):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Session is {session.status}")
    if session.user_id and session.user_id != device.user_id:
        logger.warning(
            "Deny rejected: device user %s does not match session %s user %s",
            device.user_id, session_id[:8], session.user_id,
        )
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Device does not match session user")
    session.status = "expired"
    db.commit()
    logger.info("QR session %s denied by user %s", session_id[:8], device.user_id)
    return MessageResponse(message="Login denied")


# ── Exchange: browser swaps approved session for a JWT access token ──────────

@router.post("/sessions/{session_id}/token", response_model=TokenResponse)
def exchange_token(session_id: str, response: Response, db: Session = Depends(get_db)):
    """Browser calls this once the session status is 'approved'.

    Issues a JWT access token in an HttpOnly cookie and marks the session
    'consumed' so it cannot be reused.
    """
    session = _get_session(session_id, db)
    if session.status != "approved":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Session is {session.status}, expected approved")
    if not session.user_id or not session.user:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Session has no user")

    session.status = "consumed"
    db.commit()

    access = create_access_token(session.user_id)
    response.set_cookie(
        ACCESS_COOKIE,
        access,
        max_age=settings.access_token_minutes * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    return TokenResponse(
        access_token=access,
        expires_in=settings.access_token_minutes * 60,
    )
