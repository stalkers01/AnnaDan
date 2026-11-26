"""Typed application settings loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Annadan API"
    environment: str = "development"
    api_prefix: str = "/api/v1"
    secret_key: str = "change-this-secret-before-deploying"
    access_token_minutes: int = 30
    database_url: str = "sqlite:///./annadan.db"
    cors_origins: list[str] = [
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]

    require_email_verification: bool = False
    require_phone_verification: bool = False
    require_safety_review: bool = False
    expose_otp_in_development: bool = False
    frontend_base_url: str = "http://127.0.0.1:5500"

    resend_api_key: str | None = None
    email_from: str = "Annadan <onboarding@resend.dev>"

    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_from_number: str | None = None
    twilio_verify_service_sid: str | None = None

    cloudinary_url: str | None = None
    cloudinary_folder: str = "annadan/donations"
    upload_max_bytes: int = 5 * 1024 * 1024

    razorpay_key_id: str | None = None
    razorpay_key_secret: str | None = None
    razorpay_webhook_secret: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
