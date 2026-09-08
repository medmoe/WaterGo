import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.models import UserRole
from app.services import telegram
from tests.utils.user import create_random_user, get_auth_headers_for_user
from tests.utils.utils import random_phone_number

BASE = settings.API_V1_STR


def test_create_dispatcher_returns_link_code(client: TestClient, db: Session) -> None:
    admin = create_random_user(db, role=UserRole.admin)
    r = client.post(
        f"{BASE}/users/",
        headers=get_auth_headers_for_user(admin),
        json={"phone_number": random_phone_number(), "role": "dispatcher"},
    )
    assert r.status_code == 200, r.text
    code = r.json()["telegram_link_code"]
    assert code and len(code) == 6
    # the code resolves to the new user
    assert telegram.consume_link_code(code) is not None


def test_create_customer_has_no_link_code(client: TestClient, db: Session) -> None:
    admin = create_random_user(db, role=UserRole.admin)
    r = client.post(
        f"{BASE}/users/",
        headers=get_auth_headers_for_user(admin),
        json={"phone_number": random_phone_number(), "role": "customer"},
    )
    assert r.status_code == 200
    assert r.json()["telegram_link_code"] is None


def test_reissue_link_code(client: TestClient, db: Session) -> None:
    admin = create_random_user(db, role=UserRole.admin)
    driver = create_random_user(db, role=UserRole.driver)
    r = client.post(
        f"{BASE}/users/{driver.id}/telegram-link-code",
        headers=get_auth_headers_for_user(admin),
    )
    assert r.status_code == 200
    assert telegram.consume_link_code(r.json()["code"]) == driver.id


def test_reissue_rejects_non_team_role(client: TestClient, db: Session) -> None:
    admin = create_random_user(db, role=UserRole.admin)
    customer = create_random_user(db, role=UserRole.customer)
    r = client.post(
        f"{BASE}/users/{customer.id}/telegram-link-code",
        headers=get_auth_headers_for_user(admin),
    )
    assert r.status_code == 400


def test_webhook_link_flow(client: TestClient, db: Session) -> None:
    user = create_random_user(db, role=UserRole.dispatcher)
    code = telegram.issue_link_code(user.id)
    r = client.post(
        f"{BASE}/telegram/webhook",
        json={"message": {"chat": {"id": 424242}, "text": f"/link {code}"}},
    )
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    db.refresh(user)
    assert user.telegram_chat_id == "424242"


def test_webhook_rejects_bad_secret(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.core.config.settings.TELEGRAM_WEBHOOK_SECRET", "s3cr3t")
    r = client.post(
        f"{BASE}/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"},
        json={"message": {"chat": {"id": 1}, "text": "/start"}},
    )
    assert r.status_code == 403


def test_webhook_accepts_good_secret(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.core.config.settings.TELEGRAM_WEBHOOK_SECRET", "s3cr3t")
    r = client.post(
        f"{BASE}/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "s3cr3t"},
        json={"message": {"chat": {"id": 1}, "text": "/start"}},
    )
    assert r.status_code == 200
