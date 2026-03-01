"""NukeBread constants."""

BRIDGE_HOST = "127.0.0.1"
BRIDGE_PORT = 9100
BRIDGE_TIMEOUT = 30.0

VERSION = "0.1.0"
SERVER_NAME = "nukebread"

# Node classes that are noise when reading graphs
FILTERED_NODE_CLASSES = frozenset({
    "Viewer",
    "BackdropNode",
    "StickyNote",
})

# Common node class aliases for natural language matching
NODE_CLASS_ALIASES: dict[str, str] = {
    "grade": "Grade",
    "merge": "Merge2",
    "blur": "Blur",
    "roto": "Roto",
    "rotopaint": "RotoPaint",
    "tracker": "Tracker4",
    "cornerpin": "CornerPin2D",
    "transform": "Transform",
    "crop": "Crop",
    "reformat": "Reformat",
    "colorcorrect": "ColorCorrect",
    "hueshift": "HueCorrect",
    "keylight": "OFXuk.co.thefoundry.keylight.keylight_v201",
    "shuffle": "Shuffle2",
    "read": "Read",
    "write": "Write",
    "constant": "Constant",
    "dot": "Dot",
    "switch": "Switch",
    "dissolve": "Dissolve",
    "premult": "Premult",
    "unpremult": "Unpremult",
    "copy": "Copy",
    "channelmerge": "ChannelMerge",
    "expression": "Expression",
    "colorspace": "Colorspace",
    "ociocdltransform": "OCIOCDLTransform",
    "vectorblur": "VectorBlur",
    "motionblur": "MotionBlur",
    "denoise": "Denoise2",
    "edgeblur": "EdgeBlur",
    "erode": "FilterErode",
    "softenedges": "EdgeBlur",
    "lightwrap": "LightWrap",
}
