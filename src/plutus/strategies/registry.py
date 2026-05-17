"""Strategy registry: maps name -> class, loads enabled ones from config."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable

T = TypeVar("T")

REGISTRY: dict[str, type[Any]] = {}


def register(name: str) -> Callable[[type[T]], type[T]]:
    """Decorator that adds a strategy class to REGISTRY under `name`."""

    def deco(cls: type[T]) -> type[T]:
        if name in REGISTRY:
            msg = f"strategy {name!r} already registered"
            raise ValueError(msg)
        REGISTRY[name] = cls
        return cls

    return deco


def load_enabled(config: dict[str, Any]) -> list[Any]:
    """Instantiate every strategy in config['strategies'] that has enabled=True."""
    out: list[Any] = []
    for name, params in config.get("strategies", {}).items():
        if not params.get("enabled", False):
            continue
        if name not in REGISTRY:
            msg = f"unknown strategy: {name}"
            raise KeyError(msg)
        kwargs = {k: v for k, v in params.items() if k != "enabled"}
        out.append(REGISTRY[name](**kwargs))
    return out
