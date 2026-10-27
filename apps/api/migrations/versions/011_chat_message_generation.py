"""Record which generation produced each chat answer.

Revision ID: 011
Revises: 010
"""

from alembic import op
import sqlalchemy as sa

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("chat_messages", sa.Column("generation_provider", sa.String(50), nullable=True))
    op.add_column("chat_messages", sa.Column("generation_model", sa.String(200), nullable=True))


def downgrade() -> None:
    op.drop_column("chat_messages", "generation_model")
    op.drop_column("chat_messages", "generation_provider")
