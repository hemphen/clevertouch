"""Keep live account tests opt-in."""

from __future__ import annotations

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register explicit opt-in for tests that contact the vendor API."""
    parser.addoption("--live", action="store_true", help="Run live account tests")


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Skip live tests unless explicitly requested."""
    if config.getoption("--live"):
        return
    skip_live = pytest.mark.skip(reason="Live account tests require --live")
    for item in items:
        if item.get_closest_marker("live"):
            item.add_marker(skip_live)
