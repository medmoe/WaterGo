from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.models import RouteStatus, UserRole
from app.services import routes as routes_service
from tests.utils.fleet import build_route
from tests.utils.user import create_random_user, get_auth_headers_for_user

BASE = settings.API_V1_STR


def test_cash_reconciliation_sums_per_driver(client: TestClient, db: Session) -> None:
    driver = create_random_user(db, role=UserRole.driver)
    route = build_route(db, driver=driver, n_orders=2)
    routes_service.update_route(db, route, status=RouteStatus.in_progress)
    # deliver both stops; collect cash on only the first
    routes_service.mark_delivered(db, route.stops[0].id, driver)
    routes_service.mark_payment_collected(db, route.stops[0].id, driver)
    routes_service.mark_delivered(db, route.stops[1].id, driver)

    expected_total = sum(s.order.total_price_dzd for s in route.stops if s.order)
    collected_total = route.stops[0].order.total_price_dzd

    admin = create_random_user(db, role=UserRole.admin)
    r = client.get(
        f"{BASE}/admin/reports/cash-reconciliation",
        headers=get_auth_headers_for_user(admin),
        params={"date": str(datetime.now(UTC).date())},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    row = next(x for x in body["rows"] if x["driver_id"] == str(driver.id))
    assert row["delivered_stops"] == 2
    assert float(row["expected_cash_dzd"]) == float(expected_total)
    assert row["collected_stops"] == 1
    assert float(row["collected_cash_dzd"]) == float(collected_total)
    assert float(body["total_collected_dzd"]) >= float(collected_total)


def test_cash_reconciliation_admin_only(client: TestClient, db: Session) -> None:
    dispatcher = create_random_user(db, role=UserRole.dispatcher)
    r = client.get(
        f"{BASE}/admin/reports/cash-reconciliation",
        headers=get_auth_headers_for_user(dispatcher),
    )
    assert r.status_code == 403


def test_cash_reconciliation_empty_day(client: TestClient, db: Session) -> None:
    admin = create_random_user(db, role=UserRole.admin)
    r = client.get(
        f"{BASE}/admin/reports/cash-reconciliation",
        headers=get_auth_headers_for_user(admin),
        params={"date": "2000-01-01"},
    )
    assert r.status_code == 200
    assert r.json()["rows"] == []
    assert float(r.json()["total_expected_dzd"]) == 0.0
