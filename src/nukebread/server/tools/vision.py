"""MCP tools for vision — frame grabs, pixel sampling, and comparisons."""

from __future__ import annotations

import json

from mcp.server import Server

from nukebread.server.nuke_client import NukeClient


def register(server: Server, nuke_client: NukeClient) -> None:
    """Register all vision tools with the MCP server."""

    @server.tool()
    async def grab_frame(node_name: str | None = None, frame: int | None = None) -> str:
        """Render a frame and return it as a base64-encoded image. Uses the current viewer node and frame if not specified."""
        result = await nuke_client.send("grab_frame", {
            "node_name": node_name,
            "frame": frame,
        })
        return json.dumps(result)

    @server.tool()
    async def grab_roi(
        node_name: str,
        x: int,
        y: int,
        width: int,
        height: int,
        frame: int | None = None,
    ) -> str:
        """Grab a specific rectangular region of a frame as a base64 image."""
        result = await nuke_client.send("grab_roi", {
            "node_name": node_name,
            "x": x,
            "y": y,
            "width": width,
            "height": height,
            "frame": frame,
        })
        return json.dumps(result)

    @server.tool()
    async def grab_comparison(
        node_a: str,
        node_b: str,
        frame: int | None = None,
        mode: str = "wipe",
    ) -> str:
        """Render a before/after comparison of two nodes. Mode: 'wipe', 'diff', or 'side_by_side'."""
        result = await nuke_client.send("grab_comparison", {
            "node_a": node_a,
            "node_b": node_b,
            "frame": frame,
            "mode": mode,
        })
        return json.dumps(result)

    @server.tool()
    async def grab_frame_range(
        node_name: str,
        start: int,
        end: int,
        step: int = 1,
    ) -> str:
        """Grab multiple frames for temporal analysis. Returns a list of base64 images."""
        result = await nuke_client.send("grab_frame_range", {
            "node_name": node_name,
            "start": start,
            "end": end,
            "step": step,
        })
        return json.dumps(result)

    @server.tool()
    async def read_pixel(
        node_name: str,
        x: int,
        y: int,
        frame: int | None = None,
    ) -> str:
        """Sample RGBA pixel values at a specific coordinate."""
        result = await nuke_client.send("read_pixel", {
            "node_name": node_name,
            "x": x,
            "y": y,
            "frame": frame,
        })
        return json.dumps(result)
