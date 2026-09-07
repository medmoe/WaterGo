import uuid
from typing import Any

from fastapi import APIRouter

from app.api.deps import AdminUser, CurrentUserOptional, SessionDep
from app.models import ReviewCreate, ReviewPublic, ReviewsPublic
from app.services import reviews as reviews_service

router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.post("", response_model=ReviewPublic)
def create_review(
    *, session: SessionDep, current_user: CurrentUserOptional, body: ReviewCreate
) -> Any:
    """
    Leave a rating for a delivered order. Authorised either by the signed
    review token from the SMS link (no login) or by the logged-in customer /
    an admin.
    """
    return reviews_service.create_review(
        session,
        order_id=body.order_id,
        rating=body.rating,
        comment=body.comment,
        token=body.token,
        current_user=current_user,
    )


@router.get("", response_model=ReviewsPublic)
def list_reviews(
    session: SessionDep, _admin: AdminUser, order_id: uuid.UUID | None = None
) -> Any:
    """Reviews, for the owner's internal reporting (admin only)."""
    data = reviews_service.list_reviews(session, order_id=order_id)
    return ReviewsPublic(data=data, count=len(data))
