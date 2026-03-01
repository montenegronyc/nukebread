"""MCP server entry point. Runs as stdio subprocess."""

from __future__ import annotations

import asyncio
import logging
from mcp.server import Server
from mcp.server.stdio import stdio_server

from nukebread.common.constants import SERVER_NAME, VERSION
from nukebread.server.nuke_client import NukeClient
from nukebread.server.tools import register_all_tools

logger = logging.getLogger(__name__)


def create_server() -> tuple[Server, NukeClient]:
    server = Server(SERVER_NAME)
    nuke_client = NukeClient()
    register_all_tools(server, nuke_client)
    return server, nuke_client


async def run() -> None:
    server, nuke_client = create_server()

    try:
        await nuke_client.connect()
        logger.info(f"NukeBread MCP server v{VERSION} connected to Nuke bridge")
    except (ConnectionRefusedError, OSError):
        logger.warning("Could not connect to Nuke bridge — tools will attempt reconnection on first use")

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run())


if __name__ == "__main__":
    main()
