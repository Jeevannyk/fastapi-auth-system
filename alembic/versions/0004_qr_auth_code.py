"""Add transient raw auth_code column to qr_sessions

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-01

The browser polls a QR session's status and, for an OAuth flow, must be handed
the raw one-time authorization code so it can redirect the user agent back to
the client. We store that raw code transiently (cleared the moment it is
delivered) alongside the existing ``auth_code_hash`` used for verification.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("qr_sessions", sa.Column("auth_code", sa.String(128), nullable=True))


def downgrade() -> None:
    op.drop_column("qr_sessions", "auth_code")
