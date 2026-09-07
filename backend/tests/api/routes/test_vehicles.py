from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.models import UserRole
from tests.utils.fleet import random_plate
from tests.utils.user import create_random_user, get_auth_headers_for_user

BASE = settings.API_V1_STR


def _dispatcher_headers(db: Session) -> dict[str, str]:
    return get_auth_headers_for_user(create_random_user(db, role=UserRole.dispatcher))


def test_create_list_update_vehicle(client: TestClient, db: Session) -> None:
    headers = _dispatcher_headers(db)
    plate = random_plate()
    r = client.post(
        f"{BASE}/vehicles",
        headers=headers,
        json={"plate_number": plate, "capacity_liters": 3000},
    )
    assert r.status_code == 200, r.text
    vid = r.json()["id"]
    assert r.json()["status"] == "available"

    r = client.get(f"{BASE}/vehicles", headers=headers)
    assert r.status_code == 200
    assert any(v["id"] == vid for v in r.json()["data"])

    r = client.patch(
        f"{BASE}/vehicles/{vid}",
        headers=headers,
        json={"status": "maintenance", "current_odometer_km": 120000},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "maintenance"
    assert r.json()["current_odometer_km"] == 120000


def test_duplicate_plate_rejected(client: TestClient, db: Session) -> None:
    headers = _dispatcher_headers(db)
    plate = random_plate()
    body = {"plate_number": plate, "capacity_liters": 2500}
    assert (
        client.post(f"{BASE}/vehicles", headers=headers, json=body).status_code == 200
    )
    r = client.post(f"{BASE}/vehicles", headers=headers, json=body)
    assert r.status_code == 400


def test_maintenance_log_bumps_odometer(client: TestClient, db: Session) -> None:
    headers = _dispatcher_headers(db)
    vid = client.post(
        f"{BASE}/vehicles",
        headers=headers,
        json={"plate_number": random_plate(), "capacity_liters": 4000},
    ).json()["id"]

    r = client.post(
        f"{BASE}/vehicles/{vid}/maintenance-logs",
        headers=headers,
        json={
            "type": "tire",
            "odometer_km_at_event": 45000,
            "notes": "front-left replaced",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["type"] == "tire"

    v = client.get(f"{BASE}/vehicles", headers=headers).json()["data"]
    odo = next(x["current_odometer_km"] for x in v if x["id"] == vid)
    assert odo == 45000


def test_fleet_requires_dispatcher(client: TestClient, db: Session) -> None:
    customer = create_random_user(db, role=UserRole.customer)
    r = client.get(f"{BASE}/vehicles", headers=get_auth_headers_for_user(customer))
    assert r.status_code == 403
