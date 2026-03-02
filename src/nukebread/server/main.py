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

# Lazy-init RAG store (shared across MCP tools)
_rag_store = None

def _get_rag_store():
    global _rag_store
    if _rag_store is None:
        from nukebread.server.rag.store import CompPatternStore
        _rag_store = CompPatternStore()
    return _rag_store


async def _call(command: str, params: dict | None = None) -> str:
    """Send a command to the Nuke bridge and return JSON. Wraps errors clearly."""
    try:
        result = await nuke_client.send(command, params)
        return json.dumps(result)
    except ConnectionRefusedError:
        return json.dumps({"error": "Cannot connect to Nuke bridge on port 9100. Is the bridge running?"})
    except TimeoutError as e:
        return json.dumps({"error": str(e)})
    except Exception as e:
        return json.dumps({"error": f"{type(e).__name__}: {e}"})


# --- Graph Read ---

@mcp.tool()
async def read_full_graph(include_viewers: bool = False) -> str:
    """Return the complete node DAG as JSON. Filters out Viewer and BackdropNode noise by default."""
    return await _call("read_full_graph", {"include_viewers": include_viewers})

@mcp.tool()
async def read_selected_nodes() -> str:
    """Return currently selected nodes with their upstream and downstream connections."""
    return await _call("read_selected_nodes")

@mcp.tool()
async def read_node_detail(node_name: str) -> str:
    """Deep dump of every knob and its value on a specific node."""
    return await _call("read_node_detail", {"node_name": node_name})

@mcp.tool()
async def trace_pipe(node_name: str, direction: str = "upstream") -> str:
    """Follow the pipe chain from a node. Direction: 'upstream' or 'downstream'."""
    return await _call("trace_pipe", {"node_name": node_name, "direction": direction})

@mcp.tool()
async def find_nodes_by_class(class_name: str) -> str:
    """Find all nodes of a given class (e.g. 'Merge2', 'Grade', 'Read')."""
    return await _call("find_nodes_by_class", {"class_name": class_name})

@mcp.tool()
async def get_errors() -> str:
    """Return all nodes that have errors, with their error messages."""
    return await _call("get_errors")


# --- Graph Write ---

@mcp.tool()
async def create_node(class_name: str, name: str | None = None, knobs: dict | None = None, connect_to: str | None = None, insert_after: str | None = None) -> str:
    """Create a node. Optionally set knobs, connect to an existing node, or splice inline."""
    return await _call("create_node", {"class_name": class_name, "name": name, "knobs": knobs, "connect_to": connect_to, "insert_after": insert_after})

@mcp.tool()
async def create_node_tree(tree: list[dict]) -> str:
    """PREFERRED over create_node for multi-node setups. Batch-create nodes in a single call. Each dict: class_name, name, knobs, connect_from (name of earlier node in this list), input_index (0=B-pipe, 1=A-pipe), x, y. Auto-positions vertically when x/y omitted."""
    return await _call("create_node_tree", {"tree": tree})

@mcp.tool()
async def connect_nodes(from_node: str, to_node: str, input_index: int = 0) -> str:
    """Wire from_node's output into to_node's input at the given index."""
    return await _call("connect_nodes", {"from_node": from_node, "to_node": to_node, "input_index": input_index})

@mcp.tool()
async def disconnect_node(node_name: str, input_index: int | None = None) -> str:
    """Disconnect a node's input. If input_index is None, disconnect all inputs."""
    return await _call("disconnect_node", {"node_name": node_name, "input_index": input_index})

@mcp.tool()
async def delete_nodes(node_names: list[str]) -> str:
    """Delete the specified nodes with connection safety checks."""
    return await _call("delete_nodes", {"node_names": node_names})

@mcp.tool()
async def set_knob(node_name: str, knob_name: str, value: object) -> str:
    """Set any knob value on a node."""
    return await _call("set_knob", {"node_name": node_name, "knob_name": knob_name, "value": value})

@mcp.tool()
async def set_expression(node_name: str, knob_name: str, expression: str) -> str:
    """Write a Nuke expression (TCL or Python) on a knob."""
    return await _call("set_expression", {"node_name": node_name, "knob_name": knob_name, "expression": expression})

@mcp.tool()
async def set_animation(node_name: str, knob_name: str, keyframes: list[dict]) -> str:
    """Set animation keyframes. Each keyframe: {frame, value, interpolation?}."""
    return await _call("set_animation", {"node_name": node_name, "knob_name": knob_name, "keyframes": keyframes})

@mcp.tool()
async def duplicate_branch(node_name: str) -> str:
    """Duplicate a node and everything upstream of it."""
    return await _call("duplicate_branch", {"node_name": node_name})

@mcp.tool()
async def replace_node(old_node: str, new_class: str, preserve_connections: bool = True) -> str:
    """Swap a node's class while optionally preserving its connections."""
    return await _call("replace_node", {"old_node": old_node, "new_class": new_class, "preserve_connections": preserve_connections})


# --- Vision ---

@mcp.tool()
async def grab_frame(node_name: str | None = None, frame: int | None = None) -> str:
    """Render a frame and return it as base64-encoded PNG."""
    return await _call("grab_frame", {"node_name": node_name, "frame": frame})

@mcp.tool()
async def grab_roi(node_name: str, x: int, y: int, width: int, height: int, frame: int | None = None) -> str:
    """Grab a rectangular region of a frame as a base64 image."""
    return await _call("grab_roi", {"node_name": node_name, "x": x, "y": y, "width": width, "height": height, "frame": frame})

@mcp.tool()
async def grab_comparison(node_a: str, node_b: str, frame: int | None = None, mode: str = "wipe") -> str:
    """Render a before/after comparison. Mode: 'wipe', 'diff', or 'side_by_side'."""
    return await _call("grab_comparison", {"node_a": node_a, "node_b": node_b, "frame": frame, "mode": mode})

@mcp.tool()
async def grab_frame_range(node_name: str, start: int, end: int, step: int = 1) -> str:
    """Grab multiple frames for temporal analysis."""
    return await _call("grab_frame_range", {"node_name": node_name, "start": start, "end": end, "step": step})

@mcp.tool()
async def read_pixel(node_name: str, x: int, y: int, frame: int | None = None) -> str:
    """Sample RGBA pixel values at a specific coordinate."""
    return await _call("read_pixel", {"node_name": node_name, "x": x, "y": y, "frame": frame})


# --- Project Info ---

@mcp.tool()
async def get_script_info() -> str:
    """Return script metadata: name, frame range, format, fps, color management."""
    return await _call("get_script_info")

@mcp.tool()
async def get_layer_channels(node_name: str) -> str:
    """List all available channels at a given node in the pipe."""
    return await _call("get_layer_channels", {"node_name": node_name})

@mcp.tool()
async def list_read_nodes() -> str:
    """List all Read nodes with their file paths, frame ranges, and colorspace settings."""
    return await _call("list_read_nodes")

@mcp.tool()
async def get_viewer_state() -> str:
    """Return the current viewer state: active node, channels, exposure, gain."""
    return await _call("get_viewer_state")

@mcp.tool()
async def get_project_color_pipeline() -> str:
    """Return the OCIO config path, working colorspace, and display/view transform."""
    return await _call("get_project_color_pipeline")


# --- Execution & Safety ---

@mcp.tool()
async def execute_python(code: str) -> str:
    """Execute raw Python code in Nuke's script interpreter. Use for bulk operations — e.g. setting multiple knobs, creating complex setups, anything that would otherwise need many individual tool calls. You have full access to the `nuke` module. Store output in a variable named `result` to return it."""
    return await _call("execute_python", {"code": code})

@mcp.tool()
async def undo(steps: int = 1) -> str:
    """Undo the last action(s) in Nuke's undo stack."""
    return await _call("undo", {"steps": steps})

@mcp.tool()
async def begin_undo_group(name: str) -> str:
    """Start a named undo group. All subsequent operations become a single undo step."""
    return await _call("begin_undo_group", {"name": name})

@mcp.tool()
async def end_undo_group() -> str:
    """End the current undo group."""
    return await _call("end_undo_group")

@mcp.tool()
async def save_script_backup() -> str:
    """Save a timestamped backup of the current script."""
    return await _call("save_script_backup")


# --- RAG: Comp Pattern Library ---

@mcp.tool()
async def search_patterns(
    query: str,
    top_k: int = 5,
    category: str | None = None,
    node_classes: list[str] | None = None,
    include_graph: bool = False,
) -> str:
    """Search the comp pattern library for relevant techniques. Use this before building comps to find proven recipes.

    Categories: color_correction, keying, merge_operations, transform_motion,
    blur_defocus, 3d_compositing, camera_lens, matte_refinement, tracking, general_recipe.
    """
    store = _get_rag_store()
    results = store.search(
        query=query, top_k=top_k, category=category,
        node_classes=node_classes, include_graph=include_graph,
    )
    return json.dumps([
        {
            "pattern_id": r.pattern_id,
            "name": r.name,
            "description": r.description,
            "category": r.category,
            "similarity": round(r.similarity, 4),
            "node_count": r.node_count,
            "avg_score": r.avg_score,
            "graph_json": r.graph_json,
        }
        for r in results
    ], default=str)


@mcp.tool()
async def save_pattern(
    name: str,
    description: str,
    graph: dict,
    category: str | None = None,
    tags: list[str] | None = None,
    use_cases: list[str] | None = None,
    source_type: str = "manual",
) -> str:
    """Save the current comp (or part of it) as a reusable pattern in the library."""
    store = _get_rag_store()
    pattern_id = store.save_pattern(
        name=name,
        description=description,
        graph_dict=graph,
        category=category,
        tags=tags,
        use_cases=use_cases,
        source_type=source_type,
    )
    return json.dumps({"pattern_id": pattern_id, "status": "saved"})


@mcp.tool()
async def rate_pattern(
    pattern_id: int,
    success: bool,
    score: int | None = None,
    notes: str | None = None,
) -> str:
    """Rate a pattern after using it. Helps the library learn which patterns work best."""
    store = _get_rag_store()
    store.rate_pattern(pattern_id, success, score, notes)
    return json.dumps({"status": "rated", "pattern_id": pattern_id})


@mcp.tool()
async def get_pattern(pattern_id: int) -> str:
    """Get full details of a pattern including its node graph."""
    store = _get_rag_store()
    pattern = store.get_pattern(pattern_id)
    if pattern is None:
        return json.dumps({"error": f"Pattern {pattern_id} not found"})
    return json.dumps(pattern, default=str)


@mcp.tool()
async def list_patterns(category: str | None = None, limit: int = 20) -> str:
    """List patterns in the library, optionally filtered by category."""
    store = _get_rag_store()
    patterns = store.list_patterns(category=category, limit=limit)
    return json.dumps({"patterns": patterns, "count": len(patterns)}, default=str)


@mcp.tool()
async def pattern_stats() -> str:
    """Return statistics about the comp pattern library."""
    store = _get_rag_store()
    return json.dumps(store.stats())


@mcp.tool()
async def import_nk_file(file_path: str) -> str:
    """Import patterns from a .nk (Nuke script) file into the pattern library."""
    from nukebread.server.rag.nk_parser import parse_nk_file

    store = _get_rag_store()
    patterns = parse_nk_file(file_path)
    saved_ids = []
    for pattern in patterns:
        pid = store.save_pattern(
            name=pattern["name"],
            description=pattern["description"],
            graph_dict=pattern["graph"],
            category=pattern["category"],
            source_script=file_path,
            source_type="nk_import",
        )
        saved_ids.append(pid)

    return json.dumps({
        "status": "imported",
        "patterns_saved": len(saved_ids),
        "pattern_ids": saved_ids,
    })


@mcp.tool()
async def import_nk_folder(folder_path: str) -> str:
    """Bulk-import all .nk files from a folder into the pattern library.

    Parses each .nk file with full connection extraction, splits into
    connected sub-patterns, and stores them with embeddings for search.
    Skips duplicates automatically.
    """
    from nukebread.server.rag.nk_parser import parse_nk_file
    from pathlib import Path

    folder = Path(folder_path)
    if not folder.is_dir():
        return json.dumps({"error": f"Directory not found: {folder_path}"})

    nk_files = sorted(folder.glob("*.nk"))
    if not nk_files:
        return json.dumps({"error": f"No .nk files found in {folder_path}"})

    store = _get_rag_store()
    total_patterns = 0
    total_skipped = 0
    total_errors = 0
    file_results = []

    for nk_file in nk_files:
        try:
            patterns = parse_nk_file(str(nk_file))
            if not patterns:
                file_results.append({"file": nk_file.name, "patterns": 0, "status": "empty"})
                continue

            saved = 0
            skipped = 0
            for pattern in patterns:
                try:
                    store.save_pattern(
                        name=pattern["name"],
                        description=pattern["description"],
                        graph_dict=pattern["graph"],
                        category=pattern["category"],
                        source_script=str(nk_file),
                        source_type="nk_import",
                    )
                    saved += 1
                    total_patterns += 1
                except Exception as exc:
                    err_str = str(exc).lower()
                    if "unique" in err_str or "duplicate" in err_str:
                        skipped += 1
                        total_skipped += 1
                    else:
                        total_errors += 1

            file_results.append({
                "file": nk_file.name,
                "patterns": saved,
                "skipped": skipped,
            })
        except Exception as exc:
            total_errors += 1
            file_results.append({
                "file": nk_file.name,
                "patterns": 0,
                "error": str(exc),
            })

    stats = store.stats()
    return json.dumps({
        "status": "complete",
        "files_processed": len(nk_files),
        "patterns_saved": total_patterns,
        "duplicates_skipped": total_skipped,
        "errors": total_errors,
        "library_total": stats["total_patterns"],
        "files": file_results,
    })


# ------------------------------------------------------------------

def main() -> None:
    logging.basicConfig(level=logging.INFO)

    # Start RAG HTTP API on a daemon thread (for plugin-side access)
    try:
        from nukebread.server.rag.api import start_rag_api
        start_rag_api(port=9200)
    except Exception:
        logger.warning("Could not start RAG API — pattern library unavailable via HTTP", exc_info=True)

    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()
