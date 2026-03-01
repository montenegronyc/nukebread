"""NukeBread plugin — runs inside Nuke's Python environment.

Call ``nukebread.plugin.start()`` from your menu.py to launch the bridge
server that the MCP server connects to over TCP.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nukebread.plugin.bridge import BridgeServer

_bridge: BridgeServer | None = None
_registry = None  # populated by get_registry()


def start() -> None:
    """Initialize and start the NukeBread bridge server."""
    global _bridge

    if _bridge is not None:
        import nuke
        nuke.message("NukeBread bridge is already running.")
        return

    from nukebread.common.constants import BRIDGE_HOST, BRIDGE_PORT
    from nukebread.plugin.bridge import BridgeServer

    registry = get_registry()
    _bridge = BridgeServer(host=BRIDGE_HOST, port=BRIDGE_PORT, registry=registry)
    _bridge.start()

    import nuke
    nuke.tprint(f"[NukeBread] Bridge server started on {BRIDGE_HOST}:{BRIDGE_PORT}")


def stop() -> None:
    """Stop the bridge server if running."""
    global _bridge
    if _bridge is not None:
        _bridge.stop()
        _bridge = None
        import nuke
        nuke.tprint("[NukeBread] Bridge server stopped.")


def get_registry():
    """Return the shared ToolRegistry, building it on first access."""
    global _registry
    if _registry is None:
        _registry = _build_registry()
    return _registry


def _build_registry():
    """Create and populate a ToolRegistry with all command handlers."""
    from nukebread.plugin.tool_registry import ToolRegistry, TOOL_SCHEMAS
    from nukebread.plugin import serializer, node_factory, frame_grabber

    reg = ToolRegistry()

    # --- Graph read commands ---
    reg.register("read_full_graph", lambda params: serializer.serialize_graph(
        include_viewers=params.get("include_viewers", False),
    ).to_dict(), TOOL_SCHEMAS.get("read_full_graph"))

    reg.register("read_selected_nodes",
                 lambda params: serializer.serialize_selected().to_dict(),
                 TOOL_SCHEMAS.get("read_selected_nodes"))

    reg.register("read_node_detail",
                 lambda params: _node_detail(params["node_name"]),
                 TOOL_SCHEMAS.get("read_node_detail"))

    reg.register("trace_pipe", lambda params: [
        n.to_dict() for n in serializer.trace_pipe(
            params["node_name"], params.get("direction", "upstream"),
        )
    ], TOOL_SCHEMAS.get("trace_pipe"))

    reg.register("find_nodes_by_class",
                 lambda params: _find_by_class(params["class_name"]),
                 TOOL_SCHEMAS.get("find_nodes_by_class"))

    reg.register("get_errors", lambda params: _get_errors(),
                 TOOL_SCHEMAS.get("get_errors"))

    # --- Graph write commands ---
    reg.register("create_node", lambda params: node_factory.create_node(
        class_name=params["class_name"],
        name=params.get("name"),
        knobs=params.get("knobs"),
        connect_to=params.get("connect_to"),
        insert_after=params.get("insert_after"),
        x=params.get("x"),
        y=params.get("y"),
    ), TOOL_SCHEMAS.get("create_node"))

    reg.register("create_node_tree",
                 lambda params: node_factory.create_node_tree(params["tree"]))

    reg.register("connect_nodes", lambda params: node_factory.connect(
        params["from_node"], params["to_node"], params.get("input_index", 0),
    ), TOOL_SCHEMAS.get("connect_nodes"))

    reg.register("disconnect_node", lambda params: node_factory.disconnect(
        params["node_name"], params.get("input_index"),
    ))

    reg.register("delete_nodes",
                 lambda params: node_factory.delete_nodes(params["node_names"]),
                 TOOL_SCHEMAS.get("delete_nodes"))

    reg.register("set_knob", lambda params: node_factory.set_knob_value(
        params["node_name"], params["knob_name"], params["value"],
    ), TOOL_SCHEMAS.get("set_knob"))

    reg.register("set_expression", lambda params: node_factory.set_knob_expression(
        params["node_name"], params["knob_name"], params["expression"],
    ), TOOL_SCHEMAS.get("set_expression"))

    reg.register("set_animation", lambda params: node_factory.set_animation_keys(
        params["node_name"], params["knob_name"], params["keyframes"],
    ))

    reg.register("duplicate_branch",
                 lambda params: node_factory.duplicate_branch(params["node_name"]))

    reg.register("replace_node", lambda params: node_factory.replace_node(
        params["old_node"], params["new_class"], params.get("preserve_connections", True),
    ))

    # --- Vision commands ---
    reg.register("grab_frame", lambda params: frame_grabber.grab_frame(
        node_name=params.get("node_name"),
        frame=params.get("frame"),
    ).to_dict(), TOOL_SCHEMAS.get("grab_frame"))

    reg.register("grab_roi", lambda params: frame_grabber.grab_roi(
        params["node_name"], params["x"], params["y"],
        params["width"], params["height"], params.get("frame"),
    ).to_dict())

    reg.register("grab_comparison", lambda params: frame_grabber.grab_comparison(
        params["node_a"], params["node_b"],
        frame=params.get("frame"), mode=params.get("mode", "wipe"),
    ).to_dict())

    reg.register("grab_frame_range", lambda params: [
        r.to_dict() for r in frame_grabber.grab_frame_range(
            params["node_name"], params["start"], params["end"], params.get("step", 1),
        )
    ])

    reg.register("read_pixel", lambda params: frame_grabber.read_pixel(
        params["node_name"], params["x"], params["y"], params.get("frame"),
    ).to_dict(), TOOL_SCHEMAS.get("read_pixel"))

    # --- Project context commands ---
    reg.register("get_script_info", lambda params: _get_script_info(),
                 TOOL_SCHEMAS.get("get_script_info"))
    reg.register("get_layer_channels",
                 lambda params: _get_layer_channels(params["node_name"]))
    reg.register("list_read_nodes", lambda params: _list_read_nodes(),
                 TOOL_SCHEMAS.get("list_read_nodes"))
    reg.register("get_viewer_state", lambda params: _get_viewer_state())
    reg.register("get_project_color_pipeline", lambda params: _get_color_pipeline())

    # --- Execution & safety commands ---
    reg.register("execute_python",
                 lambda params: _execute_python(params["code"]),
                 TOOL_SCHEMAS.get("execute_python"))
    reg.register("undo", lambda params: _undo(params.get("steps", 1)))
    reg.register("begin_undo_group",
                 lambda params: _begin_undo_group(params["name"]))
    reg.register("end_undo_group", lambda params: _end_undo_group())
    reg.register("save_script_backup", lambda params: _save_script_backup())

    return reg


# ---------------------------------------------------------------------------
# Inline helpers
# ---------------------------------------------------------------------------

def _node_detail(node_name: str) -> dict:
    import nuke
    node = nuke.toNode(node_name)
    if node is None:
        raise ValueError(f"Node '{node_name}' not found")
    from nukebread.plugin.serializer import serialize_node
    return serialize_node(node, all_knobs=True).to_dict()


def _find_by_class(class_name: str) -> list[dict]:
    import nuke
    from nukebread.plugin.serializer import serialize_node
    return [
        serialize_node(n).to_dict()
        for n in nuke.allNodes(class_name)
    ]


def _get_errors() -> list[dict]:
    import nuke
    from nukebread.plugin.serializer import serialize_node
    results = []
    for node in nuke.allNodes():
        if node.hasError():
            results.append(serialize_node(node).to_dict())
    return results


def _get_script_info() -> dict:
    import nuke
    from nukebread.common.types import ScriptInfo
    root = nuke.root()
    return ScriptInfo(
        name=root.name(),
        path=nuke.scriptName() if nuke.scriptName() else "",
        first_frame=int(root["first_frame"].value()),
        last_frame=int(root["last_frame"].value()),
        fps=root["fps"].value(),
        format_name=root.format().name(),
        format_width=root.format().width(),
        format_height=root.format().height(),
        proxy_mode=root["proxy"].value(),
    ).to_dict()


def _get_layer_channels(node_name: str) -> list[str]:
    import nuke
    node = nuke.toNode(node_name)
    if node is None:
        raise ValueError(f"Node '{node_name}' not found")
    return sorted(node.channels())


def _list_read_nodes() -> list[dict]:
    import nuke
    from nukebread.common.types import ReadNodeInfo
    results = []
    for node in nuke.allNodes("Read"):
        results.append(ReadNodeInfo(
            node_name=node.name(),
            file_path=node["file"].value(),
            first_frame=int(node["first"].value()),
            last_frame=int(node["last"].value()),
            colorspace=node["colorspace"].value(),
            format_name=node.format().name() if node.format() else "",
            channels=sorted(node.channels()),
        ).to_dict())
    return results


def _get_viewer_state() -> dict:
    import nuke
    from nukebread.common.types import ViewerState
    viewers = nuke.allNodes("Viewer")
    if not viewers:
        return ViewerState().to_dict()
    v = viewers[0]
    input_node = v.input(0)
    return ViewerState(
        viewer_node=v.name(),
        input_node=input_node.name() if input_node else "",
        channels=v["channels"].value() if v.knob("channels") else "rgba",
        exposure=v["exposure"].value() if v.knob("exposure") else 0.0,
        gain=v["gain"].value() if v.knob("gain") else 1.0,
        gamma=v["gamma"].value() if v.knob("gamma") else 1.0,
        frame=nuke.frame(),
    ).to_dict()


def _get_color_pipeline() -> dict:
    import nuke
    from nukebread.common.types import ColorPipeline
    root = nuke.root()
    return ColorPipeline(
        ocio_config=root["OCIO_config"].value() if root.knob("OCIO_config") else "",
        working_space=root["workingSpaceLUT"].value() if root.knob("workingSpaceLUT") else "",
        display=root["monitorLut"].value() if root.knob("monitorLut") else "",
        view=root["monitorOutLUT"].value() if root.knob("monitorOutLUT") else "",
        color_management=root["colorManagement"].value() if root.knob("colorManagement") else "Nuke",
    ).to_dict()


def _execute_python(code: str) -> dict:
    import nuke
    result_locals: dict = {}
    try:
        exec(code, {"nuke": nuke, "__builtins__": __builtins__}, result_locals)
        output = result_locals.get("result", None)
        return {"status": "ok", "output": str(output) if output is not None else None}
    except Exception as e:
        return {"status": "error", "error": f"{type(e).__name__}: {e}"}


def _undo(steps: int) -> str:
    import nuke
    for _ in range(steps):
        nuke.undo()
    return f"Undid {steps} step(s)"


def _begin_undo_group(name: str) -> str:
    import nuke
    nuke.Undo.begin(name)
    return f"Started undo group: {name}"


def _end_undo_group() -> str:
    import nuke
    nuke.Undo.end()
    return "Ended undo group"


def _save_script_backup() -> str:
    import nuke
    import os
    import time
    script_path = nuke.scriptName()
    if not script_path:
        return "No script saved yet — nothing to back up"
    base, ext = os.path.splitext(script_path)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    backup_path = f"{base}_backup_{timestamp}{ext}"
    nuke.scriptSaveAs(backup_path)
    nuke.scriptOpen(script_path)
    return f"Backup saved to {backup_path}"
