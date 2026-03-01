"""Tests for NukeClient."""

from __future__ import annotations

from nukebread.server.nuke_client import NukeClient
from nukebread.common.constants import BRIDGE_HOST, BRIDGE_PORT


def test_client_creation() -> None:
    """NukeClient should instantiate with default host/port."""
    client = NukeClient()
    assert client.host == BRIDGE_HOST
    assert client.port == BRIDGE_PORT


def test_client_not_connected_initially() -> None:
    """A freshly created client should not report as connected."""
    client = NukeClient()
    assert client.connected is False
