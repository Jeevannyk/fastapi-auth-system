from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, LargeBinary, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    full_name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=True)  # Nullable for OAuth-only users
    google_id = Column(String, unique=True, nullable=True, index=True)  # Google OAuth ID
    google_email = Column(String, nullable=True)  # Verified Google email
    auth_provider = Column(String, default="local")  # "local", "google", "both"
    mfa_enabled = Column(Boolean, default=True)  # MFA is enabled by default
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    webauthn_credentials = relationship("WebAuthnCredential", back_populates="user", cascade="all, delete-orphan")
    mfa_challenges = relationship("MFAChallenge", back_populates="user", cascade="all, delete-orphan")


class WebAuthnCredential(Base):
    """Stores WebAuthn/Passkey credentials for biometric authentication"""
    __tablename__ = "webauthn_credentials"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # WebAuthn credential data (public-key based - NO biometric data stored)
    credential_id = Column(LargeBinary, unique=True, nullable=False)  # Unique credential identifier
    public_key = Column(LargeBinary, nullable=False)  # Public key (private key stays on device)
    sign_count = Column(Integer, default=0)  # Counter for replay attack prevention
    
    # Credential metadata
    device_name = Column(String, nullable=True)  # e.g., "Windows Hello", "Touch ID"
    aaguid = Column(String, nullable=True)  # Authenticator AAGUID
    credential_type = Column(String, default="public-key")
    transports = Column(Text, nullable=True)  # JSON array of transports: ["internal", "usb", etc.]
    
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used_at = Column(DateTime, nullable=True)
    
    # Relationship
    user = relationship("User", back_populates="webauthn_credentials")


class MFAChallenge(Base):
    """Stores real MFA verification codes sent via email"""
    __tablename__ = "mfa_challenges"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # The verification code (2-digit number for Google-style matching)
    challenge_code = Column(Integer, nullable=False)
    
    # Delivery tracking
    delivery_method = Column(String, default="email")  # "email", "push", "authenticator"
    sent_to = Column(String, nullable=True)  # Email address or device ID
    sent_at = Column(DateTime, default=datetime.utcnow)
    
    # Security constraints
    expires_at = Column(DateTime, nullable=False)  # Time-limited (2 minutes)
    used = Column(Boolean, default=False)  # Single-use
    attempts = Column(Integer, default=0)  # Track failed attempts
    max_attempts = Column(Integer, default=3)  # Lock after 3 wrong attempts
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    user = relationship("User", back_populates="mfa_challenges")


class WebAuthnChallenge(Base):
    """Temporary storage for WebAuthn registration/authentication challenges"""
    __tablename__ = "webauthn_challenges"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)  # Nullable for registration
    email = Column(String, nullable=True, index=True)  # For registration before user exists
    
    challenge = Column(LargeBinary, nullable=False)  # The challenge bytes
    challenge_type = Column(String, nullable=False)  # "registration" or "authentication"
    
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class TwoFactorChallenge(Base):
    """Legacy - Stores temporary 2FA number matching challenges (deprecated - use MFAChallenge)"""
    __tablename__ = "two_factor_challenges"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    challenge_number = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)


class Session(Base):
    __tablename__ = "sessions"
    
    session_id = Column(String, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, default=lambda: datetime.utcnow() + timedelta(minutes=30))
    
    # Session security
    mfa_verified = Column(Boolean, default=False)  # True after MFA verification
    webauthn_verified = Column(Boolean, default=False)  # True after biometric verification
    
    # Relationship to user
    user = relationship("User", back_populates="sessions")
