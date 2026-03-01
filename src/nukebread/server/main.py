"""MCP server entry point. Runs as stdio subprocess."""

from __future__ import annotations

import json
import logging

from mcp.server import FastMCP

from nukebread.common.constants import SERVER_NAME
from nukebread.server.nuke_client import NukeClient

logger = logging.getLogger(__name__)

mcp = FastMCP(SERVER_NAME)
nuke_client = NukeClient()


# --- Graph Read ---

@mcp.tool()
async def read_full_graph(include_viewers: bool = False) -> str:
    """Return the complete node DAG as JSON. Filters out Viewer and BackdropNode noise by default."""
    return json.dumps(await nuke_client.send("read_full_graph", {"include_viewers": include_viewers}))

@mcp.tool()
async def read_selected_nodes() -> str:
    """Return currently selected nodes with their upstream and downstream connections."""
    return json.dumps(await nuke_client.send("read_selected_nodes"))

@mcp.tool()
async def read_node_detail(node_name: str) -> str:
    """Deep dump of every knob and its value on a specific node."""
    return json.dumps(await nuke_client.send("read_node_detail", {"node_name": node_name}))

@mcp.tool()
async def trace_pipe(node_name: str, direction: str = "upstream") -> str:
    """Follow the pipe chain from a node. Direction: 'upstream' or 'downstream'."""
    return json.dumps(await nuke_client.send("trace_pipe", {"node_name": node_name, "direction": direction}))

@mcp.tool()
async def find_nodes_by_class(class_name: str) -> str:
    """Find all nodes of a given class (e.g. 'Merge2', 'Grade', 'Read')."""
    return json.dumps(await nuke_client.send("find_nodes_by_class", {"class_name": class_name}))

@mcp.tool()
async def get_errors() -> str:
    """Return all nodes that have errors, with their error messages."""
    return json.dumps(await nuke_client.send("get_errors"))


# --- Graph Write ---

@mcp.tool()
async def create_node(class_name: str, name: str | None = None, knobs: dict | None = None, connect_to: str | None = None, insert_after: str | None = None) -> str:
    """Create a node. Optionally set knobs, connect to an existing node, or splice inline."""
    return json.dumps(await nuke_client.send("create_node", {"class_name": class_name, "name": name, "knobs": knobs, "connect_to": connect_to, "insert_after": insert_after}))

@mcp.tool()
async def create_node_tree(tree: list[dict]) -> str:
    """Batch-create nodes from a structured list. Each dict: class_name, name, knobs, connect_from, input_index."""
    return json.dumps(await nuke_client.send("create_node_tree", {"tree": tree}))

@mcp.tool()
async def connect_nodes(from_node: str, to_node: str, input_index: int = 0) -> str:
    """Wire from_node's output into to_node's input at the given index."""
    return json.dumps(await nuke_client.send("connect_nodes", {"from_node": from_node, "to_node": to_node, "input_index": input_index}))

@mcp.tool()
async def disconnect_node(node_name: str, input_index: int | None = None) -> str:
    """Disconnect a node's input. If input_index is None, disconnect all inputs."""
    return json.dumps(await nuke_client.send("disconnect_node", {"node_name": node_name, "input_index": input_index}))

@mcp.tool()
async def delete_nodes(node_names: list[str]) -> str:
    """Delete the specified nodes with connection safety checks."""
    return json.dumps(await nuke_client.send("delete_nodes", {"node_names": node_names}))

@mcp.tool()
async def set_knob(node_name: str, knob_name: str, value: object) -> str:
    """Set any knob value on a node."""
    return json.dumps(await nuke_client.send("set_knob", {"node_name": node_name, "knob_name": knob_name, "value": value}))

@mcp.tool()
async def set_expression(node_name: str, knob_name: str, expression: str) -> str:
    """Write a Nuke expression (TCL or Python) on a knob."""
    return json.dumps(await nuke_client.send("set_expression", {"node_name": node_name, "knob_name": knob_name, "expression": expression}))

@mcp.tool()
async def set_animation(node_name: str, knob_name: str, keyframes: list[dict]) -> str:
    """Set animation keyframes. Each keyframe: {frame, value, interpolation?}."""
    return json.dumps(await nuke_client.send("set_animation", {"node_name": node_name, "knob_name": knob_name, "keyframes": keyframes}))

@mcp.tool()
async def duplicate_branch(node_name: str) -> str:
    """Duplicate a node and everything upstream of it."""
    return json.dumps(await nuke_client.send("duplicate_branch", {"node_name": node_name}))

@mcp.tool()
async def replace_node(old_node: str, new_class: str, preserve_connections: bool = True) -> str:
    """Swap a node's class while optionally preserving its connections."""
    return json.dumps(await nuke_client.send("replace_node", {"old_node": old_node, "new_class": new_class, "preserve_connections": preserve_connections}))


# --- Vision ---

@mcp.tool()
async def grab_frame(node_name: str | None = None, frame: int | None = None) -> str:
    """Render a frame and return it as base64-encoded PNG."""
    return json.dumps(await nuke_client.send("grab_frame", {"node_name": node_name, "frame": frame}))

@mcp.tool()
async def grab_roi(node_name: str, x: int, y: int, width: int, height: int, frame: int | None = None) -> str:
    """Grab a rectangular region of a frame as a base64 image."""
    return json.dumps(await nuke_client.send("grab_roi", {"node_name": node_name, "x": x, "y": y, "width": width, "height": height, "frame": frame}))

@mcp.tool()
async def grab_comparison(node_a: str, node_b: str, frame: int | None = None, mode: str = "wipe") -> str:
    """Render a before/after comparison. Mode: 'wipe', 'diff', or 'side_by_side'."""
    return json.dumps(await nuke_client.send("grab_comparison", {"node_a": node_a, "node_b": node_b, "frame": frame, "mode": mode}))

@mcp.tool()
async def grab_frame_range(node_name: str, start: int, end: int, step: int = 1) -> str:
    """Grab multiple frames for temporal analysis."""
    return json.dumps(await nuke_client.send("grab_frame_range", {"node_name": node_name, "start": start, "end": end, "step": step}))

@mcp.tool()
async def read_pixel(node_name: str, x: int, y: int, frame: int | None = None) -> str:
    """Sample RGBA pixel values at a specific coordinate."""
    return json.dumps(await nuke_client.send("read_pixel", {"node_name": node_name, "x": x, "y": y, "frame": frame}))


# --- Project Info ---

@mcp.tool()
async def get_script_info() -> str:
    """Return script metadata: name, frame range, format, fps, color management."""
    return json.dumps(await nuke_client.send("get_script_info"))

@mcp.tool()
async def get_layer_channels(node_name: str) -> str:
    """List all available channels at a given node in the pipe."""
    return json.dumps(await nuke_client.send("get_layer_channels", {"node_name": node_name}))

@mcp.tool()
async def list_read_nodes() -> str:
    """List all Read nodes with their file paths, frame ranges, and colorspace settings."""
    return json.dumps(await nuke_client.send("list_read_nodes"))

@mcp.tool()
async def get_viewer_state() -> str:
    """Return the current viewer state: active node, channels, exposure, gain."""
    return json.dumps(await nuke_client.send("get_viewer_state"))

@mcp.tool()
async def get_project_color_pipeline() -> str:
    """Return the OCIO config path, working colorspace, and display/view transform."""
    return json.dumps(await nuke_client.send("get_project_color_pipeline"))


# --- Execution & Safety ---

@mcp.tool()
async def execute_python(code: str) -> str:
    """Execute raw Python code in Nuke's script interpreter."""
    return json.dumps(await nuke_client.send("execute_python", {"code": code}))

@mcp.tool()
async def undo(steps: int = 1) -> str:
    """Undo the last action(s) in Nuke's undo stack."""
    return json.dumps(await nuke_client.send("undo", {"steps": steps}))

@mcp.tool()
async def begin_undo_group(name: str) -> str:
    """Start a named undo group. All subsequent operations become a single undo step."""
    return json.dumps(await nuke_client.send("begin_undo_group", {"name": name}))

@mcp.tool()
async def end_undo_group() -> str:
    """End the current undo group."""
    return json.dumps(await nuke_client.send("end_undo_group"))

@mcp.tool()
async def save_script_backup() -> str:
    """Save a timestamped backup of the current script."""
    return json.dumps(await nuke_client.send("save_script_backup"))


# ------------------------------------------------------------------

def main() -> None:
    logging.basicConfig(level=logging.INFO)
    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()
