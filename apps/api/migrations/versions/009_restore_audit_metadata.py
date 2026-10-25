"""Restore legacy audit details without overwriting newer records.

Revision ID: 009
Revises: 008
"""

from alembic import op
import sqlalchemy as sa

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 001 stored details in metadata; 006 added meta without copying them.
    # JSON null is distinct from SQL NULL (including SQLAlchemy JSON None).
    # Keep metadata so conflicting historical details are never discarded.
    op.execute(sa.text(
        "UPDATE audit_log SET meta = metadata "
        "WHERE (meta IS NULL OR CAST(meta AS TEXT) = 'null') "
        "AND metadata IS NOT NULL AND CAST(metadata AS TEXT) <> 'null'"
    ))


def downgrade() -> None:
    # A copy cannot be distinguished from details written after the upgrade.
    # Retain both columns and their data when returning to 008.
    pass
