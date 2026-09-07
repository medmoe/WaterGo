from sqlmodel import Session, select

from app.models import (
    NotificationLog,
    NotificationPurpose,
    NotificationStatus,
)
from app.services import reviews as reviews_service
from app.tasks import send_notification
from tests.utils.fleet import deliver_order
from tests.utils.order import create_random_order


def _logs(db: Session, order_id, purpose: NotificationPurpose) -> list[NotificationLog]:
    db.expire_all()
    return list(
        db.exec(
            select(NotificationLog)
            .where(NotificationLog.order_id == order_id)
            .where(NotificationLog.purpose == purpose)
        ).all()
    )


def test_order_creation_enqueues_order_received(db: Session) -> None:
    order = create_random_order(db)
    logs = _logs(db, order.id, NotificationPurpose.order_received)
    assert len(logs) == 1
    assert logs[0].status == NotificationStatus.sent


def test_delivery_enqueues_review_request(db: Session) -> None:
    order = deliver_order(db)
    logs = _logs(db, order.id, NotificationPurpose.review_request)
    assert len(logs) == 1
    assert logs[0].status == NotificationStatus.sent


def test_send_notification_without_phone_logs_failed(db: Session) -> None:
    send_notification.run(None, NotificationPurpose.other.value)
    db.expire_all()
    row = db.exec(
        select(NotificationLog)
        .where(NotificationLog.purpose == NotificationPurpose.other)
        .order_by(NotificationLog.created_at.desc())
    ).first()
    assert row is not None
    assert row.status == NotificationStatus.failed


def test_review_token_roundtrip(db: Session) -> None:
    order = deliver_order(db)
    token = reviews_service.make_review_token(order.id)
    assert reviews_service.verify_review_token(order.id, token) is True
    assert reviews_service.verify_review_token(order.id, "bogus") is False
