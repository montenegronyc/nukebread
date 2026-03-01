"""Tests for graph serializer logic."""

from __future__ import annotations

from tests.mocks.nuke_mock import MockNode, add_mock_node


def test_serialize_empty_graph() -> None:
    """An empty node list produces an empty GraphData."""
    from nukebread.common.types import GraphData

    graph = GraphData(nodes=[])
    assert graph.nodes == []
    assert graph.script_name == ""


def test_serialize_single_node() -> None:
    """A single mock node should map to a valid NodeInfo."""
    from nukebread.common.types import NodeInfo

    node = MockNode(name="Grade_HeroFace", class_name="Grade", x=100, y=200)
    info = NodeInfo(
        name=node.name(),
        class_name=node.Class(),
        x=node.xpos(),
        y=node.ypos(),
    )
    assert info.name == "Grade_HeroFace"
    assert info.class_name == "Grade"
    assert info.x == 100
    assert info.y == 200
    assert info.inputs == []
    assert info.knobs == []


def test_filtered_classes_excluded() -> None:
    """Viewer and BackdropNode classes should be in the filter set."""
    from nukebread.common.constants import FILTERED_NODE_CLASSES

    viewer = MockNode(name="Viewer1", class_name="Viewer")
    backdrop = MockNode(name="Backdrop1", class_name="BackdropNode")
    grade = MockNode(name="Grade1", class_name="Grade")

    add_mock_node(viewer)
    add_mock_node(backdrop)
    add_mock_node(grade)

    assert viewer.Class() in FILTERED_NODE_CLASSES
    assert backdrop.Class() in FILTERED_NODE_CLASSES
    assert grade.Class() not in FILTERED_NODE_CLASSES
