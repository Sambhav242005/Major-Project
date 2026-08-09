"""Add mcp_auth_tokens for persisted OAuth tokens.

Revision ID: 004
Revises: 003
Create Date: 2026-08-09
"""
from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mcp_auth_tokens",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("connection_id", sa.Uuid(), sa.ForeignKey("mcp_connections.id", ondelete="CASCADE"), nullable=False),
        sa.Column("access_token", sa.Text, nullable=False),
        sa.Column("token_type", sa.String(20), server_default="Bearer"),
        sa.Column("refresh_token", sa.Text),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scope", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_mcp_auth_tokens_connection",
        "mcp_auth_tokens",
        ["connection_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_mcp_auth_tokens_connection")
    op.drop_table("mcp_auth_tokens")
