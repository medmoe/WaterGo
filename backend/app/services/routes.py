"""Route building and execution (section 8: Dispatch + Driver)."""

from datetime import UTC, date, datetime
from uuid import UUID

from fastapi import HTTPException
from sqlmodel import Session, col, func, select

from app.models import (
    Location,
    Order,
    OrderStatus,
    PendingMapPoint,
    Route,
    RouteStatus,
    RouteStop,
    User,
    UserRole,
    Vehicle,
    VehicleStatus,
)
from app.services import orders as orders_service


def pending_map(session: Session) -> list[PendingMapPoint]:
    """Confirmed orders not yet attached to a route, as geo points."""
    statement = (
        select(Order, Location)
        .join(Location, col(Order.location_id) == col(Location.id))
        .outerjoin(RouteStop, col(RouteStop.order_id) == col(Order.id))
        .where(Order.status == OrderStatus.confirmed)
        .where(col(RouteStop.id).is_(None))
        .order_by(col(Order.created_at))
    )
    rows = session.exec(statement).all()
    return [
        PendingMapPoint(
            order_id=order.id,
            raw_lat=loc.raw_lat,
            raw_lng=loc.raw_lng,
            customer_phone=order.customer_phone,
            quantity_liters=order.quantity_liters,
            landmark_text=loc.landmark_text,
            commune=loc.commune,
        )
        for order, loc in rows
    ]


def create_route(
    session: Session,
    *,
    vehicle_id: UUID,
    driver_id: UUID,
    planned_date: date,
    order_ids: list[UUID],
) -> Route:
    vehicle = session.get(Vehicle, vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    driver = session.get(User, driver_id)
    if not driver or driver.role != UserRole.driver:
        raise HTTPException(
            status_code=422, detail="driver_id must reference a user with role=driver"
        )

    if len(set(order_ids)) != len(order_ids):
        raise HTTPException(status_code=422, detail="Duplicate order ids")

    orders: list[Order] = []
    for oid in order_ids:
        order = session.get(Order, oid)
        if not order:
            raise HTTPException(status_code=404, detail=f"Order {oid} not found")
        if order.status != OrderStatus.confirmed:
            raise HTTPException(
                status_code=409,
                detail=f"Order {oid} is {order.status.value}, not confirmed",
            )
        if session.exec(select(RouteStop).where(RouteStop.order_id == oid)).first():
            raise HTTPException(
                status_code=409, detail=f"Order {oid} is already on a route"
            )
        orders.append(order)

    route = Route(
        vehicle_id=vehicle_id,
        driver_id=driver_id,
        planned_date=planned_date,
        status=RouteStatus.planned,
    )
    session.add(route)
    session.flush()

    for seq, order in enumerate(orders, start=1):
        session.add(
            RouteStop(route_id=route.id, order_id=order.id, sequence_number=seq)
        )
        orders_service.transition_status(session, order, OrderStatus.assigned)

    session.commit()
    session.refresh(route)
    return route


def update_route(
    session: Session,
    route: Route,
    *,
    status: RouteStatus | None = None,
    order_ids: list[UUID] | None = None,
) -> Route:
    if order_ids is not None:
        _reorder_stops(session, route, order_ids)
    if status is not None and status != route.status:
        _change_route_status(session, route, status)

    session.add(route)
    session.commit()
    session.refresh(route)
    return route


def _reorder_stops(session: Session, route: Route, order_ids: list[UUID]) -> None:
    current = {stop.order_id: stop for stop in route.stops}
    if set(order_ids) != set(current) or len(order_ids) != len(current):
        raise HTTPException(
            status_code=422,
            detail="order_ids must be a permutation of the route's current stops",
        )
    for seq, oid in enumerate(order_ids, start=1):
        current[oid].sequence_number = seq
        session.add(current[oid])


_ROUTE_FLOW: dict[RouteStatus, set[RouteStatus]] = {
    RouteStatus.planned: {RouteStatus.in_progress},
    RouteStatus.in_progress: {RouteStatus.completed},
    RouteStatus.completed: set(),
}


def _change_route_status(
    session: Session, route: Route, new_status: RouteStatus
) -> None:
    if new_status not in _ROUTE_FLOW[route.status]:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot move route from {route.status.value} to {new_status.value}",
        )

    vehicle = session.get(Vehicle, route.vehicle_id)

    if new_status == RouteStatus.in_progress:
        # route-level en_route: propagate to every stop's order (section 6)
        for stop in route.stops:
            if stop.order and stop.order.status == OrderStatus.assigned:
                orders_service.transition_status(
                    session, stop.order, OrderStatus.en_route
                )
        if vehicle:
            vehicle.status = VehicleStatus.on_route
            session.add(vehicle)
    elif new_status == RouteStatus.completed:
        if vehicle:
            vehicle.status = VehicleStatus.available
            session.add(vehicle)

    route.status = new_status
    session.add(route)


# --------------------------------------------------------------------------
# Driver side
# --------------------------------------------------------------------------


def todays_route(session: Session, driver: User) -> Route | None:
    today = datetime.now(UTC).date()
    statement = (
        select(Route)
        .where(Route.driver_id == driver.id)
        .where(Route.planned_date == today)
        .order_by(col(Route.created_at).desc())
    )
    return session.exec(statement).first()


def _stop_for_driver(session: Session, stop_id: UUID, driver: User) -> RouteStop:
    stop = session.get(RouteStop, stop_id)
    if not stop:
        raise HTTPException(status_code=404, detail="Stop not found")
    route = session.get(Route, stop.route_id)
    if not route or route.driver_id != driver.id:
        raise HTTPException(status_code=403, detail="Not your stop")
    return stop


def mark_delivered(session: Session, stop_id: UUID, driver: User) -> RouteStop:
    stop = _stop_for_driver(session, stop_id, driver)
    if stop.delivered_at is not None:
        return stop
    order = session.get(Order, stop.order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status != OrderStatus.en_route:
        raise HTTPException(
            status_code=409,
            detail="The route must be in progress before a stop can be delivered",
        )
    orders_service.transition_status(session, order, OrderStatus.delivered)
    stop.delivered_at = datetime.now(UTC)
    session.add(stop)
    session.commit()
    session.refresh(stop)
    return stop


def mark_payment_collected(session: Session, stop_id: UUID, driver: User) -> RouteStop:
    stop = _stop_for_driver(session, stop_id, driver)
    if stop.delivered_at is None:
        raise HTTPException(
            status_code=409, detail="Mark the stop delivered before collecting cash"
        )
    if not stop.payment_collected:
        stop.payment_collected = True
        stop.payment_collected_at = datetime.now(UTC)
        session.add(stop)
        session.commit()
        session.refresh(stop)
    return stop


def list_routes(
    session: Session, *, planned_date: date | None = None
) -> tuple[list[Route], int]:
    statement = select(Route)
    count_stmt = select(func.count()).select_from(Route)
    if planned_date is not None:
        statement = statement.where(Route.planned_date == planned_date)
        count_stmt = count_stmt.where(Route.planned_date == planned_date)
    statement = statement.order_by(col(Route.planned_date).desc())
    return list(session.exec(statement).all()), session.exec(count_stmt).one()
