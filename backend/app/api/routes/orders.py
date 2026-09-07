import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import (
    CurrentUser,
    CurrentUserOptional,
    DispatcherUser,
    SessionDep,
)
from app.models import (
    Order,
    OrderCancel,
    OrderCreate,
    OrderPublic,
    OrdersPublic,
    OrderStatus,
    UserRole,
)
from app.services import orders as orders_service

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("", response_model=OrderPublic)
def create_order(
    *, session: SessionDep, current_user: CurrentUserOptional, order_in: OrderCreate
) -> Any:
    """
    Place an order. Works for a logged-in customer or, if guest checkout is
    allowed, an anonymous caller who supplies ``customer_phone``.
    """
    return orders_service.create_order(
        session, order_in=order_in, current_user=current_user
    )


@router.get("", response_model=OrdersPublic)
def list_orders(
    session: SessionDep,
    current_user: CurrentUser,
    status: OrderStatus | None = None,
    mine: bool = Query(default=False),
) -> Any:
    """
    List orders. Customers only ever see their own; dispatchers/admins see all
    unless ``mine=true``.
    """
    data, count = orders_service.list_orders(
        session, requester=current_user, status=status, mine=mine
    )
    return OrdersPublic(data=data, count=count)


@router.get("/{order_id}", response_model=OrderPublic)
def read_order(
    session: SessionDep,
    order_id: uuid.UUID,
    current_user: CurrentUserOptional,
    phone: str | None = None,
) -> Any:
    """
    Order detail. A logged-in customer may read their own orders; dispatch may
    read any; a guest may read an order by passing the matching ``phone``.
    """
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if current_user and current_user.role in (UserRole.dispatcher, UserRole.admin):
        return order
    if current_user and order.customer_id == current_user.id:
        return order
    if phone and phone == order.customer_phone:
        return order
    raise HTTPException(status_code=403, detail="Not enough permissions")


@router.patch("/{order_id}/confirm", response_model=OrderPublic)
def confirm_order(
    session: SessionDep, order_id: uuid.UUID, dispatcher: DispatcherUser
) -> Any:
    """Dispatcher confirms an order after the phone call (status -> confirmed)."""
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return orders_service.transition_status(
        session, order, OrderStatus.confirmed, actor=dispatcher
    )


@router.patch("/{order_id}/cancel", response_model=OrderPublic)
def cancel_order(
    *,
    session: SessionDep,
    order_id: uuid.UUID,
    current_user: CurrentUser,
    body: OrderCancel,
) -> Any:
    """Cancel an order. Allowed from pending/confirmed only (section 6)."""
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    is_staff = current_user.role in (UserRole.dispatcher, UserRole.admin)
    if not is_staff and order.customer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    return orders_service.transition_status(
        session, order, OrderStatus.cancelled, reason=body.cancelled_reason
    )
