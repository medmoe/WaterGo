"""Order lifecycle (sections 6 and 8).

The status state machine lives entirely in :func:`transition_status`; routers
never set ``Order.status`` directly.
"""

from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import func
from sqlmodel import Session, col, select

from app.models import (
    Location,
    Order,
    OrderCreate,
    OrderStatus,
    User,
    UserRole,
)
from app.services import pricing
from app.services.ws import manager as ws_manager

# section 6:
#   pending -> confirmed -> assigned -> en_route -> delivered
#   pending -> cancelled ;  confirmed -> cancelled
# `assigned -> confirmed` is an un-assign step (removing an order from a route,
# section 8 PATCH /dispatch/routes); it is not drawn in section 6 but is needed
# for route editing.
ALLOWED_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.pending: {OrderStatus.confirmed, OrderStatus.cancelled},
    OrderStatus.confirmed: {OrderStatus.assigned, OrderStatus.cancelled},
    OrderStatus.assigned: {OrderStatus.en_route, OrderStatus.confirmed},
    OrderStatus.en_route: {OrderStatus.delivered},
    OrderStatus.delivered: set(),
    OrderStatus.cancelled: set(),
}


def _point(lat: float, lng: float) -> object:
    # geography(Point, 4326); PostGIS takes (lng, lat).
    return func.ST_SetSRID(func.ST_MakePoint(lng, lat), 4326)


def create_order(
    session: Session, *, order_in: OrderCreate, current_user: User | None
) -> Order:
    """Create a pending order. Snapshots the active per-liter price."""
    phone = order_in.customer_phone or (
        current_user.phone_number if current_user else None
    )
    if not phone:
        raise HTTPException(
            status_code=422,
            detail="customer_phone is required for guest orders",
        )

    location = Location(
        user_id=current_user.id if current_user else None,
        raw_lat=order_in.location.raw_lat,
        raw_lng=order_in.location.raw_lng,
        landmark_text=order_in.location.landmark_text,
        commune=order_in.location.commune,
        geom=_point(order_in.location.raw_lat, order_in.location.raw_lng),
    )
    session.add(location)
    session.flush()

    price = pricing.get_current_price(session)
    order = Order(
        customer_id=current_user.id if current_user else None,
        customer_phone=phone,
        location_id=location.id,
        quantity_liters=order_in.quantity_liters,
        price_per_liter_dzd=price,
        total_price_dzd=price * order_in.quantity_liters,
        status=OrderStatus.pending,
        requested_window_start=order_in.requested_window_start,
        requested_window_end=order_in.requested_window_end,
    )
    session.add(order)
    session.commit()
    session.refresh(order)

    from app.models import NotificationPurpose
    from app.tasks import enqueue_notification

    enqueue_notification(order.id, NotificationPurpose.order_received)
    return order


def transition_status(
    session: Session,
    order: Order,
    new_status: OrderStatus,
    *,
    actor: User | None = None,
    reason: str | None = None,
) -> Order:
    """Move ``order`` to ``new_status``, enforcing section 6 and applying the
    side effects for that target status. This is the only place order status
    changes."""
    if new_status == order.status:
        return order
    if new_status not in ALLOWED_TRANSITIONS[order.status]:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Cannot move order from {order.status.value} to {new_status.value}"
            ),
        )

    if new_status == OrderStatus.confirmed and order.status == OrderStatus.pending:
        order.confirmed_by = actor.id if actor else None
        order.confirmed_at = datetime.now(UTC)
    elif new_status == OrderStatus.confirmed and order.status == OrderStatus.assigned:
        # un-assign: keep the original confirmation metadata
        pass
    elif new_status == OrderStatus.cancelled:
        order.cancelled_reason = reason

    order.status = new_status
    session.add(order)
    session.commit()
    session.refresh(order)

    if new_status == OrderStatus.confirmed:
        ws_manager.notify_dispatch(
            {"type": "order_confirmed", "order_id": str(order.id)}
        )

    return order


def list_orders(
    session: Session,
    *,
    requester: User,
    status: OrderStatus | None = None,
    mine: bool = False,
) -> tuple[list[Order], int]:
    statement = select(Order)
    count_stmt = select(func.count()).select_from(Order)

    is_staff = requester.role in (UserRole.dispatcher, UserRole.admin)
    if not is_staff or mine:
        statement = statement.where(Order.customer_id == requester.id)
        count_stmt = count_stmt.where(Order.customer_id == requester.id)
    if status is not None:
        statement = statement.where(Order.status == status)
        count_stmt = count_stmt.where(Order.status == status)

    statement = statement.order_by(col(Order.created_at).desc())
    orders = list(session.exec(statement).all())
    count = session.exec(count_stmt).one()
    return orders, count
