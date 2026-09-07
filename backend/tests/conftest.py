from collections.abc import Generator

import fakeredis
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel

from app.core.config import settings
from app.core.db import engine, init_db
from app.main import app
from app.models import UserRole
from app.worker import celery_app
from tests.utils.user import authentication_token_from_phone

# Run Celery tasks inline instead of over a real broker.
celery_app.conf.task_always_eager = True
celery_app.conf.task_eager_propagates = False


@pytest.fixture(autouse=True)
def fake_redis(monkeypatch: pytest.MonkeyPatch) -> fakeredis.FakeRedis:
    """Back the OTP store with an in-memory Redis for every test."""
    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr("app.services.otp.get_redis", lambda: fake)
    return fake


@pytest.fixture(scope="session", autouse=True)
def db() -> Generator[Session]:
    with Session(engine) as session:
        init_db(session)
        yield session
        # Wipe every table in FK-safe order so each run starts clean.
        for table in reversed(SQLModel.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()


@pytest.fixture(scope="module")
def client() -> Generator[TestClient]:
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def superuser_token_headers(db: Session) -> dict[str, str]:
    return authentication_token_from_phone(
        db=db, phone_number=settings.FIRST_SUPERUSER_PHONE, role=UserRole.admin
    )


@pytest.fixture(scope="module")
def normal_user_token_headers(db: Session) -> dict[str, str]:
    return authentication_token_from_phone(
        db=db, phone_number=settings.TEST_USER_PHONE, role=UserRole.customer
    )
