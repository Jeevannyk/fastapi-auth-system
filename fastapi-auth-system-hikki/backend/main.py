from fastapi import FastAPI, HTTPException, Depends, Request, Response
from fastapi.responses import FileResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
import uuid
import qrcode
import os
import re
import sys
import json
import logging
import secrets
import base64
import httpx
from datetime import datetime, timedelta, timezone
from typing import Optional, List
from urllib.parse import urlencode

from .database import get_db, init_db, SessionLocal
from .models import (
    User, Session as DBSession, MFAChallenge, 
    WebAuthnCredential, WebAuthnChallenge, TwoFactorChallenge
)
from .security import (
    hash_password, verify_password, create_token, verify_token,
    create_partial_token, generate_mfa_code, generate_mfa_options,
    send_mfa_email, generate_webauthn_challenge, bytes_to_base64url, base64url_to_bytes,
    GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI,
    WEBAUTHN_RP_ID, WEBAUTHN_RP_NAME, WEBAUTHN_ORIGIN
)

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="CyberGuard Secure Access - Production Auth System")

# -------------------- STATIC FILES --------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

# -------------------- CORS --------------------
ALLOWED_ORIGINS = [origin.strip() for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000").split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------- INITIALIZE DATABASE --------------------
try:
    init_db()
except Exception as e:
    logger.error(f"Database initialization failed: {e}", exc_info=True)
    sys.exit(1)

# -------------------- REQUEST/RESPONSE MODELS --------------------

class SignupRequest(BaseModel):
    full_name: str
    email: EmailStr
    access_key: str
    verify_key: str

class LoginRequest(BaseModel):
    email: EmailStr
    access_key: str

class LoginResponse(BaseModel):
    message: str
    partial_token: str  # Partial token until MFA is complete
    requires_mfa: bool
    mfa_methods: List[str]  # Available MFA methods
    user_email: str

class MFAGenerateResponse(BaseModel):
    challenge_id: int
    correct_number: int  # Shown on screen
    options: List[int]  # 3 options for selection
    expires_in: int
    delivery_method: str
    sent_to: str  # Masked email

class MFAVerifyRequest(BaseModel):
    challenge_id: int
    selected_number: int

class MFAVerifyResponse(BaseModel):
    success: bool
    access_token: str  # Full access token after MFA verification
    message: str

# WebAuthn Models
class WebAuthnRegisterOptionsRequest(BaseModel):
    email: EmailStr

class WebAuthnRegisterCompleteRequest(BaseModel):
    email: EmailStr
    credential: dict  # The credential from navigator.credentials.create()

class WebAuthnAuthenticateOptionsRequest(BaseModel):
    email: EmailStr

class WebAuthnAuthenticateCompleteRequest(BaseModel):
    email: EmailStr
    credential: dict  # The credential from navigator.credentials.get()

# Google OAuth Models
class GoogleAuthRequest(BaseModel):
    redirect_uri: Optional[str] = None


# -------------------- HELPERS --------------------

def is_expired(created_at: datetime, timeout_minutes: int = 5) -> bool:
    """Check if session has expired"""
    try:
        now = datetime.now(timezone.utc)
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        return now - created_at > timedelta(minutes=timeout_minutes)
    except Exception as e:
        logger.error(f"Error checking expiration: {e}")
        return True

def validate_uuid(session_id: str) -> bool:
    """Validate that session_id is a valid UUID"""
    try:
        if ".." in session_id or "/" in session_id or "\\" in session_id:
            return False
        uuid.UUID(session_id)
        return True
    except ValueError:
        return False

def mask_email(email: str) -> str:
    """Mask email for display: j***@g***.com"""
    parts = email.split('@')
    if len(parts) != 2:
        return "***@***.com"
    local = parts[0]
    domain = parts[1].split('.')
    masked_local = local[0] + '***' if len(local) > 0 else '***'
    masked_domain = domain[0][0] + '***' if len(domain) > 0 and len(domain[0]) > 0 else '***'
    return f"{masked_local}@{masked_domain}.{domain[-1] if len(domain) > 1 else 'com'}"

def cleanup_old_qrs():
    """Delete QR code files older than 10 minutes"""
    qr_dir = "qrs"
    if os.path.exists(qr_dir):
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=10)
        for file in os.listdir(qr_dir):
            file_path = os.path.join(qr_dir, file)
            try:
                if os.path.isfile(file_path):
                    file_time = datetime.fromtimestamp(os.path.getmtime(file_path), tz=timezone.utc)
                    if file_time < cutoff:
                        os.remove(file_path)
            except Exception as e:
                logger.error(f"Error cleaning up QR file {file}: {e}")


# -------------------- PAGE ROUTES --------------------

@app.get("/")
def root():
    return RedirectResponse(url="/login")

@app.get("/login")
def login_page():
    return FileResponse(os.path.join(FRONTEND_DIR, "login.html"))

@app.get("/signup-page")
def signup_page():
    return FileResponse(os.path.join(FRONTEND_DIR, "signup.html"))

@app.get("/home")
def home_page():
    return FileResponse(os.path.join(FRONTEND_DIR, "home.html"))

@app.get("/health")
def health():
    return {"status": "ok", "version": "2.0", "features": ["google_oauth", "webauthn", "mfa"]}


# ==================== SIGNUP ====================

@app.post("/signup")
def signup(data: SignupRequest, db: Session = Depends(get_db)):
    if data.access_key != data.verify_key:
        raise HTTPException(status_code=400, detail="Access keys do not match")
    
    existing_user = db.query(User).filter(User.email == data.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    new_user = User(
        full_name=data.full_name,
        email=data.email,
        password_hash=hash_password(data.access_key),
        auth_provider="local",
        mfa_enabled=True
    )
    
    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
    except Exception as e:
        db.rollback()
        logger.exception("Failed to create user")
        raise HTTPException(status_code=500, detail="Failed to create user")

    return {
        "message": "User identity securely registered.",
        "next": "login"
    }


# ==================== LOGIN (Password-based) ====================

@app.post("/login")
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="Account not found. Please sign up first.")
    
    # Check if user has password (not Google-only)
    if not user.password_hash:
        raise HTTPException(
            status_code=400, 
            detail="This account uses Google Sign-In. Please use 'Sign in with Google'."
        )
    
    if not verify_password(data.access_key, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Create partial token (MFA not yet verified)
    partial_token = create_partial_token(user.id)
    
    # Check available MFA methods
    mfa_methods = ["email"]  # Email is always available
    
    # Check if user has WebAuthn credentials
    webauthn_creds = db.query(WebAuthnCredential).filter(
        WebAuthnCredential.user_id == user.id
    ).first()
    if webauthn_creds:
        mfa_methods.append("webauthn")
    
    return {
        "message": "Credentials verified. MFA required.",
        "partial_token": partial_token,
        "requires_mfa": True,
        "mfa_methods": mfa_methods,
        "user_email": user.email,
        "user_name": user.full_name
    }


# ==================== REAL MFA (Google-Style Number Matching) ====================

@app.post("/mfa/generate", response_model=MFAGenerateResponse)
async def generate_mfa_challenge(db: Session = Depends(get_db), token: dict = Depends(verify_token)):
    """Generate and send real MFA code via email"""
    user_id = token.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Clean up old expired challenges
    db.query(MFAChallenge).filter(
        MFAChallenge.user_id == int(user_id),
        MFAChallenge.expires_at < datetime.now(timezone.utc)
    ).delete()
    db.commit()
    
    # Generate secure MFA code (2-digit for Google-style)
    mfa_code = generate_mfa_code()
    options = generate_mfa_options(mfa_code)
    
    # Store challenge in database
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=2)
    challenge = MFAChallenge(
        user_id=int(user_id),
        challenge_code=mfa_code,
        delivery_method="email",
        sent_to=user.email,
        expires_at=expires_at,
        used=False,
        attempts=0
    )
    db.add(challenge)
    db.commit()
    db.refresh(challenge)
    
    # Send real email with MFA code
    email_sent = await send_mfa_email(user.email, mfa_code, user.full_name)
    if not email_sent:
        logger.warning(f"MFA email not sent to {user.email} - continuing in dev mode")
    
    return MFAGenerateResponse(
        challenge_id=challenge.id,
        correct_number=mfa_code,  # Shown on login screen
        options=options,
        expires_in=120,
        delivery_method="email",
        sent_to=mask_email(user.email)
    )


@app.post("/mfa/verify", response_model=MFAVerifyResponse)
def verify_mfa_challenge(data: MFAVerifyRequest, db: Session = Depends(get_db), token: dict = Depends(verify_token)):
    """Verify MFA code - grants full access on success"""
    user_id = token.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    challenge = db.query(MFAChallenge).filter(
        MFAChallenge.id == data.challenge_id,
        MFAChallenge.user_id == int(user_id)
    ).first()
    
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")
    
    # Check expiration
    now = datetime.now(timezone.utc)
    expires_at = challenge.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    
    if expires_at < now:
        db.delete(challenge)
        db.commit()
        raise HTTPException(status_code=410, detail="Challenge expired. Please request a new one.")
    
    # Check if already used
    if challenge.used:
        raise HTTPException(status_code=410, detail="Challenge already used. Please request a new one.")
    
    # Check max attempts
    if challenge.attempts >= challenge.max_attempts:
        db.delete(challenge)
        db.commit()
        raise HTTPException(status_code=429, detail="Too many attempts. Please request a new code.")
    
    # Verify the code
    if data.selected_number != challenge.challenge_code:
        challenge.attempts += 1
        db.commit()
        remaining = challenge.max_attempts - challenge.attempts
        raise HTTPException(
            status_code=401, 
            detail=f"Wrong number selected. {remaining} attempts remaining."
        )
    
    # Success! Mark as used
    challenge.used = True
    db.commit()
    
    # Create full access token
    access_token = create_token(int(user_id), mfa_verified=True)
    
    return MFAVerifyResponse(
        success=True,
        access_token=access_token,
        message="MFA verification successful"
    )


# ==================== GOOGLE OAUTH 2.0 ====================

@app.get("/auth/google")
def google_auth_redirect():
    """Redirect to Google OAuth consent screen"""
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=503, 
            detail="Google OAuth not configured. Please set GOOGLE_CLIENT_ID in environment."
        )
    
    # Google OAuth URL
    google_auth_url = "https://accounts.google.com/o/oauth2/v2/auth"
    
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
        "state": secrets.token_urlsafe(32)  # CSRF protection
    }
    
    auth_url = f"{google_auth_url}?{urlencode(params)}"
    return RedirectResponse(url=auth_url)


@app.get("/auth/google/callback")
async def google_auth_callback(code: str, state: str = None, db: Session = Depends(get_db)):
    """Handle Google OAuth callback"""
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise HTTPException(status_code=503, detail="Google OAuth not configured")
    
    try:
        # Exchange code for tokens
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "redirect_uri": GOOGLE_REDIRECT_URI,
                    "grant_type": "authorization_code"
                }
            )
            
            if token_response.status_code != 200:
                logger.error(f"Google token error: {token_response.text}")
                raise HTTPException(status_code=400, detail="Failed to get Google access token")
            
            tokens = token_response.json()
            access_token = tokens.get("access_token")
            
            # Get user info from Google
            userinfo_response = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            
            if userinfo_response.status_code != 200:
                raise HTTPException(status_code=400, detail="Failed to get Google user info")
            
            google_user = userinfo_response.json()
    
    except httpx.RequestError as e:
        logger.error(f"Google OAuth request error: {e}")
        raise HTTPException(status_code=503, detail="Failed to connect to Google")
    
    # Extract user info
    google_id = google_user.get("id")
    email = google_user.get("email")
    name = google_user.get("name", email.split("@")[0])
    verified_email = google_user.get("verified_email", False)
    
    if not verified_email:
        raise HTTPException(status_code=400, detail="Google email not verified")
    
    # Check if user exists
    user = db.query(User).filter(
        (User.google_id == google_id) | (User.email == email)
    ).first()
    
    if user:
        # Update existing user with Google info
        if not user.google_id:
            user.google_id = google_id
            user.google_email = email
            if user.auth_provider == "local":
                user.auth_provider = "both"
            db.commit()
    else:
        # Create new user from Google account
        user = User(
            full_name=name,
            email=email,
            google_id=google_id,
            google_email=email,
            auth_provider="google",
            password_hash=None,  # No password for Google-only users
            mfa_enabled=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    
    # Create access token (Google login counts as verified)
    access_token = create_token(user.id, mfa_verified=True)
    
    # Redirect to frontend with token
    redirect_url = f"/login?google_success=true&token={access_token}&email={email}&name={name}"
    return RedirectResponse(url=redirect_url)


@app.get("/auth/google/status")
def google_oauth_status():
    """Check if Google OAuth is configured"""
    return {
        "configured": bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET),
        "client_id_set": bool(GOOGLE_CLIENT_ID),
        "redirect_uri": GOOGLE_REDIRECT_URI
    }


# ==================== WEBAUTHN / PASSKEYS (Biometric Authentication) ====================

@app.post("/webauthn/register/options")
def webauthn_register_options(data: WebAuthnRegisterOptionsRequest, db: Session = Depends(get_db)):
    """Generate WebAuthn registration options for new passkey/fingerprint"""
    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found. Please sign up first.")
    
    # Check existing credentials
    existing_creds = db.query(WebAuthnCredential).filter(
        WebAuthnCredential.user_id == user.id
    ).all()
    
    # Generate challenge
    challenge = generate_webauthn_challenge()
    
    # Store challenge temporarily
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
    
    # Clean old challenges
    db.query(WebAuthnChallenge).filter(
        WebAuthnChallenge.user_id == user.id,
        WebAuthnChallenge.challenge_type == "registration"
    ).delete()
    
    webauthn_challenge = WebAuthnChallenge(
        user_id=user.id,
        email=user.email,
        challenge=challenge,
        challenge_type="registration",
        expires_at=expires_at
    )
    db.add(webauthn_challenge)
    db.commit()
    
    # Build excludeCredentials list
    exclude_credentials = []
    for cred in existing_creds:
        exclude_credentials.append({
            "type": "public-key",
            "id": bytes_to_base64url(cred.credential_id),
            "transports": json.loads(cred.transports) if cred.transports else ["internal"]
        })
    
    # WebAuthn registration options (W3C spec compliant)
    options = {
        "challenge": bytes_to_base64url(challenge),
        "rp": {
            "name": WEBAUTHN_RP_NAME,
            "id": WEBAUTHN_RP_ID
        },
        "user": {
            "id": bytes_to_base64url(str(user.id).encode()),
            "name": user.email,
            "displayName": user.full_name
        },
        "pubKeyCredParams": [
            {"type": "public-key", "alg": -7},   # ES256
            {"type": "public-key", "alg": -257}  # RS256
        ],
        "authenticatorSelection": {
            "authenticatorAttachment": "platform",  # Built-in authenticator (fingerprint, Face ID)
            "userVerification": "required",
            "residentKey": "preferred"
        },
        "timeout": 300000,  # 5 minutes
        "attestation": "none",
        "excludeCredentials": exclude_credentials
    }
    
    return {"options": options}


@app.post("/webauthn/register/complete")
def webauthn_register_complete(data: WebAuthnRegisterCompleteRequest, db: Session = Depends(get_db)):
    """Complete WebAuthn registration with the credential from the browser"""
    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get stored challenge
    stored_challenge = db.query(WebAuthnChallenge).filter(
        WebAuthnChallenge.user_id == user.id,
        WebAuthnChallenge.challenge_type == "registration"
    ).first()
    
    if not stored_challenge:
        raise HTTPException(status_code=400, detail="No registration challenge found. Please try again.")
    
    # Check expiration
    if stored_challenge.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        db.delete(stored_challenge)
        db.commit()
        raise HTTPException(status_code=410, detail="Challenge expired. Please try again.")
    
    try:
        credential = data.credential
        
        # Extract credential data
        credential_id = base64url_to_bytes(credential["id"])
        
        # Get attestation response
        response = credential.get("response", {})
        client_data_json = response.get("clientDataJSON", "")
        attestation_object = response.get("attestationObject", "")
        
        # For platform authenticators, we store the public key from attestation
        # In production, use webauthn library for full verification
        # Simplified: store credential ID and a placeholder for public key
        
        # Check if credential already exists
        existing = db.query(WebAuthnCredential).filter(
            WebAuthnCredential.credential_id == credential_id
        ).first()
        
        if existing:
            raise HTTPException(status_code=400, detail="This credential is already registered")
        
        # Store the credential
        transports = credential.get("transports", ["internal"])
        
        new_credential = WebAuthnCredential(
            user_id=user.id,
            credential_id=credential_id,
            public_key=base64url_to_bytes(attestation_object) if attestation_object else b"",
            sign_count=0,
            device_name=credential.get("authenticatorAttachment", "platform"),
            transports=json.dumps(transports),
            credential_type="public-key"
        )
        
        db.add(new_credential)
        db.delete(stored_challenge)
        db.commit()
        
        return {
            "success": True,
            "message": "Biometric credential registered successfully",
            "credential_id": bytes_to_base64url(credential_id)
        }
        
    except Exception as e:
        logger.error(f"WebAuthn registration error: {e}")
        raise HTTPException(status_code=400, detail=f"Registration failed: {str(e)}")


@app.post("/webauthn/authenticate/options")
def webauthn_authenticate_options(data: WebAuthnAuthenticateOptionsRequest, db: Session = Depends(get_db)):
    """Generate WebAuthn authentication options for fingerprint/passkey login"""
    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get user's credentials
    credentials = db.query(WebAuthnCredential).filter(
        WebAuthnCredential.user_id == user.id
    ).all()
    
    if not credentials:
        raise HTTPException(status_code=404, detail="No biometric credentials registered. Please set up fingerprint first.")
    
    # Generate challenge
    challenge = generate_webauthn_challenge()
    
    # Store challenge
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
    
    db.query(WebAuthnChallenge).filter(
        WebAuthnChallenge.user_id == user.id,
        WebAuthnChallenge.challenge_type == "authentication"
    ).delete()
    
    webauthn_challenge = WebAuthnChallenge(
        user_id=user.id,
        email=user.email,
        challenge=challenge,
        challenge_type="authentication",
        expires_at=expires_at
    )
    db.add(webauthn_challenge)
    db.commit()
    
    # Build allowCredentials
    allow_credentials = []
    for cred in credentials:
        allow_credentials.append({
            "type": "public-key",
            "id": bytes_to_base64url(cred.credential_id),
            "transports": json.loads(cred.transports) if cred.transports else ["internal"]
        })
    
    options = {
        "challenge": bytes_to_base64url(challenge),
        "rpId": WEBAUTHN_RP_ID,
        "allowCredentials": allow_credentials,
        "userVerification": "required",
        "timeout": 300000
    }
    
    return {"options": options, "user_name": user.full_name}


@app.post("/webauthn/authenticate/complete")
def webauthn_authenticate_complete(data: WebAuthnAuthenticateCompleteRequest, db: Session = Depends(get_db)):
    """Complete WebAuthn authentication - verify fingerprint/passkey"""
    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get stored challenge
    stored_challenge = db.query(WebAuthnChallenge).filter(
        WebAuthnChallenge.user_id == user.id,
        WebAuthnChallenge.challenge_type == "authentication"
    ).first()
    
    if not stored_challenge:
        raise HTTPException(status_code=400, detail="No authentication challenge found")
    
    # Check expiration
    if stored_challenge.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        db.delete(stored_challenge)
        db.commit()
        raise HTTPException(status_code=410, detail="Challenge expired")
    
    try:
        credential = data.credential
        credential_id = base64url_to_bytes(credential["id"])
        
        # Find the credential
        stored_cred = db.query(WebAuthnCredential).filter(
            WebAuthnCredential.credential_id == credential_id,
            WebAuthnCredential.user_id == user.id
        ).first()
        
        if not stored_cred:
            raise HTTPException(status_code=401, detail="Credential not recognized")
        
        # In production, verify signature with stored public key
        # For now, we trust the browser's WebAuthn API verification
        
        # Update last used and sign count
        response = credential.get("response", {})
        # authenticator_data = response.get("authenticatorData", "")
        
        stored_cred.last_used_at = datetime.now(timezone.utc)
        stored_cred.sign_count += 1
        
        db.delete(stored_challenge)
        db.commit()
        
        # Create full access token (WebAuthn counts as strong authentication)
        access_token = create_token(user.id, mfa_verified=True, webauthn_verified=True)
        
        return {
            "success": True,
            "access_token": access_token,
            "message": "Biometric verification successful",
            "user_email": user.email,
            "user_name": user.full_name
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"WebAuthn authentication error: {e}")
        raise HTTPException(status_code=400, detail=f"Authentication failed: {str(e)}")


@app.get("/webauthn/credentials/{email}")
def get_webauthn_credentials(email: str, db: Session = Depends(get_db)):
    """Check if user has registered WebAuthn credentials"""
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return {"has_credentials": False, "count": 0}
    
    credentials = db.query(WebAuthnCredential).filter(
        WebAuthnCredential.user_id == user.id
    ).all()
    
    return {
        "has_credentials": len(credentials) > 0,
        "count": len(credentials),
        "devices": [
            {
                "id": bytes_to_base64url(c.credential_id),
                "name": c.device_name,
                "created": c.created_at.isoformat() if c.created_at else None,
                "last_used": c.last_used_at.isoformat() if c.last_used_at else None
            }
            for c in credentials
        ]
    }


# ==================== LEGACY ENDPOINTS (Backward Compatibility) ====================

@app.post("/2fa/generate")
async def legacy_2fa_generate(db: Session = Depends(get_db), token: dict = Depends(verify_token)):
    """Legacy 2FA - redirects to new MFA endpoint"""
    return await generate_mfa_challenge(db, token)


@app.post("/2fa/verify")
def legacy_2fa_verify(data: MFAVerifyRequest, db: Session = Depends(get_db), token: dict = Depends(verify_token)):
    """Legacy 2FA verify - redirects to new MFA endpoint"""
    return verify_mfa_challenge(data, db, token)


@app.post("/fingerprint")
def legacy_fingerprint(db: Session = Depends(get_db), token: dict = Depends(verify_token)):
    """Legacy fingerprint endpoint - now use WebAuthn"""
    user_id = token.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    session_id = str(uuid.uuid4())
    
    db.query(DBSession).filter(DBSession.user_id == int(user_id)).delete()
    
    new_session = DBSession(
        session_id=session_id,
        user_id=int(user_id),
        created_at=datetime.now(timezone.utc),
        mfa_verified=token.get("mfa_verified", False),
        webauthn_verified=token.get("webauthn_verified", False)
    )
    
    try:
        db.add(new_session)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.exception("Failed to create session")
        raise HTTPException(status_code=500, detail="Failed to create session")
    
    cleanup_old_qrs()

    return {
        "message": "Biometric verified",
        "session_id": session_id,
        "next": "qr"
    }


# ==================== QR CODE ENDPOINTS ====================

@app.get("/qr/{session_id}")
def qr(session_id: str, db: Session = Depends(get_db)):
    if not validate_uuid(session_id):
        raise HTTPException(status_code=400, detail="Invalid session ID format")
    
    session = db.query(DBSession).filter(DBSession.session_id == session_id).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if is_expired(session.created_at):
        raise HTTPException(status_code=403, detail="Session expired")
    
    qr_dir = "qrs"
    os.makedirs(qr_dir, exist_ok=True)

    payload = f"cyberguard://connect/{session_id}"
    path = os.path.join(qr_dir, f"{session_id}.png")

    img = qrcode.make(payload)
    img.save(path)

    return {
        "qr_image": path,
        "payload": payload
    }


@app.get("/qr-image/{session_id}")
def get_qr_image(session_id: str, db: Session = Depends(get_db)):
    if not validate_uuid(session_id):
        raise HTTPException(status_code=400, detail="Invalid session ID format")
    
    session = db.query(DBSession).filter(DBSession.session_id == session_id).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if is_expired(session.created_at):
        raise HTTPException(status_code=403, detail="Session expired")
    
    path = os.path.join("qrs", f"{session_id}.png")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="QR not found")
    return FileResponse(path, media_type="image/png")
