"""Passwordless QR-code authentication — full schema rebuild

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-27

Drops the password-based schema and replaces it with the four tables that
power the QR identity-provider architecture:

  users              — profile only, no password hash
  registered_devices — trusted authenticator devices (token stored as SHA-256 hash)
  qr_sessions        — lifecycle of each QR login attempt
  oauth_clients      — third-party apps that use Cipher as their IdP
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop all tables from the previous password-based schema
    op.drop_table("refresh_tokens")
    op.drop_table("users")

    # ── users ────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("full_name", sa.String(120), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_id", "users", ["id"], unique=False)
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # ── registered_devices ───────────────────────────────────────────────────
    op.create_table(
        "registered_devices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False, server_default="My Device"),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_registered_devices_user_id", "registered_devices", ["user_id"])
    op.create_index("ix_registered_devices_token_hash", "registered_devices", ["token_hash"], unique=True)

    # ── qr_sessions ──────────────────────────────────────────────────────────
    op.create_table(
        "qr_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("client_id", sa.String(64), nullable=True),
        sa.Column("redirect_uri", sa.String(512), nullable=True),
        sa.Column("scope", sa.String(255), nullable=False, server_default="openid profile email"),
        sa.Column("auth_code_hash", sa.String(64), nullable=True),
        sa.Column("auth_code_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_qr_sessions_session_id", "qr_sessions", ["session_id"], unique=True)
    op.create_index("ix_qr_sessions_user_id", "qr_sessions", ["user_id"])
    op.create_index("ix_qr_sessions_auth_code_hash", "qr_sessions", ["auth_code_hash"], unique=True)

    # ── oauth_clients ────────────────────────────────────────────────────────
    op.create_table(
        "oauth_clients",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("client_id", sa.String(64), nullable=False),
        sa.Column("client_secret_hash", sa.String(64), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("redirect_uris", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_oauth_clients_client_id", "oauth_clients", ["client_id"], unique=True)


def downgrade() -> None:
    op.drop_table("oauth_clients")
    op.drop_table("qr_sessions")
    op.drop_table("registered_devices")
    op.drop_table("users")

    # Restore minimal previous schema (users + refresh_tokens only)
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("full_name", sa.String(120), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("totp_secret", sa.String(64), nullable=True),
        sa.Column("totp_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("verification_token_hash", sa.String(255), nullable=True),
        sa.Column("verification_token_expires", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reset_token_hash", sa.String(255), nullable=True),
        sa.Column("reset_token_expires", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_login_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
