from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.models import OrderStatus, UserRole
from tests.utils.order import create_random_order, order_payload
from tests.utils.user import create_random_user, get_auth_headers_for_user
from tests.utils.utils import random_phone_number

BASE = settings.API_V1_STR


def test_guest_can_place_order(client: TestClient) -> None:
    phone = random_phone_number()
    r = client.post(
        f"{BASE}/orders", json=order_payload(quantity_liters=1500, customer_phone=phone)
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "pending"
    assert body["customer_id"] is None
    assert body["customer_phone"] == phone
    assert body["quantity_liters"] == 1500
    # price snapshot: default 4 DZD/L
    assert float(body["price_per_liter_dzd"]) == 4.0
    assert float(body["total_price_dzd"]) == 6000.0
    assert body["location"]["commune"] == "Batna"


def test_logged_in_customer_order_links_account(
    client: TestClient, db: Session
) -> None:
    customer = create_random_user(db, role=UserRole.customer)
    headers = get_auth_headers_for_user(customer)
    payload = order_payload()
    payload.pop("customer_phone")
    r = client.post(f"{BASE}/orders", json=payload, headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["customer_id"] == str(customer.id)
    assert body["customer_phone"] == customer.phone_number


def test_order_quantity_capped_at_4000(client: TestClient) -> None:
    r = client.post(f"{BASE}/orders", json=order_payload(quantity_liters=5000))
    assert r.status_code == 422


def test_get_order_by_id_guest_needs_phone(client: TestClient, db: Session) -> None:
    order = create_random_order(db)
    r = client.get(f"{BASE}/orders/{order.id}")
    assert r.status_code == 403
    r = client.get(f"{BASE}/orders/{order.id}", params={"phone": order.customer_phone})
    assert r.status_code == 200
    assert r.json()["id"] == str(order.id)


def test_customer_sees_only_their_orders(client: TestClient, db: Session) -> None:
    c1 = create_random_user(db, role=UserRole.customer)
    c2 = create_random_user(db, role=UserRole.customer)
    create_random_order(db, customer=c1)
    create_random_order(db, customer=c1)
    create_random_order(db, customer=c2)

    r = client.get(f"{BASE}/orders", headers=get_auth_headers_for_user(c1))
    assert r.status_code == 200
    assert r.json()["count"] == 2

    other = create_random_order(db, customer=c2)
    r = client.get(f"{BASE}/orders/{other.id}", headers=get_auth_headers_for_user(c1))
    assert r.status_code == 403


def test_dispatcher_sees_all_and_can_filter_status(
    client: TestClient, db: Session
) -> None:
    dispatcher = create_random_user(db, role=UserRole.dispatcher)
    headers = get_auth_headers_for_user(dispatcher)
    o = create_random_order(db)
    create_random_order(db)

    r = client.get(f"{BASE}/orders", headers=headers, params={"status": "pending"})
    assert r.status_code == 200
    assert r.json()["count"] >= 2

    client.patch(f"{BASE}/orders/{o.id}/confirm", headers=headers)
    r = client.get(f"{BASE}/orders", headers=headers, params={"status": "confirmed"})
    ids = [row["id"] for row in r.json()["data"]]
    assert str(o.id) in ids


def test_confirm_requires_dispatcher(client: TestClient, db: Session) -> None:
    customer = create_random_user(db, role=UserRole.customer)
    order = create_random_order(db, customer=customer)
    r = client.patch(
        f"{BASE}/orders/{order.id}/confirm",
        headers=get_auth_headers_for_user(customer),
    )
    assert r.status_code == 403


def test_confirm_sets_metadata(client: TestClient, db: Session) -> None:
    dispatcher = create_random_user(db, role=UserRole.dispatcher)
    order = create_random_order(db)
    r = client.patch(
        f"{BASE}/orders/{order.id}/confirm",
        headers=get_auth_headers_for_user(dispatcher),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "confirmed"
    assert body["confirmed_by"] == str(dispatcher.id)
    assert body["confirmed_at"] is not None


def test_customer_can_cancel_own_pending_order(client: TestClient, db: Session) -> None:
    customer = create_random_user(db, role=UserRole.customer)
    order = create_random_order(db, customer=customer)
    r = client.patch(
        f"{BASE}/orders/{order.id}/cancel",
        headers=get_auth_headers_for_user(customer),
        json={"cancelled_reason": "no longer needed"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"
    assert r.json()["cancelled_reason"] == "no longer needed"


def test_cancel_rejected_after_assigned(client: TestClient, db: Session) -> None:
    from app.services import orders as orders_service

    dispatcher = create_random_user(db, role=UserRole.dispatcher)
    order = create_random_order(db)
    orders_service.transition_status(db, order, OrderStatus.confirmed)
    orders_service.transition_status(db, order, OrderStatus.assigned)
    r = client.patch(
        f"{BASE}/orders/{order.id}/cancel",
        headers=get_auth_headers_for_user(dispatcher),
        json={},
    )
    assert r.status_code == 409
