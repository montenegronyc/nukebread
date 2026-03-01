"""NukeBread plugin — runs inside Nuke's Python environment.

Call ``nukebread.plugin.start()`` from your menu.py to launch the bridge
server that the MCP server connects to over TCP.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nukebread.plugin.bridge import BridgeServer

_bridge: BridgeServer | None = None


def start() -> None:
    """Initialize and start the NukeBread bridge server.

    Intended to be called once from Nuke's menu.py, e.g.::

        import nukebread.plugin
        nukebread.plugin.start()

    The bridge server runs in a daemon thread so it does not prevent
    Nuke from exiting.  All registered command handlers dispatch their
    Nuke API calls back to the main thread via ``nuke.executeInMainThread``.
    """
    global _bridge

    if _bridge is not None:
        # Already running — avoid double-start.
        import nuke
        nuke.message("NukeBread bridge is already running.")
        return

    from nukebread.common.constants import BRIDGE_HOST, BRIDGE_PORT
    from nukebread.plugin.bridge import BridgeServer
    from nukebread.plugin import _register_default_handlers

    _bridge = BridgeServer(host=BRIDGE_HOST, port=BRIDGE_PORT)
    _register_default_handlers(_bridge)
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


def _register_default_handlers(bridge: BridgeServer) -> None:
    """Wire up all built-in command handlers."""
    from nukebread.plugin import serializer, node_factory, frame_grabber

    # --- Graph read commands ---
    bridge.register_handler("read_full_graph", lambda params: serializer.serialize_graph(
        include_viewers=params.get("include_viewers", False),
    ).model_dump())

    bridge.register_handler("read_selected_nodes", lambda params: serializer.serialize_selected().model_dump())

    bridge.register_handler("read_node_detail", lambda params: _node_detail(params["node_name"]))

    bridge.register_handler("trace_pipe", lambda params: [
        n.model_dump() for n in serializer.trace_pipe(
            params["node_name"], params.get("direction", "upstream"),
        )
    ])

    bridge.register_handler("find_nodes_by_class", lambda params: _find_by_class(params["class_name"]))

    bridge.register_handler("get_errors", lambda params: _get_errors())

    # --- Graph write commands ---
    bridge.register_handler("create_node", lambda params: node_factory.create_node(
        class_name=params["class_name"],
        name=params.get("name"),
        knobs=params.get("knobs"),
        connect_to=params.get("connect_to"),
        insert_after=params.get("insert_after"),
        x=params.get("x"),
        y=params.get("y"),
    ))

    bridge.register_handler("create_node_tree", lambda params: node_factory.create_node_tree(params["tree"]))

    bridge.register_handler("connect_nodes", lambda params: node_factory.connect(
        params["from_node"], params["to_node"], params.get("input_index", 0),
    ))

    bridge.register_handler("disconnect_node", lambda params: node_factory.disconnect(
        params["node_name"], params.get("input_index"),
    ))

    bridge.register_handler("delete_nodes", lambda params: node_factory.delete_nodes(params["node_names"]))

    bridge.register_handler("set_knob", lambda params: node_factory.set_knob_value(
        params["node_name"], params["knob_name"], params["value"],
    ))

    bridge.register_handler("set_expression", lambda params: node_factory.set_knob_expression(
        params["node_name"], params["knob_name"], params["expression"],
    ))

    bridge.register_handler("set_animation", lambda params: node_factory.set_animation_keys(
        params["node_name"], params["knob_name"], params["keyframes"],
    ))

    bridge.register_handler("duplicate_branch", lambda params: node_factory.duplicate_branch(params["node_name"]))

    bridge.register_handler("replace_node", lambda params: node_factory.replace_node(
        params["old_node"], params["new_class"], params.get("preserve_connections", True),
    ))

    # --- Vision commands ---
    bridge.register_handler("grab_frame", lambda params: frame_grabber.grab_frame(
        node_name=params.get("node_name"),
        frame=params.get("frame"),
    ).model_dump())

    bridge.register_handler("grab_roi", lambda params: frame_grabber.grab_roi(
        params["node_name"], params["x"], params["y"],
        params["width"], params["height"], params.get("frame"),
    ).model_dump())

    bridge.register_handler("grab_comparison", lambda params: frame_grabber.grab_comparison(
        params["node_a"], params["node_b"],
        frame=params.get("frame"), mode=params.get("mode", "wipe"),
    ).model_dump())

    bridge.register_handler("grab_frame_range", lambda params: [
        r.model_dump() for r in frame_grabber.grab_frame_range(
            params["node_name"], params["start"], params["end"], params.get("step", 1),
        )
    ])

    bridge.register_handler("read_pixel", lambda params: frame_grabber.read_pixel(
        params["node_name"], params["x"], params["y"], params.get("frame"),
    ).model_dump())

    # --- Project context commands ---
    bridge.register_handler("get_script_info", lambda params: _get_script_info())
    bridge.register_handler("get_layer_channels", lambda params: _get_layer_channels(params["node_name"]))
    bridge.register_handler("list_read_nodes", lambda params: _list_read_nodes())
    bridge.register_handler("get_viewer_state", lambda params: _get_viewer_state())
    bridge.register_handler("get_project_color_pipeline", lambda params: _get_color_pipeline())


# ---------------------------------------------------------------------------
# Inline helpers for project-context and graph-read commands that don't
# warrant their own module.
# ---------------------------------------------------------------------------

def _node_detail(node_name: str) -> dict:
    import nuke
    node = nuke.toNode(node_name)
    if node is None:
        raise ValueError(f"Node '{node_name}' not found")
    from nukebread.plugin.serializer import serialize_node
    return serialize_node(node, all_knobs=True).model_dump()


def _find_by_class(class_name: str) -> list[dict]:
    import nuke
    from nukebread.plugin.serializer import serialize_node
    return [
        serialize_node(n).model_dump()
        for n in nuke.allNodes(class_name)
    ]


def _get_errors() -> list[dict]:
    import nuke
    from nukebread.plugin.serializer import serialize_node
    results = []
    for node in nuke.allNodes():
        if node.hasError():
            results.append(serialize_node(node).model_dump())
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
    ).model_dump()


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
        ).model_dump())
    return results


def _get_viewer_state() -> dict:
    import nuke
    from nukebread.common.types import ViewerState
    viewers = nuke.allNodes("Viewer")
    if not viewers:
        return ViewerState().model_dump()
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
    ).model_dump()


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
    ).model_dump()
