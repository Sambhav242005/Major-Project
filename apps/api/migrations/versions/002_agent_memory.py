"""add agent ownership and memory tables

Revision ID: 002
Revises: 001
Create Date: 2026-08-08
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add owner_id to agents table
    op.add_column(
        "agents",
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("profiles.id"), nullable=True),
    )
    op.add_column(
        "agents",
        sa.Column("last_checkpoint", postgresql.JSON, nullable=True),
    )
    op.add_column(
        "agents",
        sa.Column("last_active_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Create agent_memory table
    op.create_table(
        "agent_memory",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.func.gen_random_uuid()),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("memory_type", sa.String(20), nullable=False),  # working, episodic, semantic
        sa.Column("content", postgresql.JSON, nullable=False),
        sa.Column("embedding", sa.Text),  # stored as JSON array of floats for now
        sa.Column("metadata", postgresql.JSON, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_agent_memory_agent_id", "agent_memory", ["agent_id"])
    op.create_index("ix_agent_memory_project_id", "agent_memory", ["project_id"])
    op.create_index("ix_agent_memory_type", "agent_memory", ["memory_type"])

    # Create agent_checkpoints table for stop/resume
    op.create_table(
        "agent_checkpoints",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.func.gen_random_uuid()),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_tasks.id"), nullable=True),
        sa.Column("state", postgresql.JSON, nullable=False),  # working memory snapshot
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_agent_checkpoints_agent_id", "agent_checkpoints", ["agent_id"])


def downgrade() -> None:
    op.drop_table("agent_checkpoints")
    op.drop_table("agent_memory")
    op.drop_column("agents", "owner_id")
    op.drop_column("agents", "last_checkpoint")
    op.drop_column("agents", "last_active_at")
