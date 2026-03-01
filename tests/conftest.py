"""Pytest fixtures for NukeBread tests."""

from __future__ import annotations

import sys
from unittest.mock import patch

import pytest

from tests.mocks import nuke_mock


@pytest.fixture(autouse=True)
def _reset_nuke_mock() -> None:
    """Reset mock nuke state before every test."""
    nuke_mock.reset()


@pytest.fixture()
def mock_nuke():
    """Patch the ``nuke`` module with our mock so imports resolve."""
    with patch.dict(sys.modules, {"nuke": nuke_mock}):
        yield nuke_mock


@pytest.fixture()
def nuke_client():
    """Create a NukeClient instance (not connected)."""
    from nukebread.server.nuke_client import NukeClient

    return NukeClient()
