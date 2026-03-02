"""Parse .nk files (Nuke TCL scripts) into GraphData-compatible dicts.

Nuke scripts are TCL-based with a stack-oriented connection model:
  - Nodes are written top-to-bottom in a ClassName { knobs } block format
  - Each new node implicitly connects to the previous node via the stack
  - ``set VAR [stack 0]`` saves the current stack top to a variable
  - ``push $VAR`` restores a variable onto the stack (for branching)
  - ``push 0`` pushes a null (disconnected input)
  - ``inputs N`` declares how many inputs a node expects (popped from stack)

v2 parser: full connection extraction via stack simulation.
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

from nukebread.server.rag.formats import graph_to_text, classify_pattern


# Node classes that are NOT compositor nodes — skip during ingestion
_SKIP_CLASSES = frozenset({
    "Root", "Preferences", "Project",
    "define_window_layout_xml", "define_color_knobs",
    "Viewer", "BackdropNode", "StickyNote",
})

# Regex patterns for TCL stack operations
_RE_SET_STACK = re.compile(r'^set\s+(\w+)\s+\[stack\s+0\]', re.MULTILINE)
_RE_PUSH_VAR = re.compile(r'^push\s+\$(\w+)', re.MULTILINE)
_RE_PUSH_ZERO = re.compile(r'^push\s+0\s*$', re.MULTILINE)
_RE_NODE_OPEN = re.compile(r'^(\w+)\s*\{', re.MULTILINE)

# Expression/animation detection
_RE_CURVE = re.compile(r'\{curve\s')
_RE_TCL_EXPR = re.compile(r'\[|frame|random|noise|sin|cos|clamp')


def parse_nk_file(file_path: str) -> list[dict]:
    """Parse a .nk file and return a list of pattern dicts.

    Each dict has keys: ``name``, ``description``, ``graph``, ``category``.

    The script is split into connected components — each independent
    sub-graph becomes a separate pattern. The full script is always
    included as one pattern as well.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    text = path.read_text(encoding="utf-8", errors="replace")
    nodes = _parse_with_connections(text)

    if not nodes:
        return []

    patterns: list[dict] = []

    # Full script as one pattern
    full_graph = {
        "nodes": nodes,
        "script_name": path.stem,
        "frame_range": [1, 100],
        "current_frame": 1,
    }
    patterns.append({
        "name": path.stem,
        "description": graph_to_text(full_graph),
        "graph": full_graph,
        "category": classify_pattern(full_graph),
    })

    # Split into connected components (sub-patterns)
    components = _split_into_components(nodes)
    if len(components) > 1:
        for i, comp_nodes in enumerate(components):
            if len(comp_nodes) < 2:
                continue  # Skip trivial single-node components
            sub_graph = {
                "nodes": comp_nodes,
                "script_name": f"{path.stem}_part{i + 1}",
                "frame_range": [1, 100],
                "current_frame": 1,
            }
            patterns.append({
                "name": f"{path.stem}_part{i + 1}",
                "description": graph_to_text(sub_graph),
                "graph": sub_graph,
                "category": classify_pattern(sub_graph),
            })

    return patterns


def _parse_with_connections(text: str) -> list[dict]:
    """Parse .nk text with full stack simulation for connections.

    Simulates Nuke's stack-based connection model:
    1. Creating a node pops ``inputs`` items from the stack (default 1)
    2. The node itself is then pushed onto the stack
    3. ``set VAR [stack 0]`` saves stack top to a variable
    4. ``push $VAR`` restores a variable onto the stack
    5. ``push 0`` pushes None (disconnected)

    The first pop from the stack becomes input 0 (the B-pipe/main input).
    """
    nodes: list[dict] = []
    stack: list[str | None] = []       # Stack of node names (None = disconnected)
    variables: dict[str, str | None] = {}  # TCL variable -> node name

    # Parse into a sequence of operations
    operations = _tokenize(text)

    for op in operations:
        if op[0] == "set":
            # set VARNAME [stack 0]
            var_name = op[1]
            variables[var_name] = stack[-1] if stack else None

        elif op[0] == "push_var":
            # push $VARNAME
            var_name = op[1]
            stack.append(variables.get(var_name))

        elif op[0] == "push_zero":
            # push 0
            stack.append(None)

        elif op[0] == "node":
            class_name = op[1]
            body = op[2]

            knobs = _parse_knobs(body)

            # Extract input count before treating as a knob
            input_count = _to_int(knobs.pop("inputs", "1"))

            if class_name in _SKIP_CLASSES:
                # Consume inputs from stack to keep simulation accurate
                if input_count > 0:
                    for _ in range(min(input_count, len(stack))):
                        stack.pop()
                # Skipped nodes don't push onto the stack
                continue

            name = knobs.pop("name", class_name)
            xpos = _to_int(knobs.pop("xpos", "0"))
            ypos = _to_int(knobs.pop("ypos", "0"))
            label = knobs.pop("label", "")

            # Pop inputs from stack
            node_inputs: list[dict] = []
            if input_count == 0:
                # Source node — no inputs, just pushes itself
                pass
            else:
                for input_idx in range(input_count):
                    if stack:
                        source = stack.pop()
                    else:
                        source = None
                    if source is not None:
                        node_inputs.append({
                            "source_node": source,
                            "input_index": input_idx,
                        })

            # Build knob list with expression/animation detection
            knob_list = []
            for k, v in knobs.items():
                is_expr = _is_expression(v)
                is_anim = _is_animated(v)
                knob_list.append({
                    "name": k,
                    "type": "Unknown",
                    "value": None if is_expr else _coerce_value(v),
                    "expression": v if is_expr else None,
                    "animated": is_anim,
                })

            node_dict = {
                "name": name,
                "class_name": class_name,
                "x": xpos,
                "y": ypos,
                "inputs": node_inputs,
                "knobs": knob_list,
                "selected": False,
                "has_error": False,
                "error_message": None,
                "label": label,
                "tile_color": None,
            }
            nodes.append(node_dict)

            # Push this node onto the stack
            stack.append(name)

    return nodes


def _tokenize(text: str) -> list[tuple]:
    """Tokenize .nk text into a sequence of operations.

    Returns list of tuples:
      ("set", var_name)
      ("push_var", var_name)
      ("push_zero",)
      ("node", class_name, body_text)
    """
    ops: list[tuple] = []
    i = 0
    n = len(text)

    while i < n:
        # Skip whitespace/blank lines
        while i < n and text[i] in ' \t\n\r':
            i += 1
        if i >= n:
            break

        rest = text[i:]

        # Check for "set VAR [stack 0]"
        m = _RE_SET_STACK.match(rest)
        if m:
            ops.append(("set", m.group(1)))
            i += m.end()
            continue

        # Check for "push $VAR"
        m = _RE_PUSH_VAR.match(rest)
        if m:
            ops.append(("push_var", m.group(1)))
            i += m.end()
            continue

        # Check for "push 0"
        m = _RE_PUSH_ZERO.match(rest)
        if m:
            ops.append(("push_zero",))
            i += m.end()
            continue

        # Check for "ClassName {"
        m = _RE_NODE_OPEN.match(rest)
        if m:
            class_name = m.group(1)

            # Some non-node top-level blocks we skip entirely
            if class_name in ("add_layer", "version",
                              "define_window_layout_xml",
                              "define_color_knobs"):
                # Skip the entire block by finding the matching brace
                block_start = i + m.end()
                j = block_start
                depth = 1
                while j < n and depth > 0:
                    if text[j] == '{':
                        depth += 1
                    elif text[j] == '}':
                        depth -= 1
                    j += 1
                i = j
                continue

            # It's a node block — find the matching closing brace
            block_start = i + m.end()
            j = block_start
            depth = 1
            while j < n and depth > 0:
                if text[j] == '{':
                    depth += 1
                elif text[j] == '}':
                    depth -= 1
                j += 1

            body = text[block_start:j - 1]
            ops.append(("node", class_name, body))
            i = j
            continue

        # Skip comment lines (including #! shebang)
        if rest.startswith('#'):
            end = rest.find('\n')
            i += (end + 1) if end >= 0 else len(rest)
            continue

        # Skip add_layer without braces (single-line form)
        if rest.startswith('add_layer '):
            end = rest.find('\n')
            i += (end + 1) if end >= 0 else len(rest)
            continue

        # Skip version line
        if rest.startswith('version '):
            end = rest.find('\n')
            i += (end + 1) if end >= 0 else len(rest)
            continue

        # Skip anything else on this line
        end = rest.find('\n')
        i += (end + 1) if end >= 0 else len(rest)

    return ops


def _split_into_components(nodes: list[dict]) -> list[list[dict]]:
    """Split nodes into connected components (independent sub-graphs).

    Uses union-find on node connections to identify independent groups.
    """
    if len(nodes) <= 1:
        return [nodes]

    name_to_idx = {n["name"]: i for i, n in enumerate(nodes)}
    parent = list(range(len(nodes)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for i, node in enumerate(nodes):
        for conn in node.get("inputs", []):
            src_name = conn.get("source_node")
            if src_name and src_name in name_to_idx:
                union(i, name_to_idx[src_name])

    # Group by root
    groups: dict[int, list[dict]] = defaultdict(list)
    for i, node in enumerate(nodes):
        groups[find(i)].append(node)

    # Sort components by size (largest first)
    return sorted(groups.values(), key=len, reverse=True)


def _parse_knobs(body: str) -> dict[str, str]:
    """Parse knob assignments from a node body.

    Handles multi-line brace-wrapped values like:
        white {1.1 1.0 0.95 1.0}
        addUserKnob {20 User}
        control_points {3 3 3 6
         1 {-0.5 -0.5 0} ...}
    """
    knobs: dict[str, str] = {}
    lines = body.strip().split("\n")

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        i += 1

        if not line or line.startswith("#"):
            continue

        # Handle "knob_name value" format
        parts = line.split(None, 1)
        if len(parts) == 2:
            key, value = parts[0], parts[1]

            # If value has unmatched braces, collect continuation lines
            if "{" in value and value.count("{") > value.count("}"):
                while i < len(lines) and value.count("{") > value.count("}"):
                    value += "\n" + lines[i].strip()
                    i += 1

            knobs[key] = value
        elif len(parts) == 1:
            knobs[parts[0]] = "true"

    return knobs


def _is_expression(value: str) -> bool:
    """Detect if a knob value is a TCL/Python expression or animated curve."""
    if not isinstance(value, str):
        return False
    # Animated curves are effectively expressions
    if _is_animated(value):
        return True
    # Quoted expressions like "new?v(redness, greenness, blueness):color"
    if value.startswith('"') and ('?' in value or 'frame' in value or
                                  'random' in value):
        return True
    # TCL expressions with brackets or known functions
    if _RE_TCL_EXPR.search(value):
        # But not simple brace-wrapped lists like {1.0 0.5 0.3}
        if value.startswith('{') and value.endswith('}'):
            inner = value[1:-1].strip()
            # Simple number list? Not an expression
            try:
                [float(x) for x in inner.split()]
                return False
            except ValueError:
                pass
        return True
    return False


def _is_animated(value: str) -> bool:
    """Detect if a knob value contains animation curves."""
    if not isinstance(value, str):
        return False
    return bool(_RE_CURVE.search(value))


def _coerce_value(value: str):
    """Convert string values from .nk format to Python types."""
    # Strip surrounding quotes
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]

    # Try integer
    try:
        return int(value)
    except ValueError:
        pass

    # Try float
    try:
        return float(value)
    except ValueError:
        pass

    # Handle brace-wrapped lists like {1.0 0.5 0.3 1.0}
    if value.startswith("{") and value.endswith("}"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        try:
            return [float(x) for x in inner.split()]
        except ValueError:
            return inner

    # Boolean-ish
    if value == "true":
        return True
    if value == "false":
        return False

    return value


def _to_int(value: str) -> int:
    """Convert to int, defaulting to 0."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0


def build_connections_summary(nodes: list[dict]) -> str:
    """Build a compact connection fingerprint for a node graph.

    Example: ``Read→Grade→Merge2(over)[Read→Premult]``
    """
    if not nodes:
        return ""

    node_map = {n["name"]: n for n in nodes}

    # Find terminal nodes (not referenced as source by anyone)
    all_sources = set()
    for n in nodes:
        for conn in n.get("inputs", []):
            all_sources.add(conn.get("source_node", ""))
    terminals = [n for n in nodes if n["name"] not in all_sources]
    if not terminals:
        terminals = [nodes[-1]]

    # Walk upstream from the terminal with the most connections
    terminal = max(terminals, key=lambda n: len(n.get("inputs", [])),
                   default=nodes[-1])

    visited: set[str] = set()

    def _walk(node_name: str) -> str:
        if node_name in visited or node_name not in node_map:
            return node_name.split("_")[0] if "_" in node_name else node_name
        visited.add(node_name)
        node = node_map[node_name]
        cls = node["class_name"]

        inputs = sorted(node.get("inputs", []), key=lambda c: c["input_index"])
        if not inputs:
            return cls

        main_chain = ""
        side_branches: list[str] = []

        for conn in inputs:
            src = conn["source_node"]
            idx = conn["input_index"]
            upstream = _walk(src)

            if idx == 0:
                main_chain = f"{upstream}→{cls}"
            else:
                side_branches.append(f"[{upstream}]")

        # Add merge operation if present
        op_knob = next(
            (k for k in node.get("knobs", []) if k["name"] == "operation"),
            None,
        )
        if op_knob and op_knob.get("value"):
            main_chain = main_chain.replace(cls, f"{cls}({op_knob['value']})")

        result = main_chain or cls
        for sb in side_branches:
            result += sb

        return result

    summary = _walk(terminal["name"])
    # Truncate if too long
    if len(summary) > 500:
        summary = summary[:497] + "..."
    return summary
