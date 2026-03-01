"""Bridge protocol between MCP server and Nuke plugin.

Messages are newline-delimited JSON over TCP socket.
Each message has a type, an optional id (for request/response pairing),
and a payload.
"""

from __future__ import annotations

import json
from enum import Enum
from pydantic import BaseModel, Field


class MessageType(str, Enum):
    REQUEST = "request"
    RESPONSE = "response"
    ERROR = "error"
    PING = "ping"
    PONG = "pong"


class BridgeMessage(BaseModel):
    """Wire format for bridge communication."""

    type: MessageType
    id: str = ""
    command: str = ""
    params: dict = Field(default_factory=dict)
    result: object = None
    error: str | None = None

    def to_bytes(self) -> bytes:
        return self.model_dump_json().encode("utf-8") + b"\n"

    @classmethod
    def from_bytes(cls, data: bytes) -> BridgeMessage:
        return cls.model_validate_json(data.strip())


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
