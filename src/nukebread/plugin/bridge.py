"""TCP bridge server that runs inside Nuke's Python environment.

Counterpart to ``nukebread.server.nuke_client.NukeClient``.  Receives
newline-delimited JSON messages (see ``nukebread.common.protocol``),
dispatches them to registered handler functions, and sends back results.

ALL Nuke API calls are routed through ``nuke.executeInMainThread()`` so
that the background socket thread never touches Nuke's non-thread-safe
internals directly.
"""

from __future__ import annotations

import json
import logging
import socket
import traceback
import threading
from typing import Any, Callable

import nuke

from nukebread.common.constants import BRIDGE_HOST, BRIDGE_PORT
from nukebread.common.protocol import (
    BridgeMessage,
    MessageType,
    decode_message,
    make_response,
    make_error,
)

logger = logging.getLogger("nukebread.bridge")

HandlerFunc = Callable[[dict[str, Any]], Any]


class BridgeServer:
    """TCP server that listens for MCP bridge commands inside Nuke.

    Parameters
    ----------
    host:
        Bind address.  Defaults to ``BRIDGE_HOST`` (127.0.0.1).
    port:
        Bind port.  Defaults to ``BRIDGE_PORT`` (9100).
    """

    def __init__(self, host: str = BRIDGE_HOST, port: int = BRIDGE_PORT) -> None:
        self.host = host
        self.port = port
        self._handlers: dict[str, HandlerFunc] = {}
        self._server_socket: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._running = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register_handler(self, command: str, handler: HandlerFunc) -> None:
        """Register a callable for *command*.

        The handler receives a ``dict`` of parameters and must return a
        JSON-serialisable value.  It will be executed on Nuke's main
        thread via ``nuke.executeInMainThread``.
        """
        self._handlers[command] = handler

    def start(self) -> None:
        """Bind the socket and start the accept loop in a daemon thread."""
        if self._running:
            return

        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.bind((self.host, self.port))
        self._server_socket.listen(1)
        self._server_socket.settimeout(1.0)  # allow periodic shutdown checks

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
        """Accept connections in the background thread."""
        while self._running:
            try:
                assert self._server_socket is not None
                conn, addr = self._server_socket.accept()
            except socket.timeout:
                continue
            except OSError:
                break

            logger.info("Client connected from %s", addr)
            # Handle each client in its own daemon thread so the accept
            # loop can continue listening for reconnections.
            t = threading.Thread(target=self._handle_client, args=(conn,), daemon=True)
            t.start()

    def _handle_client(self, conn: socket.socket) -> None:
        """Read messages from a connected client until EOF."""
        buf = b""
        try:
            while self._running:
                chunk = conn.recv(65536)
                if not chunk:
                    break
                buf += chunk

                # Process complete newline-delimited messages.
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
        """Decode a message, dispatch it, and return a response."""
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
        """Look up a handler and execute it on Nuke's main thread."""
        handler = self._handlers.get(command)
        if handler is None:
            return make_error(f"Unknown command: {command}", msg_id)

        # Container to pass result/error out of the main-thread closure.
        result_box: dict[str, Any] = {}

        def _run_on_main() -> None:
            try:
                result_box["value"] = handler(params)
            except Exception:
                result_box["error"] = traceback.format_exc()

        # nuke.executeInMainThread blocks until the callable has finished
        # on the main thread, making this safe to use synchronously.
        nuke.executeInMainThread(_run_on_main)

        if "error" in result_box:
            return make_error(result_box["error"], msg_id)

        return make_response(result_box.get("value"), msg_id)
