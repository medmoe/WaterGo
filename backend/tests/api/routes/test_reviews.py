from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.models import UserRole
from app.services import reviews as reviews_service
from tests.utils.fleet import deliver_order
from tests.utils.order import create_random_order
from tests.utils.user import create_random_user, get_auth_headers_for_user

BASE = settings.API_V1_STR


def test_review_with_token_no_login(client: TestClient, db: Session) -> None:
    order = deliver_order(db)
    token = reviews_service.make_review_token(order.id)
    r = client.post(
        f"{BASE}/reviews",
        json={
            "order_id": str(order.id),
            "rating": 5,
            "comment": "Livraison rapide",
            "token": token,
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["rating"] == 5


def test_review_rejected_for_non_delivered_order(
    client: TestClient, db: Session
) -> None:
    order = create_random_order(db)
    token = reviews_service.make_review_token(order.id)
    r = client.post(
        f"{BASE}/reviews",
        json={"order_id": str(order.id), "rating": 4, "token": token},
    )
    assert r.status_code == 409


def test_review_requires_token_or_auth(client: TestClient, db: Session) -> None:
    order = deliver_order(db)
    r = client.post(f"{BASE}/reviews", json={"order_id": str(order.id), "rating": 3})
    assert r.status_code == 403


def test_review_is_one_per_order(client: TestClient, db: Session) -> None:
    order = deliver_order(db)
    token = reviews_service.make_review_token(order.id)
    body = {"order_id": str(order.id), "rating": 4, "token": token}
    assert client.post(f"{BASE}/reviews", json=body).status_code == 200
    assert client.post(f"{BASE}/reviews", json=body).status_code == 409


def test_review_rating_bounds(client: TestClient, db: Session) -> None:
    order = deliver_order(db)
    token = reviews_service.make_review_token(order.id)
    r = client.post(
        f"{BASE}/reviews",
        json={"order_id": str(order.id), "rating": 9, "token": token},
    )
    assert r.status_code == 422


def test_list_reviews_admin_only(client: TestClient, db: Session) -> None:
    order = deliver_order(db)
    token = reviews_service.make_review_token(order.id)
    client.post(
        f"{BASE}/reviews",
        json={"order_id": str(order.id), "rating": 5, "token": token},
    )

    admin = create_random_user(db, role=UserRole.admin)
    r = client.get(
        f"{BASE}/reviews",
        headers=get_auth_headers_for_user(admin),
        params={"order_id": str(order.id)},
    )
    assert r.status_code == 200
    assert r.json()["count"] == 1

    dispatcher = create_random_user(db, role=UserRole.dispatcher)
    r = client.get(f"{BASE}/reviews", headers=get_auth_headers_for_user(dispatcher))
    assert r.status_code == 403
