from fastapi.encoders import jsonable_encoder
from sqlmodel import Session

from app import crud
from app.models import User, UserCreate, UserUpdate
from tests.utils.utils import random_email


def test_create_user(db: Session) -> None:
    email = random_email()
    user_in = UserCreate(email=email)
    user = crud.create_user(session=db, user_create=user_in)
    assert user.email == email


def test_check_if_user_is_active(db: Session) -> None:
    user_in = UserCreate(email=random_email())
    user = crud.create_user(session=db, user_create=user_in)
    assert user.is_active is True


def test_check_if_user_is_active_inactive(db: Session) -> None:
    user_in = UserCreate(email=random_email(), is_active=False)
    user = crud.create_user(session=db, user_create=user_in)
    assert user.is_active is False


def test_check_if_user_is_superuser(db: Session) -> None:
    user_in = UserCreate(email=random_email(), is_superuser=True)
    user = crud.create_user(session=db, user_create=user_in)
    assert user.is_superuser is True


def test_check_if_user_is_superuser_normal_user(db: Session) -> None:
    user_in = UserCreate(email=random_email())
    user = crud.create_user(session=db, user_create=user_in)
    assert user.is_superuser is False


def test_get_user(db: Session) -> None:
    user_in = UserCreate(email=random_email(), is_superuser=True)
    user = crud.create_user(session=db, user_create=user_in)
    user_2 = db.get(User, user.id)
    assert user_2
    assert user.email == user_2.email
    assert jsonable_encoder(user) == jsonable_encoder(user_2)


def test_update_user(db: Session) -> None:
    user_in = UserCreate(email=random_email(), is_superuser=True)
    user = crud.create_user(session=db, user_create=user_in)
    new_full_name = "Updated Name"
    user_in_update = UserUpdate(full_name=new_full_name, is_superuser=True)
    crud.update_user(session=db, db_user=user, user_in=user_in_update)
    user_2 = db.get(User, user.id)
    assert user_2
    assert user_2.full_name == new_full_name
