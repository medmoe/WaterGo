import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import col, func, select

from app import crud
from app.api.deps import (
    AdminUser,
    CurrentUser,
    SessionDep,
    get_current_admin,
)
from app.models import (
    Message,
    TelegramLinkCode,
    User,
    UserCreate,
    UserCreated,
    UserPublic,
    UserRole,
    UsersPublic,
    UserUpdate,
    UserUpdateMe,
)
from app.services import telegram

router = APIRouter(prefix="/users", tags=["users"])

_TELEGRAM_ROLES = {UserRole.dispatcher, UserRole.driver}


@router.get(
    "/",
    dependencies=[Depends(get_current_admin)],
    response_model=UsersPublic,
)
def read_users(session: SessionDep, skip: int = 0, limit: int = 100) -> Any:
    """
    Retrieve users.
    """
    count_statement = select(func.count()).select_from(User)
    count = session.exec(count_statement).one()

    statement = (
        select(User).order_by(col(User.created_at).desc()).offset(skip).limit(limit)
    )
    users = session.exec(statement).all()

    users_public = [UserPublic.model_validate(user) for user in users]
    return UsersPublic(data=users_public, count=count)


@router.post("/", dependencies=[Depends(get_current_admin)], response_model=UserCreated)
def create_user(*, session: SessionDep, user_in: UserCreate) -> Any:
    """
    Create a new user (dispatcher/driver/admin accounts are created here by an
    admin; customers self-register via OTP). For dispatcher/driver accounts the
    response includes a one-time ``telegram_link_code`` to hand over.
    """
    user = crud.get_user_by_phone(session=session, phone_number=user_in.phone_number)
    if user:
        raise HTTPException(
            status_code=400,
            detail="A user with this phone number already exists.",
        )
    user = crud.create_user(session=session, user_create=user_in)
    code = telegram.issue_link_code(user.id) if user.role in _TELEGRAM_ROLES else None
    return UserCreated(
        **UserPublic.model_validate(user).model_dump(), telegram_link_code=code
    )


@router.post("/{user_id}/telegram-link-code", response_model=TelegramLinkCode)
def reissue_telegram_link_code(
    *, session: SessionDep, _admin: AdminUser, user_id: uuid.UUID
) -> Any:
    """Issue a fresh Telegram linking code for a dispatcher/driver."""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.role not in _TELEGRAM_ROLES:
        raise HTTPException(
            status_code=400,
            detail="Only dispatcher/driver accounts use Telegram linking",
        )
    return TelegramLinkCode(code=telegram.issue_link_code(user.id))


@router.patch("/me", response_model=UserPublic)
def update_user_me(
    *, session: SessionDep, user_in: UserUpdateMe, current_user: CurrentUser
) -> Any:
    """
    Update own user.
    """
    user_data = user_in.model_dump(exclude_unset=True)
    current_user.sqlmodel_update(user_data)
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return current_user


@router.get("/me", response_model=UserPublic)
def read_user_me(current_user: CurrentUser) -> Any:
    """
    Get current user.
    """
    return current_user


@router.delete("/me", response_model=Message)
def delete_user_me(session: SessionDep, current_user: CurrentUser) -> Any:
    """
    Delete own user.
    """
    if current_user.role == UserRole.admin:
        raise HTTPException(
            status_code=403, detail="Admins are not allowed to delete themselves"
        )
    session.delete(current_user)
    session.commit()
    return Message(message="User deleted successfully")


@router.get("/{user_id}", response_model=UserPublic)
def read_user_by_id(
    user_id: uuid.UUID, session: SessionDep, current_user: CurrentUser
) -> Any:
    """
    Get a specific user by id.
    """
    user = session.get(User, user_id)
    if user == current_user:
        return user
    if current_user.role != UserRole.admin:
        raise HTTPException(
            status_code=403,
            detail="The user doesn't have enough privileges",
        )
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.patch(
    "/{user_id}",
    dependencies=[Depends(get_current_admin)],
    response_model=UserPublic,
)
def update_user(
    *,
    session: SessionDep,
    user_id: uuid.UUID,
    user_in: UserUpdate,
) -> Any:
    """
    Update a user.
    """
    db_user = session.get(User, user_id)
    if not db_user:
        raise HTTPException(
            status_code=404,
            detail="The user with this id does not exist in the system",
        )
    if user_in.phone_number:
        existing_user = crud.get_user_by_phone(
            session=session, phone_number=user_in.phone_number
        )
        if existing_user and existing_user.id != user_id:
            raise HTTPException(
                status_code=409,
                detail="A user with this phone number already exists",
            )

    return crud.update_user(session=session, db_user=db_user, user_in=user_in)


@router.delete("/{user_id}", dependencies=[Depends(get_current_admin)])
def delete_user(
    session: SessionDep, current_user: CurrentUser, user_id: uuid.UUID
) -> Message:
    """
    Delete a user.
    """
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user == current_user:
        raise HTTPException(
            status_code=403, detail="Admins are not allowed to delete themselves"
        )
    session.delete(user)
    session.commit()
    return Message(message="User deleted successfully")
