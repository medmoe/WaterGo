from datetime import timedelta

from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.core.security import create_access_token
from app.models import User, UserCreate, UserRole
from tests.utils.utils import random_phone_number


def get_auth_headers_for_user(user: User) -> dict[str, str]:
    """Mint a JWT directly for the given user, bypassing the OTP flow.

    ``get_current_user`` only validates the token, so tests can build valid
    credentials without going through the OTP endpoints.
    """
    token = create_access_token(
        user.id, expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {"Authorization": f"Bearer {token}"}


def create_random_user(db: Session, *, role: UserRole = UserRole.customer) -> User:
    user_in = UserCreate(phone_number=random_phone_number(), role=role)
    return crud.create_user(session=db, user_create=user_in)


def authentication_token_from_phone(
    *, db: Session, phone_number: str, role: UserRole = UserRole.customer
) -> dict[str, str]:
    """
    Return valid auth headers for the user with the given phone number.

    If the user doesn't exist it is created first.
    """
    user = crud.get_user_by_phone(session=db, phone_number=phone_number)
    if not user:
        user_in = UserCreate(phone_number=phone_number, role=role)
        user = crud.create_user(session=db, user_create=user_in)
    return get_auth_headers_for_user(user)
