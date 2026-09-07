import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Optional

from geoalchemy2 import Geography
from sqlalchemy import Column, DateTime, Index, Numeric
from sqlmodel import Field, Relationship, SQLModel


def get_datetime_utc() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Enums (section 5)
# ---------------------------------------------------------------------------


class UserRole(StrEnum):
    customer = "customer"
    dispatcher = "dispatcher"
    driver = "driver"
    admin = "admin"


class VehicleStatus(StrEnum):
    available = "available"
    on_route = "on_route"
    maintenance = "maintenance"


class MaintenanceType(StrEnum):
    tire = "tire"
    oil = "oil"
    service = "service"
    other = "other"


class OrderStatus(StrEnum):
    pending = "pending"
    confirmed = "confirmed"
    assigned = "assigned"
    en_route = "en_route"
    delivered = "delivered"
    cancelled = "cancelled"


class RouteStatus(StrEnum):
    planned = "planned"
    in_progress = "in_progress"
    completed = "completed"


class NotificationChannel(StrEnum):
    sms = "sms"
    whatsapp = "whatsapp"


class NotificationPurpose(StrEnum):
    order_received = "order_received"
    confirmation_call_reminder = "confirmation_call_reminder"
    review_request = "review_request"
    other = "other"


class NotificationStatus(StrEnum):
    sent = "sent"
    failed = "failed"


# ---------------------------------------------------------------------------
# Shared building blocks
# ---------------------------------------------------------------------------


class TimestampMixin(SQLModel):
    """created_at / updated_at, implied on every table (section 5)."""

    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
        nullable=False,
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
        sa_column_kwargs={"onupdate": get_datetime_utc},
        nullable=False,
    )


# ---------------------------------------------------------------------------
# users
# ---------------------------------------------------------------------------


class UserBase(SQLModel):
    phone_number: str = Field(unique=True, index=True, max_length=20)
    full_name: str | None = Field(default=None, max_length=255)
    role: UserRole = Field(default=UserRole.customer)
    is_active: bool = Field(default=True)


class UserCreate(UserBase):
    pass


class UserUpdate(SQLModel):
    phone_number: str | None = Field(default=None, max_length=20)
    full_name: str | None = Field(default=None, max_length=255)
    role: UserRole | None = None
    is_active: bool | None = None


class UserUpdateMe(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)


class User(UserBase, TimestampMixin, table=True):
    __tablename__ = "users"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

    locations: list["Location"] = Relationship(back_populates="user")
    orders: list["Order"] = Relationship(
        back_populates="customer",
        sa_relationship_kwargs={"foreign_keys": "Order.customer_id"},
    )
    routes: list["Route"] = Relationship(back_populates="driver")


class UserPublic(UserBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int


# ---------------------------------------------------------------------------
# locations
# ---------------------------------------------------------------------------


class LocationBase(SQLModel):
    landmark_text: str = Field(max_length=500)
    commune: str = Field(max_length=255)
    raw_lat: float
    raw_lng: float


class Location(LocationBase, TimestampMixin, table=True):
    __tablename__ = "locations"
    __table_args__ = (Index("ix_locations_geom", "geom", postgresql_using="gist"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID | None = Field(
        default=None, foreign_key="users.id", ondelete="SET NULL"
    )
    # PostGIS geography point. raw_lat/raw_lng are kept alongside for display
    # without PostGIS functions (section 5).
    geom: object | None = Field(
        default=None,
        sa_column=Column(
            Geography(geometry_type="POINT", srid=4326, spatial_index=False),
            nullable=False,
        ),
    )

    user: User | None = Relationship(back_populates="locations")
    orders: list["Order"] = Relationship(back_populates="location")


class LocationCreate(SQLModel):
    raw_lat: float = Field(ge=-90, le=90)
    raw_lng: float = Field(ge=-180, le=180)
    landmark_text: str = Field(max_length=500)
    commune: str = Field(max_length=255)


class LocationPublic(LocationBase):
    id: uuid.UUID


# ---------------------------------------------------------------------------
# vehicles
# ---------------------------------------------------------------------------


class VehicleBase(SQLModel):
    plate_number: str = Field(unique=True, max_length=32)
    capacity_liters: int
    status: VehicleStatus = Field(default=VehicleStatus.available)
    current_odometer_km: int = Field(default=0)


class VehicleCreate(VehicleBase):
    pass


class VehicleUpdate(SQLModel):
    plate_number: str | None = Field(default=None, max_length=32)
    capacity_liters: int | None = None
    status: VehicleStatus | None = None
    current_odometer_km: int | None = None


class Vehicle(VehicleBase, TimestampMixin, table=True):
    __tablename__ = "vehicles"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

    maintenance_logs: list["MaintenanceLog"] = Relationship(
        back_populates="vehicle", cascade_delete=True
    )
    routes: list["Route"] = Relationship(back_populates="vehicle")


class VehiclePublic(VehicleBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class VehiclesPublic(SQLModel):
    data: list[VehiclePublic]
    count: int


# ---------------------------------------------------------------------------
# maintenance_logs
# ---------------------------------------------------------------------------


class MaintenanceLogBase(SQLModel):
    type: MaintenanceType
    odometer_km_at_event: int
    notes: str | None = Field(default=None, max_length=1000)


class MaintenanceLogCreate(MaintenanceLogBase):
    pass


class MaintenanceLog(MaintenanceLogBase, TimestampMixin, table=True):
    __tablename__ = "maintenance_logs"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    vehicle_id: uuid.UUID = Field(foreign_key="vehicles.id", ondelete="CASCADE")

    vehicle: Vehicle | None = Relationship(back_populates="maintenance_logs")


class MaintenanceLogPublic(MaintenanceLogBase):
    id: uuid.UUID
    vehicle_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# pricing_settings
# ---------------------------------------------------------------------------


class PricingSettingBase(SQLModel):
    price_per_liter_dzd: Decimal = Field(
        sa_type=Numeric(10, 2),  # type: ignore
        nullable=False,
    )
    effective_from: datetime = Field(
        sa_type=DateTime(timezone=True),  # type: ignore
        nullable=False,
    )


class PricingSetting(PricingSettingBase, TimestampMixin, table=True):
    __tablename__ = "pricing_settings"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)


class PricingSettingCreate(SQLModel):
    price_per_liter_dzd: Decimal = Field(gt=0)
    effective_from: datetime | None = None


class PricingSettingPublic(SQLModel):
    id: uuid.UUID
    price_per_liter_dzd: Decimal
    effective_from: datetime


class PricingCurrent(SQLModel):
    price_per_liter_dzd: Decimal
    effective_from: datetime | None = None
    is_default: bool = False


# ---------------------------------------------------------------------------
# orders
# ---------------------------------------------------------------------------


class Order(TimestampMixin, table=True):
    __tablename__ = "orders"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    customer_id: uuid.UUID | None = Field(
        default=None, foreign_key="users.id", ondelete="SET NULL"
    )
    # Always stored on the order so dispatch can call regardless of account state.
    customer_phone: str = Field(max_length=20)
    location_id: uuid.UUID = Field(foreign_key="locations.id")
    quantity_liters: int
    price_per_liter_dzd: Decimal = Field(
        sa_type=Numeric(10, 2),  # type: ignore
        nullable=False,
    )
    total_price_dzd: Decimal = Field(
        sa_type=Numeric(12, 2),  # type: ignore
        nullable=False,
    )
    status: OrderStatus = Field(default=OrderStatus.pending, index=True)
    requested_window_start: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    requested_window_end: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    confirmed_by: uuid.UUID | None = Field(
        default=None, foreign_key="users.id", ondelete="SET NULL"
    )
    confirmed_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    cancelled_reason: str | None = Field(default=None, max_length=500)

    customer: User | None = Relationship(
        back_populates="orders",
        sa_relationship_kwargs={"foreign_keys": "Order.customer_id"},
    )
    location: Location | None = Relationship(back_populates="orders")
    route_stop: Optional["RouteStop"] = Relationship(
        back_populates="order", cascade_delete=True
    )
    review: Optional["Review"] = Relationship(
        back_populates="order", cascade_delete=True
    )


# A single order can't exceed what one tanker carries (section 7).
MAX_ORDER_LITERS = 4000


class OrderCreate(SQLModel):
    location: LocationCreate
    quantity_liters: int = Field(ge=1, le=MAX_ORDER_LITERS)
    customer_phone: str | None = Field(default=None, max_length=20)
    requested_window_start: datetime | None = None
    requested_window_end: datetime | None = None


class OrderCancel(SQLModel):
    cancelled_reason: str | None = Field(default=None, max_length=500)


class OrderPublic(SQLModel):
    id: uuid.UUID
    customer_id: uuid.UUID | None
    customer_phone: str
    location_id: uuid.UUID
    quantity_liters: int
    price_per_liter_dzd: Decimal
    total_price_dzd: Decimal
    status: OrderStatus
    requested_window_start: datetime | None
    requested_window_end: datetime | None
    confirmed_by: uuid.UUID | None
    confirmed_at: datetime | None
    cancelled_reason: str | None
    created_at: datetime
    updated_at: datetime
    location: LocationPublic | None = None


class OrdersPublic(SQLModel):
    data: list[OrderPublic]
    count: int


# ---------------------------------------------------------------------------
# routes
# ---------------------------------------------------------------------------


class Route(TimestampMixin, table=True):
    __tablename__ = "routes"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    vehicle_id: uuid.UUID = Field(foreign_key="vehicles.id")
    driver_id: uuid.UUID = Field(foreign_key="users.id")
    planned_date: date
    status: RouteStatus = Field(default=RouteStatus.planned)

    vehicle: Vehicle | None = Relationship(back_populates="routes")
    driver: User | None = Relationship(back_populates="routes")
    stops: list["RouteStop"] = Relationship(
        back_populates="route",
        cascade_delete=True,
        sa_relationship_kwargs={"order_by": "RouteStop.sequence_number"},
    )


# ---------------------------------------------------------------------------
# route_stops
# ---------------------------------------------------------------------------


class RouteStop(TimestampMixin, table=True):
    __tablename__ = "route_stops"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    route_id: uuid.UUID = Field(foreign_key="routes.id", ondelete="CASCADE")
    order_id: uuid.UUID = Field(
        foreign_key="orders.id", unique=True, ondelete="CASCADE"
    )
    sequence_number: int
    delivered_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    payment_collected: bool = Field(default=False)
    payment_collected_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )

    route: Route | None = Relationship(back_populates="stops")
    order: Order | None = Relationship(back_populates="route_stop")


class RouteCreate(SQLModel):
    vehicle_id: uuid.UUID
    driver_id: uuid.UUID
    planned_date: date
    order_ids: list[uuid.UUID] = Field(min_length=1)


class RouteUpdate(SQLModel):
    status: RouteStatus | None = None
    # A full re-ordering of the route's existing stops (a permutation of the
    # current order ids). Not for adding/removing stops.
    order_ids: list[uuid.UUID] | None = None


class RouteStopPublic(SQLModel):
    id: uuid.UUID
    route_id: uuid.UUID
    order_id: uuid.UUID
    sequence_number: int
    delivered_at: datetime | None
    payment_collected: bool
    payment_collected_at: datetime | None
    order: OrderPublic | None = None


class RoutePublic(SQLModel):
    id: uuid.UUID
    vehicle_id: uuid.UUID
    driver_id: uuid.UUID
    planned_date: date
    status: RouteStatus
    created_at: datetime
    updated_at: datetime
    stops: list[RouteStopPublic] = []


class RoutesPublic(SQLModel):
    data: list[RoutePublic]
    count: int


class PendingMapPoint(SQLModel):
    order_id: uuid.UUID
    raw_lat: float
    raw_lng: float
    customer_phone: str
    quantity_liters: int
    landmark_text: str
    commune: str


# ---------------------------------------------------------------------------
# reviews
# ---------------------------------------------------------------------------


class ReviewBase(SQLModel):
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=1000)


class Review(ReviewBase, TimestampMixin, table=True):
    __tablename__ = "reviews"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    order_id: uuid.UUID = Field(
        foreign_key="orders.id", unique=True, ondelete="CASCADE"
    )
    customer_id: uuid.UUID | None = Field(
        default=None, foreign_key="users.id", ondelete="SET NULL"
    )

    order: Order | None = Relationship(back_populates="review")


class ReviewCreate(ReviewBase):
    order_id: uuid.UUID
    token: str | None = None


class ReviewPublic(ReviewBase):
    id: uuid.UUID
    order_id: uuid.UUID
    customer_id: uuid.UUID | None
    created_at: datetime


class ReviewsPublic(SQLModel):
    data: list[ReviewPublic]
    count: int


# ---------------------------------------------------------------------------
# reports (section 13)
# ---------------------------------------------------------------------------


class DriverCashRow(SQLModel):
    driver_id: uuid.UUID
    driver_name: str | None
    driver_phone: str
    delivered_stops: int
    expected_cash_dzd: Decimal
    collected_stops: int
    collected_cash_dzd: Decimal


class CashReconciliationReport(SQLModel):
    date: date
    rows: list[DriverCashRow]
    total_expected_dzd: Decimal
    total_collected_dzd: Decimal


# ---------------------------------------------------------------------------
# notification_logs
# ---------------------------------------------------------------------------


class NotificationLog(TimestampMixin, table=True):
    __tablename__ = "notification_logs"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    order_id: uuid.UUID | None = Field(
        default=None, foreign_key="orders.id", ondelete="SET NULL"
    )
    channel: NotificationChannel
    purpose: NotificationPurpose
    status: NotificationStatus


# ---------------------------------------------------------------------------
# Auth / generic payloads
# ---------------------------------------------------------------------------


class Message(SQLModel):
    message: str


class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(SQLModel):
    sub: str | None = None


class OTPRequest(SQLModel):
    phone_number: str = Field(min_length=6, max_length=20)


class OTPVerify(SQLModel):
    phone_number: str = Field(min_length=6, max_length=20)
    code: str = Field(min_length=4, max_length=8)
