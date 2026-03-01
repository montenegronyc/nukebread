"""TCP bridge server that runs inside Nuke's Python environment.

Counterpart to ``nukebread.server.nuke_client.NukeClient``.  Receives
newline-delimited JSON messages (see ``nukebread.common.protocol``),
dispatches them to registered handler functions, and sends back results.

ALL Nuke API calls are routed through the shared ``ToolRegistry`` which
uses ``nuke.executeInMainThread()`` so that the background socket thread
never touches Nuke's non-thread-safe internals directly.
"""

from __future__ import annotations

import logging
import socket
import threading
from typing import TYPE_CHECKING

from nukebread.common.constants import BRIDGE_HOST, BRIDGE_PORT
from nukebread.common.protocol import (
    BridgeMessage,
    MessageType,
    decode_message,
    make_response,
    make_error,
)

if TYPE_CHECKING:
    from nukebread.plugin.tool_registry import ToolRegistry

logger = logging.getLogger("nukebread.bridge")


class BridgeServer:
    """TCP server that listens for MCP bridge commands inside Nuke."""

    def __init__(
        self,
        host: str = BRIDGE_HOST,
        port: int = BRIDGE_PORT,
        registry: ToolRegistry | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self._registry = registry
        self._server_socket: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._running = False

    def start(self) -> None:
        """Bind the socket and start the accept loop in a daemon thread."""
        if self._running:
            return

        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.bind((self.host, self.port))
        self._server_socket.listen(1)
        self._server_socket.settimeout(1.0)

        self._running = True
        self._thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._thread.start()
        logger.info("BridgeServer listening on %s:%d", self.host, self.port)

    def stop(self) -> None:
        """Signal the accept loop to exit and close the socket."""
        self._running = False
        if self._server_socket:
            try:
                self._server_socket.close()
            except OSError:
                pass
            self._server_socket = None
        if self._thread:
            self._thread.join(timeout=5.0)
            self._thread = None
        logger.info("BridgeServer stopped.")

    # ------------------------------------------------------------------
    # Internal — server loop
    # ------------------------------------------------------------------

    def _accept_loop(self) -> None:
        while self._running:
            try:
                assert self._server_socket is not None
                conn, addr = self._server_socket.accept()
            except socket.timeout:
                continue
            except OSError:
                break

            logger.info("Client connected from %s", addr)
            t = threading.Thread(target=self._handle_client, args=(conn,), daemon=True)
            t.start()

    def _handle_client(self, conn: socket.socket) -> None:
        buf = b""
        try:
            while self._running:
                chunk = conn.recv(65536)
                if not chunk:
                    break
                buf += chunk

                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    if not line.strip():
                        continue
                    response = self._process_message(line)
                    conn.sendall(response.to_bytes())
        except (ConnectionResetError, BrokenPipeError):
            logger.info("Client disconnected.")
        except Exception:
            logger.exception("Unexpected error in client handler")
        finally:
            try:
                conn.close()
            except OSError:
                pass

    # ------------------------------------------------------------------
    # Internal — message processing
    # ------------------------------------------------------------------

    def _process_message(self, data: bytes) -> BridgeMessage:
        try:
            msg = decode_message(data)
        except Exception as exc:
            return make_error(f"Malformed message: {exc}")

        if msg.type == MessageType.PING:
            return BridgeMessage(type=MessageType.PONG, id=msg.id)

        if msg.type != MessageType.REQUEST:
            return make_error(f"Unexpected message type: {msg.type}", msg.id)

        return self._dispatch(msg.command, msg.params, msg.id)

    def _dispatch(self, command: str, params: dict, msg_id: str) -> BridgeMessage:
        if self._registry is None:
            return make_error("No tool registry configured", msg_id)

        if not self._registry.has(command):
            return make_error(f"Unknown command: {command}", msg_id)

        try:
            result = self._registry.execute(command, params)
            return make_response(result, msg_id)
        except Exception as exc:
            return make_error(str(exc), msg_id)
