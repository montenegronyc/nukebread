"""PySide6 chat panel for NukeBread inside Nuke 17.

Provides an interactive chat interface where the user can talk to Claude
directly from within Nuke.  Claude has access to the same compositor tools
(read graph, create nodes, grab frames, etc.) via the shared ToolRegistry.

The API call runs on a background thread to keep the UI responsive.
Qt signals push events back to the main thread for display updates.
"""

from __future__ import annotations

import threading

from PySide6 import QtWidgets, QtCore, QtGui


# ---------------------------------------------------------------------------
# Chat worker — runs on a background thread, signals events to the UI
# ---------------------------------------------------------------------------


class _ChatSignals(QtCore.QObject):
    """Signals emitted by the chat worker thread."""
    text_received = QtCore.Signal(str)
    tool_called = QtCore.Signal(str, str)   # tool_name, summary
    tool_result = QtCore.Signal(str, str)   # tool_name, status
    error = QtCore.Signal(str)
    finished = QtCore.Signal()


# ---------------------------------------------------------------------------
# Panel widget
# ---------------------------------------------------------------------------


class NukeBreadPanel(QtWidgets.QWidget):
    """Interactive chat panel that lives inside Nuke's panel system."""

    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("NukeBread")
        self.setMinimumWidth(380)
        self.setMinimumHeight(500)

        self._chat_backend = None  # lazy init
        self._signals = _ChatSignals()
        self._worker_thread: threading.Thread | None = None
        self._is_working = False

        self._build_ui()
        self._connect_signals()

        # Poll bridge status every 3 seconds
        self._status_timer = QtCore.QTimer(self)
        self._status_timer.timeout.connect(self._check_bridge_status)
        self._status_timer.start(3000)
        self._check_bridge_status()

    # --- UI construction ---

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Status bar
        status_row = QtWidgets.QHBoxLayout()
        self._status = QtWidgets.QLabel("Bridge: checking...")
        self._status.setStyleSheet(
            "color: #aaa; font-size: 11px; padding: 2px 4px;"
        )
        status_row.addWidget(self._status)
        status_row.addStretch()

        self._clear_btn = QtWidgets.QPushButton("Clear")
        self._clear_btn.setFixedWidth(50)
        self._clear_btn.setStyleSheet("font-size: 11px;")
        self._clear_btn.clicked.connect(self._on_clear)
        status_row.addWidget(self._clear_btn)

        layout.addLayout(status_row)

        # Chat display
        self._chat = QtWidgets.QTextEdit()
        self._chat.setReadOnly(True)
        self._chat.setStyleSheet(
            "QTextEdit { background: #1a1a1a; color: #ddd; "
            "font-family: 'Menlo', 'Consolas', monospace; font-size: 12px; "
            "border: 1px solid #333; border-radius: 4px; padding: 6px; }"
        )
        layout.addWidget(self._chat, stretch=1)

        # Input row
        input_row = QtWidgets.QHBoxLayout()
        input_row.setSpacing(4)

        self._input = QtWidgets.QLineEdit()
        self._input.setPlaceholderText("Ask NukeBread...")
        self._input.setStyleSheet(
            "QLineEdit { background: #222; color: #eee; border: 1px solid #444; "
            "border-radius: 4px; padding: 6px 8px; font-size: 13px; "
            "font-family: 'Menlo', 'Consolas', monospace; }"
            "QLineEdit:focus { border-color: #6c6; }"
        )
        self._input.returnPressed.connect(self._on_send)
        input_row.addWidget(self._input, stretch=1)

        self._send_btn = QtWidgets.QPushButton("Send")
        self._send_btn.setFixedWidth(60)
        self._send_btn.setStyleSheet(
            "QPushButton { background: #3a6; color: white; border: none; "
            "border-radius: 4px; padding: 6px; font-size: 12px; font-weight: bold; }"
            "QPushButton:hover { background: #4b7; }"
            "QPushButton:disabled { background: #555; color: #888; }"
        )
        self._send_btn.clicked.connect(self._on_send)
        input_row.addWidget(self._send_btn)

        layout.addLayout(input_row)

    def _connect_signals(self) -> None:
        self._signals.text_received.connect(self._on_text_received)
        self._signals.tool_called.connect(self._on_tool_called)
        self._signals.tool_result.connect(self._on_tool_result)
        self._signals.error.connect(self._on_error)
        self._signals.finished.connect(self._on_finished)

    # --- Lazy init chat backend ---

    def _get_backend(self):
        if self._chat_backend is None:
            from nukebread.plugin.chat_backend import ChatBackend
            self._chat_backend = ChatBackend()
        return self._chat_backend

    # --- Public API ---

    def log(self, text: str, color: str = "#ddd") -> None:
        """Append a line to the chat display."""
        self._chat.append(f'<span style="color:{color};">{text}</span>')
        self._scroll_to_bottom()

    def set_status(self, connected: bool) -> None:
        if connected:
            self._status.setText("Bridge: connected")
            self._status.setStyleSheet(
                "color: #6c6; font-size: 11px; padding: 2px 4px;"
            )
        else:
            self._status.setText("Bridge: disconnected")
            self._status.setStyleSheet(
                "color: #aaa; font-size: 11px; padding: 2px 4px;"
            )

    # --- Slots ---

    @QtCore.Slot()
    def _on_send(self) -> None:
        text = self._input.text().strip()
        if not text or self._is_working:
            return

        # Show user message
        self._append_user(text)
        self._input.clear()

        # Disable input while working
        self._set_working(True)

        # Run on background thread
        backend = self._get_backend()
        self._worker_thread = threading.Thread(
            target=self._worker_run,
            args=(backend, text),
            daemon=True,
        )
        self._worker_thread.start()

    def _worker_run(self, backend, text: str) -> None:
        """Runs on background thread — calls the Claude API."""
        try:
            events = backend.send_message(text)
            for event in events:
                if event.kind == "text":
                    self._signals.text_received.emit(event.content)
                elif event.kind == "tool_call":
                    self._signals.tool_called.emit(
                        event.tool_name, event.content,
                    )
                elif event.kind == "tool_result":
                    self._signals.tool_result.emit(
                        event.tool_name, event.content,
                    )
                elif event.kind == "error":
                    self._signals.error.emit(event.content)
        except Exception as exc:
            self._signals.error.emit(str(exc))
        finally:
            self._signals.finished.emit()

    @QtCore.Slot()
    def _on_clear(self) -> None:
        self._chat.clear()
        backend = self._get_backend()
        backend.clear()
        self.log("Conversation cleared.", "#777")

    @QtCore.Slot(str)
    def _on_text_received(self, text: str) -> None:
        self._append_assistant(text)

    @QtCore.Slot(str, str)
    def _on_tool_called(self, tool_name: str, summary: str) -> None:
        self._append_system(f"\U0001F527 {summary}")

    @QtCore.Slot(str, str)
    def _on_tool_result(self, tool_name: str, status: str) -> None:
        self._append_system(f"  \u2713 {status}", "#6a6")

    @QtCore.Slot(str)
    def _on_error(self, error: str) -> None:
        self._append_system(f"\u26A0 {error}", "#e66")

    @QtCore.Slot()
    def _on_finished(self) -> None:
        self._set_working(False)

    @QtCore.Slot()
    def _check_bridge_status(self) -> None:
        import nukebread.plugin as plugin
        self.set_status(plugin._bridge is not None)

    # --- Helpers ---

    def _set_working(self, working: bool) -> None:
        self._is_working = working
        self._send_btn.setEnabled(not working)
        self._input.setEnabled(not working)
        if not working:
            self._input.setFocus()

    def _append_user(self, text: str) -> None:
        escaped = _escape_html(text)
        self._chat.append(
            f'<div style="margin:6px 0;">'
            f'<span style="color:#6cf;font-weight:bold;">You:</span> '
            f'<span style="color:#ddd;">{escaped}</span></div>'
        )
        self._scroll_to_bottom()

    def _append_assistant(self, text: str) -> None:
        # Convert markdown-lite to HTML (basic formatting)
        formatted = _format_response(text)
        self._chat.append(
            f'<div style="margin:6px 0;">'
            f'<span style="color:#f90;font-weight:bold;">NukeBread:</span> '
            f'<span style="color:#ddd;">{formatted}</span></div>'
        )
        self._scroll_to_bottom()

    def _append_system(self, text: str, color: str = "#888") -> None:
        escaped = _escape_html(text)
        self._chat.append(
            f'<div style="margin:2px 0 2px 8px;">'
            f'<span style="color:{color};font-size:11px;">{escaped}</span></div>'
        )
        self._scroll_to_bottom()

    def _scroll_to_bottom(self) -> None:
        sb = self._chat.verticalScrollBar()
        sb.setValue(sb.maximum())


# ---------------------------------------------------------------------------
# Text formatting helpers
# ---------------------------------------------------------------------------


def _escape_html(text: str) -> str:
    """Escape HTML special characters."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _format_response(text: str) -> str:
    """Light markdown-to-HTML conversion for chat display."""
    import re

    # Escape HTML first
    text = _escape_html(text)

    # Code blocks: ```...```
    text = re.sub(
        r"```(\w*)\n(.*?)```",
        lambda m: (
            f'<div style="background:#2a2a2a;padding:4px 8px;margin:4px 0;'
            f'border-radius:3px;font-family:monospace;font-size:11px;'
            f'color:#cfc;white-space:pre-wrap;">{m.group(2)}</div>'
        ),
        text,
        flags=re.DOTALL,
    )

    # Inline code: `...`
    text = re.sub(
        r"`([^`]+)`",
        r'<span style="background:#2a2a2a;padding:1px 4px;border-radius:2px;'
        r'font-family:monospace;color:#cfc;">\1</span>',
        text,
    )

    # Bold: **...**
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)

    # Newlines to <br>
    text = text.replace("\n", "<br>")

    return text


# ---------------------------------------------------------------------------
# Panel registration
# ---------------------------------------------------------------------------


def register_panel() -> None:
    """Register NukeBread as a dockable panel in Nuke's panel system."""
    try:
        import nukescripts  # type: ignore[import-not-found]

        nukescripts.registerWidgetAsPanel(
            "nukebread.plugin.panel.NukeBreadPanel",
            "NukeBread",
            "com.nukebread.panel",
        )
    except ImportError:
        pass
