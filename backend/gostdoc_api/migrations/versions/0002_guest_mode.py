"""guest mode

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "guest_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_guest_sessions_token_hash"), "guest_sessions", ["token_hash"], unique=True
    )
    with op.batch_alter_table("jobs") as batch:
        batch.alter_column("user_id", existing_type=sa.Integer(), nullable=True)
        batch.add_column(sa.Column("guest_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("client_ip", sa.String(length=45), nullable=True))
        batch.create_foreign_key(
            "fk_jobs_guest_id_guest_sessions",
            "guest_sessions",
            ["guest_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_index(op.f("ix_jobs_guest_id"), ["guest_id"], unique=False)
        batch.create_index(op.f("ix_jobs_client_ip"), ["client_ip"], unique=False)


def downgrade() -> None:
    op.execute("DELETE FROM jobs WHERE user_id IS NULL")
    with op.batch_alter_table("jobs") as batch:
        batch.drop_index(op.f("ix_jobs_client_ip"))
        batch.drop_index(op.f("ix_jobs_guest_id"))
        batch.drop_constraint("fk_jobs_guest_id_guest_sessions", type_="foreignkey")
        batch.drop_column("client_ip")
        batch.drop_column("guest_id")
        batch.alter_column("user_id", existing_type=sa.Integer(), nullable=False)
    op.drop_index(op.f("ix_guest_sessions_token_hash"), table_name="guest_sessions")
    op.drop_table("guest_sessions")
