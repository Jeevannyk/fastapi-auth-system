import bcrypt
import pyotp
import secrets
import base64
import json
import os
import asyncio
from jose import jwt, JWTError
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, Header
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# -------------------- ENVIRONMENT CONFIGURATION --------------------
# Fail fast if SECRET_KEY is not set (allow fallback only in development)
if "SECRET_KEY" not in os.environ:
    if os.getenv("ENVIRONMENT") != "development":
        raise RuntimeError("SECRET_KEY environment variable must be set for production")
    SECRET_KEY = "your-secret-key-change-in-production-use-env-variable"
else:
    SECRET_KEY = os.environ["SECRET_KEY"]

ALGO = "HS256"

# Google OAuth Configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")

# Email Configuration (for real MFA)
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", "noreply@cyberguard.com")

# WebAuthn Configuration
WEBAUTHN_RP_ID = os.getenv("WEBAUTHN_RP_ID", "localhost")  # Relying Party ID (domain)
WEBAUTHN_RP_NAME = os.getenv("WEBAUTHN_RP_NAME", "CyberGuard Secure Access")
WEBAUTHN_ORIGIN = os.getenv("WEBAUTHN_ORIGIN", "http://localhost:8000")


# -------------------- PASSWORD HASHING --------------------
def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    if not password:
        raise ValueError("Password cannot be empty")
    password_bytes = str(password).encode('utf-8')
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')


def verify_password(password: str, hashed_password: str) -> bool:
    """Verify a password against a hashed password"""
    if not password or not hashed_password:
        return False
    try:
        password_bytes = str(password).encode('utf-8')
        hashed_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except Exception:
        return False


# -------------------- JWT TOKENS --------------------
def create_token(user_id: int, mfa_verified: bool = False, webauthn_verified: bool = False) -> str:
    """Create a JWT token with security flags"""
    payload = {
        "sub": str(user_id),
        "mfa_verified": mfa_verified,
        "webauthn_verified": webauthn_verified,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=30)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGO)


def create_partial_token(user_id: int) -> str:
    """Create a partial token for MFA pending state (short-lived)"""
    payload = {
        "sub": str(user_id),
        "partial": True,  # Indicates MFA not yet completed
        "exp": datetime.now(timezone.utc) + timedelta(minutes=5)  # Short expiry for MFA flow
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGO)


def verify_token(authorization: str = Header(None)):
    """Verify JWT token from Authorization header"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    
    try:
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Invalid authorization format")
        
        token = authorization.split(" ")[1]
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGO])
        
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        
        return {
            "user_id": user_id,
            "mfa_verified": payload.get("mfa_verified", False),
            "webauthn_verified": payload.get("webauthn_verified", False),
            "partial": payload.get("partial", False)
        }
    
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    except IndexError:
        raise HTTPException(status_code=401, detail="Invalid authorization format")


# -------------------- MFA CODE GENERATION --------------------
def generate_mfa_code() -> int:
    """Generate a secure random 2-digit MFA code (10-99) for Google-style number matching"""
    return secrets.randbelow(90) + 10  # Returns 10-99


def generate_mfa_options(correct_code: int, num_options: int = 3) -> list[int]:
    """Generate MFA options including the correct code"""
    options = {correct_code}
    while len(options) < num_options:
        fake_code = secrets.randbelow(90) + 10
        if fake_code != correct_code:
            options.add(fake_code)
    options_list = list(options)
    secrets.SystemRandom().shuffle(options_list)
    return options_list


# -------------------- EMAIL SENDING (Real MFA) --------------------
async def send_mfa_email(to_email: str, mfa_code: int, user_name: str = "User") -> bool:
    """Send real MFA verification code via email"""
    if not SMTP_USER or not SMTP_PASSWORD:
        logger.warning("SMTP not configured - MFA email not sent (dev mode)")
        return True  # Return True in dev mode to continue flow
    
    try:
        import aiosmtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        # Create email content
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"CyberGuard Verification Code: {mfa_code}"
        msg["From"] = SMTP_FROM_EMAIL
        msg["To"] = to_email
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f5f5f5; padding: 20px; }}
                .container {{ max-width: 500px; margin: 0 auto; background: white; border-radius: 12px; padding: 40px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }}
                .header {{ text-align: center; margin-bottom: 30px; }}
                .code {{ font-size: 48px; font-weight: bold; color: #135bec; text-align: center; padding: 20px; background: #f0f5ff; border-radius: 8px; letter-spacing: 8px; }}
                .footer {{ text-align: center; color: #666; font-size: 12px; margin-top: 30px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1 style="color: #135bec;">🔐 CyberGuard</h1>
                    <p>Verification Required</p>
                </div>
                <p>Hello {user_name},</p>
                <p>Someone is trying to sign in to your account. To verify it's you, match this number on your device:</p>
                <div class="code">{mfa_code}</div>
                <p style="color: #666; font-size: 14px; margin-top: 20px;">
                    ⏱️ This code expires in 2 minutes.<br>
                    🔒 Do not share this code with anyone.
                </p>
                <div class="footer">
                    <p>If you didn't request this, please ignore this email.</p>
                    <p>© 2026 CyberGuard Inc.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        text_content = f"""
        CyberGuard Verification Code
        
        Hello {user_name},
        
        Your verification code is: {mfa_code}
        
        This code expires in 2 minutes.
        Do not share this code with anyone.
        
        If you didn't request this, please ignore this email.
        """
        
        msg.attach(MIMEText(text_content, "plain"))
        msg.attach(MIMEText(html_content, "html"))
        
        # Send email
        await aiosmtplib.send(
            msg,
            hostname=SMTP_HOST,
            port=SMTP_PORT,
            username=SMTP_USER,
            password=SMTP_PASSWORD,
            start_tls=True
        )
        
        logger.info(f"MFA email sent to {to_email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send MFA email: {e}")
        return False


# -------------------- WEBAUTHN HELPERS --------------------
def generate_webauthn_challenge() -> bytes:
    """Generate a cryptographically secure challenge for WebAuthn"""
    return secrets.token_bytes(32)


def bytes_to_base64url(data: bytes) -> str:
    """Convert bytes to base64url encoding (WebAuthn standard)"""
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('utf-8')


def base64url_to_bytes(data: str) -> bytes:
    """Convert base64url string to bytes"""
    # Add padding if needed
    padding = 4 - len(data) % 4
    if padding != 4:
        data += '=' * padding
    return base64.urlsafe_b64decode(data)


# -------------------- LEGACY FUNCTIONS --------------------
def verify_otp(secret, otp):
    """Verify TOTP code (legacy - for authenticator apps)"""
    return pyotp.TOTP(secret).verify(otp)
