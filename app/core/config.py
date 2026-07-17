"""Application settings loaded from environment variables."""
from decimal import Decimal
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Payout Management Service"
    app_env: str = "development"
    log_level: str = "INFO"

    database_url: str = "sqlite:///./payout.db"

    advance_payout_rate: Decimal = Field(default=Decimal("0.10"))
    withdrawal_cooldown_hours: int = 24

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
