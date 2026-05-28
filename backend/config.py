from functools import lru_cache
from typing import Annotated, List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = Field("development", alias="ENVIRONMENT")
    secret_key: str = Field(..., alias="SECRET_KEY", min_length=32)
    database_url: str = Field("sqlite:///./auth.db", alias="DATABASE_URL")

    access_token_minutes: int = Field(15, alias="ACCESS_TOKEN_MINUTES")
    refresh_token_days: int = Field(14, alias="REFRESH_TOKEN_DAYS")

    allowed_origins: Annotated[List[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:8000", "http://127.0.0.1:8000"],
        alias="ALLOWED_ORIGINS",
    )
    cookie_secure: bool = Field(False, alias="COOKIE_SECURE")
    cookie_domain: str | None = Field(None, alias="COOKIE_DOMAIN")

    login_rate_limit: str = Field("5/minute", alias="LOGIN_RATE_LIMIT")
    signup_rate_limit: str = Field("3/minute", alias="SIGNUP_RATE_LIMIT")

    lockout_threshold: int = Field(5, alias="LOCKOUT_THRESHOLD")
    lockout_minutes: int = Field(15, alias="LOCKOUT_MINUTES")

    totp_issuer: str = Field("Cipher", alias="TOTP_ISSUER")

    email_enabled: bool = Field(False, alias="EMAIL_ENABLED")
    smtp_host: str = Field("localhost", alias="SMTP_HOST")
    smtp_port: int = Field(587, alias="SMTP_PORT")
    smtp_user: str = Field("", alias="SMTP_USER")
    smtp_password: str = Field("", alias="SMTP_PASSWORD")
    smtp_from: str = Field("noreply@cipher.app", alias="SMTP_FROM")
    app_base_url: str = Field("http://localhost:8000", alias="APP_BASE_URL")

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def split_origins(cls, v):
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
