from datetime import UTC, date, datetime
from typing import Any

from fastapi import APIRouter

from app.api.deps import AdminUser, SessionDep
from app.models import CashReconciliationReport
from app.services import reports as reports_service

router = APIRouter(prefix="/admin/reports", tags=["reports"])


@router.get("/cash-reconciliation", response_model=CashReconciliationReport)
def cash_reconciliation(
    session: SessionDep, _admin: AdminUser, date: date | None = None
) -> Any:
    """
    Per-driver expected vs collected cash for delivered stops on a given day
    (defaults to today).
    """
    on_date = date or datetime.now(UTC).date()
    return reports_service.cash_reconciliation(session, on_date)
