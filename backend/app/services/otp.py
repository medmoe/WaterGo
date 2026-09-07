"""Phone-number OTP: generate, store in Redis, verify (section 9)."""

import logging
import secrets
from typing import cast

from app.core.config import settings
from app.core.redis_client import get_redis
from app.services import notifications

logger = logging.getLogger("app.otp")

CODE_LENGTH = 6
MAX_ATTEMPTS = 5


def _code_key(phone_number: str) -> str:
    return f"otp:code:{phone_number}"


def _attempts_key(phone_number: str) -> str:
    return f"otp:attempts:{phone_number}"


def generate_code() -> str:
    return "".join(secrets.choice("0123456789") for _ in range(CODE_LENGTH))


def request_otp(phone_number: str) -> str:
    """Create a fresh code, store it with a TTL and send it. Returns the code
    (callers must not expose it - it is returned only for logging/tests)."""
    code = generate_code()
    r = get_redis()
    pipe = r.pipeline()
    pipe.set(_code_key(phone_number), code, ex=settings.OTP_EXPIRY_SECONDS)
    pipe.delete(_attempts_key(phone_number))
    pipe.execute()

    notifications.send(
        phone_number,
        f"Votre code de vérification Batna Water est {code}. "
        f"Il expire dans {settings.OTP_EXPIRY_SECONDS // 60} minutes.",
    )
    logger.info("OTP issued for %s", phone_number)
    return code


def verify_otp(phone_number: str, code: str) -> bool:
    """True if ``code`` matches the stored one. Consumes the code on success and
    enforces a per-code attempt cap."""
    r = get_redis()
    stored = cast("str | None", r.get(_code_key(phone_number)))
    if stored is None:
        return False

    attempts = cast("int", r.incr(_attempts_key(phone_number)))
    if attempts == 1:
        r.expire(_attempts_key(phone_number), settings.OTP_EXPIRY_SECONDS)
    if attempts > MAX_ATTEMPTS:
        r.delete(_code_key(phone_number))
        return False

    if not secrets.compare_digest(stored, code):
        return False

    r.delete(_code_key(phone_number))
    r.delete(_attempts_key(phone_number))
    return True
