"""Bridge protocol between MCP server and Nuke plugin.

Messages are newline-delimited JSON over TCP socket.
Each message has a type, an optional id (for request/response pairing),
and a payload.

Uses stdlib only — no pydantic, so it works inside Nuke's embedded Python.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from enum import Enum


class MessageType(str, Enum):
    REQUEST = "request"
    RESPONSE = "response"
    ERROR = "error"
    PING = "ping"
    PONG = "pong"


@dataclass
class BridgeMessage:
    """Wire format for bridge communication."""

    type: MessageType
    id: str = ""
    command: str = ""
    params: dict = field(default_factory=dict)
    result: object = None
    error: str | None = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["type"] = self.type.value
        return d

    def to_bytes(self) -> bytes:
        return json.dumps(self.to_dict()).encode("utf-8") + b"\n"

    @classmethod
    def from_bytes(cls, data: bytes) -> BridgeMessage:
        d = json.loads(data.strip())
        d["type"] = MessageType(d["type"])
        return cls(**d)


def encode_message(msg: BridgeMessage) -> bytes:
    return msg.to_bytes()


def decode_message(data: bytes) -> BridgeMessage:
    return BridgeMessage.from_bytes(data)


def make_request(command: str, params: dict | None = None, msg_id: str = "") -> BridgeMessage:
    return BridgeMessage(
        type=MessageType.REQUEST,
        id=msg_id,
        command=command,
        params=params or {},
    )


def make_response(result: object, msg_id: str = "") -> BridgeMessage:
    return BridgeMessage(
        type=MessageType.RESPONSE,
        id=msg_id,
        result=result,
    )


def make_error(error: str, msg_id: str = "") -> BridgeMessage:
    return BridgeMessage(
        type=MessageType.ERROR,
        id=msg_id,
        error=error,
    )
