"""MCP tools for reading the Nuke node graph."""

from __future__ import annotations

import json

from mcp.server import Server

from nukebread.server.nuke_client import NukeClient


def register(server: Server, nuke_client: NukeClient) -> None:
    """Register all graph-read tools with the MCP server."""

    @server.tool()
    async def read_full_graph(include_viewers: bool = False) -> str:
        """Return the complete node DAG as JSON. Filters out Viewer and BackdropNode noise by default."""
        result = await nuke_client.send("read_full_graph", {"include_viewers": include_viewers})
        return json.dumps(result)

    @server.tool()
    async def read_selected_nodes() -> str:
        """Return currently selected nodes with their upstream and downstream connections."""
        result = await nuke_client.send("read_selected_nodes")
        return json.dumps(result)

    @server.tool()
    async def read_node_detail(node_name: str) -> str:
        """Deep dump of every knob and its value on a specific node."""
        result = await nuke_client.send("read_node_detail", {"node_name": node_name})
        return json.dumps(result)

    @server.tool()
    async def trace_pipe(node_name: str, direction: str = "upstream") -> str:
        """Follow the pipe chain from a node. Direction: 'upstream' or 'downstream'."""
        result = await nuke_client.send("trace_pipe", {"node_name": node_name, "direction": direction})
        return json.dumps(result)

    @server.tool()
    async def find_nodes_by_class(class_name: str) -> str:
        """Find all nodes of a given class (e.g. 'Merge2', 'Grade', 'Read')."""
        result = await nuke_client.send("find_nodes_by_class", {"class_name": class_name})
        return json.dumps(result)

    @server.tool()
    async def get_errors() -> str:
        """Return all nodes that have errors, with their error messages."""
        result = await nuke_client.send("get_errors")
        return json.dumps(result)
