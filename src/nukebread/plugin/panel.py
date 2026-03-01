"""PySide6 chat panel for NukeBread inside Nuke 17."""

from __future__ import annotations

from PySide6 import QtWidgets, QtCore, QtGui


class NukeBreadPanel(QtWidgets.QWidget):
    """Chat panel that lives inside Nuke's panel system."""

    message_sent = QtCore.Signal(str)

    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("NukeBread")
        self.setMinimumWidth(360)
        self.setMinimumHeight(400)
        self._build_ui()

    # --- UI construction ---

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Status bar
        self._status = QtWidgets.QLabel("Bridge: disconnected")
        self._status.setStyleSheet(
            "color: #aaa; font-size: 11px; padding: 2px 4px;"
        )
        layout.addWidget(self._status)

        # Chat display
        self._chat = QtWidgets.QTextEdit()
        self._chat.setReadOnly(True)
        self._chat.setStyleSheet(
            "QTextEdit { background: #1a1a1a; color: #ddd; font-family: monospace; font-size: 12px; }"
        )
        layout.addWidget(self._chat, stretch=1)

        # Input area
        input_row = QtWidgets.QHBoxLayout()
        input_row.setSpacing(4)

        self._input = QtWidgets.QLineEdit()
        self._input.setPlaceholderText("Ask NukeBread...")
        self._input.returnPressed.connect(self.on_send)
        input_row.addWidget(self._input, stretch=1)

        self._send_btn = QtWidgets.QPushButton("Send")
        self._send_btn.setFixedWidth(60)
        self._send_btn.clicked.connect(self.on_send)
        input_row.addWidget(self._send_btn)

        layout.addLayout(input_row)

    # --- Public API ---

    def add_message(self, sender: str, text: str) -> None:
        """Append a message to the chat display."""
        color = "#7ec8e3" if sender.lower() == "nukebread" else "#e0e0e0"
        self._chat.append(
            f'<span style="color:{color};font-weight:bold;">{sender}:</span> '
            f'<span style="color:#ddd;">{text}</span>'
        )
        # Scroll to bottom
        scrollbar = self._chat.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def set_status(self, connected: bool) -> None:
        """Update the bridge connection indicator."""
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
    def on_send(self) -> None:
        """Handle send button / return key."""
        text = self._input.text().strip()
        if not text:
            return
        self._input.clear()
        self.add_message("You", text)
        self.message_sent.emit(text)
        # TODO Phase 1: direct Claude API call
        # TODO Phase 2: route through MCP bridge
        self._handle_stub_response(text)

    def _handle_stub_response(self, user_text: str) -> None:
        """Placeholder until the bridge/API is wired up."""
        self.add_message(
            "NukeBread",
            "[stub] Bridge not connected yet. Message received.",
        )


def register_panel() -> None:
    """Register NukeBread panel with Nuke's panel system.

    Call this from menu.py after Nuke has finished loading.
    """
    try:
        import nuke  # type: ignore[import-not-found]

        def _make_panel() -> NukeBreadPanel:
            return NukeBreadPanel()

        nuke.panels.register(  # type: ignore[attr-defined]
            "NukeBread",
            _make_panel,
        )
    except ImportError:
        # Running outside Nuke — skip registration
        pass
