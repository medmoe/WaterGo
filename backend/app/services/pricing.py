"""Pricing (section 7).

Price is per-liter and history-preserving: never update a row in place, always
insert a new one, and read the latest row whose ``effective_from <= now()``.
"""

from datetime import UTC, datetime
from decimal import Decimal

from sqlmodel import Session, desc, select

from app.models import PricingSetting

DEFAULT_PRICE_PER_LITER_DZD = Decimal("4")


def get_current_pricing(session: Session) -> PricingSetting | None:
    statement = (
        select(PricingSetting)
        .where(PricingSetting.effective_from <= datetime.now(UTC))
        .order_by(desc(PricingSetting.effective_from))
        .limit(1)
    )
    return session.exec(statement).first()


def get_current_price(session: Session) -> Decimal:
    row = get_current_pricing(session)
    return row.price_per_liter_dzd if row else DEFAULT_PRICE_PER_LITER_DZD


def add_pricing(
    session: Session,
    *,
    price_per_liter_dzd: Decimal,
    effective_from: datetime | None = None,
) -> PricingSetting:
    row = PricingSetting(
        price_per_liter_dzd=price_per_liter_dzd,
        effective_from=effective_from or datetime.now(UTC),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row
