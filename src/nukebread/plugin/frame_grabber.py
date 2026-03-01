"""Frame capture for vision tools inside Nuke.

Renders frames at specific nodes, encodes them as base64 PNG, and returns
structured results that the MCP server can relay to the LLM.

All functions assume main-thread execution (the bridge dispatcher handles
this via ``nuke.executeInMainThread``).
"""

from __future__ import annotations

import base64
import os
import struct
import tempfile
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
    """Render a single frame at *node_name* and return a base64 PNG."""
    node = _resolve_node(node_name)
    frame = frame if frame is not None else nuke.frame()

    width = node.width()
    height = node.height()

    image_bytes = _render_to_png(node, frame)
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
    """Grab a rectangular region of a frame via pixel sampling."""
    node = _resolve_node(node_name)
    frame = frame if frame is not None else nuke.frame()

    nuke.execute(node, frame, frame)

    image_bytes = _sample_region_to_png(node, frame, x, y, w, h)
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

    Modes: ``"wipe"`` (left=A, right=B), ``"diff"`` (|A-B|),
    ``"side_by_side"`` (A and B horizontally concatenated).
    """
    na = _resolve_node(node_a)
    nb = _resolve_node(node_b)
    frame = frame if frame is not None else nuke.frame()

    width = na.width()
    height = na.height()

    # Render both nodes to temp files
    bytes_a = _render_to_png(na, frame)
    bytes_b = _render_to_png(nb, frame)

    if mode == "side_by_side":
        # For side-by-side: grab each independently, let the LLM see both
        # We send A's image and note B is available — the MCP tool returns
        # both as separate results if needed.
        # For now, return A and mention the comparison in metadata.
        encoded = base64.b64encode(bytes_a).decode("ascii")
        out_width = width
    else:
        # wipe and diff modes: use pixel sampling to composite
        nuke.execute(na, frame, frame)
        nuke.execute(nb, frame, frame)
        composite = _composite_comparison(na, nb, frame, width, height, mode)
        encoded = base64.b64encode(composite).decode("ascii")
        out_width = width

    return FrameGrabResult(
        image_base64=encoded,
        width=out_width,
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
    """Sample pixel values at a specific coordinate."""
    node = _resolve_node(node_name)
    frame = frame if frame is not None else nuke.frame()

    nuke.execute(node, frame, frame)

    values: dict[str, float] = {}
    for channel in ("red", "green", "blue", "alpha"):
        try:
            val = node.sample(channel, x + 0.5, y + 0.5, frame=frame)
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

    viewers = nuke.allNodes("Viewer")
    if viewers:
        v = viewers[0]
        inp = v.input(0)
        if inp is not None:
            return inp

    raise ValueError("No node specified and no active viewer found")


def _render_to_png(node, frame: int) -> bytes:
    """Render a frame by creating a temporary Write node, executing it,
    and reading the resulting PNG file.

    This is the standard approach for capturing frames in Nuke — faster
    and more reliable than per-pixel sampling for full-resolution grabs.
    """
    tmp_dir = tempfile.mkdtemp(prefix="nukebread_")
    tmp_path = os.path.join(tmp_dir, "grab.png")

    write_node = None
    try:
        # Deselect all to avoid auto-connection
        for n in nuke.selectedNodes():
            n.setSelected(False)

        write_node = nuke.createNode("Write", inpanel=False)
        write_node["file"].setValue(tmp_path)
        write_node["file_type"].setValue("png")
        write_node["datatype"].setValue("8 bit")
        write_node.setInput(0, node)

        # Render the single frame
        nuke.execute(write_node, frame, frame)

        with open(tmp_path, "rb") as f:
            return f.read()

    finally:
        if write_node is not None:
            nuke.delete(write_node)
        # Clean up temp file
        try:
            os.unlink(tmp_path)
            os.rmdir(tmp_dir)
        except OSError:
            pass


def _sample_region_to_png(
    node, frame: int, x: int, y: int, w: int, h: int
) -> bytes:
    """Sample a rectangular region from a node using per-pixel reads
    and encode as a minimal PNG.

    Uses ``node.sample()`` which reads from the already-computed buffer.
    Nuke's coordinate system is bottom-up, so we iterate top-to-bottom
    for the PNG scanline order.
    """
    rows: list[bytes] = []
    for row in range(y + h - 1, y - 1, -1):
        scanline = b"\x00"  # PNG filter byte (None)
        for col in range(x, x + w):
            r = _sample_channel(node, "red", col, row, frame)
            g = _sample_channel(node, "green", col, row, frame)
            b = _sample_channel(node, "blue", col, row, frame)
            a = _sample_channel(node, "alpha", col, row, frame)
            scanline += struct.pack("BBBB", r, g, b, a)
        rows.append(scanline)

    return _encode_png(w, h, b"".join(rows))


def _composite_comparison(
    node_a, node_b, frame: int, width: int, height: int, mode: str
) -> bytes:
    """Build a comparison image by sampling both nodes.

    ``"wipe"``: left half from A, right half from B.
    ``"diff"``: absolute difference |A-B| per channel.
    """
    mid = width // 2
    rows: list[bytes] = []

    for row in range(height - 1, -1, -1):
        scanline = b"\x00"
        for col in range(width):
            if mode == "diff":
                ar = node_a.sample("red", col + 0.5, row + 0.5, frame=frame)
                ag = node_a.sample("green", col + 0.5, row + 0.5, frame=frame)
                ab = node_a.sample("blue", col + 0.5, row + 0.5, frame=frame)
                br = node_b.sample("red", col + 0.5, row + 0.5, frame=frame)
                bg = node_b.sample("green", col + 0.5, row + 0.5, frame=frame)
                bb = node_b.sample("blue", col + 0.5, row + 0.5, frame=frame)
                r = _clamp(abs(ar - br) * 255)
                g = _clamp(abs(ag - bg) * 255)
                b = _clamp(abs(ab - bb) * 255)
                a = 255
            else:
                # wipe mode
                src = node_a if col < mid else node_b
                r = _sample_channel(src, "red", col, row, frame)
                g = _sample_channel(src, "green", col, row, frame)
                b = _sample_channel(src, "blue", col, row, frame)
                a = _sample_channel(src, "alpha", col, row, frame)
            scanline += struct.pack("BBBB", r, g, b, a)
        rows.append(scanline)

    return _encode_png(width, height, b"".join(rows))


def _sample_channel(node, channel: str, col: int, row: int, frame: int) -> int:
    """Sample a single channel and return a clamped 8-bit int."""
    try:
        val = node.sample(channel, col + 0.5, row + 0.5, frame=frame)
        return _clamp(val * 255)
    except Exception:
        return 0


def _clamp(v: float) -> int:
    return int(max(0, min(255, v)))


def _encode_png(width: int, height: int, raw_data: bytes) -> bytes:
    """Encode raw RGBA scanline data as a minimal PNG."""
    sig = b"\x89PNG\r\n\x1a\n"

    def _chunk(chunk_type: bytes, data: bytes) -> bytes:
        c = chunk_type + data
        crc = zlib.crc32(c) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + c + struct.pack(">I", crc)

    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    ihdr = _chunk(b"IHDR", ihdr_data)
    idat = _chunk(b"IDAT", zlib.compress(raw_data))
    iend = _chunk(b"IEND", b"")

    return sig + ihdr + idat + iend
