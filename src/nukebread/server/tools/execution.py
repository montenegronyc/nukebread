"""MCP tools for execution, undo management, and script safety."""

from __future__ import annotations

import json

from mcp.server import Server

from nukebread.server.nuke_client import NukeClient


def register(server: Server, nuke_client: NukeClient) -> None:
    """Register all execution and safety tools with the MCP server."""

    @server.tool()
    async def execute_python(code: str) -> str:
        """Execute raw Python code in Nuke's script interpreter. Use for operations not covered by other tools."""
        result = await nuke_client.send("execute_python", {"code": code})
        return json.dumps(result)

    @server.tool()
    async def undo(steps: int = 1) -> str:
        """Undo the last action(s) in Nuke's undo stack."""
        result = await nuke_client.send("undo", {"steps": steps})
        return json.dumps(result)

    @server.tool()
    async def begin_undo_group(name: str) -> str:
        """Start a named undo group. All subsequent operations will be grouped into a single undo step."""
        result = await nuke_client.send("begin_undo_group", {"name": name})
        return json.dumps(result)

    @server.tool()
    async def end_undo_group() -> str:
        """End the current undo group."""
        result = await nuke_client.send("end_undo_group")
        return json.dumps(result)

    @server.tool()
    async def save_script_backup() -> str:
        """Save a timestamped backup of the current script before major operations."""
        result = await nuke_client.send("save_script_backup")
        return json.dumps(result)
