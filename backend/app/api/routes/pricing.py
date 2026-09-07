from typing import Any

from fastapi import APIRouter

from app.api.deps import AdminUser, SessionDep
from app.models import PricingCurrent, PricingSettingCreate, PricingSettingPublic
from app.services import pricing

router = APIRouter(prefix="/pricing", tags=["pricing"])


@router.get("/current", response_model=PricingCurrent)
def read_current_pricing(session: SessionDep) -> Any:
    """
    Active per-liter price. Falls back to the section 7 default when no pricing
    row has been configured yet.
    """
    row = pricing.get_current_pricing(session)
    if row is None:
        return PricingCurrent(
            price_per_liter_dzd=pricing.DEFAULT_PRICE_PER_LITER_DZD,
            is_default=True,
        )
    return PricingCurrent(
        price_per_liter_dzd=row.price_per_liter_dzd,
        effective_from=row.effective_from,
    )


@router.post("", response_model=PricingSettingPublic)
def create_pricing(
    *, session: SessionDep, _admin: AdminUser, body: PricingSettingCreate
) -> Any:
    """
    Insert a new pricing row (admin only). Never updates an existing row so
    historical orders stay traceable to the price that applied.
    """
    return pricing.add_pricing(
        session,
        price_per_liter_dzd=body.price_per_liter_dzd,
        effective_from=body.effective_from,
    )
