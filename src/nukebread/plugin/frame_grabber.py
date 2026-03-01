"""Frame capture for vision tools inside Nuke.

Renders frames at specific nodes, encodes them as base64 PNG, and returns
structured results that the MCP server can relay to the LLM.

All functions assume main-thread execution (the bridge dispatcher handles
this via ``nuke.executeInMainThread``).
"""

from __future__ import annotations

import base64
import struct
import tempfile
import os
import zlib
from typing import Any

import nuke

from nukebread.common.types import FrameGrabResult, PixelSample


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------


def grab_frame(
    node_name: str | None = None,
    frame: int | None = None,
) -> FrameGrabResult:
    """Render a single frame at *node_name* and return a base64 PNG.

    Parameters
    ----------
    node_name:
        Node to render.  If ``None``, the current viewer input is used.
    frame:
        Frame number.  If ``None``, the current script frame is used.
    """
    node = _resolve_node(node_name)
    frame = frame if frame is not None else nuke.frame()

    width = node.width()
    height = node.height()

    # Force a compute so pixel data is available.
    nuke.execute(node, frame, frame)

    image_bytes = _render_node_to_png(node, frame, width, height)
    encoded = base64.b64encode(image_bytes).decode("ascii")

    return FrameGrabResult(
        image_base64=encoded,
        width=width,
        height=height,
        frame=frame,
        node_name=node.name(),
    )


def grab_roi(
    node_name: str,
    x: int,
    y: int,
    w: int,
    h: int,
    frame: int | None = None,
) -> FrameGrabResult:
    """Grab a rectangular region of a frame.

    The ROI is specified in pixel coordinates from the bottom-left origin
    (Nuke's native coordinate system).
    """
    node = _resolve_node(node_name)
    frame = frame if frame is not None else nuke.frame()

    nuke.execute(node, frame, frame)

    # TODO: implement ROI cropping
    # Approach: sample the sub-region from the node's buffer using
    # node.sample(channel, x, y) in a nested loop, then encode
    # the cropped pixel block as PNG.  For now, grab the full frame
    # and note the region metadata.

    image_bytes = _render_node_to_png(node, frame, w, h, roi=(x, y, w, h))
    encoded = base64.b64encode(image_bytes).decode("ascii")

    return FrameGrabResult(
        image_base64=encoded,
        width=w,
        height=h,
        frame=frame,
        node_name=node.name(),
    )


def grab_comparison(
    node_a: str,
    node_b: str,
    frame: int | None = None,
    mode: str = "wipe",
) -> FrameGrabResult:
    """Render an A/B comparison of two nodes.

    Parameters
    ----------
    mode:
        ``"wipe"``  — left half from A, right half from B.
        ``"diff"``  — absolute difference image.
        ``"side_by_side"`` — A and B placed side by side.
    """
    na = _resolve_node(node_a)
    nb = _resolve_node(node_b)
    frame = frame if frame is not None else nuke.frame()

    nuke.execute(na, frame, frame)
    nuke.execute(nb, frame, frame)

    width = na.width()
    height = na.height()

    # TODO: implement full comparison modes
    # Approach for wipe: sample left half pixels from A, right half from B.
    # Approach for diff: sample both, compute |A-B| per channel.
    # Approach for side_by_side: create a 2x-wide image buffer.
    #
    # For now, use a temporary Contact Sheet / Merge setup or fall back
    # to grabbing node A as a placeholder.

    image_bytes = _render_node_to_png(na, frame, width, height)
    encoded = base64.b64encode(image_bytes).decode("ascii")

    return FrameGrabResult(
        image_base64=encoded,
        width=width,
        height=height,
        frame=frame,
        node_name=f"{na.name()} vs {nb.name()}",
        channels="rgba",
    )


def grab_frame_range(
    node_name: str,
    start: int,
    end: int,
    step: int = 1,
) -> list[FrameGrabResult]:
    """Grab multiple frames for temporal analysis."""
    results: list[FrameGrabResult] = []
    for f in range(start, end + 1, step):
        results.append(grab_frame(node_name, f))
    return results


def read_pixel(
    node_name: str,
    x: int,
    y: int,
    frame: int | None = None,
) -> PixelSample:
    """Sample pixel values at a specific coordinate.

    Returns per-channel float values using ``nuke.Node.sample()``.
    """
    node = _resolve_node(node_name)
    frame = frame if frame is not None else nuke.frame()

    nuke.execute(node, frame, frame)

    values: dict[str, float] = {}
    for channel in ("red", "green", "blue", "alpha"):
        try:
            val = node.sample(channel, x, y, frame=frame)
            values[channel] = val
        except Exception:
            values[channel] = 0.0

    return PixelSample(
        x=x,
        y=y,
        frame=frame,
        node_name=node.name(),
        values=values,
    )


# ------------------------------------------------------------------
# Private helpers
# ------------------------------------------------------------------


def _resolve_node(node_name: str | None):
    """Resolve a node name to a nuke.Node, defaulting to the viewer input."""
    if node_name is not None:
        node = nuke.toNode(node_name)
        if node is None:
            raise ValueError(f"Node '{node_name}' not found")
        return node

    # Fall back to the current viewer's input node.
    viewers = nuke.allNodes("Viewer")
    if viewers:
        v = viewers[0]
        inp = v.input(0)
        if inp is not None:
            return inp

    raise ValueError("No node specified and no active viewer found")


def _render_node_to_png(
    node,
    frame: int,
    width: int,
    height: int,
    roi: tuple[int, int, int, int] | None = None,
) -> bytes:
    """Sample pixel data from *node* and encode it as a PNG byte string.

    Uses ``nuke.Node.sample()`` to read per-pixel channel values and
    builds a minimal PNG with Python's stdlib (``zlib`` + ``struct``).
    This avoids external dependencies in Nuke's embedded Python.

    Parameters
    ----------
    roi:
        Optional (x, y, w, h) to read a sub-region.  When ``None``,
        reads the full width x height.
    """
    if roi is not None:
        rx, ry, rw, rh = roi
    else:
        rx, ry, rw, rh = 0, 0, width, height

    # TODO: implement full pixel sampling
    # The pattern is:
    #   rows = []
    #   for row in range(ry + rh - 1, ry - 1, -1):  # Nuke is bottom-up
    #       scanline = b"\x00"  # PNG filter byte (None)
    #       for col in range(rx, rx + rw):
    #           r = int(max(0, min(255, node.sample("red",   col + 0.5, row + 0.5, frame=frame) * 255)))
    #           g = int(max(0, min(255, node.sample("green", col + 0.5, row + 0.5, frame=frame) * 255)))
    #           b = int(max(0, min(255, node.sample("blue",  col + 0.5, row + 0.5, frame=frame) * 255)))
    #           a = int(max(0, min(255, node.sample("alpha", col + 0.5, row + 0.5, frame=frame) * 255)))
    #           scanline += struct.pack("BBBB", r, g, b, a)
    #       rows.append(scanline)
    #   raw = b"".join(rows)
    #
    # For performance on large images this should use nuke.execute() to
    # write a temp file and read it back.  The sample() approach works
    # for thumbnails / small ROIs.

    # Placeholder: produce a 1x1 transparent PNG so callers still get
    # valid base64 data.  Replace with real sampling above.
    return _minimal_png(rw, rh)


def _minimal_png(width: int, height: int) -> bytes:
    """Create a minimal valid RGBA PNG (transparent) of given dimensions.

    Used as a placeholder until full pixel sampling is implemented.
    """
    # PNG signature
    sig = b"\x89PNG\r\n\x1a\n"

    def _chunk(chunk_type: bytes, data: bytes) -> bytes:
        c = chunk_type + data
        crc = zlib.crc32(c) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + c + struct.pack(">I", crc)

    # IHDR
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    ihdr = _chunk(b"IHDR", ihdr_data)

    # IDAT — all pixels transparent black
    raw_row = b"\x00" + b"\x00\x00\x00\x00" * width
    raw = raw_row * height
    compressed = zlib.compress(raw)
    idat = _chunk(b"IDAT", compressed)

    # IEND
    iend = _chunk(b"IEND", b"")

    return sig + ihdr + idat + iend
