"""Universe / strategy config loader."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    from pathlib import Path


def load_universe(path: Path) -> dict[str, Any]:
    """Load and parse the universe YAML file."""
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        msg = f"universe yaml at {path} must be a mapping"
        raise TypeError(msg)
    return data
