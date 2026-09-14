"""Celery tasks (section 11).

Discovered by ``app.worker`` via ``autodiscover_tasks(["app"])``.
"""

import logging
from uuid import UUID

from sqlmodel import Session

from app.core.db import engine
from app.models import (
    NotificationChannel,
    NotificationLog,
    NotificationPurpose,
    NotificationStatus,
    Order,
    OrderStatus,
    Route,
    UserRole,
)
from app.services import notifications, telegram
from app.services import reviews as reviews_service
from app.worker import celery_app

logger = logging.getLogger("app.tasks")


_MESSAGES = {
    NotificationPurpose.order_received: (
        "Batna Water : nous avons bien reçu votre commande. "
        "Un agent vous appellera pour confirmer."
    ),
    NotificationPurpose.confirmation_call_reminder: (
        "Batna Water : merci de rester joignable, un agent va vous appeler "
        "pour confirmer votre commande."
    ),
}


def _log(
    session: Session,
    *,
    order_id: UUID | None,
    channel: NotificationChannel,
    purpose: NotificationPurpose,
    status: NotificationStatus,
) -> None:
    session.add(
        NotificationLog(
            order_id=order_id,
            channel=channel,
            purpose=purpose,
            status=status,
        )
    )
    session.commit()


@celery_app.task(name="app.tasks.send_notification")
def send_notification(
    order_id: str | None,
    purpose: str,
    *,
    channel: str = NotificationChannel.sms.value,
    message: str | None = None,
) -> None:
    """Send an SMS/WhatsApp for ``order_id`` and record a NotificationLog row."""
    purpose_enum = NotificationPurpose(purpose)
    channel_enum = NotificationChannel(channel)
    oid = UUID(order_id) if order_id else None

    with Session(engine) as session:
        phone: str | None = None
        if oid is not None:
            order = session.get(Order, oid)
            phone = order.customer_phone if order else None

        text = message or _MESSAGES.get(purpose_enum)
        ok = False
        if phone and text:
            ok = notifications.send(phone, text)
        else:
            logger.warning(
                "send_notification skipped: order_id=%s phone=%s", order_id, phone
            )

        _log(
            session,
            order_id=oid,
            channel=channel_enum,
            purpose=purpose_enum,
            status=NotificationStatus.sent if ok else NotificationStatus.failed,
        )


@celery_app.task(name="app.tasks.request_review")
def request_review(order_id: str) -> None:
    """Ask the customer to rate a delivered order (section 14)."""
    oid = UUID(order_id)
    with Session(engine) as session:
        order = session.get(Order, oid)
        if not order or order.status != OrderStatus.delivered:
            logger.warning("request_review skipped: order %s not delivered", order_id)
            return
        link = reviews_service.review_link(oid)
        ok = notifications.send(
            order.customer_phone,
            f"Batna Water : merci pour votre commande ! Donnez votre avis : {link}",
        )
        _log(
            session,
            order_id=oid,
            channel=NotificationChannel.sms,
            purpose=NotificationPurpose.review_request,
            status=NotificationStatus.sent if ok else NotificationStatus.failed,
        )


# --------------------------------------------------------------------------
# Internal-team Telegram notifications (Part B)
# --------------------------------------------------------------------------


@celery_app.task(name="app.tasks.notify_dispatchers_new_order")
def notify_dispatchers_new_order(order_id: str) -> None:
    with Session(engine) as session:
        order = session.get(Order, UUID(order_id))
        if not order:
            return
        loc = order.location
        where = f"{loc.landmark_text}, {loc.commune}" if loc else "?"
        telegram.send_to_role(
            session,
            UserRole.dispatcher,
            f"🆕 Nouvelle commande : {order.quantity_liters} L\n"
            f"{where}\nTél : {order.customer_phone}",
        )


@celery_app.task(name="app.tasks.notify_driver_route_assigned")
def notify_driver_route_assigned(route_id: str) -> None:
    with Session(engine) as session:
        route = session.get(Route, UUID(route_id))
        if route is None or not route.driver or not route.driver.telegram_chat_id:
            return
        telegram.send_message(
            route.driver.telegram_chat_id,
            f"🚚 Nouvelle tournée pour le {route.planned_date} — "
            f"{len(route.stops)} arrêt(s).",
        )


@celery_app.task(name="app.tasks.notify_driver_route_started")
def notify_driver_route_started(route_id: str) -> None:
    """Ping the driver the moment the dispatcher starts their route.

    Not in the original interim-messaging spec (which only covers the
    "assigned" event), added because a route is very often created the day
    before it runs - the driver needs a nudge when it's actually time to go,
    not just when it was scheduled.
    """
    with Session(engine) as session:
        route = session.get(Route, UUID(route_id))
        if route is None or not route.driver or not route.driver.telegram_chat_id:
            return
        telegram.send_message(
            route.driver.telegram_chat_id,
            f"▶️ Votre tournée du {route.planned_date} démarre — "
            f"{len(route.stops)} arrêt(s). Bonne route !",
        )


@celery_app.task(name="app.tasks.sms_gateway_healthcheck")
def sms_gateway_healthcheck() -> None:
    """Alert dispatchers on Telegram if the SMS gateway is unreachable (A.5)."""
    healthy = notifications.provider_healthy()
    if healthy is None or healthy:
        return
    logger.error("SMS gateway health check failed")
    with Session(engine) as session:
        telegram.send_to_role(
            session,
            UserRole.dispatcher,
            "⚠️ La passerelle SMS est injoignable — les SMS clients (OTP, "
            "confirmations) ne partent plus. Vérifiez le téléphone.",
        )


def enqueue_notification(order_id: UUID, purpose: NotificationPurpose) -> None:
    """Fire-and-forget helper for the service layer; never raises."""
    try:
        send_notification.delay(str(order_id), purpose.value)
    except Exception:  # noqa: BLE001
        logger.exception("failed to enqueue send_notification for %s", order_id)


def enqueue_review_request(order_id: UUID) -> None:
    try:
        request_review.delay(str(order_id))
    except Exception:  # noqa: BLE001
        logger.exception("failed to enqueue request_review for %s", order_id)


def enqueue_new_order_notification(order_id: UUID) -> None:
    try:
        notify_dispatchers_new_order.delay(str(order_id))
    except Exception:  # noqa: BLE001
        logger.exception("failed to enqueue new-order Telegram for %s", order_id)


def enqueue_route_assigned_notification(route_id: UUID) -> None:
    try:
        notify_driver_route_assigned.delay(str(route_id))
    except Exception:  # noqa: BLE001
        logger.exception("failed to enqueue route-assigned Telegram for %s", route_id)


def enqueue_route_started_notification(route_id: UUID) -> None:
    try:
        notify_driver_route_started.delay(str(route_id))
    except Exception:  # noqa: BLE001
        logger.exception("failed to enqueue route-started Telegram for %s", route_id)
