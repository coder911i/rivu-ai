"""Application configuration using pydantic-settings."""

from functools import lru_cache
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    APP_NAME: str = "Rivu"
    APP_VERSION: str = "0.1.0"
    APP_ENV: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000"]

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://rivu:rivu_dev_password@localhost:5432/rivu"
    DATABASE_URL_SYNC: str = "postgresql://rivu:rivu_dev_password@localhost:5432/rivu"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30

    # Auth
    JWT_SECRET: str = "CHANGE_THIS_IN_PRODUCTION_RANDOM_SECRET"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # AI Providers
    GROQ_API_KEY: Optional[str] = None
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    OPENAI_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    DEFAULT_AI_PROVIDER: str = "groq"

    # S3 / Object Storage
    S3_ENDPOINT: str = "http://localhost:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_BUCKET: str = "rivu-datasets"
    S3_REGION: str = "us-east-1"
    S3_USE_SSL: bool = False

    # Processing
    MAX_UPLOAD_SIZE_MB: int = 500
    MAX_PROFILE_SAMPLE_ROWS: int = 100_000
    MAX_AI_SAMPLE_ROWS: int = 1_000
    JOB_WORKER_CONCURRENCY: int = 4

    @property
    def MAX_UPLOAD_SIZE_BYTES(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    @property
    def ALLOWED_ORIGINS_LIST(self) -> List[str]:
        return self.ALLOWED_ORIGINS


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
