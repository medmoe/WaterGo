import httpx
import pytest

from app.services.notifications import (
    AndroidGatewaySmsProvider,
    LoggingProvider,
    _build_provider,
)


def _provider_with_handler(handler) -> AndroidGatewaySmsProvider:
    p = AndroidGatewaySmsProvider("http://phone.local:8080", "secret", device_id="d1")
    p._client = httpx.Client(  # noqa: SLF001
        transport=httpx.MockTransport(handler),
        headers={"Authorization": "Bearer secret"},
    )
    return p


def test_send_success_returns_true_and_posts_expected_body() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["json"] = __import__("json").loads(request.content)
        return httpx.Response(202, json={"id": "msg-123", "state": "Pending"})

    p = _provider_with_handler(handler)
    assert p.send("+213555111222", "hello") is True
    assert seen["url"].endswith("/message")
    assert seen["json"] == {
        "message": "hello",
        "phoneNumbers": ["+213555111222"],
        "deviceId": "d1",
    }


def test_send_failure_returns_false_not_raises() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    p = _provider_with_handler(handler)
    assert p.send("+213555111222", "hello") is False


def test_send_handles_transport_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("phone offline")

    p = _provider_with_handler(handler)
    assert p.send("+213555111222", "hello") is False


def test_healthy_reflects_gateway_status() -> None:
    p = _provider_with_handler(lambda r: httpx.Response(200))
    assert p.healthy() is True

    def down(_r: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline")

    p2 = _provider_with_handler(down)
    assert p2.healthy() is False


def test_build_provider_selects_gateway_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.core.config.settings.SMS_GATEWAY_BASE_URL", "http://phone.local"
    )
    monkeypatch.setattr("app.core.config.settings.SMS_GATEWAY_API_KEY", "k")
    assert isinstance(_build_provider(), AndroidGatewaySmsProvider)


def test_build_provider_defaults_to_logging(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.core.config.settings.SMS_GATEWAY_BASE_URL", None)
    monkeypatch.setattr("app.core.config.settings.SMS_GATEWAY_API_KEY", None)
    assert isinstance(_build_provider(), LoggingProvider)
