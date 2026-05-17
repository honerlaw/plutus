"""Tests for the strategy registry."""

from __future__ import annotations

from typing import Any

import pytest

from plutus.strategies.registry import REGISTRY, load_enabled, register


def test_register_adds_to_registry() -> None:
    @register("test_dummy")
    class Dummy:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

    assert "test_dummy" in REGISTRY
    assert REGISTRY["test_dummy"] is Dummy


def test_register_rejects_duplicate() -> None:
    @register("test_dup")
    class A: ...

    with pytest.raises(ValueError, match="already registered"):

        @register("test_dup")
        class B: ...


def test_load_enabled_instantiates_only_enabled() -> None:
    @register("alpha")
    class Alpha:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

    @register("beta")
    class Beta:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

    config = {
        "strategies": {
            "alpha": {"enabled": True, "x": 1},
            "beta": {"enabled": False, "y": 2},
        }
    }
    loaded = load_enabled(config)
    assert len(loaded) == 1
    assert isinstance(loaded[0], Alpha)
    assert loaded[0].kwargs == {"x": 1}


def test_load_enabled_unknown_strategy_raises() -> None:
    config = {"strategies": {"does_not_exist": {"enabled": True}}}
    with pytest.raises(KeyError, match="does_not_exist"):
        load_enabled(config)
