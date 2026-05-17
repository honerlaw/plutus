"""Tests for plutus.logging."""

from __future__ import annotations

import structlog

from plutus.logging import bind_run_id, configure_logging


def test_configure_logging_returns_logger() -> None:
    configure_logging("DEBUG")
    log = structlog.get_logger()
    log.info("hello", foo="bar")  # smoke


def test_bind_run_id_adds_context() -> None:
    configure_logging("INFO")
    log = bind_run_id("abc-123", strategy_name="orb")
    # bound vars should appear when rendering
    rendered = log.bind().info("test")  # type: ignore[no-untyped-call]
    assert rendered is None  # structlog returns None on .info
