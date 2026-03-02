"""Convert GraphData dicts into embeddable text descriptions.

The output reads like a compositor describing the comp to a colleague:
'A grade feeding into a merge over the background, with an edge blur on
the matte channel feeding the merge mask.'
"""

from __future__ import annotations

from collections import Counter

# Node classes mapped to compositor categories
CATEGORY_KEYWORDS: dict[str, set[str]] = {
    "color_correction": {
        "Grade", "ColorCorrect", "HueCorrect", "Saturation",
        "ColorLookup", "OCIOColorSpace", "OCIOCDLTransform",
        "HueShift", "Clamp", "Invert", "Multiply",
    },
    "keying": {
        "Keylight", "IBKGizmo", "IBKColour", "Primatte",
        "ChromaKeyer", "Difference", "Keymix",
    },
    "merge_operations": {
        "Merge2", "Merge", "ChannelMerge", "Keymix",
        "AddMix", "Dissolve", "Switch",
    },
    "transform_motion": {
        "Transform", "CornerPin2D", "Tracker4", "Reconcile3D",
        "SplineWarp3", "GridWarp", "TransformMasked", "Stabilize2D",
    },
    "blur_defocus": {
        "Blur", "Defocus", "ZDefocus", "BokehBlur", "VectorBlur",
        "MotionBlur", "GodRays", "SoftClip",
    },
    "3d_compositing": {
        "ScanlineRender", "Card3D", "Camera3", "DeepMerge",
        "DeepToImage", "Scene", "ReadGeo2", "WriteGeo",
    },
    "camera_lens": {
        "LensDistortion", "ChromaticAberration", "Flare",
        "Vignette", "iDistort", "STMap",
    },
    "matte_refinement": {
        "EdgeBlur", "FilterErode", "Dilate", "LightWrap",
        "EdgeExtend", "SpillSuppress", "Erode",
    },
    "tracking": {
        "Tracker4", "CameraTracker", "PlanarTracker",
        "Reconcile3D", "CornerPin2D",
    },
    "particles": {
        "ParticleEmitter", "ParticleExpression", "ParticleSpawn",
        "ParticleTurbulence", "ParticleDrag", "ParticleGravity",
        "ParticlePointForce", "ParticleDirectionalForce", "ParticleWind",
        "ParticleVortex", "ParticleBounce", "ParticleSettings",
        "ParticleLookAt", "ParticleMotionAlign", "ParticleFuse",
        "ParticleCurve", "ParticleAttractToSphere", "ParticleKill",
    },
    "deep_compositing": {
        "DeepRead", "DeepWrite", "DeepMerge", "DeepToImage",
        "DeepFromImage", "DeepRecolor", "DeepExpression",
        "DeepCrop", "DeepTransform", "DeepHoldout",
    },
}


def graph_to_text(graph_dict: dict) -> str:
    """Convert a GraphData dict into embeddable natural language text.

    Produces a description like:
    'Comp pattern with 5 nodes: Read, Grade, Merge2, Blur, Write.
    Main pipe: Read_BG -> Grade_BG_Warmth -> Merge_CG.
    Grade_BG_Warmth: gain=[1.1, 1.0, 0.95, 1.0].
    Read_CG feeds into Merge_CG A-pipe.'
    """
    nodes = graph_dict.get("nodes", [])
    if not nodes:
        return "Empty pattern with no nodes."

    lines: list[str] = []
    node_map = {n["name"]: n for n in nodes}
    node_classes = [n["class_name"] for n in nodes]

    # Header summary
    class_summary = _summarize_classes(node_classes)
    lines.append(f"Comp pattern with {len(nodes)} nodes: {class_summary}.")

    # Trace the B-pipe (main chain through input 0)
    b_pipe = _trace_b_pipe(nodes, node_map)
    if b_pipe:
        pipe_desc = " -> ".join(
            f"{n['name']} ({n['class_name']})" for n in b_pipe
        )
        lines.append(f"Main pipe: {pipe_desc}.")

    # Key knob settings
    for node in nodes:
        knob_desc = _describe_knobs(node)
        if knob_desc:
            lines.append(f"{node['name']}: {knob_desc}")

    # Side branches (inputs other than 0)
    for node in nodes:
        for conn in node.get("inputs", []):
            if conn["input_index"] > 0:
                source = conn["source_node"]
                label = (
                    "A-pipe"
                    if conn["input_index"] == 1
                    else f"input {conn['input_index']}"
                )
                lines.append(f"{source} feeds into {node['name']} {label}.")

    # Labels (compositors put important notes in labels)
    for node in nodes:
        label = node.get("label", "")
        if label:
            lines.append(f"{node['name']} label: '{label}'.")

    return "\n".join(lines)


def classify_pattern(graph_dict: dict) -> str:
    """Auto-classify a pattern into a category based on node classes used."""
    nodes = graph_dict.get("nodes", [])
    classes_used = {n["class_name"] for n in nodes}

    scores: dict[str, int] = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        overlap = classes_used & keywords
        if overlap:
            scores[category] = len(overlap)

    if not scores:
        return "general_recipe"
    return max(scores, key=lambda k: scores[k])


def extract_node_classes(graph_dict: dict) -> list[str]:
    """Return sorted unique node classes from a graph dict."""
    return sorted({n["class_name"] for n in graph_dict.get("nodes", [])})


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _summarize_classes(classes: list[str]) -> str:
    """Produce a compact class summary like 'Grade, Merge2, Blur (x2)'."""
    counts = Counter(classes)
    parts: list[str] = []
    for cls, count in counts.most_common():
        if count > 1:
            parts.append(f"{cls} (x{count})")
        else:
            parts.append(cls)
    return ", ".join(parts)


def _trace_b_pipe(
    nodes: list[dict], node_map: dict[str, dict]
) -> list[dict]:
    """Find the main B-pipe chain by following input 0 connections."""
    # Nodes that are referenced as input 0 by another node
    has_downstream: set[str] = set()
    for node in nodes:
        for conn in node.get("inputs", []):
            if conn["input_index"] == 0:
                has_downstream.add(conn["source_node"])

    # Terminal node: has inputs but nobody references it as input 0
    terminal = None
    for node in nodes:
        if node["name"] not in has_downstream and node.get("inputs"):
            terminal = node
            break

    if terminal is None and nodes:
        terminal = nodes[-1]

    # Walk upstream through input 0
    chain: list[dict] = []
    current = terminal
    visited: set[str] = set()
    while current and current["name"] not in visited:
        visited.add(current["name"])
        chain.append(current)
        input_0 = None
        for conn in current.get("inputs", []):
            if conn["input_index"] == 0 and conn["source_node"] in node_map:
                input_0 = node_map[conn["source_node"]]
                break
        current = input_0

    chain.reverse()
    return chain


def _describe_knobs(node: dict) -> str:
    """Describe notable knob values on a node."""
    knobs = node.get("knobs", [])
    if not knobs:
        return ""

    # Skip boring/positional knobs
    skip = {
        "xpos", "ypos", "selected", "name", "label", "tile_color",
        "postage_stamp", "hide_input", "note_font", "note_font_size",
        "note_font_color", "dope_sheet", "bookmark", "gl_color",
        "mapsize", "cached", "process_mask", "inject", "indicators",
    }

    notable: list[str] = []
    for knob in knobs:
        name = knob["name"]
        value = knob["value"]
        if name in skip:
            continue
        if name == "disable" and value is False:
            continue
        # Skip default values that are uninformative
        if value is None or value == "" or value == 0:
            continue
        notable.append(f"{name}={value}")

    return ", ".join(notable[:8])  # cap to avoid huge descriptions
