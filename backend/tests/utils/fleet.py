import random
import string
from datetime import UTC, datetime

from sqlmodel import Session

from app.models import (
    Order,
    OrderStatus,
    Route,
    RouteStatus,
    User,
    UserRole,
    Vehicle,
)
from app.services import orders as orders_service
from app.services import routes as routes_service
from tests.utils.order import create_random_order
from tests.utils.user import create_random_user


def random_plate() -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=8))


def create_vehicle(db: Session, *, capacity_liters: int = 3000) -> Vehicle:
    vehicle = Vehicle(plate_number=random_plate(), capacity_liters=capacity_liters)
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    return vehicle


def create_confirmed_order(db: Session) -> Order:
    order = create_random_order(db)
    orders_service.transition_status(db, order, OrderStatus.confirmed)
    return order


def build_route(
    db: Session,
    *,
    driver: User | None = None,
    vehicle: Vehicle | None = None,
    n_orders: int = 2,
) -> Route:
    driver = driver or create_random_user(db, role=UserRole.driver)
    vehicle = vehicle or create_vehicle(db)
    order_ids = [create_confirmed_order(db).id for _ in range(n_orders)]
    return routes_service.create_route(
        db,
        vehicle_id=vehicle.id,
        driver_id=driver.id,
        planned_date=datetime.now(UTC).date(),
        order_ids=order_ids,
    )


def deliver_order(db: Session) -> Order:
    """Take a brand-new order all the way to delivered."""
    driver = create_random_user(db, role=UserRole.driver)
    route = build_route(db, driver=driver, n_orders=1)
    routes_service.update_route(db, route, status=RouteStatus.in_progress)
    routes_service.mark_delivered(db, route.stops[0].id, driver)
    order = db.get(Order, route.stops[0].order_id)
    assert order and order.status == OrderStatus.delivered
    return order
