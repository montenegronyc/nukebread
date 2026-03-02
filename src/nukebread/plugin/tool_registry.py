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

        nuke.executeInMainThreadWithResult(_run_on_main)

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
    "create_node_tree": {
        "name": "create_node_tree",
        "description": "Batch-create a chain of connected nodes in one call. PREFERRED over create_node for multi-node setups. Each entry: class_name, name, knobs, connect_from (name of earlier node in this list), input_index (0=B-pipe, 1=A-pipe).",
        "input_schema": {
            "type": "object",
            "properties": {
                "tree": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "class_name": {"type": "string"},
                            "name": {"type": "string"},
                            "knobs": {"type": "object", "additionalProperties": True},
                            "connect_from": {"type": "string"},
                            "input_index": {"type": "integer"},
                            "x": {"type": "integer"},
                            "y": {"type": "integer"},
                        },
                        "required": ["class_name"],
                    },
                },
            },
            "required": ["tree"],
        },
    },
    "disconnect_node": {
        "name": "disconnect_node",
        "description": "Disconnect a node's input. If input_index is omitted, all inputs are disconnected.",
        "input_schema": {
            "type": "object",
            "properties": {
                "node_name": {"type": "string"},
                "input_index": {"type": "integer", "description": "Specific input to disconnect (omit for all)."},
            },
            "required": ["node_name"],
        },
    },
    "set_animation": {
        "name": "set_animation",
        "description": "Set animation keyframes on a knob. Each keyframe: {frame, value, interpolation?}.",
        "input_schema": {
            "type": "object",
            "properties": {
                "node_name": {"type": "string"},
                "knob_name": {"type": "string"},
                "keyframes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "frame": {"type": "integer"},
                            "value": {"type": "number"},
                            "interpolation": {"type": "string", "enum": ["smooth", "linear", "constant"]},
                        },
                        "required": ["frame", "value"],
                    },
                },
            },
            "required": ["node_name", "knob_name", "keyframes"],
        },
    },
    "duplicate_branch": {
        "name": "duplicate_branch",
        "description": "Duplicate a node and everything upstream of it.",
        "input_schema": {
            "type": "object",
            "properties": {
                "node_name": {"type": "string"},
            },
            "required": ["node_name"],
        },
    },
    "replace_node": {
        "name": "replace_node",
        "description": "Swap a node's class while preserving its connections.",
        "input_schema": {
            "type": "object",
            "properties": {
                "old_node": {"type": "string", "description": "Node to replace."},
                "new_class": {"type": "string", "description": "New node class."},
                "preserve_connections": {"type": "boolean", "description": "Keep wiring (default true)."},
            },
            "required": ["old_node", "new_class"],
        },
    },
    "grab_comparison": {
        "name": "grab_comparison",
        "description": "Render a before/after comparison of two nodes. Mode: wipe, diff, or side_by_side.",
        "input_schema": {
            "type": "object",
            "properties": {
                "node_a": {"type": "string"},
                "node_b": {"type": "string"},
                "frame": {"type": "integer"},
                "mode": {"type": "string", "enum": ["wipe", "diff", "side_by_side"]},
            },
            "required": ["node_a", "node_b"],
        },
    },
    "begin_undo_group": {
        "name": "begin_undo_group",
        "description": "Start a named undo group. All subsequent operations become a single undo step.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Name for the undo group."},
            },
            "required": ["name"],
        },
    },
    "end_undo_group": {
        "name": "end_undo_group",
        "description": "End the current undo group.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    "undo": {
        "name": "undo",
        "description": "Undo the last action(s).",
        "input_schema": {
            "type": "object",
            "properties": {
                "steps": {"type": "integer", "description": "Number of undo steps (default 1)."},
            },
            "required": [],
        },
    },
    "get_layer_channels": {
        "name": "get_layer_channels",
        "description": "List all available channels at a given node.",
        "input_schema": {
            "type": "object",
            "properties": {
                "node_name": {"type": "string"},
            },
            "required": ["node_name"],
        },
    },
    "get_viewer_state": {
        "name": "get_viewer_state",
        "description": "Return the current viewer state: active node, channels, exposure, gain.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    "get_project_color_pipeline": {
        "name": "get_project_color_pipeline",
        "description": "Return the OCIO config path, working colorspace, and display/view transform.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    "save_script_backup": {
        "name": "save_script_backup",
        "description": "Save a timestamped backup of the current script.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    "grab_roi": {
        "name": "grab_roi",
        "description": "Grab a rectangular region of a frame as a base64 image.",
        "input_schema": {
            "type": "object",
            "properties": {
                "node_name": {"type": "string"},
                "x": {"type": "integer"},
                "y": {"type": "integer"},
                "width": {"type": "integer"},
                "height": {"type": "integer"},
                "frame": {"type": "integer"},
            },
            "required": ["node_name", "x", "y", "width", "height"],
        },
    },
    "grab_frame_range": {
        "name": "grab_frame_range",
        "description": "Grab multiple frames for temporal analysis.",
        "input_schema": {
            "type": "object",
            "properties": {
                "node_name": {"type": "string"},
                "start": {"type": "integer"},
                "end": {"type": "integer"},
                "step": {"type": "integer"},
            },
            "required": ["node_name", "start", "end"],
        },
    },

    # --- RAG: Comp Pattern Library ---

    "save_pattern": {
        "name": "save_pattern",
        "description": "Save the current comp as a reusable pattern in the library. Reads the graph and sends it to the pattern store.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Descriptive name for the pattern."},
                "description": {"type": "string", "description": "What this comp does and when to use it."},
                "category": {"type": "string", "description": "Optional category override."},
                "tags": {"type": "array", "items": {"type": "string"}, "description": "Optional tags."},
            },
            "required": ["name", "description"],
        },
    },
    "rate_pattern": {
        "name": "rate_pattern",
        "description": "Rate a pattern after using it. Helps the library learn which patterns work best.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern_id": {"type": "integer", "description": "The pattern ID to rate."},
                "success": {"type": "boolean", "description": "Whether the pattern worked well."},
                "score": {"type": "integer", "description": "Rating 1-5 (optional)."},
                "notes": {"type": "string", "description": "Optional notes."},
            },
            "required": ["pattern_id", "success"],
        },
    },
}
