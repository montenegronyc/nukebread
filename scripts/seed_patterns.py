#!/usr/bin/env python3
"""Seed the comp pattern library with foundational patterns.

Run after the database is up:
    docker compose up -d
    uv run python scripts/seed_patterns.py
"""

from __future__ import annotations

import sys

from nukebread.server.rag.store import CompPatternStore

SEED_PATTERNS = [
    {
        "name": "Basic CG Over",
        "description": (
            "Standard CG element comp over a background plate. "
            "Premults the CG, applies a Grade for color matching, "
            "then Merges over the plate using the alpha channel."
        ),
        "category": "merge_operations",
        "tags": ["cg", "over", "premult", "merge"],
        "use_cases": [
            "Compositing a CG object onto a live-action plate",
            "Adding rendered 3D elements to a scene",
        ],
        "graph": {
            "nodes": [
                {"name": "Read_BG", "class_name": "Read", "x": 0, "y": 0,
                 "inputs": [], "knobs": [], "selected": False, "has_error": False,
                 "error_message": None, "label": "Background plate", "tile_color": None},
                {"name": "Read_CG", "class_name": "Read", "x": 200, "y": 0,
                 "inputs": [], "knobs": [], "selected": False, "has_error": False,
                 "error_message": None, "label": "CG render", "tile_color": None},
                {"name": "Premult_CG", "class_name": "Premult", "x": 200, "y": 50,
                 "inputs": [{"name": "Read_CG", "index": 0}], "knobs": [],
                 "selected": False, "has_error": False, "error_message": None,
                 "label": "", "tile_color": None},
                {"name": "Grade_CG", "class_name": "Grade", "x": 200, "y": 100,
                 "inputs": [{"name": "Premult_CG", "index": 0}],
                 "knobs": [
                     {"name": "whitepoint", "type": "Color_Knob",
                      "value": [1.0, 1.0, 1.0, 1.0], "expression": None, "animated": False},
                     {"name": "gamma", "type": "Color_Knob",
                      "value": [1.0, 1.0, 1.0, 1.0], "expression": None, "animated": False},
                 ],
                 "selected": False, "has_error": False, "error_message": None,
                 "label": "Match plate color", "tile_color": None},
                {"name": "Merge_CG", "class_name": "Merge2", "x": 0, "y": 150,
                 "inputs": [
                     {"name": "Read_BG", "index": 0},
                     {"name": "Grade_CG", "index": 1},
                 ],
                 "knobs": [
                     {"name": "operation", "type": "Enumeration_Knob",
                      "value": "over", "expression": None, "animated": False},
                 ],
                 "selected": False, "has_error": False, "error_message": None,
                 "label": "CG over BG", "tile_color": None},
            ],
            "script_name": "basic_cg_over",
            "frame_range": [1, 100],
            "current_frame": 1,
        },
    },
    {
        "name": "Chroma Key Pipeline",
        "description": (
            "Greenscreen keying workflow using Keylight for the primary key, "
            "followed by EdgeBlur for edge softening and an Erode to clean up "
            "edges. The resulting matte is applied via Premult before merging."
        ),
        "category": "keying",
        "tags": ["greenscreen", "keylight", "chroma", "keying", "matte"],
        "use_cases": [
            "Extracting a subject from a green/blue screen shoot",
            "Clean key with edge refinement",
        ],
        "graph": {
            "nodes": [
                {"name": "Read_GS", "class_name": "Read", "x": 0, "y": 0,
                 "inputs": [], "knobs": [], "selected": False, "has_error": False,
                 "error_message": None, "label": "Greenscreen plate", "tile_color": None},
                {"name": "Keylight_Main", "class_name": "OFXuk.co.thefoundry.keylight.keylight_v201",
                 "x": 0, "y": 50,
                 "inputs": [{"name": "Read_GS", "index": 0}],
                 "knobs": [
                     {"name": "screenColour", "type": "Color_Knob",
                      "value": [0.0, 1.0, 0.0], "expression": None, "animated": False},
                 ],
                 "selected": False, "has_error": False, "error_message": None,
                 "label": "Primary key", "tile_color": None},
                {"name": "EdgeBlur_Key", "class_name": "EdgeBlur", "x": 0, "y": 100,
                 "inputs": [{"name": "Keylight_Main", "index": 0}],
                 "knobs": [
                     {"name": "size", "type": "WH_Knob",
                      "value": 2.0, "expression": None, "animated": False},
                 ],
                 "selected": False, "has_error": False, "error_message": None,
                 "label": "Soften edges", "tile_color": None},
                {"name": "Erode_Key", "class_name": "FilterErode", "x": 0, "y": 150,
                 "inputs": [{"name": "EdgeBlur_Key", "index": 0}],
                 "knobs": [
                     {"name": "size", "type": "WH_Knob",
                      "value": -0.5, "expression": None, "animated": False},
                     {"name": "channels", "type": "Channel_Knob",
                      "value": "alpha", "expression": None, "animated": False},
                 ],
                 "selected": False, "has_error": False, "error_message": None,
                 "label": "Clean edges", "tile_color": None},
                {"name": "Premult_Key", "class_name": "Premult", "x": 0, "y": 200,
                 "inputs": [{"name": "Erode_Key", "index": 0}],
                 "knobs": [],
                 "selected": False, "has_error": False, "error_message": None,
                 "label": "", "tile_color": None},
            ],
            "script_name": "chroma_key_pipeline",
            "frame_range": [1, 100],
            "current_frame": 1,
        },
    },
    {
        "name": "Warm Grade on Plate",
        "description": (
            "Applies a warm golden-hour color grade to a plate. "
            "Uses Grade to lift the gain toward amber/gold, "
            "adds slight lift in the shadows, and a gentle gamma push."
        ),
        "category": "color_correction",
        "tags": ["grade", "warm", "color", "golden_hour"],
        "use_cases": [
            "Warming up a daylight exterior plate",
            "Adding a golden-hour feel to a shot",
        ],
        "graph": {
            "nodes": [
                {"name": "Read_Plate", "class_name": "Read", "x": 0, "y": 0,
                 "inputs": [], "knobs": [], "selected": False, "has_error": False,
                 "error_message": None, "label": "Source plate", "tile_color": None},
                {"name": "Grade_Warm", "class_name": "Grade", "x": 0, "y": 50,
                 "inputs": [{"name": "Read_Plate", "index": 0}],
                 "knobs": [
                     {"name": "whitepoint", "type": "Color_Knob",
                      "value": [1.1, 1.0, 0.85, 1.0], "expression": None, "animated": False},
                     {"name": "gamma", "type": "Color_Knob",
                      "value": [1.05, 1.0, 0.95, 1.0], "expression": None, "animated": False},
                     {"name": "black", "type": "Color_Knob",
                      "value": [0.02, 0.015, 0.01, 0.0], "expression": None, "animated": False},
                 ],
                 "selected": False, "has_error": False, "error_message": None,
                 "label": "Warm golden hour", "tile_color": None},
            ],
            "script_name": "warm_grade",
            "frame_range": [1, 100],
            "current_frame": 1,
        },
    },
    {
        "name": "Sky Replacement",
        "description": (
            "Replace the sky in a plate using a roto matte or keyed sky region. "
            "The new sky is graded to match, then merged under the foreground "
            "via a ChannelMerge on the matte."
        ),
        "category": "merge_operations",
        "tags": ["sky", "replacement", "roto", "merge"],
        "use_cases": [
            "Replacing an overcast sky with a dramatic sunset",
            "Adding clouds or CG sky to a clear plate",
        ],
        "graph": {
            "nodes": [
                {"name": "Read_Plate", "class_name": "Read", "x": 0, "y": 0,
                 "inputs": [], "knobs": [], "selected": False, "has_error": False,
                 "error_message": None, "label": "Original plate", "tile_color": None},
                {"name": "Read_Sky", "class_name": "Read", "x": 200, "y": 0,
                 "inputs": [], "knobs": [], "selected": False, "has_error": False,
                 "error_message": None, "label": "New sky", "tile_color": None},
                {"name": "Roto_SkyMask", "class_name": "Roto", "x": -200, "y": 50,
                 "inputs": [{"name": "Read_Plate", "index": 0}],
                 "knobs": [], "selected": False, "has_error": False,
                 "error_message": None, "label": "Sky mask", "tile_color": None},
                {"name": "Grade_Sky", "class_name": "Grade", "x": 200, "y": 50,
                 "inputs": [{"name": "Read_Sky", "index": 0}],
                 "knobs": [
                     {"name": "whitepoint", "type": "Color_Knob",
                      "value": [1.0, 1.0, 1.0, 1.0], "expression": None, "animated": False},
                 ],
                 "selected": False, "has_error": False, "error_message": None,
                 "label": "Match plate exposure", "tile_color": None},
                {"name": "Merge_Sky", "class_name": "Merge2", "x": 0, "y": 100,
                 "inputs": [
                     {"name": "Read_Plate", "index": 0},
                     {"name": "Grade_Sky", "index": 1},
                 ],
                 "knobs": [
                     {"name": "operation", "type": "Enumeration_Knob",
                      "value": "over", "expression": None, "animated": False},
                 ],
                 "selected": False, "has_error": False, "error_message": None,
                 "label": "Sky replacement", "tile_color": None},
            ],
            "script_name": "sky_replacement",
            "frame_range": [1, 100],
            "current_frame": 1,
        },
    },
    {
        "name": "Screen Merge for Flares",
        "description": (
            "Add a lens flare or light effect on top of a plate using Screen merge mode. "
            "The flare is graded for intensity, then Screen-merged which adds light without "
            "darkening the background."
        ),
        "category": "merge_operations",
        "tags": ["screen", "flare", "lens", "light", "additive"],
        "use_cases": [
            "Adding lens flares to a shot",
            "Layering light leaks or bokeh effects",
        ],
        "graph": {
            "nodes": [
                {"name": "Read_BG", "class_name": "Read", "x": 0, "y": 0,
                 "inputs": [], "knobs": [], "selected": False, "has_error": False,
                 "error_message": None, "label": "Background plate", "tile_color": None},
                {"name": "Read_Flare", "class_name": "Read", "x": 200, "y": 0,
                 "inputs": [], "knobs": [], "selected": False, "has_error": False,
                 "error_message": None, "label": "Flare element", "tile_color": None},
                {"name": "Grade_Flare", "class_name": "Grade", "x": 200, "y": 50,
                 "inputs": [{"name": "Read_Flare", "index": 0}],
                 "knobs": [
                     {"name": "multiply", "type": "Color_Knob",
                      "value": [0.8, 0.8, 0.8, 1.0], "expression": None, "animated": False},
                 ],
                 "selected": False, "has_error": False, "error_message": None,
                 "label": "Flare intensity", "tile_color": None},
                {"name": "Merge_Flare", "class_name": "Merge2", "x": 0, "y": 100,
                 "inputs": [
                     {"name": "Read_BG", "index": 0},
                     {"name": "Grade_Flare", "index": 1},
                 ],
                 "knobs": [
                     {"name": "operation", "type": "Enumeration_Knob",
                      "value": "screen", "expression": None, "animated": False},
                 ],
                 "selected": False, "has_error": False, "error_message": None,
                 "label": "Screen flare", "tile_color": None},
            ],
            "script_name": "screen_merge_flares",
            "frame_range": [1, 100],
            "current_frame": 1,
        },
    },
    {
        "name": "Edge Extend for Keying",
        "description": (
            "Extends the edges of a keyed element to remove dark halos. "
            "Uses an EdgeExtend node (or Blur+iDistort technique) to push "
            "edge colors outward before premulting."
        ),
        "category": "matte_refinement",
        "tags": ["edge", "extend", "halo", "keying", "despill"],
        "use_cases": [
            "Removing dark halos from a keyed element",
            "Fixing edge contamination after a chroma key",
        ],
        "graph": {
            "nodes": [
                {"name": "Read_Keyed", "class_name": "Read", "x": 0, "y": 0,
                 "inputs": [], "knobs": [], "selected": False, "has_error": False,
                 "error_message": None, "label": "Keyed element (unpremult)", "tile_color": None},
                {"name": "Unpremult_In", "class_name": "Unpremult", "x": 0, "y": 50,
                 "inputs": [{"name": "Read_Keyed", "index": 0}],
                 "knobs": [], "selected": False, "has_error": False,
                 "error_message": None, "label": "", "tile_color": None},
                {"name": "EdgeExtend", "class_name": "EdgeExtend", "x": 0, "y": 100,
                 "inputs": [{"name": "Unpremult_In", "index": 0}],
                 "knobs": [
                     {"name": "slices", "type": "Int_Knob",
                      "value": 5, "expression": None, "animated": False},
                     {"name": "blurSize", "type": "WH_Knob",
                      "value": 3.0, "expression": None, "animated": False},
                 ],
                 "selected": False, "has_error": False, "error_message": None,
                 "label": "Push edge color outward", "tile_color": None},
                {"name": "Premult_Out", "class_name": "Premult", "x": 0, "y": 150,
                 "inputs": [{"name": "EdgeExtend", "index": 0}],
                 "knobs": [], "selected": False, "has_error": False,
                 "error_message": None, "label": "", "tile_color": None},
            ],
            "script_name": "edge_extend_keying",
            "frame_range": [1, 100],
            "current_frame": 1,
        },
    },
    {
        "name": "Defocus Background for Depth",
        "description": (
            "Apply a ZDefocus or Defocus to the background behind a subject "
            "to simulate shallow depth of field. Uses a roto mask to protect "
            "the subject area."
        ),
        "category": "blur_defocus",
        "tags": ["defocus", "depth", "bokeh", "blur", "dof"],
        "use_cases": [
            "Creating shallow depth of field in a flat-lit shot",
            "Drawing attention to a subject by blurring the background",
        ],
        "graph": {
            "nodes": [
                {"name": "Read_Plate", "class_name": "Read", "x": 0, "y": 0,
                 "inputs": [], "knobs": [], "selected": False, "has_error": False,
                 "error_message": None, "label": "Source plate", "tile_color": None},
                {"name": "Roto_Subject", "class_name": "Roto", "x": -200, "y": 50,
                 "inputs": [{"name": "Read_Plate", "index": 0}],
                 "knobs": [], "selected": False, "has_error": False,
                 "error_message": None, "label": "Subject mask", "tile_color": None},
                {"name": "Defocus_BG", "class_name": "Defocus", "x": 0, "y": 100,
                 "inputs": [{"name": "Read_Plate", "index": 0}],
                 "knobs": [
                     {"name": "defocus", "type": "WH_Knob",
                      "value": 15.0, "expression": None, "animated": False},
                     {"name": "ratio", "type": "Double_Knob",
                      "value": 1.0, "expression": None, "animated": False},
                 ],
                 "selected": False, "has_error": False, "error_message": None,
                 "label": "Background defocus", "tile_color": None},
            ],
            "script_name": "defocus_background",
            "frame_range": [1, 100],
            "current_frame": 1,
        },
    },
    {
        "name": "Stabilize and Matchmove",
        "description": (
            "Stabilizes a plate using a Tracker, applies corrections on the "
            "stabilized frame, then re-applies the original camera motion. "
            "Classic stabilize-paint-matchmove workflow."
        ),
        "category": "tracking",
        "tags": ["tracker", "stabilize", "matchmove", "paint"],
        "use_cases": [
            "Removing an object from a moving shot",
            "Clean-plating on a shaky handheld shot",
        ],
        "graph": {
            "nodes": [
                {"name": "Read_Plate", "class_name": "Read", "x": 0, "y": 0,
                 "inputs": [], "knobs": [], "selected": False, "has_error": False,
                 "error_message": None, "label": "Source plate", "tile_color": None},
                {"name": "Tracker_Stabilize", "class_name": "Tracker4", "x": 0, "y": 50,
                 "inputs": [{"name": "Read_Plate", "index": 0}],
                 "knobs": [
                     {"name": "transform", "type": "Enumeration_Knob",
                      "value": "stabilize", "expression": None, "animated": False},
                 ],
                 "selected": False, "has_error": False, "error_message": None,
                 "label": "Stabilize", "tile_color": None},
                {"name": "RotoPaint_Fix", "class_name": "RotoPaint", "x": 0, "y": 100,
                 "inputs": [{"name": "Tracker_Stabilize", "index": 0}],
                 "knobs": [], "selected": False, "has_error": False,
                 "error_message": None, "label": "Paint on stabilized", "tile_color": None},
                {"name": "Tracker_Matchmove", "class_name": "Tracker4", "x": 0, "y": 150,
                 "inputs": [{"name": "RotoPaint_Fix", "index": 0}],
                 "knobs": [
                     {"name": "transform", "type": "Enumeration_Knob",
                      "value": "match-move", "expression": None, "animated": False},
                 ],
                 "selected": False, "has_error": False, "error_message": None,
                 "label": "Re-apply motion", "tile_color": None},
            ],
            "script_name": "stabilize_matchmove",
            "frame_range": [1, 100],
            "current_frame": 1,
        },
    },
    {
        "name": "Vignette Effect",
        "description": (
            "Creates a radial vignette darkening toward the edges of frame. "
            "Uses a Radial node to generate a soft elliptical mask, "
            "then a Grade to darken the edges."
        ),
        "category": "color_correction",
        "tags": ["vignette", "radial", "grade", "darkening"],
        "use_cases": [
            "Adding cinematic vignette to a shot",
            "Drawing focus to the center of frame",
        ],
        "graph": {
            "nodes": [
                {"name": "Read_Plate", "class_name": "Read", "x": 0, "y": 0,
                 "inputs": [], "knobs": [], "selected": False, "has_error": False,
                 "error_message": None, "label": "Source plate", "tile_color": None},
                {"name": "Radial_Vignette", "class_name": "Radial", "x": -200, "y": 50,
                 "inputs": [],
                 "knobs": [
                     {"name": "area", "type": "Box_Knob",
                      "value": [200, 200, 1720, 880], "expression": None, "animated": False},
                     {"name": "softness", "type": "Double_Knob",
                      "value": 250.0, "expression": None, "animated": False},
                 ],
                 "selected": False, "has_error": False, "error_message": None,
                 "label": "Vignette shape", "tile_color": None},
                {"name": "Grade_Vignette", "class_name": "Grade", "x": 0, "y": 100,
                 "inputs": [{"name": "Read_Plate", "index": 0}],
                 "knobs": [
                     {"name": "multiply", "type": "Color_Knob",
                      "value": [0.65, 0.65, 0.65, 1.0], "expression": None, "animated": False},
                 ],
                 "selected": False, "has_error": False, "error_message": None,
                 "label": "Darken edges", "tile_color": None},
            ],
            "script_name": "vignette_effect",
            "frame_range": [1, 100],
            "current_frame": 1,
        },
    },
    {
        "name": "Glow Effect",
        "description": (
            "Adds a bloom/glow to bright areas of the image. "
            "Extracts highlights via a Keyer or Expression, blurs them, "
            "then Screen-merges back onto the original."
        ),
        "category": "camera_lens",
        "tags": ["glow", "bloom", "highlights", "screen"],
        "use_cases": [
            "Adding bloom to practical lights",
            "Creating ethereal glow on bright elements",
        ],
        "graph": {
            "nodes": [
                {"name": "Read_Plate", "class_name": "Read", "x": 0, "y": 0,
                 "inputs": [], "knobs": [], "selected": False, "has_error": False,
                 "error_message": None, "label": "Source plate", "tile_color": None},
                {"name": "Expression_Highlights", "class_name": "Expression", "x": 200, "y": 0,
                 "inputs": [{"name": "Read_Plate", "index": 0}],
                 "knobs": [
                     {"name": "expr0", "type": "String_Knob",
                      "value": "clamp(r-0.8, 0, 100)", "expression": None, "animated": False},
                     {"name": "expr1", "type": "String_Knob",
                      "value": "clamp(g-0.8, 0, 100)", "expression": None, "animated": False},
                     {"name": "expr2", "type": "String_Knob",
                      "value": "clamp(b-0.8, 0, 100)", "expression": None, "animated": False},
                 ],
                 "selected": False, "has_error": False, "error_message": None,
                 "label": "Extract highlights", "tile_color": None},
                {"name": "Blur_Glow", "class_name": "Blur", "x": 200, "y": 50,
                 "inputs": [{"name": "Expression_Highlights", "index": 0}],
                 "knobs": [
                     {"name": "size", "type": "WH_Knob",
                      "value": 50.0, "expression": None, "animated": False},
                 ],
                 "selected": False, "has_error": False, "error_message": None,
                 "label": "Bloom blur", "tile_color": None},
                {"name": "Merge_Glow", "class_name": "Merge2", "x": 0, "y": 100,
                 "inputs": [
                     {"name": "Read_Plate", "index": 0},
                     {"name": "Blur_Glow", "index": 1},
                 ],
                 "knobs": [
                     {"name": "operation", "type": "Enumeration_Knob",
                      "value": "screen", "expression": None, "animated": False},
                 ],
                 "selected": False, "has_error": False, "error_message": None,
                 "label": "Add glow", "tile_color": None},
            ],
            "script_name": "glow_effect",
            "frame_range": [1, 100],
            "current_frame": 1,
        },
    },
]


def main() -> None:
    store = CompPatternStore()

    print(f"Seeding {len(SEED_PATTERNS)} patterns...")
    for pattern_data in SEED_PATTERNS:
        try:
            pid = store.save_pattern(
                name=pattern_data["name"],
                description=pattern_data["description"],
                graph_dict=pattern_data["graph"],
                category=pattern_data["category"],
                tags=pattern_data.get("tags"),
                use_cases=pattern_data.get("use_cases"),
                source_type="seed",
            )
            print(f"  [{pid}] {pattern_data['name']} ({pattern_data['category']})")
        except Exception as exc:
            print(f"  FAILED: {pattern_data['name']} — {exc}", file=sys.stderr)

    stats = store.stats()
    print(f"\nDone. Library now has {stats['total_patterns']} patterns, "
          f"{stats['embedded_chunks']} embedded chunks.")


if __name__ == "__main__":
    main()
