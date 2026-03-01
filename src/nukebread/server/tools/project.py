"""MCP tools for reading project context — script info, channels, color pipeline."""

from __future__ import annotations

import json

from mcp.server import Server

from nukebread.server.nuke_client import NukeClient


def register(server: Server, nuke_client: NukeClient) -> None:
    """Register all project-context tools with the MCP server."""

    @server.tool()
    async def get_script_info() -> str:
        """Return script metadata: name, frame range, format, fps, and color management settings."""
        result = await nuke_client.send("get_script_info")
        return json.dumps(result)

    @server.tool()
    async def get_layer_channels(node_name: str) -> str:
        """List all available channels (layers) at a given node in the pipe."""
        result = await nuke_client.send("get_layer_channels", {"node_name": node_name})
        return json.dumps(result)

    @server.tool()
    async def list_read_nodes() -> str:
        """List all Read nodes with their file paths, frame ranges, and colorspace settings."""
        result = await nuke_client.send("list_read_nodes")
        return json.dumps(result)

    @server.tool()
    async def get_viewer_state() -> str:
        """Return the current viewer state: active node, displayed channels, exposure, and gain."""
        result = await nuke_client.send("get_viewer_state")
        return json.dumps(result)

    @server.tool()
    async def get_project_color_pipeline() -> str:
        """Return the OCIO config path, working colorspace, and display/view transform."""
        result = await nuke_client.send("get_project_color_pipeline")
        return json.dumps(result)
