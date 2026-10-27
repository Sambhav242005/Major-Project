"""Preserve source timestamps for transcripts and video frame evidence."""
from alembic import op
import sqlalchemy as sa

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("document_chunks", sa.Column("source_location", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("document_chunks", "source_location")
