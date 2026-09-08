"""SMS / WhatsApp sending, behind a small provider interface.

Everything in the app calls :func:`send`; swapping providers means implementing
:class:`NotificationProvider` and pointing :data:`provider` at it - no calling
code changes. Selection (highest priority first):

1. ``AndroidGatewaySmsProvider`` - a SIM-based Android SMS gateway, when
   ``SMS_GATEWAY_BASE_URL`` + ``SMS_GATEWAY_API_KEY`` are set (interim setup).
2. the eventual Infobip/WhatsApp provider - ``SMS_PROVIDER_*`` (not built yet).
3. ``LoggingProvider`` - logs the message (default / stub).
"""

import logging
from typing import Protocol

import httpx

from app.core.config import settings

logger = logging.getLogger("app.notifications")


class NotificationProvider(Protocol):
    def send(self, phone: str, message: str) -> bool:
        """Deliver ``message`` to ``phone``. Return True on success."""
        ...


class LoggingProvider:
    """Logs the message instead of sending it."""

    def send(self, phone: str, message: str) -> bool:
        logger.info("[stub-sms] to=%s message=%s", phone, message)
        return True

    def healthy(self) -> bool:
        return True


class AndroidGatewaySmsProvider:
    """Sends SMS through a phone running an Android SMS gateway app.

    The exact endpoint / auth / body shape depends on the gateway app you pick
    (e.g. capcom6/android-sms-gateway). Adjust :meth:`_post` to match its API
    reference - everything else is generic.
    """

    def __init__(
        self, base_url: str, api_key: str, device_id: str | None = None
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._device_id = device_id
        self._client = httpx.Client(
            timeout=15.0,
            headers={"Authorization": f"Bearer {api_key}"},
        )

    def _post(self, path: str, json: dict[str, object]) -> httpx.Response:
        return self._client.post(f"{self._base_url}{path}", json=json)

    def send(self, phone: str, message: str) -> bool:
        payload: dict[str, object] = {"message": message, "phoneNumbers": [phone]}
        if self._device_id:
            payload["deviceId"] = self._device_id
        try:
            resp = self._post("/message", payload)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("android sms gateway send to %s failed: %s", phone, exc)
            return False
        message_id = None
        try:
            message_id = resp.json().get("id")
        except ValueError:
            pass
        logger.info("android sms gateway accepted to=%s id=%s", phone, message_id)
        return True

    def healthy(self) -> bool:
        try:
            resp = self._client.get(f"{self._base_url}/health")
        except httpx.HTTPError:
            return False
        return resp.status_code < 500


def _build_provider() -> NotificationProvider:
    if settings.SMS_GATEWAY_BASE_URL and settings.SMS_GATEWAY_API_KEY:
        logger.info("notifications: using AndroidGatewaySmsProvider")
        return AndroidGatewaySmsProvider(
            settings.SMS_GATEWAY_BASE_URL,
            settings.SMS_GATEWAY_API_KEY,
            settings.SMS_GATEWAY_DEVICE_ID,
        )
    if settings.SMS_PROVIDER_API_KEY and settings.SMS_PROVIDER_BASE_URL:
        logger.warning(
            "SMS_PROVIDER_* is set but that provider isn't implemented yet; "
            "falling back to the logging stub."
        )
    return LoggingProvider()


provider: NotificationProvider = _build_provider()


def send(phone: str, message: str) -> bool:
    """Send a notification via the configured provider."""
    return provider.send(phone, message)


def provider_healthy() -> bool | None:
    """True/False for the real gateway; ``None`` when only the stub is active."""
    if isinstance(provider, LoggingProvider):
        return None
    healthy = getattr(provider, "healthy", None)
    return bool(healthy()) if callable(healthy) else None
