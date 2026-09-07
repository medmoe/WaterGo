"""SMS / WhatsApp sending, behind a small provider interface.

The real gateway for Algeria is still TBD (open question 20.3). Everything in
the app calls :func:`send`; swapping in a real provider means implementing the
:class:`NotificationProvider` protocol and pointing :data:`provider` at it -
no calling code changes.
"""

import logging
from typing import Protocol

from app.core.config import settings

logger = logging.getLogger("app.notifications")


class NotificationProvider(Protocol):
    def send(self, phone: str, message: str) -> bool:
        """Deliver ``message`` to ``phone``. Return True on success."""
        ...


class LoggingProvider:
    """Default provider: logs the message instead of sending it.

    Used until ``SMS_PROVIDER_*`` settings point at a real gateway.
    """

    def send(self, phone: str, message: str) -> bool:
        logger.info("[stub-sms] to=%s message=%s", phone, message)
        return True


def _build_provider() -> NotificationProvider:
    # When a real gateway is configured this is where it gets constructed
    # (settings.SMS_PROVIDER_API_KEY / SMS_PROVIDER_BASE_URL).
    if settings.SMS_PROVIDER_API_KEY and settings.SMS_PROVIDER_BASE_URL:
        logger.warning(
            "SMS_PROVIDER_* is set but no real provider is implemented yet; "
            "falling back to the logging stub."
        )
    return LoggingProvider()


provider: NotificationProvider = _build_provider()


def send(phone: str, message: str) -> bool:
    """Send a notification via the configured provider."""
    return provider.send(phone, message)
