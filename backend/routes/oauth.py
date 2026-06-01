"""Minimal OAuth 2.0 / OpenID Connect layer.

Allows third-party websites to use Cipher as their identity provider.

Authorization Code Flow:
  1. Client redirects user to GET /oauth/authorize?client_id=...&redirect_uri=...&scope=...
  2. Cipher shows QR login page — user scans with trusted device.
  3. After approval, Cipher redirects to redirect_uri?code=xxx
  4. Client exchanges code for access token via POST /oauth/token.
  5. Client fetches user profile from GET /oauth/userinfo.
"""

import logging
from datetime import datetime, timezone
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..deps import current_user
from ..models import OAuthClient, QRSession, User
from ..schemas import MessageResponse, OAuthTokenResponse, UserResponse
from ..security import (
    OIDC_SCOPES,
    create_access_token,
    hash_token,
    redirect_uri_allowed,
    validate_scope,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/oauth", tags=["oauth"])
settings = get_settings()


# ── OIDC Discovery ───────────────────────────────────────────────────────────

@router.get("/.well-known/openid-configuration", include_in_schema=False)
def oidc_discovery():
    base = settings.app_base_url
    return {
        "issuer": base,
        "authorization_endpoint": f"{base}/oauth/authorize",
        "token_endpoint": f"{base}/oauth/token",
        "userinfo_endpoint": f"{base}/oauth/userinfo",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code"],
        "scopes_supported": list(OIDC_SCOPES),
        "token_endpoint_auth_methods_supported": ["client_secret_post"],
        "subject_types_supported": ["public"],
        "id_token_signing_alg_values_supported": ["HS256"],
    }


# ── Authorization endpoint ───────────────────────────────────────────────────

@router.get("/authorize")
def authorize(
    client_id: str = Query(...),
    redirect_uri: str = Query(...),
    scope: str = Query("openid profile email"),
    state: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """Redirect the user to the QR login page, scoped to this OAuth client."""
    client = db.query(OAuthClient).filter(
        OAuthClient.client_id == client_id,
        OAuthClient.is_active == True,
    ).first()
    if not client:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown client_id")

    allowed = [u.strip() for u in client.redirect_uris.split(",")]
    if not redirect_uri_allowed(redirect_uri, allowed):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "redirect_uri not allowed")

    try:
        validate_scope(scope)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))

    params = urlencode({
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        **({"state": state} if state else {}),
    })
    return RedirectResponse(f"/login?{params}", status_code=302)


# ── Token endpoint ───────────────────────────────────────────────────────────

@router.post("/token", response_model=OAuthTokenResponse)
def token(
    grant_type: str = Query(...),
    code: str = Query(...),
    client_id: str = Query(...),
    client_secret: str = Query(...),
    redirect_uri: str = Query(...),
    db: Session = Depends(get_db),
):
    """Exchange a one-time authorization code for an access token."""
    if grant_type != "authorization_code":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unsupported grant_type")

    client = db.query(OAuthClient).filter(
        OAuthClient.client_id == client_id,
        OAuthClient.is_active == True,
    ).first()
    if not client or client.client_secret_hash != hash_token(client_secret):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid client credentials")

    code_hash = hash_token(code)
    session = db.query(QRSession).filter(
        QRSession.auth_code_hash == code_hash,
        QRSession.status == "approved",
    ).first()
    if not session:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or already-used code")
    if session.auth_code_expires_at and session.auth_code_expires_at < datetime.now(timezone.utc):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Authorization code expired")
    # A direct-login (non-OAuth) session has no client_id — reject it outright
    # rather than relying on a None-vs-string comparison to fall through.
    if not session.client_id or session.client_id != client_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "code was not issued for this client")
    if session.redirect_uri != redirect_uri:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "redirect_uri mismatch")

    session.status = "consumed"
    db.commit()

    access = create_access_token(session.user_id)
    return OAuthTokenResponse(
        access_token=access,
        expires_in=settings.access_token_minutes * 60,
        scope=session.scope,
    )


# ── Userinfo endpoint ────────────────────────────────────────────────────────

@router.get("/userinfo", response_model=UserResponse)
def userinfo(user: User = Depends(current_user)):
    """Standard OIDC userinfo endpoint — returns claims for the token holder."""
    return UserResponse.model_validate(user)
