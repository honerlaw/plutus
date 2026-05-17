"""Application settings loaded from environment / .env file."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Never mutate; instantiate fresh."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    alpaca_api_key: str = Field(..., alias="ALPACA_API_KEY")
    alpaca_api_secret: str = Field(..., alias="ALPACA_API_SECRET")
    alpaca_paper: bool = Field(default=True, alias="ALPACA_PAPER")
    submit_orders: bool = Field(default=True, alias="PLUTUS_SUBMIT_ORDERS")
    db_path: Path = Field(default=Path("./data/plutus.db"), alias="PLUTUS_DB_PATH")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO", alias="PLUTUS_LOG_LEVEL"
    )

    @field_validator("alpaca_paper")
    @classmethod
    def _force_paper(cls, _v: bool) -> bool:  # noqa: FBT001 - validator signature
        # Safety: plutus is a paper-only lab. The setting exists for clarity but is forced True.
        return True
