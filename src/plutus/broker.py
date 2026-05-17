"""Alpaca paper broker factory. paper=True is hard-coded."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lumibot.brokers import Alpaca

    from plutus.config import (
        Settings,
    )


def make_paper_broker(settings: Settings) -> Alpaca:
    """Construct an Alpaca paper broker. paper=True is hard-coded for safety."""
    # Deferred import: lumibot triggers third-party deprecation warnings at module
    # load time (websockets.legacy, pandas future.no_silent_downcasting). Importing
    # inside the function keeps those warnings scoped to call-time, where pytest
    # filterwarnings and monkeypatching are already active.
    from lumibot.brokers import Alpaca

    config = {
        "API_KEY": settings.alpaca_api_key,
        "API_SECRET": settings.alpaca_api_secret,
        "PAPER": True,  # NEVER change to False. See AGENTS.md.
    }
    return Alpaca(config)
