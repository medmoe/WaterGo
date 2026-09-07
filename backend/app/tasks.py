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
)
from app.services import notifications
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
