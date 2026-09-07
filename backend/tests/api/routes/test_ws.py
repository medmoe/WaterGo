from datetime import timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.core.security import create_access_token
from app.models import UserRole
from tests.utils.fleet import create_vehicle
from tests.utils.order import create_random_order
from tests.utils.user import create_random_user

BASE = settings.API_V1_STR


def _token(user_id: object) -> str:
    return create_access_token(user_id, expires_delta=timedelta(minutes=5))


def test_dispatch_ws_rejects_non_dispatcher(client: TestClient, db: Session) -> None:
    customer = create_random_user(db, role=UserRole.customer)
    try:
        with client.websocket_connect(
            f"{BASE}/ws/dispatch?token={_token(customer.id)}"
        ):
            pass
        raised = False
    except Exception:
        raised = True
    assert raised


def test_dispatch_ws_receives_order_confirmed(client: TestClient, db: Session) -> None:
    dispatcher = create_random_user(db, role=UserRole.dispatcher)
    order = create_random_order(db)

    with client.websocket_connect(
        f"{BASE}/ws/dispatch?token={_token(dispatcher.id)}"
    ) as ws:
        r = client.patch(
            f"{BASE}/orders/{order.id}/confirm",
            headers={"Authorization": f"Bearer {_token(dispatcher.id)}"},
        )
        assert r.status_code == 200
        event = ws.receive_json()
        assert event["type"] == "order_confirmed"
        assert event["order_id"] == str(order.id)


def test_driver_ws_receives_route_assignment(client: TestClient, db: Session) -> None:
    from datetime import UTC, datetime

    dispatcher = create_random_user(db, role=UserRole.dispatcher)
    driver = create_random_user(db, role=UserRole.driver)
    vehicle = create_vehicle(db)
    order = create_random_order(db)
    client.patch(
        f"{BASE}/orders/{order.id}/confirm",
        headers={"Authorization": f"Bearer {_token(dispatcher.id)}"},
    )

    with client.websocket_connect(
        f"{BASE}/ws/driver/{driver.id}?token={_token(driver.id)}"
    ) as ws:
        r = client.post(
            f"{BASE}/dispatch/routes",
            headers={"Authorization": f"Bearer {_token(dispatcher.id)}"},
            json={
                "vehicle_id": str(vehicle.id),
                "driver_id": str(driver.id),
                "planned_date": str(datetime.now(UTC).date()),
                "order_ids": [str(order.id)],
            },
        )
        assert r.status_code == 200, r.text
        event = ws.receive_json()
        assert event["type"] == "route_assigned"
        assert event["route_id"] == r.json()["id"]


def test_driver_ws_rejects_other_driver(client: TestClient, db: Session) -> None:
    d1 = create_random_user(db, role=UserRole.driver)
    d2 = create_random_user(db, role=UserRole.driver)
    try:
        with client.websocket_connect(
            f"{BASE}/ws/driver/{d1.id}?token={_token(d2.id)}"
        ):
            pass
        raised = False
    except Exception:
        raised = True
    assert raised
