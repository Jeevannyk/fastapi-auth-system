from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, TypeDecorator
from sqlalchemy.orm import relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    """Tz-aware UTC datetimes — works on both SQLite and Postgres."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(254), unique=True, index=True, nullable=False)
    full_name = Column(String(120), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(UTCDateTime(), default=utcnow, nullable=False)

    devices = relationship("RegisteredDevice", back_populates="user", cascade="all, delete-orphan")
    qr_sessions = relationship("QRSession", back_populates="user")


class RegisteredDevice(Base):
    """A trusted authenticator device owned by a user.

    The raw device token is issued once at enrollment and never stored —
    only its SHA-256 hash lives here.
    """

    __tablename__ = "registered_devices"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(120), nullable=False, default="My Device")
    token_hash = Column(String(64), unique=True, index=True, nullable=False)
    last_used_at = Column(UTCDateTime(), nullable=True)
    created_at = Column(UTCDateTime(), default=utcnow, nullable=False)

    user = relationship("User", back_populates="devices")


class QRSession(Base):
    """Lifecycle of a single QR login attempt.

    Status flow:
        pending → scanned → approved → consumed
                                     ↘ expired  (any stage if past expires_at)
    """

    __tablename__ = "qr_sessions"

    id = Column(Integer, primary_key=True)
    session_id = Column(String(64), unique=True, index=True, nullable=False)

    # pending | scanned | approved | consumed | expired
    status = Column(String(20), default="pending", nullable=False)

    # Populated after the device scans & approves
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    # ── OAuth / cross-site context ──────────────────────────────────────────
    client_id = Column(String(64), nullable=True)
    redirect_uri = Column(String(512), nullable=True)
    scope = Column(String(255), nullable=False, default="openid profile email")

    # One-time authorization code (post-approval, OAuth code exchange)
    auth_code_hash = Column(String(64), nullable=True, unique=True, index=True)
    auth_code_expires_at = Column(UTCDateTime(), nullable=True)

    expires_at = Column(UTCDateTime(), nullable=False)
    created_at = Column(UTCDateTime(), default=utcnow, nullable=False)

    user = relationship("User", back_populates="qr_sessions")


class OAuthClient(Base):
    """A registered third-party application that uses Cipher as its IdP."""

    __tablename__ = "oauth_clients"

    id = Column(Integer, primary_key=True)
    client_id = Column(String(64), unique=True, index=True, nullable=False)
    client_secret_hash = Column(String(64), nullable=False)
    name = Column(String(120), nullable=False)
    # Comma-separated list of allowed redirect URIs
    redirect_uris = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(UTCDateTime(), default=utcnow, nullable=False)
