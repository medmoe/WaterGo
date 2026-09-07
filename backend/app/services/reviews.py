"""Reviews (section 14).

Public review links carry a signed token tied to the order id - no login
needed. Reviews are internal reporting only (no public display in MVP).
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from fastapi import HTTPException
from jwt.exceptions import InvalidTokenError
from sqlmodel import Session, col, select

from app.core import security
from app.core.config import settings
from app.models import Order, OrderStatus, Review, User, UserRole

REVIEW_TOKEN_PURPOSE = "review"
REVIEW_TOKEN_TTL_DAYS = 14


def make_review_token(order_id: UUID) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": str(order_id),
            "purpose": REVIEW_TOKEN_PURPOSE,
            "nbf": now,
            "exp": now + timedelta(days=REVIEW_TOKEN_TTL_DAYS),
        },
        settings.SECRET_KEY,
        algorithm=security.ALGORITHM,
    )


def verify_review_token(order_id: UUID, token: str) -> bool:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
    except InvalidTokenError:
        return False
    return payload.get("purpose") == REVIEW_TOKEN_PURPOSE and payload.get("sub") == str(
        order_id
    )


def review_link(order_id: UUID) -> str:
    return (
        f"{settings.FRONTEND_HOST}/review/{order_id}"
        f"?token={make_review_token(order_id)}"
    )


def create_review(
    session: Session,
    *,
    order_id: UUID,
    rating: int,
    comment: str | None,
    token: str | None = None,
    current_user: User | None = None,
) -> Review:
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status != OrderStatus.delivered:
        raise HTTPException(
            status_code=409, detail="Only delivered orders can be reviewed"
        )

    authorised = bool(token and verify_review_token(order_id, token))
    if not authorised and current_user is not None:
        authorised = (
            current_user.role == UserRole.admin or order.customer_id == current_user.id
        )
    if not authorised:
        raise HTTPException(status_code=403, detail="Not allowed to review this order")

    if session.exec(select(Review).where(Review.order_id == order_id)).first():
        raise HTTPException(
            status_code=409, detail="This order has already been reviewed"
        )

    review = Review(
        order_id=order_id,
        customer_id=order.customer_id or (current_user.id if current_user else None),
        rating=rating,
        comment=comment,
    )
    session.add(review)
    session.commit()
    session.refresh(review)
    return review


def list_reviews(session: Session, *, order_id: UUID | None = None) -> list[Review]:
    statement = select(Review).order_by(col(Review.created_at).desc())
    if order_id is not None:
        statement = statement.where(Review.order_id == order_id)
    return list(session.exec(statement).all())
