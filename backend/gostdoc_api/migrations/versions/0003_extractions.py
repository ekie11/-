"""extractions

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import op

from gostdoc_api.models import JSONType

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "extractions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("base_profile_id", sa.String(length=64), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=True),
        sa.Column("result", JSONType, nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("counts_toward_limit", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_extractions_user_id"), "extractions", ["user_id"], unique=False)
    op.create_index(op.f("ix_extractions_created_at"), "extractions", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_extractions_created_at"), table_name="extractions")
    op.drop_index(op.f("ix_extractions_user_id"), table_name="extractions")
    op.drop_table("extractions")
