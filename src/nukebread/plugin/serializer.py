"""Serialize Nuke's node graph into NukeBread Pydantic models.

Every function in this module runs inside Nuke's Python interpreter and
therefore has full access to the ``nuke`` module.  They should only be
called from the main thread (the bridge dispatcher handles this).
"""

from __future__ import annotations

from typing import Any

import nuke

from nukebread.common.constants import FILTERED_NODE_CLASSES
from nukebread.common.types import (
    GraphData,
    KnobValue,
    NodeConnection,
    NodeInfo,
)


# ------------------------------------------------------------------
# Public serialization helpers
# ------------------------------------------------------------------


def serialize_graph(include_viewers: bool = False) -> GraphData:
    """Walk every node in the script and return a ``GraphData`` snapshot.

    Parameters
    ----------
    include_viewers:
        When *False* (default), Viewer, BackdropNode, and StickyNote
        nodes are omitted to reduce noise.
    """
    nodes: list[NodeInfo] = []
    for node in nuke.allNodes():
        if not include_viewers and node.Class() in FILTERED_NODE_CLASSES:
            continue
        nodes.append(serialize_node(node))

    root = nuke.root()
    first = int(root["first_frame"].value())
    last = int(root["last_frame"].value())

    return GraphData(
        nodes=nodes,
        script_name=root.name(),
        frame_range=(first, last),
        current_frame=nuke.frame(),
    )


def serialize_node(node, all_knobs: bool = False) -> NodeInfo:
    """Convert a ``nuke.Node`` into a ``NodeInfo`` model.

    Parameters
    ----------
    node:
        A ``nuke.Node`` instance.
    all_knobs:
        When *True*, serialize every visible knob on the node.
        When *False*, only a curated set of important knobs are included.
    """
    knobs = _serialize_knobs(node, all_knobs)
    connections = get_node_connections(node)

    error_msg: str | None = None
    has_error = node.hasError()
    if has_error:
        # node.error() may not exist in all Nuke versions
        error_msg = getattr(node, "error", lambda: "")() or None

    label = node["label"].value() if node.knob("label") else ""
    tile_color = int(node["tile_color"].value()) if node.knob("tile_color") else None

    return NodeInfo(
        name=node.name(),
        class_name=node.Class(),
        x=int(node.xpos()),
        y=int(node.ypos()),
        inputs=connections,
        knobs=knobs,
        selected=node.isSelected(),
        has_error=has_error,
        error_message=error_msg,
        label=label,
        tile_color=tile_color,
    )


def serialize_knob(knob) -> KnobValue:
    """Convert a single ``nuke.Knob`` into a ``KnobValue`` model."""
    value: Any
    try:
        value = knob.value()
    except Exception:
        value = str(knob)

    expression: str | None = None
    if knob.hasExpression():
        try:
            expression = knob.toScript()
        except Exception:
            expression = None

    animated = False
    try:
        animated = knob.isAnimated()
    except Exception:
        pass

    return KnobValue(
        name=knob.name(),
        type=knob.Class(),
        value=_coerce_value(value),
        expression=expression,
        animated=animated,
    )


def get_node_connections(node) -> list[NodeConnection]:
    """Return the list of input connections for *node*."""
    connections: list[NodeConnection] = []
    for i in range(node.inputs()):
        source = node.input(i)
        if source is not None:
            connections.append(NodeConnection(
                input_index=i,
                source_node=source.name(),
            ))
    return connections


def serialize_selected() -> GraphData:
    """Serialize only the selected nodes, plus one level of upstream and
    downstream context so the LLM can reason about connections.
    """
    selected = nuke.selectedNodes()
    if not selected:
        return GraphData(
            script_name=nuke.root().name(),
            frame_range=(
                int(nuke.root()["first_frame"].value()),
                int(nuke.root()["last_frame"].value()),
            ),
            current_frame=nuke.frame(),
        )

    seen: set[str] = set()
    nodes: list[NodeInfo] = []

    for node in selected:
        if node.name() not in seen:
            seen.add(node.name())
            nodes.append(serialize_node(node))

        # One level upstream.
        for i in range(node.inputs()):
            src = node.input(i)
            if src is not None and src.name() not in seen:
                seen.add(src.name())
                nodes.append(serialize_node(src))

        # One level downstream.
        for dep in node.dependent():
            if dep.name() not in seen and dep.Class() not in FILTERED_NODE_CLASSES:
                seen.add(dep.name())
                nodes.append(serialize_node(dep))

    root = nuke.root()
    return GraphData(
        nodes=nodes,
        script_name=root.name(),
        frame_range=(int(root["first_frame"].value()), int(root["last_frame"].value())),
        current_frame=nuke.frame(),
    )


def trace_pipe(node_name: str, direction: str) -> list[NodeInfo]:
    """Follow connections from *node_name* in the given direction.

    Parameters
    ----------
    node_name:
        Starting node name.
    direction:
        ``"upstream"`` follows input 0 recursively.
        ``"downstream"`` follows dependents recursively.
    """
    start = nuke.toNode(node_name)
    if start is None:
        raise ValueError(f"Node '{node_name}' not found")

    visited: set[str] = set()
    result: list[NodeInfo] = []

    def _walk_upstream(n) -> None:
        if n is None or n.name() in visited:
            return
        visited.add(n.name())
        result.append(serialize_node(n))
        # Follow input 0 (the B pipe / main pipe).
        src = n.input(0)
        if src is not None:
            _walk_upstream(src)

    def _walk_downstream(n) -> None:
        if n is None or n.name() in visited:
            return
        visited.add(n.name())
        result.append(serialize_node(n))
        for dep in n.dependent():
            if dep.Class() not in FILTERED_NODE_CLASSES:
                _walk_downstream(dep)

    if direction == "upstream":
        _walk_upstream(start)
    elif direction == "downstream":
        _walk_downstream(start)
    else:
        raise ValueError(f"direction must be 'upstream' or 'downstream', got '{direction}'")

    return result


# ------------------------------------------------------------------
# Private helpers
# ------------------------------------------------------------------

# Knobs that are almost always interesting when doing a summary read.
_IMPORTANT_KNOBS = frozenset({
    "file", "channels", "size", "mix", "operation", "value",
    "whitepoint", "blackpoint", "white", "black", "multiply",
    "add", "gamma", "saturation", "offset", "gain", "lift",
    "colorspace_in", "colorspace_out", "colorspace",
    "translate", "rotate", "scale", "center", "skewX", "skewY",
    "filter", "motionblur", "shutter", "disable",
    "first_frame", "last_frame", "frame_mode", "frame",
})


def _serialize_knobs(node, all_knobs: bool) -> list[KnobValue]:
    """Serialize knobs on *node*.

    When *all_knobs* is False, only knobs whose names are in
    ``_IMPORTANT_KNOBS`` or that have been user-modified are included.
    """
    results: list[KnobValue] = []
    for knob in node.knobs().values():
        if not all_knobs:
            # Skip tab/group/obsolete knobs and knobs with no useful
            # value for the LLM.
            if knob.Class() in ("Tab_Knob", "BeginTabGroup_Knob", "EndTabGroup_Knob",
                                "Obsolete_Knob", "Help_Knob", "Text_Knob"):
                continue
            if knob.name() not in _IMPORTANT_KNOBS and not knob.isAnimated():
                # Also include if the knob was explicitly set by the user.
                try:
                    if not knob.notDefault():
                        continue
                except Exception:
                    continue

        results.append(serialize_knob(knob))

    return results


def _coerce_value(value: Any) -> Any:
    """Make a knob value JSON-safe."""
    if isinstance(value, (bool, int, float, str, type(None))):
        return value
    if isinstance(value, (list, tuple)):
        return [_coerce_value(v) for v in value]
    # Fallback — stringify opaque types.
    return str(value)
