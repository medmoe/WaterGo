from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

from app.api.deps import SessionDep
from app.core.config import settings
from app.services import telegram

router = APIRouter(prefix="/telegram", tags=["telegram"])


@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    session: SessionDep,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> Any:
    """
    Inbound bot messages (Telegram calls this). Used mainly for the
    ``/link <code>`` flow. Always answers 200 so Telegram doesn't retry.
    """
    if (
        settings.TELEGRAM_WEBHOOK_SECRET
        and x_telegram_bot_api_secret_token != settings.TELEGRAM_WEBHOOK_SECRET
    ):
        raise HTTPException(status_code=403, detail="bad secret token")

    try:
        update = await request.json()
    except ValueError:
        return {"ok": True}

    if isinstance(update, dict):
        telegram.handle_update(session, update)
    return {"ok": True}
