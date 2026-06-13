"""Structlog setup. Idempotent — safe to call multiple times."""

from __future__ import annotations

import logging
from typing import Any

import structlog


def configure_logging(level: str = "INFO") -> None:
    """Configure structlog + stdlib logging at the given level."""
    logging.basicConfig(format="%(message)s", level=level)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(level)),
        cache_logger_on_first_use=True,
    )


def bind_run_id(run_id: str, **extra: Any) -> structlog.stdlib.BoundLogger:
    """Return a logger pre-bound with run_id and any extra context."""
    return structlog.get_logger().bind(run_id=run_id, **extra)
