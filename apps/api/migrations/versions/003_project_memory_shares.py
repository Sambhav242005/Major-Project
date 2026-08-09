"""Add project_memory_shares for cross-project memory sharing.

Revision ID: 003
Revises: 002
Create Date: 2026-08-08
"""
from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_memory_shares",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("source_project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("target_project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("permission", sa.String(10), nullable=False, server_default="read"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("source_project_id", "target_project_id"),
    )
    op.create_index(
        "ix_project_memory_shares_target",
        "project_memory_shares",
        ["target_project_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_project_memory_shares_target")
    op.drop_table("project_memory_shares")
