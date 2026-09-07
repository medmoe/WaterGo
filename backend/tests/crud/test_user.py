from fastapi.encoders import jsonable_encoder
from sqlmodel import Session

from app import crud
from app.models import User, UserCreate, UserRole, UserUpdate
from tests.utils.utils import random_phone_number


def test_create_user(db: Session) -> None:
    phone = random_phone_number()
    user_in = UserCreate(phone_number=phone)
    user = crud.create_user(session=db, user_create=user_in)
    assert user.phone_number == phone
    assert user.role == UserRole.customer


def test_get_user_by_phone(db: Session) -> None:
    phone = random_phone_number()
    crud.create_user(session=db, user_create=UserCreate(phone_number=phone))
    found = crud.get_user_by_phone(session=db, phone_number=phone)
    assert found
    assert found.phone_number == phone


def test_get_or_create_user_by_phone(db: Session) -> None:
    phone = random_phone_number()
    user, created = crud.get_or_create_user_by_phone(session=db, phone_number=phone)
    assert created is True
    assert user.role == UserRole.customer
    same, created_again = crud.get_or_create_user_by_phone(
        session=db, phone_number=phone
    )
    assert created_again is False
    assert same.id == user.id


def test_check_if_user_is_active_inactive(db: Session) -> None:
    user_in = UserCreate(phone_number=random_phone_number(), is_active=False)
    user = crud.create_user(session=db, user_create=user_in)
    assert user.is_active is False


def test_check_if_user_is_admin(db: Session) -> None:
    user_in = UserCreate(phone_number=random_phone_number(), role=UserRole.admin)
    user = crud.create_user(session=db, user_create=user_in)
    assert user.role == UserRole.admin


def test_get_user(db: Session) -> None:
    user_in = UserCreate(phone_number=random_phone_number(), role=UserRole.dispatcher)
    user = crud.create_user(session=db, user_create=user_in)
    user_2 = db.get(User, user.id)
    assert user_2
    assert user.phone_number == user_2.phone_number
    assert jsonable_encoder(user) == jsonable_encoder(user_2)


def test_update_user(db: Session) -> None:
    user_in = UserCreate(phone_number=random_phone_number())
    user = crud.create_user(session=db, user_create=user_in)
    user_in_update = UserUpdate(full_name="Updated Name", role=UserRole.driver)
    crud.update_user(session=db, db_user=user, user_in=user_in_update)
    user_2 = db.get(User, user.id)
    assert user_2
    assert user_2.full_name == "Updated Name"
    assert user_2.role == UserRole.driver
