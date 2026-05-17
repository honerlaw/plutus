"""Root conftest.py — project-wide pytest configuration.

Pre-imports third-party packages that emit DeprecationWarnings at module-load
time so that those warnings fire BEFORE pytest activates its -W error filter.
This prevents addopts ``-W error`` from turning lumibot / alpaca-py / pandas
import-time warnings into test failures.
"""

from __future__ import annotations

import warnings

# Suppress third-party DeprecationWarnings that fire at import time and would
# otherwise cause -W error (from addopts) to fail collection / test setup.
with warnings.catch_warnings():
    warnings.filterwarnings(
        "ignore",
        message="websockets.legacy is deprecated",
        category=DeprecationWarning,
    )
    warnings.filterwarnings(
        "ignore",
        message=".*no_silent_downcasting.*",
        category=DeprecationWarning,
    )
    # Pre-import so subsequent imports hit sys.modules cache (no re-warning).
    import lumibot.brokers
    import lumibot.strategies  # noqa: F401 — pre-warm strategies so adapter.py import is clean
