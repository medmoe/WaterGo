"""Telegram bot: internal-team notifications + the account-linking flow.

Free push for the dispatcher/driver, alongside (not instead of) the WebSocket
channel. Not customer-facing. A Telegram bot can only message a user who has
messaged it first, so linking is: admin hands over a one-time code -> the person
sends ``/link <code>`` to the bot -> we store their chat id.
"""

import logging
import secrets
from typing import Any, cast
from uuid import UUID

import httpx
from sqlmodel import Session, col, select

from app.core.config import settings
from app.core.redis_client import get_redis
from app.models import User, UserRole

logger = logging.getLogger("app.telegram")

LINK_CODE_TTL_SECONDS = 3600
_LINK_KEY = "tg:link:{code}"
_API_BASE = "https://api.telegram.org"


def enabled() -> bool:
    return bool(settings.TELEGRAM_BOT_TOKEN)


def _client() -> httpx.Client:
    return httpx.Client(
        base_url=f"{_API_BASE}/bot{settings.TELEGRAM_BOT_TOKEN}", timeout=15.0
    )


def send_message(chat_id: str, text: str) -> bool:
    if not enabled():
        logger.debug("telegram disabled; would send to %s: %s", chat_id, text)
        return False
    try:
        resp = _client().post(
            "/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "disable_web_page_preview": True,
            },
        )
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        logger.error("telegram send to %s failed: %s", chat_id, exc)
        return False
    return True


def send_to_role(session: Session, role: UserRole, text: str) -> int:
    """Send ``text`` to every active user of ``role`` who has linked Telegram.
    Returns the number of messages accepted."""
    statement = (
        select(User)
        .where(User.role == role)
        .where(User.is_active == True)  # noqa: E712
        .where(col(User.telegram_chat_id).is_not(None))
    )
    sent = 0
    for user in session.exec(statement).all():
        if user.telegram_chat_id and send_message(user.telegram_chat_id, text):
            sent += 1
    return sent


# --- linking codes ---------------------------------------------------------


def issue_link_code(user_id: UUID) -> str:
    code = "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(6))
    get_redis().set(_LINK_KEY.format(code=code), str(user_id), ex=LINK_CODE_TTL_SECONDS)
    return code


def consume_link_code(code: str) -> UUID | None:
    r = get_redis()
    key = _LINK_KEY.format(code=code.strip().upper())
    raw = cast("str | None", r.get(key))
    if raw is None:
        return None
    r.delete(key)
    try:
        return UUID(raw)
    except ValueError:
        return None


# --- inbound webhook -----------------------------------------------------


_HELP = (
    "Bienvenue chez Batna Water. Pour lier votre compte, envoyez :\n"
    "/link VOTRE-CODE\n"
    "(le code vous est fourni par l'administrateur)."
)


def handle_update(session: Session, update: dict[str, Any]) -> str | None:
    """Process one Telegram update. Returns the reply text that was sent (for
    tests/logging), or None if the update carried nothing actionable."""
    message = update.get("message") or update.get("edited_message")
    if not message:
        return None
    chat_id = str(message.get("chat", {}).get("id", ""))
    text = (message.get("text") or "").strip()
    if not chat_id or not text:
        return None

    if text.startswith("/start"):
        send_message(chat_id, _HELP)
        return _HELP

    if text.startswith("/link"):
        parts = text.split(maxsplit=1)
        code = parts[1].strip() if len(parts) == 2 else ""
        user_id = consume_link_code(code) if code else None
        user = session.get(User, user_id) if user_id else None
        if not user:
            reply = (
                "Code invalide ou expiré. Demandez un nouveau code à l'administrateur."
            )
        else:
            user.telegram_chat_id = chat_id
            session.add(user)
            session.commit()
            reply = f"✅ Compte lié ({user.full_name or user.phone_number})."
        send_message(chat_id, reply)
        return reply

    return None
