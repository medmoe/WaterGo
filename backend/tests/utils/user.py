from datetime import timedelta

from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.core.security import create_access_token
from app.models import User, UserCreate
from tests.utils.utils import random_email


def get_auth_headers_for_user(user: User) -> dict[str, str]:
    """Mint a JWT directly for the given user, bypassing the login flow.

    ``get_current_user`` only validates the token, so tests can build valid
    credentials without going through the OTP endpoints.
    """
    token = create_access_token(
        user.id, expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {"Authorization": f"Bearer {token}"}


def create_random_user(db: Session, *, is_superuser: bool = False) -> User:
    user_in = UserCreate(email=random_email(), is_superuser=is_superuser)
    return crud.create_user(session=db, user_create=user_in)


def authentication_token_from_email(
    *, email: str, db: Session, is_superuser: bool = False
) -> dict[str, str]:
    """
    Return valid auth headers for the user with the given email.

    If the user doesn't exist it is created first.
    """
    user = crud.get_user_by_email(session=db, email=email)
    if not user:
        user_in = UserCreate(email=email, is_superuser=is_superuser)
        user = crud.create_user(session=db, user_create=user_in)
    return get_auth_headers_for_user(user)
