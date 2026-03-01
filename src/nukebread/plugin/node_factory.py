"""Node creation and manipulation helpers for Nuke.

All functions run inside Nuke's Python environment and assume they are
called on the main thread (the bridge dispatcher handles this via
``nuke.executeInMainThread``).
"""

from __future__ import annotations

from typing import Any

import nuke


# ------------------------------------------------------------------
# Node creation
# ------------------------------------------------------------------


def create_node(
    class_name: str,
    name: str | None = None,
    knobs: dict[str, Any] | None = None,
    connect_to: str | None = None,
    insert_after: str | None = None,
    x: int | None = None,
    y: int | None = None,
) -> str:
    """Create a single node and return its name.

    Parameters
    ----------
    class_name:
        Nuke node class, e.g. ``"Grade"``, ``"Merge2"``.
    name:
        Desired node name.  Nuke may append a number if it collides.
    knobs:
        Dict of knob_name -> value to set after creation.
    connect_to:
        Name of an existing node whose output feeds into input 0 of the
        new node.
    insert_after:
        Name of an existing node.  The new node is spliced inline: it
        inherits the target's downstream connections and connects its
        input 0 to the target.
    x, y:
        Position on the node graph.
    """
    # Deselect everything first so nuke.createNode doesn't auto-connect.
    for n in nuke.selectedNodes():
        n.setSelected(False)

    if insert_after is not None:
        target = nuke.toNode(insert_after)
        if target is None:
            raise ValueError(f"insert_after node '{insert_after}' not found")
        target.setSelected(True)
        node = nuke.createNode(class_name, inpanel=False)
    else:
        node = nuke.createNode(class_name, inpanel=False)

    if name:
        node.setName(name)

    if x is not None:
        node.setXpos(x)
    if y is not None:
        node.setYpos(y)

    if connect_to is not None and insert_after is None:
        source = nuke.toNode(connect_to)
        if source is None:
            raise ValueError(f"connect_to node '{connect_to}' not found")
        node.setInput(0, source)

    if knobs:
        for k, v in knobs.items():
            knob = node.knob(k)
            if knob is None:
                continue
            _set_knob(knob, v)

    return node.name()


def create_node_tree(tree_definition: list[dict]) -> list[str]:
    """Batch-create a chain of nodes from a list of definitions.

    Each entry is a dict with keys matching ``NodeTreeEntry`` fields:
    ``class_name``, ``name``, ``knobs``, ``connect_from``, ``input_index``.

    Returns the list of created node names.
    """
    created: dict[str, Any] = {}  # name -> nuke.Node
    result_names: list[str] = []

    for entry in tree_definition:
        cls = entry["class_name"]
        desired_name = entry.get("name", "")
        knobs = entry.get("knobs", {})
        connect_from = entry.get("connect_from")
        input_index = entry.get("input_index", 0)

        # Deselect all before creating to avoid auto-wiring.
        for n in nuke.selectedNodes():
            n.setSelected(False)

        node = nuke.createNode(cls, inpanel=False)
        if desired_name:
            node.setName(desired_name)

        for k, v in knobs.items():
            knob = node.knob(k)
            if knob is not None:
                _set_knob(knob, v)

        if connect_from and connect_from in created:
            node.setInput(input_index, created[connect_from])

        created[node.name()] = node
        result_names.append(node.name())

    return result_names


# ------------------------------------------------------------------
# Connection management
# ------------------------------------------------------------------


def connect(from_name: str, to_name: str, input_index: int = 0) -> str:
    """Wire *from_name*'s output into *to_name*'s input at *input_index*.

    Returns a confirmation string.
    """
    src = nuke.toNode(from_name)
    dst = nuke.toNode(to_name)
    if src is None:
        raise ValueError(f"Source node '{from_name}' not found")
    if dst is None:
        raise ValueError(f"Destination node '{to_name}' not found")

    dst.setInput(input_index, src)
    return f"Connected {from_name} -> {to_name}[{input_index}]"


def disconnect(node_name: str, input_index: int | None = None) -> str:
    """Disconnect inputs on *node_name*.

    If *input_index* is ``None``, all inputs are disconnected.
    """
    node = nuke.toNode(node_name)
    if node is None:
        raise ValueError(f"Node '{node_name}' not found")

    if input_index is not None:
        node.setInput(input_index, None)
        return f"Disconnected {node_name}[{input_index}]"

    for i in range(node.inputs()):
        node.setInput(i, None)
    return f"Disconnected all inputs on {node_name}"


# ------------------------------------------------------------------
# Deletion
# ------------------------------------------------------------------


def delete_nodes(node_names: list[str]) -> str:
    """Delete the named nodes.

    Reconnects downstream dependents to the deleted node's input 0 source
    where possible, to avoid breaking the pipe.
    """
    for name in node_names:
        node = nuke.toNode(name)
        if node is None:
            continue

        # Try to preserve the pipe: if the node has a single input and
        # downstream dependents, reconnect them.
        src = node.input(0)
        for dep in node.dependent():
            for i in range(dep.inputs()):
                if dep.input(i) == node:
                    dep.setInput(i, src)

        nuke.delete(node)

    return f"Deleted {len(node_names)} node(s)"


# ------------------------------------------------------------------
# Knob manipulation
# ------------------------------------------------------------------


def set_knob_value(node_name: str, knob_name: str, value: Any) -> str:
    """Set a knob's value on an existing node."""
    node = nuke.toNode(node_name)
    if node is None:
        raise ValueError(f"Node '{node_name}' not found")
    knob = node.knob(knob_name)
    if knob is None:
        raise ValueError(f"Knob '{knob_name}' not found on {node_name}")
    _set_knob(knob, value)
    return f"Set {node_name}.{knob_name} = {value!r}"


def set_knob_expression(node_name: str, knob_name: str, expression: str) -> str:
    """Set an expression (TCL or Python) on a knob."""
    node = nuke.toNode(node_name)
    if node is None:
        raise ValueError(f"Node '{node_name}' not found")
    knob = node.knob(knob_name)
    if knob is None:
        raise ValueError(f"Knob '{knob_name}' not found on {node_name}")
    knob.setExpression(expression)
    return f"Set expression on {node_name}.{knob_name}: {expression}"


def set_animation_keys(
    node_name: str,
    knob_name: str,
    keyframes: list[dict],
) -> str:
    """Set animation keyframes on a knob.

    Parameters
    ----------
    keyframes:
        List of dicts, each with ``frame`` (int), ``value`` (float), and
        optional ``interpolation`` (``"smooth"``, ``"linear"``,
        ``"constant"``).
    """
    node = nuke.toNode(node_name)
    if node is None:
        raise ValueError(f"Node '{node_name}' not found")
    knob = node.knob(knob_name)
    if knob is None:
        raise ValueError(f"Knob '{knob_name}' not found on {node_name}")

    knob.setAnimated()
    for kf in keyframes:
        frame = kf["frame"]
        value = kf["value"]
        knob.setValueAt(value, frame)

        # TODO: implement interpolation type mapping
        # interp = kf.get("interpolation", "smooth")
        # Nuke's animation curve API uses nuke.SMOOTH, nuke.LINEAR,
        # nuke.CONSTANT etc.  The knob.animation(0) curve object would
        # need its keys iterated to set interpolation per-key.

    return f"Set {len(keyframes)} keyframes on {node_name}.{knob_name}"


# ------------------------------------------------------------------
# Advanced operations
# ------------------------------------------------------------------


def duplicate_branch(node_name: str) -> str:
    """Duplicate *node_name* and everything upstream, return the new tip name.

    Uses Nuke's built-in copy/paste mechanism.
    """
    node = nuke.toNode(node_name)
    if node is None:
        raise ValueError(f"Node '{node_name}' not found")

    # Select the node and all upstream nodes.
    for n in nuke.selectedNodes():
        n.setSelected(False)

    nuke.selectConnectedNodes()  # selects nothing since nothing is selected
    node.setSelected(True)

    # Walk upstream and select everything.
    _select_upstream(node)

    # Copy and paste the selection.
    nuke.nodeCopy("%clipboard%")
    nuke.nodePaste("%clipboard%")

    # The pasted nodes are now selected. Find the one matching the
    # original class at the tip.
    pasted = nuke.selectedNodes()
    if pasted:
        return pasted[0].name()

    return node_name  # fallback


def replace_node(
    old_name: str,
    new_class: str,
    preserve_connections: bool = True,
) -> str:
    """Replace *old_name* with a new node of *new_class*.

    When *preserve_connections* is True, input and output wiring is
    transferred to the replacement node.
    """
    old_node = nuke.toNode(old_name)
    if old_node is None:
        raise ValueError(f"Node '{old_name}' not found")

    # Capture connections before deletion.
    inputs: list[tuple[int, Any]] = []
    for i in range(old_node.inputs()):
        src = old_node.input(i)
        if src is not None:
            inputs.append((i, src))

    dependents: list[tuple[Any, int]] = []
    for dep in old_node.dependent():
        for i in range(dep.inputs()):
            if dep.input(i) == old_node:
                dependents.append((dep, i))

    xpos = old_node.xpos()
    ypos = old_node.ypos()

    # Create the replacement.
    for n in nuke.selectedNodes():
        n.setSelected(False)
    new_node = nuke.createNode(new_class, inpanel=False)
    new_node.setXpos(xpos)
    new_node.setYpos(ypos)

    if preserve_connections:
        for idx, src in inputs:
            if idx < new_node.inputs() or new_node.inputs() == 0:
                new_node.setInput(idx, src)
        for dep, idx in dependents:
            dep.setInput(idx, new_node)

    nuke.delete(old_node)
    return new_node.name()


# ------------------------------------------------------------------
# Private helpers
# ------------------------------------------------------------------


def _set_knob(knob, value: Any) -> None:
    """Set a knob value, handling common type coercions."""
    if isinstance(value, list):
        knob.setValue(value)
    elif isinstance(value, bool):
        knob.setValue(value)
    elif isinstance(value, (int, float)):
        knob.setValue(value)
    elif isinstance(value, str):
        knob.setValue(value)
    else:
        knob.setValue(str(value))


def _select_upstream(node) -> None:
    """Recursively select *node* and all upstream nodes."""
    if node is None or node.isSelected():
        return
    node.setSelected(True)
    for i in range(node.inputs()):
        _select_upstream(node.input(i))
