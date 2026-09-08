import warnings
from typing import Literal, Self

from pydantic import (
    HttpUrl,
    PostgresDsn,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Top-level .env (one level above ./backend/); ../.env.local overrides it
        # and is git-ignored - put real secrets (bot tokens, gateway keys) there.
        env_file=("../.env", "../.env.local"),
        env_ignore_empty=True,
        extra="ignore",
    )
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str
    # 60 minutes * 24 hours * 8 days = 8 days
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8
    FRONTEND_HOST: str = "http://localhost:5173"
    FASTAPI_ENV: Literal["development"] | None = None

    PROJECT_NAME: str
    SENTRY_DSN: HttpUrl | None = None
    DATABASE_URL: PostgresDsn

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def _use_psycopg_driver(cls, value: str | PostgresDsn) -> str:
        database_url = str(value)
        for scheme in ("postgres://", "postgresql://"):
            if database_url.startswith(scheme):
                return database_url.replace(scheme, "postgresql+psycopg://", 1)
        return database_url

    POSTGIS_ENABLED: bool = True

    # Redis is the Celery broker/result backend and the OTP code store.
    REDIS_URL: str = "redis://localhost:6379/0"

    # OTP auth (section 9)
    OTP_EXPIRY_SECONDS: int = 300

    # SMS / WhatsApp provider (section 11). SMS_PROVIDER_* is reserved for the
    # eventual Infobip/WhatsApp integration.
    SMS_PROVIDER_API_KEY: str | None = None
    SMS_PROVIDER_BASE_URL: str | None = None

    # Interim SMS: a SIM-based Android SMS gateway (see docs/interim-messaging).
    # When both are set, this takes precedence over SMS_PROVIDER_* and the stub.
    SMS_GATEWAY_BASE_URL: str | None = None
    SMS_GATEWAY_API_KEY: str | None = None
    SMS_GATEWAY_DEVICE_ID: str | None = None

    # Telegram bot for internal-team notifications (dispatcher/driver).
    TELEGRAM_BOT_TOKEN: str | None = None
    # Optional: value of the X-Telegram-Bot-Api-Secret-Token header Telegram
    # sends to the webhook (set when registering the webhook with setWebhook).
    TELEGRAM_WEBHOOK_SECRET: str | None = None

    # Route clustering (section 12) - not wired up yet.
    ROUTE_CLUSTER_DISTANCE_METERS: int = 1500

    # Phone number (E.164) of the bootstrap admin account, seeded by init_db.
    FIRST_SUPERUSER_PHONE: str = "+213555000000"
    # Phone number used by the test suite for the "normal user" fixture.
    TEST_USER_PHONE: str = "+213555000001"

    def _check_default_secret(self, var_name: str, value: str | None) -> None:
        if value == "changethis":
            message = (
                f'The value of {var_name} is "changethis", '
                "for security, please change it, at least for deployments."
            )
            if self.FASTAPI_ENV == "development":
                warnings.warn(message, stacklevel=1)
            else:
                raise ValueError(message)

    @model_validator(mode="after")
    def _enforce_non_default_secrets(self) -> Self:
        self._check_default_secret("SECRET_KEY", self.SECRET_KEY)
        for host in self.DATABASE_URL.hosts():
            self._check_default_secret("DATABASE_URL password", host["password"])

        return self


settings = Settings()  # type: ignore # ty: ignore[unused-ignore-comment]
