"""locations, vehicles, maintenance_logs

Revision ID: 0002_locations_vehicles
Revises: 0001_users_and_postgis
Create Date: 2026-09-07

"""

import geoalchemy2
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op

# revision identifiers, used by Alembic.
revision = "0002_locations_vehicles"
down_revision = "0001_users_and_postgis"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vehicles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "plate_number",
            sqlmodel.sql.sqltypes.AutoString(length=32),
            nullable=False,
        ),
        sa.Column("capacity_liters", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("available", "on_route", "maintenance", name="vehiclestatus"),
            nullable=False,
        ),
        sa.Column("current_odometer_km", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plate_number"),
    )

    op.create_table(
        "maintenance_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("vehicle_id", sa.Uuid(), nullable=False),
        sa.Column(
            "type",
            sa.Enum("tire", "oil", "service", "other", name="maintenancetype"),
            nullable=False,
        ),
        sa.Column("odometer_km_at_event", sa.Integer(), nullable=False),
        sa.Column(
            "notes", sqlmodel.sql.sqltypes.AutoString(length=1000), nullable=True
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["vehicle_id"], ["vehicles.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "locations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column(
            "geom",
            geoalchemy2.types.Geography(
                geometry_type="POINT", srid=4326, spatial_index=False
            ),
            nullable=False,
        ),
        sa.Column(
            "landmark_text",
            sqlmodel.sql.sqltypes.AutoString(length=500),
            nullable=False,
        ),
        sa.Column(
            "commune", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False
        ),
        sa.Column("raw_lat", sa.Float(), nullable=False),
        sa.Column("raw_lng", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_locations_geom",
        "locations",
        ["geom"],
        postgresql_using="gist",
    )


def downgrade() -> None:
    op.drop_index("ix_locations_geom", table_name="locations")
    op.drop_table("locations")
    op.drop_table("maintenance_logs")
    op.drop_table("vehicles")
    sa.Enum(name="maintenancetype").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="vehiclestatus").drop(op.get_bind(), checkfirst=True)
