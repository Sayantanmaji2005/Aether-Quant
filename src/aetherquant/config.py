from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed runtime settings."""

    app_name: str = "AetherQuant"
    env: str = "dev"
    log_level: str = "INFO"
    default_symbol: str = "SPY"
    data_dir: Path = Path("data")

    initial_cash: float = Field(default=100_000, gt=0)
    commission_bps: float = Field(default=1.0, ge=0)
    slippage_bps: float = Field(default=0.5, ge=0)
    api_key: str | None = None
    admin_api_key: str | None = None
    database_url: str | None = None
    rate_limit_per_minute: int = Field(default=120, gt=0)
    live_broker_endpoint: str | None = None
    live_broker_key_id: str | None = None
    live_broker_token: str | None = None
    live_broker_provider: str = "generic-rest"
    live_broker_dry_run: bool = True

    @field_validator(
        "api_key",
        "admin_api_key",
        "database_url",
        "live_broker_endpoint",
        "live_broker_key_id",
        "live_broker_token",
        mode="before",
    )
    @classmethod
    def _blank_to_none(cls, value: object) -> object:
        if isinstance(value, str) and value.strip() == "":
            return None
        return value

    model_config = SettingsConfigDict(
        env_prefix="AETHERQ_",
        env_file=".env",
        env_file_encoding="utf-8-sig",
        extra="ignore",
    )
