"""Data types shared between MCP server and Nuke plugin.

Uses stdlib dataclasses instead of pydantic so the plugin can run
inside Nuke's embedded Python without extra dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any


def _to_dict(obj) -> dict:
    """Convert a dataclass to a plain dict, recursively."""
    return asdict(obj)


# --- Graph Structure ---


@dataclass
class KnobValue:
    """A single knob's name, type, and current value."""

    name: str
    type: str
    value: Any
    expression: str | None = None
    animated: bool = False

    def to_dict(self) -> dict:
        return _to_dict(self)


@dataclass
class NodeConnection:
    """A connection between two nodes."""

    input_index: int
    source_node: str

    def to_dict(self) -> dict:
        return _to_dict(self)


@dataclass
class NodeInfo:
    """Serialized representation of a single Nuke node."""

    name: str
    class_name: str
    x: int = 0
    y: int = 0
    inputs: list[NodeConnection] = field(default_factory=list)
    knobs: list[KnobValue] = field(default_factory=list)
    selected: bool = False
    has_error: bool = False
    error_message: str | None = None
    label: str = ""
    tile_color: int | None = None

    def to_dict(self) -> dict:
        return _to_dict(self)


@dataclass
class GraphData:
    """Complete node graph as structured data."""

    nodes: list[NodeInfo] = field(default_factory=list)
    script_name: str = ""
    frame_range: tuple[int, int] = (1, 100)
    current_frame: int = 1

    def to_dict(self) -> dict:
        return _to_dict(self)


# --- Script / Project Info ---


@dataclass
class ScriptInfo:
    """Basic script metadata."""

    name: str = ""
    path: str = ""
    first_frame: int = 1
    last_frame: int = 100
    fps: float = 24.0
    format_name: str = ""
    format_width: int = 1920
    format_height: int = 1080
    proxy_mode: bool = False

    def to_dict(self) -> dict:
        return _to_dict(self)


@dataclass
class ReadNodeInfo:
    """Info about a Read node and its source footage."""

    node_name: str
    file_path: str
    first_frame: int = 1
    last_frame: int = 100
    colorspace: str = ""
    format_name: str = ""
    channels: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return _to_dict(self)


@dataclass
class ColorPipeline:
    """OCIO / color management state."""

    ocio_config: str = ""
    working_space: str = ""
    display: str = ""
    view: str = ""
    color_management: str = ""

    def to_dict(self) -> dict:
        return _to_dict(self)


@dataclass
class ViewerState:
    """Current viewer configuration."""

    viewer_node: str = ""
    input_node: str = ""
    channels: str = "rgba"
    exposure: float = 0.0
    gain: float = 1.0
    gamma: float = 1.0
    frame: int = 1

    def to_dict(self) -> dict:
        return _to_dict(self)


# --- Tool Parameters ---


@dataclass
class CreateNodeParams:
    """Parameters for creating a single node."""

    class_name: str
    name: str | None = None
    knobs: dict[str, Any] = field(default_factory=dict)
    connect_to: str | None = None
    insert_after: str | None = None
    x: int | None = None
    y: int | None = None


@dataclass
class NodeTreeEntry:
    """One entry in a batch node tree definition."""

    class_name: str
    name: str
    knobs: dict[str, Any] = field(default_factory=dict)
    connect_from: str | None = None
    input_index: int = 0


@dataclass
class KeyframeData:
    """A single keyframe."""

    frame: int
    value: float
    interpolation: str = "smooth"


class ComparisonMode(str, Enum):
    WIPE = "wipe"
    DIFF = "diff"
    SIDE_BY_SIDE = "side_by_side"


class TraceDirection(str, Enum):
    UPSTREAM = "upstream"
    DOWNSTREAM = "downstream"


# --- Vision Results ---


@dataclass
class FrameGrabResult:
    """Result of a frame grab — base64-encoded image."""

    image_base64: str
    width: int
    height: int
    frame: int
    node_name: str
    channels: str = "rgba"

    def to_dict(self) -> dict:
        return _to_dict(self)


@dataclass
class PixelSample:
    """Pixel value at a specific coordinate."""

    x: int
    y: int
    frame: int
    node_name: str
    values: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return _to_dict(self)
