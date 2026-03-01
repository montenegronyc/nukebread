"""MCP tool definitions. Import all tool registration functions."""

from nukebread.server.tools.graph_read import register as register_graph_read
from nukebread.server.tools.graph_write import register as register_graph_write
from nukebread.server.tools.vision import register as register_vision
from nukebread.server.tools.project import register as register_project
from nukebread.server.tools.execution import register as register_execution


def register_all_tools(server, nuke_client):
    """Register all tool groups with the MCP server."""
    register_graph_read(server, nuke_client)
    register_graph_write(server, nuke_client)
    register_vision(server, nuke_client)
    register_project(server, nuke_client)
    register_execution(server, nuke_client)
