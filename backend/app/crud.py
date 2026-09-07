from typing import Any

from sqlmodel import Session, select

from app.models import User, UserCreate, UserRole, UserUpdate


def create_user(*, session: Session, user_create: UserCreate) -> User:
    db_obj = User.model_validate(user_create)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_user(*, session: Session, db_user: User, user_in: UserUpdate) -> Any:
    user_data = user_in.model_dump(exclude_unset=True)
    db_user.sqlmodel_update(user_data)
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user


def get_user_by_phone(*, session: Session, phone_number: str) -> User | None:
    statement = select(User).where(User.phone_number == phone_number)
    return session.exec(statement).first()


def get_or_create_user_by_phone(
    *, session: Session, phone_number: str, role: UserRole = UserRole.customer
) -> tuple[User, bool]:
    """Return (user, created). Self-serve signup always lands as ``customer``."""
    user = get_user_by_phone(session=session, phone_number=phone_number)
    if user:
        return user, False
    user = create_user(
        session=session,
        user_create=UserCreate(phone_number=phone_number, role=role),
    )
    return user, True
