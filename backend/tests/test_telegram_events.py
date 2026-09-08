"""Telegram side-effects wired into order/route events + the gateway healthcheck."""

import pytest
from sqlmodel import Session

from app.models import OrderStatus, RouteStatus, UserRole
from app.services import routes as routes_service
from app.tasks import sms_gateway_healthcheck
from tests.utils.fleet import build_route, create_confirmed_order, create_vehicle
from tests.utils.order import create_random_order
from tests.utils.user import create_random_user


def _link(db: Session, user, chat_id: str) -> None:
    user.telegram_chat_id = chat_id
    db.add(user)
    db.commit()


def test_new_order_pings_linked_dispatchers(
    db: Session, no_telegram_http: list[tuple[str, str]]
) -> None:
    disp = create_random_user(db, role=UserRole.dispatcher)
    _link(db, disp, "disp-chat-new-order")

    create_random_order(db)

    hits = [t for c, t in no_telegram_http if c == "disp-chat-new-order"]
    assert any("Nouvelle commande" in t for t in hits)


def test_route_assignment_pings_linked_driver(
    db: Session, no_telegram_http: list[tuple[str, str]]
) -> None:
    driver = create_random_user(db, role=UserRole.driver)
    _link(db, driver, "driver-chat-route")
    vehicle = create_vehicle(db)
    order = create_confirmed_order(db)

    routes_service.create_route(
        db,
        vehicle_id=vehicle.id,
        driver_id=driver.id,
        planned_date=order.created_at.date(),
        order_ids=[order.id],
    )
    hits = [t for c, t in no_telegram_http if c == "driver-chat-route"]
    assert any("tournée" in t for t in hits)


def test_healthcheck_alerts_when_gateway_down(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    no_telegram_http: list[tuple[str, str]],
) -> None:
    disp = create_random_user(db, role=UserRole.dispatcher)
    _link(db, disp, "disp-chat-health")
    monkeypatch.setattr("app.services.notifications.provider_healthy", lambda: False)

    sms_gateway_healthcheck.run()

    hits = [t for c, t in no_telegram_http if c == "disp-chat-health"]
    assert any("passerelle sms" in t.lower() for t in hits)


def test_healthcheck_noop_for_stub_provider(
    monkeypatch: pytest.MonkeyPatch, no_telegram_http: list[tuple[str, str]]
) -> None:
    monkeypatch.setattr("app.services.notifications.provider_healthy", lambda: None)
    sms_gateway_healthcheck.run()
    assert no_telegram_http == []


def test_route_status_change_still_works(db: Session) -> None:
    # sanity: the extra enqueue in create_route didn't break the happy path
    route = build_route(db, n_orders=1)
    routes_service.update_route(db, route, status=RouteStatus.in_progress)
    db.refresh(route)
    assert route.status == RouteStatus.in_progress
    assert route.stops[0].order.status == OrderStatus.en_route
