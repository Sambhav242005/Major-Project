"""Provenance for documents imported from external sources (GitHub).

Revision ID: 012
Revises: 011
"""

from alembic import op
import sqlalchemy as sa

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_sources",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("document_id", sa.Uuid(), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False, server_default="github"),
        sa.Column("repo_owner", sa.String(255), nullable=False),
        sa.Column("repo_name", sa.String(255), nullable=False),
        sa.Column("commit_sha", sa.String(40), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("blob_sha", sa.String(40)),
        sa.Column("content_sha256", sa.String(64)),
        sa.Column("line_start", sa.Integer()),
        sa.Column("line_end", sa.Integer()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_document_sources_document_id", "document_sources", ["document_id"])
    op.create_index("ix_document_sources_project_id", "document_sources", ["project_id"])
    # Provenance is served through membership-checked API routes, never a
    # directly exposed Supabase table. Owner/service-role sessions bypass RLS.
    op.execute("ALTER TABLE document_sources ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_index("ix_document_sources_project_id", table_name="document_sources")
    op.drop_index("ix_document_sources_document_id", table_name="document_sources")
    op.drop_table("document_sources")
