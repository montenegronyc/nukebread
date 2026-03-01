"""MCP tools for building and modifying the Nuke node graph."""

from __future__ import annotations

import json

from mcp.server import Server

from nukebread.server.nuke_client import NukeClient


def register(server: Server, nuke_client: NukeClient) -> None:
    """Register all graph-write tools with the MCP server."""

    @server.tool()
    async def create_node(
        class_name: str,
        name: str | None = None,
        knobs: dict | None = None,
        connect_to: str | None = None,
        insert_after: str | None = None,
    ) -> str:
        """Create a node. Optionally set knobs, connect its output to connect_to, or insert it after an existing node."""
        result = await nuke_client.send("create_node", {
            "class_name": class_name,
            "name": name,
            "knobs": knobs,
            "connect_to": connect_to,
            "insert_after": insert_after,
        })
        return json.dumps(result)

    @server.tool()
    async def create_node_tree(tree: list[dict]) -> str:
        """Batch-create nodes from a structured list of definitions. Each dict should have class_name and optional name, knobs, connect_to."""
        result = await nuke_client.send("create_node_tree", {"tree": tree})
        return json.dumps(result)

    @server.tool()
    async def connect_nodes(from_node: str, to_node: str, input_index: int = 0) -> str:
        """Wire from_node's output into to_node's input at the given index."""
        result = await nuke_client.send("connect_nodes", {
            "from_node": from_node,
            "to_node": to_node,
            "input_index": input_index,
        })
        return json.dumps(result)

    @server.tool()
    async def disconnect_node(node_name: str, input_index: int | None = None) -> str:
        """Disconnect a node's input. If input_index is None, disconnect all inputs."""
        result = await nuke_client.send("disconnect_node", {
            "node_name": node_name,
            "input_index": input_index,
        })
        return json.dumps(result)

    @server.tool()
    async def delete_nodes(node_names: list[str]) -> str:
        """Delete the specified nodes with connection safety checks."""
        result = await nuke_client.send("delete_nodes", {"node_names": node_names})
        return json.dumps(result)

    @server.tool()
    async def set_knob(node_name: str, knob_name: str, value: object) -> str:
        """Set any knob value on a node (e.g. size, mix, channels, file path)."""
        result = await nuke_client.send("set_knob", {
            "node_name": node_name,
            "knob_name": knob_name,
            "value": value,
        })
        return json.dumps(result)

    @server.tool()
    async def set_expression(node_name: str, knob_name: str, expression: str) -> str:
        """Write a Nuke expression (TCL or Python) on a knob."""
        result = await nuke_client.send("set_expression", {
            "node_name": node_name,
            "knob_name": knob_name,
            "expression": expression,
        })
        return json.dumps(result)

    @server.tool()
    async def set_animation(node_name: str, knob_name: str, keyframes: list[dict]) -> str:
        """Set animation keyframes on a knob. Each keyframe dict should have 'frame' and 'value', optionally 'interpolation'."""
        result = await nuke_client.send("set_animation", {
            "node_name": node_name,
            "knob_name": knob_name,
            "keyframes": keyframes,
        })
        return json.dumps(result)

    @server.tool()
    async def duplicate_branch(node_name: str) -> str:
        """Duplicate a node and everything upstream of it."""
        result = await nuke_client.send("duplicate_branch", {"node_name": node_name})
        return json.dumps(result)

    @server.tool()
    async def replace_node(old_node: str, new_class: str, preserve_connections: bool = True) -> str:
        """Swap a node's class while optionally preserving its input/output connections."""
        result = await nuke_client.send("replace_node", {
            "old_node": old_node,
            "new_class": new_class,
            "preserve_connections": preserve_connections,
        })
        return json.dumps(result)
