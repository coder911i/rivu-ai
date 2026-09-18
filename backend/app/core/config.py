"""Application configuration using pydantic-settings."""

from functools import lru_cache
from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    APP_NAME: str = "Rivu"
    APP_VERSION: str = "0.2.0"
    APP_ENV: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    ALLOWED_ORIGINS: str = "http://localhost:3000"

    DATABASE_URL: str = "postgresql+asyncpg://rivu:rivu_dev_password@localhost:5432/rivu"
    DATABASE_URL_SYNC: str = "postgresql://rivu:rivu_dev_password@localhost:5432/rivu"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30

    JWT_SECRET: str = "CHANGE_THIS_IN_PRODUCTION_RANDOM_SECRET"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    GROQ_API_KEY: Optional[str] = None
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    OPENAI_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    DEFAULT_AI_PROVIDER: str = "groq"

    S3_ENDPOINT: str = "http://localhost:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_BUCKET: str = "rivu-datasets"
    S3_REGION: str = "us-east-1"
    S3_USE_SSL: bool = False
    S3_FORCE_PATH_STYLE: bool = True
    AUTO_CREATE_SCHEMA: bool = True

    MAX_UPLOAD_SIZE_MB: int = 500
    MAX_PROFILE_SAMPLE_ROWS: int = 100_000
    MAX_AI_SAMPLE_ROWS: int = 1_000
    JOB_WORKER_CONCURRENCY: int = 4

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def normalize_origins(cls, value):
        if isinstance(value, str):
            return value
        return ",".join(value)

    @property
    def ALLOWED_ORIGINS_LIST(self) -> list[str]:
        return [item.strip() for item in self.ALLOWED_ORIGINS.split(",") if item.strip()]

    @property
    def MAX_UPLOAD_SIZE_BYTES(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    def validate_production_security(self) -> None:
        if self.APP_ENV.lower() == "production":
            if self.DEBUG:
                raise RuntimeError("DEBUG must be false in production")
            if self.JWT_SECRET.startswith("CHANGE_THIS") or len(self.JWT_SECRET) < 32:
                raise RuntimeError("JWT_SECRET must be a long random secret in production")
            if self.AUTO_CREATE_SCHEMA:
                raise RuntimeError("AUTO_CREATE_SCHEMA must be false in production; use Alembic migrations")
            if not self.S3_USE_SSL:
                raise RuntimeError("S3_USE_SSL must be true in production")
            if not self.S3_ENDPOINT.lower().startswith("https://"):
                raise RuntimeError("S3_ENDPOINT must use HTTPS in production")
            if self.S3_ACCESS_KEY in {"", "minioadmin"} or self.S3_SECRET_KEY in {"", "minioadmin"}:
                raise RuntimeError("Production S3 credentials must not use development defaults")


@lru_cache()
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_production_security()
    return settings


settings = get_settings()
