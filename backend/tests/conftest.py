from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, delete

from app.core.config import settings
from app.core.db import engine, init_db
from app.main import app
from app.models import User
from tests.utils.user import authentication_token_from_email


@pytest.fixture(scope="session", autouse=True)
def db() -> Generator[Session]:
    with Session(engine) as session:
        init_db(session)
        yield session
        statement = delete(User)
        session.execute(statement)
        session.commit()


@pytest.fixture(scope="module")
def client() -> Generator[TestClient]:
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def superuser_token_headers(db: Session) -> dict[str, str]:
    return authentication_token_from_email(
        email=settings.FIRST_SUPERUSER, db=db, is_superuser=True
    )


@pytest.fixture(scope="module")
def normal_user_token_headers(db: Session) -> dict[str, str]:
    return authentication_token_from_email(email=settings.EMAIL_TEST_USER, db=db)
