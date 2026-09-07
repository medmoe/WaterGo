from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.models import UserRole
from tests.utils.order import order_payload
from tests.utils.user import create_random_user, get_auth_headers_for_user

BASE = settings.API_V1_STR


def test_current_pricing_defaults_to_4(client: TestClient) -> None:
    r = client.get(f"{BASE}/pricing/current")
    assert r.status_code == 200
    body = r.json()
    assert float(body["price_per_liter_dzd"]) == 4.0
    assert body["is_default"] is True


def test_admin_can_set_price_and_orders_snapshot_it(
    client: TestClient, db: Session
) -> None:
    admin = create_random_user(db, role=UserRole.admin)
    r = client.post(
        f"{BASE}/pricing",
        headers=get_auth_headers_for_user(admin),
        json={"price_per_liter_dzd": "5.50"},
    )
    assert r.status_code == 200, r.text

    cur = client.get(f"{BASE}/pricing/current").json()
    assert float(cur["price_per_liter_dzd"]) == 5.5
    assert cur["is_default"] is False

    o = client.post(f"{BASE}/orders", json=order_payload(quantity_liters=200)).json()
    assert float(o["price_per_liter_dzd"]) == 5.5
    assert float(o["total_price_dzd"]) == 1100.0


def test_non_admin_cannot_set_price(client: TestClient, db: Session) -> None:
    dispatcher = create_random_user(db, role=UserRole.dispatcher)
    r = client.post(
        f"{BASE}/pricing",
        headers=get_auth_headers_for_user(dispatcher),
        json={"price_per_liter_dzd": "9"},
    )
    assert r.status_code == 403
