"""Pydantic models shared between MCP server and Nuke plugin."""

from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field


# --- Graph Structure ---


class KnobValue(BaseModel):
    """A single knob's name, type, and current value."""

    name: str
    type: str  # e.g. "Double_Knob", "Color_Knob", "Enumeration_Knob"
    value: object  # actual value — float, list, str, bool, etc.
    expression: str | None = None
    animated: bool = False


class NodeConnection(BaseModel):
    """A connection between two nodes."""

    input_index: int
    source_node: str


class NodeInfo(BaseModel):
    """Serialized representation of a single Nuke node."""

    name: str
    class_name: str  # e.g. "Grade", "Merge2", "Read"
    x: int = 0
    y: int = 0
    inputs: list[NodeConnection] = Field(default_factory=list)
    knobs: list[KnobValue] = Field(default_factory=list)
    selected: bool = False
    has_error: bool = False
    error_message: str | None = None
    label: str = ""
    tile_color: int | None = None


class GraphData(BaseModel):
    """Complete node graph as structured data."""

    nodes: list[NodeInfo] = Field(default_factory=list)
    script_name: str = ""
    frame_range: tuple[int, int] = (1, 100)
    current_frame: int = 1


# --- Script / Project Info ---


class ScriptInfo(BaseModel):
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


class ReadNodeInfo(BaseModel):
    """Info about a Read node and its source footage."""

    node_name: str
    file_path: str
    first_frame: int = 1
    last_frame: int = 100
    colorspace: str = ""
    format_name: str = ""
    channels: list[str] = Field(default_factory=list)


class ColorPipeline(BaseModel):
    """OCIO / color management state."""

    ocio_config: str = ""
    working_space: str = ""
    display: str = ""
    view: str = ""
    color_management: str = ""  # "Nuke" or "OCIO"


class ViewerState(BaseModel):
    """Current viewer configuration."""

    viewer_node: str = ""
    input_node: str = ""
    channels: str = "rgba"
    exposure: float = 0.0
    gain: float = 1.0
    gamma: float = 1.0
    frame: int = 1


# --- Tool Parameters ---


class CreateNodeParams(BaseModel):
    """Parameters for creating a single node."""

    class_name: str
    name: str | None = None
    knobs: dict[str, object] = Field(default_factory=dict)
    connect_to: str | None = None
    insert_after: str | None = None
    x: int | None = None
    y: int | None = None


class NodeTreeEntry(BaseModel):
    """One entry in a batch node tree definition."""

    class_name: str
    name: str
    knobs: dict[str, object] = Field(default_factory=dict)
    connect_from: str | None = None  # name of upstream node in this tree
    input_index: int = 0


class KeyframeData(BaseModel):
    """A single keyframe."""

    frame: int
    value: float
    interpolation: str = "smooth"  # smooth, linear, constant


class ComparisonMode(str, Enum):
    WIPE = "wipe"
    DIFF = "diff"
    SIDE_BY_SIDE = "side_by_side"


class TraceDirection(str, Enum):
    UPSTREAM = "upstream"
    DOWNSTREAM = "downstream"


# --- Vision Results ---


class FrameGrabResult(BaseModel):
    """Result of a frame grab — base64-encoded image."""

    image_base64: str
    width: int
    height: int
    frame: int
    node_name: str
    channels: str = "rgba"


class PixelSample(BaseModel):
    """Pixel value at a specific coordinate."""

    x: int
    y: int
    frame: int
    node_name: str
    values: dict[str, float] = Field(default_factory=dict)  # channel_name → value
