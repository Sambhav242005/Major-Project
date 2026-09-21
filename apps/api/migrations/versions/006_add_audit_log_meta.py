"""Add missing meta column to audit_log.

Revision ID: 006
Revises: 005
"""

from alembic import op
import sqlalchemy as sa


revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "audit_log",
        sa.Column("meta", sa.JSON(), nullable=True),
    )


def downgrade():
    op.drop_column("audit_log", "meta")
