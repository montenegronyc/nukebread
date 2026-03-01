"""TCP client that connects to the Nuke bridge server.

Sends commands as newline-delimited JSON and waits for responses.
Used by all MCP tools to execute operations inside Nuke.
"""

from __future__ import annotations

import asyncio
import uuid
from nukebread.common.constants import BRIDGE_HOST, BRIDGE_PORT, BRIDGE_TIMEOUT
from nukebread.common.protocol import (
    BridgeMessage,
    MessageType,
    decode_message,
    make_request,
)


class NukeClient:
    """Async TCP client for the Nuke bridge."""

    def __init__(self, host: str = BRIDGE_HOST, port: int = BRIDGE_PORT):
        self.host = host
        self.port = port
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._pending: dict[str, asyncio.Future[BridgeMessage]] = {}
        self._listen_task: asyncio.Task | None = None

    async def connect(self) -> None:
        self._reader, self._writer = await asyncio.open_connection(self.host, self.port)
        self._listen_task = asyncio.create_task(self._listen())

    async def disconnect(self) -> None:
        if self._listen_task:
            self._listen_task.cancel()
        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()

    @property
    def connected(self) -> bool:
        return self._writer is not None and not self._writer.is_closing()

    async def send(self, command: str, params: dict | None = None) -> object:
        """Send a command and wait for its response."""
        if not self.connected:
            await self.connect()

        msg_id = uuid.uuid4().hex[:8]
        request = make_request(command, params, msg_id)

        future: asyncio.Future[BridgeMessage] = asyncio.get_event_loop().create_future()
        self._pending[msg_id] = future

        self._writer.write(request.to_bytes())  # type: ignore
        await self._writer.drain()  # type: ignore

        try:
            response = await asyncio.wait_for(future, timeout=BRIDGE_TIMEOUT)
        except asyncio.TimeoutError:
            self._pending.pop(msg_id, None)
            raise TimeoutError(f"Nuke bridge did not respond to '{command}' within {BRIDGE_TIMEOUT}s")

        if response.type == MessageType.ERROR:
            raise RuntimeError(f"Nuke bridge error: {response.error}")

        return response.result

    async def _listen(self) -> None:
        """Background task: read responses from the bridge."""
        assert self._reader is not None
        try:
            while True:
                line = await self._reader.readline()
                if not line:
                    break
                msg = decode_message(line)
                if msg.id and msg.id in self._pending:
                    self._pending.pop(msg.id).set_result(msg)
        except asyncio.CancelledError:
            pass
