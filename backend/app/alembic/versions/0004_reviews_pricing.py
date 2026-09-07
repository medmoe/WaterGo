"""pricing_settings, reviews, notification_logs

Revision ID: 0004_reviews_pricing
Revises: 0003_orders_routes
Create Date: 2026-09-07

"""

import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op

# revision identifiers, used by Alembic.
revision = "0004_reviews_pricing"
down_revision = "0003_orders_routes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pricing_settings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "price_per_liter_dzd", sa.Numeric(precision=10, scale=2), nullable=False
        ),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "reviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=True),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column(
            "comment", sqlmodel.sql.sqltypes.AutoString(length=1000), nullable=True
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["customer_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_id"),
    )

    op.create_table(
        "notification_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=True),
        sa.Column(
            "channel",
            sa.Enum("sms", "whatsapp", name="notificationchannel"),
            nullable=False,
        ),
        sa.Column(
            "purpose",
            sa.Enum(
                "order_received",
                "confirmation_call_reminder",
                "review_request",
                "other",
                name="notificationpurpose",
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("sent", "failed", name="notificationstatus"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("notification_logs")
    op.drop_table("reviews")
    op.drop_table("pricing_settings")
    sa.Enum(name="notificationstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="notificationpurpose").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="notificationchannel").drop(op.get_bind(), checkfirst=True)
