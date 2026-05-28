"""email verification and password reset

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-27

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Existing users are grandfathered in as verified.
    op.add_column("users", sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("users", sa.Column("verification_token_hash", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("verification_token_expires", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("reset_token_hash", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("reset_token_expires", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_users_verification_token_hash", "users", ["verification_token_hash"], unique=True)
    op.create_index("ix_users_reset_token_hash", "users", ["reset_token_hash"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_reset_token_hash", table_name="users")
    op.drop_index("ix_users_verification_token_hash", table_name="users")
    op.drop_column("users", "reset_token_expires")
    op.drop_column("users", "reset_token_hash")
    op.drop_column("users", "verification_token_expires")
    op.drop_column("users", "verification_token_hash")
    op.drop_column("users", "email_verified")
