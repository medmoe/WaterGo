import pytest
from fastapi import HTTPException
from sqlmodel import Session

from app.models import OrderStatus, UserRole
from app.services import orders as orders_service
from tests.utils.order import create_random_order
from tests.utils.user import create_random_user


def _advance(db: Session, order, *statuses: OrderStatus) -> None:
    for s in statuses:
        orders_service.transition_status(db, order, s)


def test_full_happy_path(db: Session) -> None:
    order = create_random_order(db)
    dispatcher = create_random_user(db, role=UserRole.dispatcher)

    orders_service.transition_status(db, order, OrderStatus.confirmed, actor=dispatcher)
    assert order.status == OrderStatus.confirmed
    assert order.confirmed_by == dispatcher.id
    assert order.confirmed_at is not None

    _advance(
        db,
        order,
        OrderStatus.assigned,
        OrderStatus.en_route,
        OrderStatus.delivered,
    )
    assert order.status == OrderStatus.delivered


def test_cancel_from_pending_and_confirmed(db: Session) -> None:
    o1 = create_random_order(db)
    orders_service.transition_status(
        db, o1, OrderStatus.cancelled, reason="customer changed mind"
    )
    assert o1.status == OrderStatus.cancelled
    assert o1.cancelled_reason == "customer changed mind"

    o2 = create_random_order(db)
    orders_service.transition_status(db, o2, OrderStatus.confirmed)
    orders_service.transition_status(db, o2, OrderStatus.cancelled)
    assert o2.status == OrderStatus.cancelled


def test_cannot_cancel_after_dispatch(db: Session) -> None:
    order = create_random_order(db)
    _advance(db, order, OrderStatus.confirmed, OrderStatus.assigned)
    with pytest.raises(HTTPException) as exc:
        orders_service.transition_status(db, order, OrderStatus.cancelled)
    assert exc.value.status_code == 409


def test_cannot_skip_states(db: Session) -> None:
    order = create_random_order(db)
    with pytest.raises(HTTPException) as exc:
        orders_service.transition_status(db, order, OrderStatus.en_route)
    assert exc.value.status_code == 409


def test_unassign_returns_to_confirmed(db: Session) -> None:
    order = create_random_order(db)
    _advance(db, order, OrderStatus.confirmed, OrderStatus.assigned)
    orders_service.transition_status(db, order, OrderStatus.confirmed)
    assert order.status == OrderStatus.confirmed


def test_noop_transition_is_allowed(db: Session) -> None:
    order = create_random_order(db)
    orders_service.transition_status(db, order, OrderStatus.pending)
    assert order.status == OrderStatus.pending


def test_delivered_is_terminal(db: Session) -> None:
    order = create_random_order(db)
    _advance(
        db,
        order,
        OrderStatus.confirmed,
        OrderStatus.assigned,
        OrderStatus.en_route,
        OrderStatus.delivered,
    )
    with pytest.raises(HTTPException):
        orders_service.transition_status(db, order, OrderStatus.cancelled)
