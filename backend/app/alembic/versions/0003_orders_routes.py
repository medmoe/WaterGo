"""orders, routes, route_stops

Revision ID: 0003_orders_routes
Revises: 0002_locations_vehicles
Create Date: 2026-09-07

"""

import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op

# revision identifiers, used by Alembic.
revision = "0003_orders_routes"
down_revision = "0002_locations_vehicles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "routes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("vehicle_id", sa.Uuid(), nullable=False),
        sa.Column("driver_id", sa.Uuid(), nullable=False),
        sa.Column("planned_date", sa.Date(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("planned", "in_progress", "completed", name="routestatus"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["driver_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["vehicle_id"], ["vehicles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "orders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=True),
        sa.Column(
            "customer_phone",
            sqlmodel.sql.sqltypes.AutoString(length=20),
            nullable=False,
        ),
        sa.Column("location_id", sa.Uuid(), nullable=False),
        sa.Column("quantity_liters", sa.Integer(), nullable=False),
        sa.Column(
            "price_per_liter_dzd", sa.Numeric(precision=10, scale=2), nullable=False
        ),
        sa.Column(
            "total_price_dzd", sa.Numeric(precision=12, scale=2), nullable=False
        ),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "confirmed",
                "assigned",
                "en_route",
                "delivered",
                "cancelled",
                name="orderstatus",
            ),
            nullable=False,
        ),
        sa.Column(
            "requested_window_start", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("requested_window_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_by", sa.Uuid(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "cancelled_reason",
            sqlmodel.sql.sqltypes.AutoString(length=500),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["confirmed_by"], ["users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_orders_status"), "orders", ["status"], unique=False)

    op.create_table(
        "route_stops",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("route_id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payment_collected", sa.Boolean(), nullable=False),
        sa.Column("payment_collected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["route_id"], ["routes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_id"),
    )


def downgrade() -> None:
    op.drop_table("route_stops")
    op.drop_index(op.f("ix_orders_status"), table_name="orders")
    op.drop_table("orders")
    op.drop_table("routes")
    sa.Enum(name="orderstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="routestatus").drop(op.get_bind(), checkfirst=True)
