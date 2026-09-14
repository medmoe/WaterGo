from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.models import OrderStatus, UserRole
from tests.utils.fleet import build_route, create_confirmed_order, create_vehicle
from tests.utils.order import create_random_order
from tests.utils.user import create_random_user, get_auth_headers_for_user

BASE = settings.API_V1_STR


def _dispatcher_headers(db: Session) -> dict[str, str]:
    return get_auth_headers_for_user(create_random_user(db, role=UserRole.dispatcher))


def test_list_drivers_is_dispatcher_accessible_and_scoped(
    client: TestClient, db: Session
) -> None:
    # a plain dispatcher (not admin) must be able to load this - it's what
    # regressed and 403'd the whole dispatch page for non-admin dispatchers
    headers = _dispatcher_headers(db)
    driver = create_random_user(db, role=UserRole.driver)
    inactive_driver = create_random_user(db, role=UserRole.driver)
    inactive_driver.is_active = False
    db.add(inactive_driver)
    create_random_user(db, role=UserRole.customer)
    db.commit()

    r = client.get(f"{BASE}/dispatch/drivers", headers=headers)
    assert r.status_code == 200
    ids = {u["id"] for u in r.json()}
    assert str(driver.id) in ids
    assert str(inactive_driver.id) not in ids
    assert all(u["role"] == "driver" for u in r.json())


def test_list_drivers_rejects_customer(client: TestClient, db: Session) -> None:
    customer = create_random_user(db, role=UserRole.customer)
    r = client.get(
        f"{BASE}/dispatch/drivers", headers=get_auth_headers_for_user(customer)
    )
    assert r.status_code == 403


def test_pending_map_only_lists_unrouted_confirmed(
    client: TestClient, db: Session
) -> None:
    headers = _dispatcher_headers(db)
    confirmed = create_confirmed_order(db)
    create_random_order(db)  # pending, should not appear

    r = client.get(f"{BASE}/dispatch/pending-map", headers=headers)
    assert r.status_code == 200
    order_ids = {p["order_id"] for p in r.json()}
    assert str(confirmed.id) in order_ids

    # once on a route it drops off the map
    driver = create_random_user(db, role=UserRole.driver)
    vehicle = create_vehicle(db)
    client.post(
        f"{BASE}/dispatch/routes",
        headers=headers,
        json={
            "vehicle_id": str(vehicle.id),
            "driver_id": str(driver.id),
            "planned_date": str(datetime.now(UTC).date()),
            "order_ids": [str(confirmed.id)],
        },
    )
    r = client.get(f"{BASE}/dispatch/pending-map", headers=headers)
    assert str(confirmed.id) not in {p["order_id"] for p in r.json()}


def test_create_route_assigns_orders_in_sequence(
    client: TestClient, db: Session
) -> None:
    headers = _dispatcher_headers(db)
    driver = create_random_user(db, role=UserRole.driver)
    vehicle = create_vehicle(db)
    o1 = create_confirmed_order(db)
    o2 = create_confirmed_order(db)

    r = client.post(
        f"{BASE}/dispatch/routes",
        headers=headers,
        json={
            "vehicle_id": str(vehicle.id),
            "driver_id": str(driver.id),
            "planned_date": str(datetime.now(UTC).date()),
            "order_ids": [str(o2.id), str(o1.id)],
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "planned"
    seqs = {s["order_id"]: s["sequence_number"] for s in body["stops"]}
    assert seqs[str(o2.id)] == 1
    assert seqs[str(o1.id)] == 2

    db.expire_all()
    from app.models import Order

    assert db.get(Order, o1.id).status == OrderStatus.assigned


def test_create_route_rejects_non_driver(client: TestClient, db: Session) -> None:
    headers = _dispatcher_headers(db)
    not_driver = create_random_user(db, role=UserRole.customer)
    vehicle = create_vehicle(db)
    order = create_confirmed_order(db)
    r = client.post(
        f"{BASE}/dispatch/routes",
        headers=headers,
        json={
            "vehicle_id": str(vehicle.id),
            "driver_id": str(not_driver.id),
            "planned_date": str(datetime.now(UTC).date()),
            "order_ids": [str(order.id)],
        },
    )
    assert r.status_code == 422


def test_create_route_rejects_unconfirmed_order(
    client: TestClient, db: Session
) -> None:
    headers = _dispatcher_headers(db)
    driver = create_random_user(db, role=UserRole.driver)
    vehicle = create_vehicle(db)
    pending = create_random_order(db)
    r = client.post(
        f"{BASE}/dispatch/routes",
        headers=headers,
        json={
            "vehicle_id": str(vehicle.id),
            "driver_id": str(driver.id),
            "planned_date": str(datetime.now(UTC).date()),
            "order_ids": [str(pending.id)],
        },
    )
    assert r.status_code == 409


def test_reorder_stops(client: TestClient, db: Session) -> None:
    headers = _dispatcher_headers(db)
    route = build_route(db, n_orders=3)
    original = [s.order_id for s in route.stops]
    reordered = [str(original[2]), str(original[0]), str(original[1])]

    r = client.patch(
        f"{BASE}/dispatch/routes/{route.id}",
        headers=headers,
        json={"order_ids": reordered},
    )
    assert r.status_code == 200
    seqs = {s["order_id"]: s["sequence_number"] for s in r.json()["stops"]}
    assert seqs[reordered[0]] == 1
    assert seqs[reordered[2]] == 3


def test_reorder_rejects_non_permutation(client: TestClient, db: Session) -> None:
    headers = _dispatcher_headers(db)
    route = build_route(db, n_orders=2)
    r = client.patch(
        f"{BASE}/dispatch/routes/{route.id}",
        headers=headers,
        json={"order_ids": [str(route.stops[0].order_id)]},
    )
    assert r.status_code == 422


def test_route_status_in_progress_propagates_en_route(
    client: TestClient, db: Session
) -> None:
    headers = _dispatcher_headers(db)
    route = build_route(db, n_orders=2)
    r = client.patch(
        f"{BASE}/dispatch/routes/{route.id}",
        headers=headers,
        json={"status": "in_progress"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "in_progress"
    for stop in r.json()["stops"]:
        assert stop["order"]["status"] == "en_route"


def test_route_status_cannot_skip(client: TestClient, db: Session) -> None:
    headers = _dispatcher_headers(db)
    route = build_route(db, n_orders=1)
    r = client.patch(
        f"{BASE}/dispatch/routes/{route.id}",
        headers=headers,
        json={"status": "completed"},
    )
    assert r.status_code == 409


def test_dispatch_requires_dispatcher_role(client: TestClient, db: Session) -> None:
    customer = create_random_user(db, role=UserRole.customer)
    r = client.get(
        f"{BASE}/dispatch/pending-map", headers=get_auth_headers_for_user(customer)
    )
    assert r.status_code == 403
