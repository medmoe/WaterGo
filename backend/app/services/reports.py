"""End-of-day cash reconciliation (section 13).

Sums total_price_dzd for delivered stops per driver so the owner can check
declared cash against expected cash. Volume for one operational day is small,
so the per-driver aggregation is done in Python.
"""

from collections import defaultdict
from datetime import date
from decimal import Decimal

from sqlmodel import Session, col, select

from app.models import (
    CashReconciliationReport,
    DriverCashRow,
    Order,
    Route,
    RouteStop,
    User,
)


def cash_reconciliation(session: Session, on_date: date) -> CashReconciliationReport:
    statement = (
        select(RouteStop, Order, User)
        .join(Route, col(RouteStop.route_id) == col(Route.id))
        .join(Order, col(RouteStop.order_id) == col(Order.id))
        .join(User, col(Route.driver_id) == col(User.id))
        .where(Route.planned_date == on_date)
        .where(col(RouteStop.delivered_at).is_not(None))
    )

    by_driver: dict[str, DriverCashRow] = {}
    drivers: dict[str, User] = {}
    delivered: defaultdict[str, int] = defaultdict(int)
    collected: defaultdict[str, int] = defaultdict(int)
    expected: defaultdict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    got: defaultdict[str, Decimal] = defaultdict(lambda: Decimal("0"))

    for stop, order, driver in session.exec(statement).all():
        key = str(driver.id)
        drivers[key] = driver
        delivered[key] += 1
        expected[key] += order.total_price_dzd
        if stop.payment_collected:
            collected[key] += 1
            got[key] += order.total_price_dzd

    total_expected = Decimal("0")
    total_collected = Decimal("0")
    for key, driver in drivers.items():
        by_driver[key] = DriverCashRow(
            driver_id=driver.id,
            driver_name=driver.full_name,
            driver_phone=driver.phone_number,
            delivered_stops=delivered[key],
            expected_cash_dzd=expected[key],
            collected_stops=collected[key],
            collected_cash_dzd=got[key],
        )
        total_expected += expected[key]
        total_collected += got[key]

    rows = sorted(
        by_driver.values(), key=lambda r: (r.driver_name or "", r.driver_phone)
    )
    return CashReconciliationReport(
        date=on_date,
        rows=rows,
        total_expected_dzd=total_expected,
        total_collected_dzd=total_collected,
    )
