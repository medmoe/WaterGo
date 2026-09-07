from decimal import Decimal

from sqlmodel import Session

from app.models import Order, OrderCreate, User
from app.services import orders as orders_service
from tests.utils.utils import random_phone_number


def order_payload(**overrides: object) -> dict:
    payload: dict = {
        "location": {
            "raw_lat": 35.5559,
            "raw_lng": 6.1741,
            "landmark_text": "près de la mosquée El Atik",
            "commune": "Batna",
        },
        "quantity_liters": 1000,
        "customer_phone": random_phone_number(),
    }
    payload.update(overrides)
    return payload


def create_random_order(
    db: Session, *, customer: User | None = None, quantity_liters: int = 1000
) -> Order:
    order_in = OrderCreate.model_validate(
        order_payload(quantity_liters=quantity_liters)
    )
    return orders_service.create_order(db, order_in=order_in, current_user=customer)


def approx_total(quantity_liters: int, price: Decimal = Decimal("4")) -> Decimal:
    return price * quantity_liters
