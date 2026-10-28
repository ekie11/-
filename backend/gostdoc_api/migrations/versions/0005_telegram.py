"""telegram: users.telegram_id, telegram_name, email/password_hash nullable

Revision ID: 0005
Revises: 0004
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("telegram_id", sa.BigInteger(), nullable=True))
        batch.add_column(sa.Column("telegram_name", sa.String(length=255), nullable=True))
        batch.alter_column("email", existing_type=sa.String(length=320), nullable=True)
        batch.alter_column("password_hash", existing_type=sa.String(length=255), nullable=True)
        batch.create_index("ix_users_telegram_id", ["telegram_id"], unique=True)


def downgrade() -> None:
    # Пользователи бота (без почты и пароля) в прежней схеме невозможны.
    op.execute("DELETE FROM users WHERE email IS NULL OR password_hash IS NULL")
    with op.batch_alter_table("users") as batch:
        batch.drop_index("ix_users_telegram_id")
        batch.drop_column("telegram_name")
        batch.drop_column("telegram_id")
        batch.alter_column("password_hash", existing_type=sa.String(length=255), nullable=False)
        batch.alter_column("email", existing_type=sa.String(length=320), nullable=False)
