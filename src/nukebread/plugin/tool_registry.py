"""Shared tool registry for NukeBread.

Both the TCP bridge (for MCP server) and the in-panel chat backend
use this registry to look up and execute command handlers.  The registry
also stores JSON schemas for each tool so the chat backend can send
them to the Claude API as tool definitions.
"""

from __future__ import annotations

import json
import traceback
from typing import Any, Callable

HandlerFunc = Callable[[dict[str, Any]], Any]


class ToolEntry:
    __slots__ = ("handler", "schema")

    def __init__(self, handler: HandlerFunc, schema: dict | None = None) -> None:
        self.handler = handler
        self.schema = schema


class ToolRegistry:
    """Central registry of command handlers and their API schemas."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolEntry] = {}

    def register(
        self,
        command: str,
        handler: HandlerFunc,
        schema: dict | None = None,
    ) -> None:
        """Register a handler for *command* with an optional Claude API tool schema."""
        self._tools[command] = ToolEntry(handler, schema)

    def get_handler(self, command: str) -> HandlerFunc | None:
        entry = self._tools.get(command)
        return entry.handler if entry else None

    def execute(self, command: str, params: dict) -> Any:
        """Run a handler on Nuke's main thread, returning the result.

        Raises ``KeyError`` if the command is not registered, and
        re-raises any exception thrown by the handler.
        """
        import nuke

        entry = self._tools.get(command)
        if entry is None:
            raise KeyError(f"Unknown command: {command}")

        result_box: dict[str, Any] = {}

        def _run_on_main() -> None:
            try:
                result_box["value"] = entry.handler(params)
            except Exception:
                result_box["error"] = traceback.format_exc()

        nuke.executeInMainThread(_run_on_main)

        if "error" in result_box:
            raise RuntimeError(result_box["error"])

        return result_box.get("value")

    def get_claude_tools(self) -> list[dict]:
        """Return tool definitions in Claude Messages API format."""
        tools: list[dict] = []
        for name, entry in self._tools.items():
            if entry.schema is not None:
                tools.append(entry.schema)
        return tools

    def has(self, command: str) -> bool:
        return command in self._tools


# ---------------------------------------------------------------------------
# Claude API tool schemas for the interactive chat subset
# ---------------------------------------------------------------------------

TOOL_SCHEMAS: dict[str, dict] = {
    "read_full_graph": {
        "name": "read_full_graph",
        "description": "Read the entire node graph. Returns all nodes with their connections, knobs, and positions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "include_viewers": {
                    "type": "boolean",
                    "description": "Include Viewer/Backdrop/StickyNote nodes (default false).",
                },
            },
            "required": [],
        },
    },
    "read_selected_nodes": {
        "name": "read_selected_nodes",
        "description": "Read only the currently selected nodes plus one level of upstream/downstream context.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    "read_node_detail": {
        "name": "read_node_detail",
        "description": "Get detailed info for a single node including all knobs.",
        "input_schema": {
            "type": "object",
            "properties": {
                "node_name": {"type": "string", "description": "Name of the node."},
            },
            "required": ["node_name"],
        },
    },
    "find_nodes_by_class": {
        "name": "find_nodes_by_class",
        "description": "Find all nodes of a given class (e.g. 'Grade', 'Merge2').",
        "input_schema": {
            "type": "object",
            "properties": {
                "class_name": {"type": "string", "description": "Nuke node class name."},
            },
            "required": ["class_name"],
        },
    },
    "get_errors": {
        "name": "get_errors",
        "description": "List all nodes that currently have errors.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    "trace_pipe": {
        "name": "trace_pipe",
        "description": "Follow connections upstream or downstream from a node.",
        "input_schema": {
            "type": "object",
            "properties": {
                "node_name": {"type": "string", "description": "Starting node."},
                "direction": {
                    "type": "string",
                    "enum": ["upstream", "downstream"],
                    "description": "Direction to trace (default upstream).",
                },
            },
            "required": ["node_name"],
        },
    },
    "create_node": {
        "name": "create_node",
        "description": "Create a new node in the graph. Returns the created node's name.",
        "input_schema": {
            "type": "object",
            "properties": {
                "class_name": {"type": "string", "description": "Nuke node class (e.g. Grade, Blur, Merge2)."},
                "name": {"type": "string", "description": "Desired node name."},
                "knobs": {
                    "type": "object",
                    "description": "Dict of knob_name -> value to set.",
                    "additionalProperties": True,
                },
                "connect_to": {"type": "string", "description": "Connect input 0 to this node's output."},
                "insert_after": {"type": "string", "description": "Splice inline after this node."},
                "x": {"type": "integer", "description": "X position."},
                "y": {"type": "integer", "description": "Y position."},
            },
            "required": ["class_name"],
        },
    },
    "connect_nodes": {
        "name": "connect_nodes",
        "description": "Wire one node's output into another node's input.",
        "input_schema": {
            "type": "object",
            "properties": {
                "from_node": {"type": "string", "description": "Source node name."},
                "to_node": {"type": "string", "description": "Destination node name."},
                "input_index": {"type": "integer", "description": "Input index on destination (default 0)."},
            },
            "required": ["from_node", "to_node"],
        },
    },
    "delete_nodes": {
        "name": "delete_nodes",
        "description": "Delete nodes by name. Attempts to preserve pipe connections.",
        "input_schema": {
            "type": "object",
            "properties": {
                "node_names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of node names to delete.",
                },
            },
            "required": ["node_names"],
        },
    },
    "set_knob": {
        "name": "set_knob",
        "description": "Set a knob value on an existing node.",
        "input_schema": {
            "type": "object",
            "properties": {
                "node_name": {"type": "string"},
                "knob_name": {"type": "string"},
                "value": {"description": "The value to set (number, string, list, etc)."},
            },
            "required": ["node_name", "knob_name", "value"],
        },
    },
    "set_expression": {
        "name": "set_expression",
        "description": "Set a TCL or Python expression on a knob.",
        "input_schema": {
            "type": "object",
            "properties": {
                "node_name": {"type": "string"},
                "knob_name": {"type": "string"},
                "expression": {"type": "string", "description": "The expression string."},
            },
            "required": ["node_name", "knob_name", "expression"],
        },
    },
    "grab_frame": {
        "name": "grab_frame",
        "description": "Render a frame at a node and return a base64 PNG image.",
        "input_schema": {
            "type": "object",
            "properties": {
                "node_name": {"type": "string", "description": "Node to render (default: viewer input)."},
                "frame": {"type": "integer", "description": "Frame number (default: current)."},
            },
            "required": [],
        },
    },
    "read_pixel": {
        "name": "read_pixel",
        "description": "Sample RGBA values at a specific pixel coordinate.",
        "input_schema": {
            "type": "object",
            "properties": {
                "node_name": {"type": "string"},
                "x": {"type": "integer"},
                "y": {"type": "integer"},
                "frame": {"type": "integer"},
            },
            "required": ["node_name", "x", "y"],
        },
    },
    "get_script_info": {
        "name": "get_script_info",
        "description": "Get script metadata: name, path, frame range, fps, format.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    "list_read_nodes": {
        "name": "list_read_nodes",
        "description": "List all Read nodes with their file paths and frame ranges.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    "execute_python": {
        "name": "execute_python",
        "description": "Execute arbitrary Python code in Nuke's interpreter. Assign to 'result' variable to return a value.",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Python code to execute."},
            },
            "required": ["code"],
        },
    },
}
