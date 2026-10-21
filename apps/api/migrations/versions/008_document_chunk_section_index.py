"""Align document chunks with the section_index ORM field.

Revision ID: 008
Revises: 007
"""
from alembic import op
import sqlalchemy as sa

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("document_chunks", sa.Column("section_index", sa.Integer(), nullable=True, server_default="0"))


def downgrade():
    op.drop_column("document_chunks", "section_index")
