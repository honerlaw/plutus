"""Application settings loaded from environment (injected by Doppler in production)."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Never mutate; instantiate fresh.

    In production, Doppler injects all env vars at process startup.
    Locally, either run ``doppler run -- <command>`` or export the vars manually.
    """

    model_config = SettingsConfigDict(extra="ignore")

    alpaca_api_key: str = Field(..., alias="ALPACA_API_KEY")
    alpaca_api_secret: str = Field(..., alias="ALPACA_API_SECRET")
    alpaca_paper: bool = Field(default=True, alias="ALPACA_PAPER")
    submit_orders: bool = Field(default=True, alias="PLUTUS_SUBMIT_ORDERS")
    database_url: str = Field(..., alias="PLUTUS_DB_URL")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO", alias="PLUTUS_LOG_LEVEL"
    )

    @field_validator("alpaca_paper")
    @classmethod
    def _force_paper(cls, _v: bool) -> bool:  # noqa: FBT001 - validator signature
        # Safety: plutus is a paper-only lab. The setting exists for clarity but is forced True.
        return True
