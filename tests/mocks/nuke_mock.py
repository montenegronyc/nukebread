"""Mock nuke module for testing outside of Nuke.

Provides just enough surface area to test serializer, factory,
and protocol logic without a running Nuke instance.
"""

from __future__ import annotations

from contextlib import contextmanager


class MockKnob:
    """Minimal mock of a Nuke knob."""

    def __init__(
        self,
        name: str = "knob",
        value: object = 0.0,
        class_name: str = "Double_Knob",
        animated: bool = False,
        expression: str | None = None,
    ):
        self._name = name
        self._value = value
        self._class_name = class_name
        self._animated = animated
        self._expression = expression

    def name(self) -> str:
        return self._name

    def Class(self) -> str:  # noqa: N802
        return self._class_name

    def value(self) -> object:
        return self._value

    def setValue(self, v: object) -> None:  # noqa: N802
        self._value = v

    def isAnimated(self) -> bool:  # noqa: N802
        return self._animated

    def hasExpression(self) -> bool:  # noqa: N802
        return self._expression is not None

    def expression(self) -> str:
        return self._expression or ""


class MockNode:
    """Minimal mock of a Nuke node."""

    def __init__(
        self,
        name: str = "Grade1",
        class_name: str = "Grade",
        x: int = 0,
        y: int = 0,
        knobs: dict[str, MockKnob] | None = None,
    ):
        self._name = name
        self._class_name = class_name
        self._x = x
        self._y = y
        self._knobs: dict[str, MockKnob] = knobs or {}
        self._inputs: dict[int, MockNode | None] = {}

    def name(self) -> str:
        return self._name

    def Class(self) -> str:  # noqa: N802
        return self._class_name

    def xpos(self) -> int:
        return self._x

    def ypos(self) -> int:
        return self._y

    def knobs(self) -> dict[str, MockKnob]:
        return self._knobs

    def knob(self, name: str) -> MockKnob | None:
        return self._knobs.get(name)

    def input(self, i: int) -> MockNode | None:
        return self._inputs.get(i)

    def setInput(self, i: int, node: MockNode | None) -> None:  # noqa: N802
        self._inputs[i] = node


# --- Module-level state (mimics nuke module globals) ---

_all_nodes: list[MockNode] = []
_selected_nodes: list[MockNode] = []


def reset() -> None:
    """Reset mock state between tests."""
    global _all_nodes, _selected_nodes
    _all_nodes = []
    _selected_nodes = []


def add_mock_node(node: MockNode, selected: bool = False) -> MockNode:
    """Helper: add a node to the mock scene."""
    _all_nodes.append(node)
    if selected:
        _selected_nodes.append(node)
    return node


# --- Functions matching nuke module API ---


def allNodes() -> list[MockNode]:  # noqa: N802
    return list(_all_nodes)


def selectedNodes() -> list[MockNode]:  # noqa: N802
    return list(_selected_nodes)


def toNode(name: str) -> MockNode | None:  # noqa: N802
    for n in _all_nodes:
        if n.name() == name:
            return n
    return None


def createNode(class_name: str, **kwargs: object) -> MockNode:  # noqa: N802
    node = MockNode(
        name=f"{class_name}1",
        class_name=class_name,
    )
    _all_nodes.append(node)
    return node


def delete(node: MockNode) -> None:
    global _all_nodes, _selected_nodes
    _all_nodes = [n for n in _all_nodes if n is not node]
    _selected_nodes = [n for n in _selected_nodes if n is not node]


def executeInMainThread(func: object, args: tuple = ()) -> object:  # noqa: N802
    """In mock context, just call immediately."""
    return func(*args)  # type: ignore[operator]


def undo() -> None:
    """No-op in mock."""


@contextmanager
def Undo(name: str = ""):  # noqa: N802
    """Context manager matching nuke.Undo."""
    yield
