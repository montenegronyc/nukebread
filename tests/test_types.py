"""Tests for Pydantic models and protocol helpers."""

from __future__ import annotations

from nukebread.common.types import NodeInfo, GraphData
from nukebread.common.protocol import (
    BridgeMessage,
    MessageType,
    make_request,
)


def test_node_info_defaults() -> None:
    """NodeInfo with only required fields should have sane defaults."""
    info = NodeInfo(name="Blur1", class_name="Blur")
    assert info.name == "Blur1"
    assert info.class_name == "Blur"
    assert info.x == 0
    assert info.y == 0
    assert info.inputs == []
    assert info.knobs == []
    assert info.selected is False
    assert info.has_error is False
    assert info.label == ""


def test_bridge_message_roundtrip() -> None:
    """BridgeMessage should survive serialize/deserialize."""
    msg = BridgeMessage(
        type=MessageType.REQUEST,
        id="abc123",
        command="read_graph",
        params={"selected_only": True},
    )
    raw = msg.to_bytes()
    restored = BridgeMessage.from_bytes(raw)

    assert restored.type == MessageType.REQUEST
    assert restored.id == "abc123"
    assert restored.command == "read_graph"
    assert restored.params == {"selected_only": True}


def test_make_request() -> None:
    """make_request helper should produce a well-formed REQUEST message."""
    msg = make_request("create_node", {"class_name": "Grade"}, msg_id="x1")
    assert msg.type == MessageType.REQUEST
    assert msg.command == "create_node"
    assert msg.params == {"class_name": "Grade"}
    assert msg.id == "x1"
