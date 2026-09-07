from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.models import Route, RouteStatus, UserRole
from app.services import routes as routes_service
from tests.utils.fleet import build_route
from tests.utils.user import create_random_user, get_auth_headers_for_user

BASE = settings.API_V1_STR


def test_todays_route_returns_drivers_route(client: TestClient, db: Session) -> None:
    driver = create_random_user(db, role=UserRole.driver)
    route = build_route(db, driver=driver, n_orders=2)

    r = client.get(
        f"{BASE}/driver/routes/today", headers=get_auth_headers_for_user(driver)
    )
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == str(route.id)
    assert [s["sequence_number"] for s in body["stops"]] == [1, 2]
    assert body["stops"][0]["order"]["location"]["commune"] == "Batna"


def test_todays_route_empty_when_none(client: TestClient, db: Session) -> None:
    driver = create_random_user(db, role=UserRole.driver)
    r = client.get(
        f"{BASE}/driver/routes/today", headers=get_auth_headers_for_user(driver)
    )
    assert r.status_code == 204


def test_mark_delivered_requires_in_progress(client: TestClient, db: Session) -> None:
    driver = create_random_user(db, role=UserRole.driver)
    route = build_route(db, driver=driver, n_orders=1)
    stop_id = route.stops[0].id
    headers = get_auth_headers_for_user(driver)

    # route still 'planned' -> order is 'assigned', not en_route
    r = client.patch(f"{BASE}/driver/stops/{stop_id}/delivered", headers=headers)
    assert r.status_code == 409

    routes_service.update_route(db, route, status=RouteStatus.in_progress)
    r = client.patch(f"{BASE}/driver/stops/{stop_id}/delivered", headers=headers)
    assert r.status_code == 200
    assert r.json()["delivered_at"] is not None
    assert r.json()["order"]["status"] == "delivered"


def test_payment_requires_delivery_first(client: TestClient, db: Session) -> None:
    driver = create_random_user(db, role=UserRole.driver)
    route = build_route(db, driver=driver, n_orders=1)
    stop_id = route.stops[0].id
    headers = get_auth_headers_for_user(driver)

    r = client.patch(
        f"{BASE}/driver/stops/{stop_id}/payment-collected", headers=headers
    )
    assert r.status_code == 409

    routes_service.update_route(db, route, status=RouteStatus.in_progress)
    client.patch(f"{BASE}/driver/stops/{stop_id}/delivered", headers=headers)
    r = client.patch(
        f"{BASE}/driver/stops/{stop_id}/payment-collected", headers=headers
    )
    assert r.status_code == 200
    assert r.json()["payment_collected"] is True
    assert r.json()["payment_collected_at"] is not None


def test_driver_cannot_touch_another_drivers_stop(
    client: TestClient, db: Session
) -> None:
    route = build_route(db, n_orders=1)
    intruder = create_random_user(db, role=UserRole.driver)
    r = client.patch(
        f"{BASE}/driver/stops/{route.stops[0].id}/delivered",
        headers=get_auth_headers_for_user(intruder),
    )
    assert r.status_code == 403


def test_driver_endpoints_reject_non_driver(client: TestClient, db: Session) -> None:
    customer = create_random_user(db, role=UserRole.customer)
    r = client.get(
        f"{BASE}/driver/routes/today", headers=get_auth_headers_for_user(customer)
    )
    assert r.status_code == 403


def test_completing_route_frees_vehicle(client: TestClient, db: Session) -> None:
    from app.models import Vehicle, VehicleStatus

    driver = create_random_user(db, role=UserRole.driver)
    route = build_route(db, driver=driver, n_orders=1)
    routes_service.update_route(db, route, status=RouteStatus.in_progress)
    db.refresh(route)
    vehicle = db.get(Vehicle, route.vehicle_id)
    assert vehicle and vehicle.status == VehicleStatus.on_route

    headers = get_auth_headers_for_user(driver)
    client.patch(f"{BASE}/driver/stops/{route.stops[0].id}/delivered", headers=headers)
    routes_service.update_route(db, route, status=RouteStatus.completed)
    db.refresh(vehicle)
    assert vehicle.status == VehicleStatus.available
    assert db.get(Route, route.id).status == RouteStatus.completed
