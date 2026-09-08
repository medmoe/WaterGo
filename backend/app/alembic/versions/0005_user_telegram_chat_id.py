"""users.telegram_chat_id

Revision ID: 0005_user_telegram_chat_id
Revises: 0004_reviews_pricing
Create Date: 2026-09-08

"""

import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op

# revision identifiers, used by Alembic.
revision = "0005_user_telegram_chat_id"
down_revision = "0004_reviews_pricing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "telegram_chat_id",
            sqlmodel.sql.sqltypes.AutoString(length=64),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "telegram_chat_id")
