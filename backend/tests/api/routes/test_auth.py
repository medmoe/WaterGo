import fakeredis
from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.models import UserCreate, UserRole
from tests.utils.utils import random_phone_number

BASE = settings.API_V1_STR


def _request_and_read_code(
    client: TestClient, fake_redis: fakeredis.FakeRedis, phone: str
) -> str:
    r = client.post(f"{BASE}/auth/otp/request", json={"phone_number": phone})
    assert r.status_code == 200
    code = fake_redis.get(f"otp:code:{phone}")
    assert code is not None
    return str(code)


def test_request_otp_generic_response(
    client: TestClient, fake_redis: fakeredis.FakeRedis
) -> None:
    phone = random_phone_number()
    r = client.post(f"{BASE}/auth/otp/request", json={"phone_number": phone})
    assert r.status_code == 200
    assert "sent" in r.json()["message"].lower()
    assert fake_redis.get(f"otp:code:{phone}") is not None


def test_verify_otp_unknown_number_reports_no_account(
    client: TestClient, fake_redis: fakeredis.FakeRedis, db: Session
) -> None:
    # accounts are never minted here anymore: customers get one when they
    # place their first order, and dispatcher/driver/admin accounts are
    # always created by an admin - so an unknown number must fail clearly
    # instead of silently becoming a customer.
    phone = random_phone_number()
    code = _request_and_read_code(client, fake_redis, phone)

    r = client.post(
        f"{BASE}/auth/otp/verify", json={"phone_number": phone, "code": code}
    )
    assert r.status_code == 404
    assert r.json()["detail"] == "NO_ACCOUNT"
    assert crud.get_user_by_phone(session=db, phone_number=phone) is None


def test_verify_otp_succeeds_for_existing_account(
    client: TestClient, fake_redis: fakeredis.FakeRedis, db: Session
) -> None:
    phone = random_phone_number()
    crud.create_user(
        session=db, user_create=UserCreate(phone_number=phone, role=UserRole.customer)
    )
    code = _request_and_read_code(client, fake_redis, phone)

    r = client.post(
        f"{BASE}/auth/otp/verify", json={"phone_number": phone, "code": code}
    )
    assert r.status_code == 200
    token = r.json()["access_token"]
    assert token

    me = client.get(f"{BASE}/users/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["phone_number"] == phone


def test_verify_otp_preserves_existing_role(
    client: TestClient, fake_redis: fakeredis.FakeRedis, db: Session
) -> None:
    phone = random_phone_number()
    crud.create_user(
        session=db,
        user_create=UserCreate(phone_number=phone, role=UserRole.dispatcher),
    )
    code = _request_and_read_code(client, fake_redis, phone)
    r = client.post(
        f"{BASE}/auth/otp/verify", json={"phone_number": phone, "code": code}
    )
    assert r.status_code == 200
    user = crud.get_user_by_phone(session=db, phone_number=phone)
    assert user and user.role == UserRole.dispatcher


def test_verify_otp_wrong_code(
    client: TestClient, fake_redis: fakeredis.FakeRedis, db: Session
) -> None:
    phone = random_phone_number()
    crud.create_user(
        session=db, user_create=UserCreate(phone_number=phone, role=UserRole.customer)
    )
    _request_and_read_code(client, fake_redis, phone)
    r = client.post(
        f"{BASE}/auth/otp/verify", json={"phone_number": phone, "code": "000000"}
    )
    assert r.status_code == 400


def test_verify_otp_no_code_issued(client: TestClient) -> None:
    r = client.post(
        f"{BASE}/auth/otp/verify",
        json={"phone_number": random_phone_number(), "code": "123456"},
    )
    assert r.status_code == 400


def test_verify_otp_is_single_use(
    client: TestClient, fake_redis: fakeredis.FakeRedis, db: Session
) -> None:
    phone = random_phone_number()
    crud.create_user(
        session=db, user_create=UserCreate(phone_number=phone, role=UserRole.customer)
    )
    code = _request_and_read_code(client, fake_redis, phone)
    ok = client.post(
        f"{BASE}/auth/otp/verify", json={"phone_number": phone, "code": code}
    )
    assert ok.status_code == 200
    again = client.post(
        f"{BASE}/auth/otp/verify", json={"phone_number": phone, "code": code}
    )
    assert again.status_code == 400


def test_verify_otp_locks_out_after_max_attempts(
    client: TestClient, fake_redis: fakeredis.FakeRedis, db: Session
) -> None:
    phone = random_phone_number()
    crud.create_user(
        session=db, user_create=UserCreate(phone_number=phone, role=UserRole.customer)
    )
    code = _request_and_read_code(client, fake_redis, phone)
    for _ in range(5):
        client.post(
            f"{BASE}/auth/otp/verify",
            json={"phone_number": phone, "code": "999999"},
        )
    # Even the correct code is now rejected.
    r = client.post(
        f"{BASE}/auth/otp/verify", json={"phone_number": phone, "code": code}
    )
    assert r.status_code == 400
